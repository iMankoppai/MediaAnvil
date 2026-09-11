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

    /** Desktop `with_inferred_end_times`: only fill missing ends with the next start or the configured tail. */
    fun withInferredEndTimes(cues: List<SubtitleCue>, finalDurationMs: Long = 5_000L): List<SubtitleCue> {
        require(finalDurationMs > 0) { "final_duration" }
        return cues.mapIndexed { index, cue ->
            val existing = cue.endMs
            val resolved = if (existing > cue.startMs) existing else {
                val nextStart = cues.getOrNull(index + 1)?.startMs
                if (nextStart != null && nextStart > cue.startMs) nextStart else cue.startMs + finalDurationMs
            }
            cue.copy(endMs = resolved)
        }
    }

    /** Render cues as numbered SRT blocks. */
    fun cuesToSrt(cues: List<SubtitleCue>, finalDurationMs: Long = 5_000L): String {
        val blocks = withInferredEndTimes(cues, finalDurationMs).mapIndexed { index, cue ->
            "${index + 1}\n${subtitleTimestamp(cue.startMs, ",")} --> ${subtitleTimestamp(cue.endMs, ",")}\n${cue.text}"
        }
        return blocks.joinToString("\n\n") + "\n"
    }

    /** Render cues as WebVTT. */
    fun cuesToVtt(cues: List<SubtitleCue>, finalDurationMs: Long = 5_000L): String {
        val blocks = withInferredEndTimes(cues, finalDurationMs).map { cue ->
            "${subtitleTimestamp(cue.startMs, ".")} --> ${subtitleTimestamp(cue.endMs, ".")}\n${cue.text}"
        }
        return "WEBVTT\n\n" + blocks.joinToString("\n\n") + "\n"
    }

    /** `HH:MM:SS,mmm` (SRT) or `HH:MM:SS.mmm` (VTT). */
    fun subtitleTimestamp(milliseconds: Long, separator: String): String {
        val totalMs = milliseconds.coerceAtLeast(0L)
        val hours = totalMs / 3_600_000
        val minutes = totalMs % 3_600_000 / 60_000
        val seconds = totalMs % 60_000 / 1_000
        val fraction = totalMs % 1_000
        return "%02d:%02d:%02d%s%03d".format(hours, minutes, seconds, separator, fraction)
    }

    /**
     * Convert between LRC/SRT/VTT, mirroring the desktop converter: LRC keeps
     * one timestamped line per text line; SRT/VTT infer missing end times with
     * a 5s tail on the final cue.
     */
    fun convertSubtitle(text: String, from: String, to: String, finalDurationMs: Long = 5_000L): String {
        val cues = if (from.lowercase() == "lrc") SubtitleParser.parseLrc(text, finalDurationMs) else SubtitleParser.parseTimedBlocks(text)
        require(cues.isNotEmpty()) { "no_valid_cues" }
        return when (to.lowercase()) {
            "lrc" -> cuesToLrc(cues)
            "srt" -> cuesToSrt(cues, finalDurationMs)
            "vtt" -> cuesToVtt(cues, finalDurationMs)
            else -> error("unknown_target_format")
        }
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
