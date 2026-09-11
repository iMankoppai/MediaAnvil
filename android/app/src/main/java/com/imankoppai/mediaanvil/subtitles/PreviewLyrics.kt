package com.imankoppai.mediaanvil.subtitles

import android.content.Context
import android.net.Uri
import com.imankoppai.mediaanvil.data.DocumentOps
import com.imankoppai.mediaanvil.model.AudioTrack
import com.imankoppai.mediaanvil.model.SubtitleCue
import com.imankoppai.mediaanvil.tags.TagIO
import java.io.File

/**
 * Load the lyric timeline for the preview page with the desktop ordering:
 * external LRC/SRT/VTT files first (unless embedded is preferred), then MP3
 * embedded synced lyrics. LRC lines stay highlighted until the next line;
 * timed subtitle cues clear after their end.
 */
object PreviewLyrics {
    const val NO_END = Long.MAX_VALUE

    data class Timeline(val cues: List<SubtitleCue>, val fromEmbedded: Boolean)

    fun load(context: Context, track: AudioTrack, preferEmbedded: Boolean, autoLoadExternal: Boolean = true): Timeline {
        if (preferEmbedded) {
            embeddedCues(context, track)?.takeIf { it.isNotEmpty() }?.let { return Timeline(it, true) }
        }
        if (autoLoadExternal) {
            externalCues(context, track)?.takeIf { it.isNotEmpty() }?.let { return Timeline(it, false) }
        }
        if (!preferEmbedded) {
            embeddedCues(context, track)?.takeIf { it.isNotEmpty() }?.let { return Timeline(it, true) }
        }
        return Timeline(emptyList(), false)
    }

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

    private fun embeddedCues(context: Context, track: AudioTrack): List<SubtitleCue>? {
        if (track.fileName.substringAfterLast('.', "").lowercase() != "mp3") return null
        val cache: File = DocumentOps.copyToCache(context, track.uri, track.fileName)
        return try {
            TagIO.embeddedSyncedLyricsText(cache)?.let(::parseLrcTimeline)
        } catch (_: Exception) {
            null
        } finally {
            DocumentOps.deleteCache(cache)
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
            if (matches.isEmpty() || SubtitleFormats.isMetadataLine(line)) continue
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
        return entries.sortedBy { it.startMs }.mapIndexed { index, entry ->
            SubtitleCue(
                startMs = entry.startMs,
                endMs = entries.getOrNull(index + 1)?.startMs ?: NO_END,
                text = entry.text,
            )
        }
    }
}
