package com.imankoppai.mediaanvil.data

/**
 * Conservative matching of audio files with nearby lyric and cover files,
 * ported from the desktop `core/media_matcher.py` so both platforms rank
 * candidates identically.
 */
object MediaMatcher {
    val lyricExtensions = setOf("lrc", "srt", "vtt", "txt")
    val coverExtensions = setOf("jpg", "jpeg", "png", "webp", "bmp")

    enum class Priority { FULL_AUDIO_NAME, EXACT, IGNORE_SPACES, COPY_SUFFIX }

    /** A plain file mirror so ranking logic stays unit-testable without Android. */
    data class FileRef(val name: String, val parent: String)

    data class Candidates(
        val files: List<FileRef>,
        val priority: Priority?,
    ) {
        val ambiguous: Boolean get() = files.size > 1
        val single: FileRef? get() = files.singleOrNull()
    }

    private val copySuffix = Regex(
        "(?:\\s*[-_]\\s*(?:副本|copy)(?:\\s*\\d+)?|\\s*[（(]\\s*\\d+\\s*[）)])$",
        RegexOption.IGNORE_CASE,
    )

    /** Filename without its final extension, case-preserving. */
    private fun stem(name: String): String = name.substringBeforeLast('.', name)

    /** All extensions after the first dot, e.g. `song.flac` from `song.flac.lrc`. */
    private fun audioSuffix(name: String): String {
        val index = name.indexOf('.')
        return if (index < 0) "" else name.substring(index).lowercase()
    }

    private fun withoutCopySuffix(value: String): String = copySuffix.replace(value, "").trimEnd()

    private fun priority(sourceStem: String, candidateStem: String, suffix: String): Priority? {
        val source = sourceStem.casefold()
        var candidate = candidateStem.casefold()
        if (suffix.isNotEmpty() && candidate.endsWith(suffix)) {
            if (candidate.removeSuffix(suffix) == source) return Priority.FULL_AUDIO_NAME
            candidate = candidate.removeSuffix(suffix)
        }
        if (candidate == source) return Priority.EXACT
        if (candidate.filterNot(Char::isWhitespace) == source.filterNot(Char::isWhitespace)) {
            return Priority.IGNORE_SPACES
        }
        if (withoutCopySuffix(candidate) == withoutCopySuffix(source)) return Priority.COPY_SUFFIX
        return null
    }

    private fun String.casefold(): String = lowercase()

    /**
     * Keep only candidates at the strongest matched priority. Ties are all
     * retained so the caller can ask the user to choose explicitly.
     */
    fun bestCandidates(
        audioName: String,
        files: List<FileRef>,
        allowedExtensions: Set<String>,
    ): Candidates {
        val suffix = audioSuffix(audioName)
        val scored = mutableListOf<Pair<Priority, FileRef>>()
        for (file in files) {
            val extension = file.name.substringAfterLast('.', "").lowercase()
            if (extension !in allowedExtensions) continue
            val level = priority(stem(audioName), stem(file.name), suffix) ?: continue
            scored += level to file
        }
        if (scored.isEmpty()) return Candidates(emptyList(), null)
        val best = scored.minOf { it.first }
        val files = scored.filter { it.first == best }
            .sortedBy { it.second.name.lowercase() }
            .map { it.second }
        return Candidates(files, best)
    }
}
