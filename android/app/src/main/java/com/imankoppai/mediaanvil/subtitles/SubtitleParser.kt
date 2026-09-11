package com.imankoppai.mediaanvil.subtitles

import com.imankoppai.mediaanvil.model.SubtitleCue

object SubtitleParser {
    internal val lrcTimestamp = Regex("\\[(\\d{1,3}):(\\d{2})(?:[.:](\\d{1,3}))?]")
    private val timedLine = Regex(
        "(?:(\\d{1,2}):)?(\\d{2}):(\\d{2})[,.](\\d{3})\\s*-->\\s*" +
            "(?:(\\d{1,2}):)?(\\d{2}):(\\d{2})[,.](\\d{3})",
    )

    fun parse(text: String, extension: String): List<SubtitleCue> = when (extension.lowercase()) {
        "lrc" -> parseLrc(text)
        "srt", "vtt" -> parseTimedBlocks(text)
        else -> emptyList()
    }

    fun parseLrc(text: String): List<SubtitleCue> {
        val starts = buildList {
            text.lineSequence().forEach { line ->
                val content = line.replace(lrcTimestamp, "").trim()
                if (content.isNotEmpty()) {
                    lrcTimestamp.findAll(line).forEach { match ->
                        val minutes = match.groupValues[1].toLong()
                        val seconds = match.groupValues[2].toLong()
                        val fractionText = match.groupValues[3]
                        val fraction = when (fractionText.length) {
                            1 -> fractionText.toLongOrNull()?.times(100) ?: 0L
                            2 -> fractionText.toLongOrNull()?.times(10) ?: 0L
                            3 -> fractionText.toLongOrNull() ?: 0L
                            else -> 0L
                        }
                        add(minutes * 60_000 + seconds * 1_000 + fraction to content)
                    }
                }
            }
        }.sortedBy { it.first }

        return starts.mapIndexed { index, cue ->
            SubtitleCue(
                startMs = cue.first,
                endMs = starts.getOrNull(index + 1)?.first ?: cue.first + 5_000,
                text = cue.second,
            )
        }
    }

    fun parseTimedBlocks(text: String): List<SubtitleCue> {
        val normalised = text.replace("\r\n", "\n").trim()
        if (normalised.isEmpty()) return emptyList()
        return normalised.split(Regex("\n\\s*\n"))
            .mapNotNull { block ->
                val lines = block.lines().filter { it.isNotBlank() }
                val timeIndex = lines.indexOfFirst { timedLine.containsMatchIn(it) }
                if (timeIndex < 0) return@mapNotNull null
                val match = timedLine.find(lines[timeIndex]) ?: return@mapNotNull null
                val values = match.groupValues.drop(1).map { it.toLongOrNull() ?: 0L }
                val cueText = lines.drop(timeIndex + 1)
                    .joinToString("\n")
                    .replace(Regex("<[^>]+>"), "")
                    .trim()
                if (cueText.isEmpty()) return@mapNotNull null
                SubtitleCue(
                    startMs = toMillis(values[0], values[1], values[2], values[3]),
                    endMs = toMillis(values[4], values[5], values[6], values[7]),
                    text = cueText,
                )
            }
            .sortedBy(SubtitleCue::startMs)
    }

    private fun toMillis(hours: Long, minutes: Long, seconds: Long, millis: Long): Long =
        hours * 3_600_000 + minutes * 60_000 + seconds * 1_000 + millis
}
