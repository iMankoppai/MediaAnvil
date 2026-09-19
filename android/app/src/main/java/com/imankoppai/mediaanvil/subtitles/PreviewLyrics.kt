package com.imankoppai.mediaanvil.subtitles

import android.content.Context
import android.net.Uri
import com.imankoppai.mediaanvil.model.AudioTrack
import com.imankoppai.mediaanvil.model.SubtitleCue

/**
 * Load sidecar LRC/SRT/VTT lyrics for the player. LRC lines stay highlighted
 * until the next line; timed subtitle cues clear after their end.
 */
object PreviewLyrics {
    const val NO_END = Long.MAX_VALUE

    fun load(context: Context, track: AudioTrack, autoLoadExternal: Boolean = true): List<SubtitleCue> =
        if (autoLoadExternal) externalCues(context, track).orEmpty() else emptyList()

    private fun externalCues(context: Context, track: AudioTrack): List<SubtitleCue>? {
        val uri = track.subtitleUri ?: return null
        val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: return null
        val text = SubtitleLoader.decode(bytes)
        return when (track.subtitleExtension?.lowercase()) {
            "lrc" -> parseLrcTimeline(text)
            "srt", "vtt" -> SubtitleParser.parseTimedBlocks(text)
            else -> null
        }
    }

    /**
     * LRC timeline where every line ends when the next one starts and the last
     * line stays highlighted, matching the desktop preview behaviour.
     */
    fun parseLrcTimeline(text: String): List<SubtitleCue> {
        data class Entry(val startMs: Long, val text: String)

        val entries = mutableListOf<Entry>()
        for (line in text.lineSequence()) {
            val matches = SubtitleParser.lrcTimestamp.findAll(line).toList()
            if (matches.isEmpty() || LrcText.isMetadataLine(line)) continue
            val content = line.substring(matches.last().range.last + 1).trim()
            for (match in matches) {
                val minutes = match.groupValues[1].toLong()
                val seconds = match.groupValues[2].toLong()
                val fractionText = match.groupValues[3]
                val fraction = when (fractionText.length) {
                    1 -> (fractionText.toLongOrNull() ?: 0L) * 100
                    2 -> (fractionText.toLongOrNull() ?: 0L) * 10
                    else -> fractionText.toLongOrNull() ?: 0L
                }
                entries += Entry(minutes * 60_000 + seconds * 1_000 + fraction, content)
            }
        }
        val merged = entries
            .groupBy { it.startMs }
            .toSortedMap()
            .map { (startMs, sameTime) ->
                Entry(startMs, sameTime.map { it.text }.filter(String::isNotEmpty).distinct().joinToString("\n"))
            }
            // Blank timestamp lines mark instrumental gaps; dropping them keeps
            // the previous line highlighted through the gap instead of moving
            // the highlight onto an invisible empty row.
            .filter { it.text.isNotEmpty() }
        return merged.mapIndexed { index, entry ->
            SubtitleCue(
                startMs = entry.startMs,
                endMs = merged.getOrNull(index + 1)?.startMs ?: NO_END,
                text = entry.text,
            )
        }
    }
}
