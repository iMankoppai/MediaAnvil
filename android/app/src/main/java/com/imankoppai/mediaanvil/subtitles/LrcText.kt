package com.imankoppai.mediaanvil.subtitles

/** Read-only helpers for parsing external LRC files. */
internal object LrcText {
    private val metadataLine =
        Regex("^\\s*\\[(?:ar|ti|al|by|offset|length|re):.*?]\\s*$", RegexOption.IGNORE_CASE)

    fun isMetadataLine(line: String): Boolean = metadataLine.matches(line)
}
