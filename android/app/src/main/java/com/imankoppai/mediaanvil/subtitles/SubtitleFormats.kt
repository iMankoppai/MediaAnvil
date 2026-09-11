package com.imankoppai.mediaanvil.subtitles

import com.imankoppai.mediaanvil.model.SubtitleCue
import java.math.BigDecimal
import java.math.RoundingMode

/** LRC rendering and validation, matching the desktop converter behaviour. */
object SubtitleFormats {
    private val lrcTimestamp = Regex("\\[(\\d+):(\\d{2})(?:\\.(\\d{1,3}))?]")
    private val lrcMetadata = Regex("^\\s*\\[(?:ar|ti|al|by|offset|length|re):.*?]\\s*$", RegexOption.IGNORE_CASE)
    private val timingLine = Regex(
        "^\\s*(?:(\\d{1,}):)?(\\d{1,2}):(\\d{2})[.,](\\d{1,3})\\s*-->\\s*" +
            "(?:(\\d{1,}):)?(\\d{1,2}):(\\d{2})[.,](\\d{1,3})(?:\\s+.*)?$",
    )

    /** True when the text contains at least one usable LRC timestamp. */
    fun hasLrcTimestamp(text: String): Boolean = lrcTimestamp.containsMatchIn(text)

    /** True when the text contains SRT/WebVTT style `-->` timing lines. */
    fun looksLikeTimed(text: String): Boolean =
        text.lineSequence().any { timingLine.matches(it.trim()) }

    /**
     * Convert SRT or VTT text into LRC the same way the desktop does: one
     * timestamped line per source text line, centiseconds rounded half-up.
     */
    fun timedTextToLrc(text: String): String {
        val cues = SubtitleParser.parseTimedBlocks(text)
        require(cues.isNotEmpty()) { "no_valid_cues" }
        return cuesToLrc(cues)
    }

    /** Render cues as LRC, retaining each original text line. */
    fun cuesToLrc(cues: List<SubtitleCue>): String {
        val lines = mutableListOf<String>()
        for (cue in cues) {
            val timestamp = lrcTimestamp(cue.startMs)
            for (line in cue.text.lines()) {
                lines += timestamp + line
            }
        }
        return lines.joinToString("\n") + "\n"
    }

    /** Validate lyrics text before embedding, mirroring the desktop read_lrc checks. */
    fun validateEmbeddableLyrics(text: String) {
        require(text.isNotBlank()) { "empty_lyrics" }
        require(hasLrcTimestamp(text)) { "no_timestamp" }
    }

    /** `[mm:ss.cc]` with half-up rounding, matching the desktop renderer. */
    fun lrcTimestamp(milliseconds: Long): String {
        val centiseconds = BigDecimal(milliseconds)
            .divide(BigDecimal(1_000))
            .multiply(BigDecimal(100))
            .setScale(0, RoundingMode.HALF_UP)
            .toInt()
        val minutes = centiseconds / 6_000
        val seconds = (centiseconds % 6_000) / 100
        val fraction = centiseconds % 100
        return "[%02d:%02d.%02d]".format(minutes, seconds, fraction)
    }

    internal fun isMetadataLine(line: String): Boolean = lrcMetadata.matches(line)
}
