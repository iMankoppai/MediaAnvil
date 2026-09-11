package com.imankoppai.mediaanvil.tools

/**
 * Tag-based batch rename planning, ported from the desktop
 * `core/audio_renamer.py`. Pure logic — execution goes through SAF in the UI
 * layer, so this stays unit-testable on the JVM.
 */
object AudioRenamer {
    val supportedExtensions = setOf("mp3", "flac", "m4a", "ogg", "opus")
    private val allowedFields = setOf("artist", "title", "album", "track", "year")
    private val fieldToken = Regex("\\{([A-Za-z_]+)\\}")
    private val whitespace = Regex("\\s+")
    private val trackNumber = Regex("^\\s*(\\d+)")
    private val yearNumber = Regex("(\\d{4})")
    private val invalidChars = "<>:/\\|?*\""

    enum class Status { READY, READY_AVOIDED, NO_CHANGE, MISSING_TAGS, CONFLICT }

    data class Fields(
        val originalName: String,
        val artist: String = "",
        val title: String = "",
        val album: String = "",
        val track: String = "",
        val year: String = "",
    ) {
        val extension: String get() = originalName.substringAfterLast('.', "")
        val originalStem: String get() = originalName.substringBeforeLast('.', originalName)
    }

    data class PlanItem(
        val originalName: String,
        val newName: String,
        val status: Status,
        val message: String = "",
    ) {
        val canRename: Boolean get() = status == Status.READY || status == Status.READY_AVOIDED
    }

    /** Leading digits formatted as two digits, matching the desktop. */
    fun normalizeTrack(value: String?): String =
        trackNumber.find(value.orEmpty().trim())?.groupValues?.get(1)?.toInt()?.let { "%02d".format(it) } ?: ""

    /** First 4-digit group, else the raw trimmed value. */
    fun normalizeYear(value: String?): String =
        yearNumber.find(value.orEmpty().trim())?.groupValues?.get(1) ?: value.orEmpty().trim()

    fun sanitizeFilename(value: String): String {
        val cleaned = value.map { character ->
            if (character in invalidChars || character.code < 32) ' ' else character
        }.joinToString("")
        return whitespace.replace(cleaned, " ").trim().trimEnd('.')
    }

    /** Returns the set of template fields used; throws IllegalArgumentException on bad templates. */
    fun validateTemplate(template: String): Set<String> {
        require(template.isNotBlank()) { "template_empty" }
        val fields = fieldToken.findAll(template).map { it.groupValues[1] }.toList()
        fields.forEach { field ->
            require(field in allowedFields) { "unknown_field:$field" }
        }
        return fields.toSet()
    }

    fun renderName(template: String, fields: Fields, fallbackMissing: Boolean, maxLength: Int = 240): String {
        val used = validateTemplate(template)
        val values = mapOf(
            "artist" to fields.artist.trim(),
            "title" to fields.title.trim(),
            "album" to fields.album.trim(),
            "track" to normalizeTrack(fields.track),
            "year" to normalizeYear(fields.year),
        )
        val missing = used.filter { values[it].isNullOrEmpty() }
        require(missing.isEmpty() || fallbackMissing) {
            "missing_fields:${missing.joinToString("、")}"
        }
        var stem = template
        for (field in used) {
            stem = stem.replace("{${field}}", values[field].takeUnless { it.isNullOrEmpty() } ?: fields.originalStem)
        }
        stem = sanitizeFilename(stem)
        require(stem.isNotEmpty()) { "empty_name" }
        val extension = fields.extension
        val allowed = (maxLength - extension.length).coerceAtLeast(1)
        stem = stem.take(allowed).trimEnd(' ', '.')
        require(stem.isNotEmpty()) { "empty_name" }
        return "$stem.$extension"
    }

    /**
     * Build the preview plan. `existingNames` is the lowercased set of the
     * other file names already present in the target folder; renames that
     * would hit one get a `_1` style suffix like the desktop.
     */
    fun buildPlan(
        files: List<Fields>,
        template: String,
        fallbackMissing: Boolean,
        existingNames: Set<String> = emptySet(),
    ): List<PlanItem> {
        validateTemplate(template)
        val provisional = files.map { fields ->
            val newName = renderName(template, fields, fallbackMissing)
            fields.originalName to newName
        }
        val conflicts = provisional
            .groupBy { it.second.lowercase() }
            .filter { it.value.size > 1 }
            .keys
        val reserved = mutableSetOf<String>()
        return provisional.map { (originalName, newName) ->
            when {
                newName.lowercase() in conflicts ->
                    PlanItem(originalName, newName, Status.CONFLICT, "batch_conflict")
                newName.lowercase() == originalName.lowercase() -> {
                    reserved += originalName.lowercase()
                    PlanItem(originalName, newName, Status.NO_CHANGE, "already_matches")
                }
                else -> {
                    val taken = { candidate: String ->
                        candidate.lowercase() in existingNames || candidate.lowercase() in reserved
                    }
                    var candidate = newName
                    var avoided = false
                    var index = 1
                    val stem = candidate.substringBeforeLast('.', candidate)
                    val extension = candidate.substringAfterLast('.', "")
                    while (taken(candidate)) {
                        candidate = if (extension.isEmpty()) "${stem}_$index" else "${stem}_$index.$extension"
                        index++
                        avoided = true
                    }
                    reserved += candidate.lowercase()
                    if (avoided) {
                        PlanItem(originalName, candidate, Status.READY_AVOIDED, "target_exists_avoided")
                    } else {
                        PlanItem(originalName, candidate, Status.READY, "")
                    }
                }
            }
        }
    }
}
