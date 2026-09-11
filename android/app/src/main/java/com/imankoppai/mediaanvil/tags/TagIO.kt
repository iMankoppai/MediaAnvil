package com.imankoppai.mediaanvil.tags

import com.imankoppai.mediaanvil.subtitles.SubtitleFormats
import org.jaudiotagger.audio.AudioFile
import org.jaudiotagger.audio.AudioFileIO
import org.jaudiotagger.tag.FieldKey
import org.jaudiotagger.tag.Tag
import org.jaudiotagger.tag.images.Artwork
import org.jaudiotagger.tag.images.ArtworkFactory
import org.jaudiotagger.tag.id3.AbstractID3v2Frame
import org.jaudiotagger.tag.id3.AbstractID3v2Tag
import org.jaudiotagger.tag.id3.ID3v23Tag
import org.jaudiotagger.tag.id3.framebody.FrameBodyAPIC
import org.jaudiotagger.tag.id3.framebody.FrameBodySYLT
import org.jaudiotagger.tag.id3.framebody.FrameBodyUSLT
import org.jaudiotagger.tag.id3.valuepair.TextEncoding
import org.jaudiotagger.tag.mp4.Mp4Tag
import java.io.File

/**
 * Read/write audio tags through jaudiotagger, mirroring the desktop
 * mutagen-based behaviour: lyrics embed as LRC text, saving keeps every other
 * tag, and callers operate on a scratch copy so the source stays untouched.
 * Opus has no reader in jaudiotagger 3.0.1, so it stays playback-only here.
 */
object TagIO {
    const val LYRICS_DESCRIPTION = "Sub2LRC"
    const val COVER_DESCRIPTION = "Cover"

    /** Same writable set as the desktop minus Opus (no jaudiotagger support). */
    val writableExtensions = setOf("mp3", "flac", "m4a", "ogg")
    val readableExtensions = writableExtensions + setOf("wav")

    fun isTagReadable(fileName: String): Boolean = fileName.substringAfterLast('.', "").lowercase() in readableExtensions

    fun isWritable(fileName: String): Boolean = fileName.substringAfterLast('.', "").lowercase() in writableExtensions

    data class AudioInfo(
        val formatLabel: String,
        val durationSeconds: Double,
        val bitrateKbps: Int,
        val sampleRateHz: Int,
        val channels: String,
        val fileSizeBytes: Long,
        val tagCount: Int,
    )

    data class TagSnapshot(
        val title: String,
        val artist: String,
        val album: String,
        val track: String,
        val year: String,
        val hasLyrics: Boolean,
        val lyrics: String,
        val hasCover: Boolean,
        val coverData: ByteArray?,
        val coverMime: String?,
        val writable: Boolean,
        val info: AudioInfo,
    )

    data class TagChanges(
        val title: String? = null,
        val artist: String? = null,
        val album: String? = null,
        val lyricsLrc: String? = null,
        val removeLyrics: Boolean = false,
        val coverData: ByteArray? = null,
        val coverMime: String? = null,
        val removeCover: Boolean = false,
    ) {
        init {
            require(!(lyricsLrc != null && removeLyrics)) { "lyrics_replace_and_remove" }
            require(!(coverData != null && removeCover)) { "cover_replace_and_remove" }
        }
    }

    fun readSnapshot(file: File): TagSnapshot {
        val audio = AudioFileIO.read(file)
        val tag = audio.tag
        val extension = file.extension.lowercase()
        val info = readInfo(file, audio, tag, extension)
        val id3 = tag as? AbstractID3v2Tag
        val lyricsEntry = id3?.let(::readId3Lyrics) ?: readPlainLyrics(tag)
        val artwork = runCatching { tag?.firstArtwork }.getOrNull()
        return TagSnapshot(
            title = text(tag, FieldKey.TITLE),
            artist = text(tag, FieldKey.ARTIST),
            album = text(tag, FieldKey.ALBUM),
            track = text(tag, FieldKey.TRACK),
            year = text(tag, FieldKey.YEAR),
            hasLyrics = lyricsEntry != null,
            lyrics = lyricsEntry?.first.orEmpty(),
            hasCover = artwork != null,
            coverData = artwork?.binaryData,
            coverMime = artwork?.mimeType,
            writable = extension in writableExtensions,
            info = info,
        )
    }

    private fun text(tag: Tag?, key: FieldKey): String =
        runCatching { tag?.getFirst(key) }.getOrNull()?.orEmpty() ?: ""

    private fun readPlainLyrics(tag: Tag?): Pair<String, Boolean>? {
        val value = text(tag, FieldKey.LYRICS)
        return if (value.isEmpty()) null else value to SubtitleFormats.hasLrcTimestamp(value)
    }

    private fun readInfo(file: File, audio: AudioFile, tag: Tag?, extension: String): AudioInfo {
        val header = audio.audioHeader
        val label = when (extension) {
            "mp3" -> "MP3"
            "flac" -> "FLAC"
            "m4a" -> "M4A"
            "ogg" -> "OGG Vorbis"
            else -> extension.uppercase()
        }
        val tagCount = runCatching { tag?.fieldCount ?: 0 }.getOrDefault(0)
        return AudioInfo(
            formatLabel = label,
            durationSeconds = header?.trackLength?.toDouble() ?: 0.0,
            bitrateKbps = header?.bitRate?.trim()?.toIntOrNull() ?: 0,
            sampleRateHz = header?.sampleRateAsNumber ?: 0,
            channels = header?.channels.orEmpty(),
            fileSizeBytes = file.length(),
            tagCount = tagCount,
        )
    }

    private fun usltFrames(id3: AbstractID3v2Tag): List<FrameBodyUSLT> =
        runCatching { id3.getFields("USLT") }.getOrDefault(emptyList())
            .filterIsInstance<AbstractID3v2Frame>()
            .mapNotNull { it.body as? FrameBodyUSLT }

    private fun syltFrames(id3: AbstractID3v2Tag): List<FrameBodySYLT> =
        runCatching { id3.getFields("SYLT") }.getOrDefault(emptyList())
            .filterIsInstance<AbstractID3v2Frame>()
            .mapNotNull { it.body as? FrameBodySYLT }

    /** USLT preferred (Sub2LRC first), otherwise SYLT rendered as timestamped LRC lines. */
    private fun readId3Lyrics(id3: AbstractID3v2Tag): Pair<String, Boolean>? {
        val frames = usltFrames(id3)
        val preferred = frames.firstOrNull { it.description == LYRICS_DESCRIPTION } ?: frames.firstOrNull()
        if (preferred != null) {
            return preferred.lyric to SubtitleFormats.hasLrcTimestamp(preferred.lyric)
        }
        val sylt = syltFrames(id3).firstOrNull() ?: return null
        val text = renderSylt(sylt) ?: return null
        return text to true
    }

    /**
     * Render a SYLT frame into `[mm:ss.cc]text` lines. jaudiotagger exposes the
     * synchronized block as raw bytes, so parse the terminating-string stream
     * according to the SYLT frame layout.
     */
    private fun renderSylt(frame: FrameBodySYLT): String? = runCatching {
        val encoding = frame.textEncoding.toInt() and 0xFF
        val raw = frame.lyrics ?: return@runCatching null
        val charset = when (encoding) {
            1 -> Charsets.UTF_16
            2 -> Charsets.UTF_16BE
            3 -> Charsets.UTF_8
            else -> Charsets.ISO_8859_1
        }
        val doubleByteTerminator = encoding == 1 || encoding == 2
        val lines = mutableListOf<String>()
        var index = 0
        fun findTerminator(from: Int): Int {
            var i = from
            while (i < raw.size) {
                if (raw[i] == 0.toByte() && (!doubleByteTerminator || (i + 1 < raw.size && raw[i + 1] == 0.toByte() && (i - from) % 2 == 0))) {
                    return i
                }
                i++
            }
            return -1
        }
        while (index < raw.size) {
            val textEnd = findTerminator(index)
            if (textEnd < 0) break
            val text = String(raw.copyOfRange(index, textEnd), charset).trimEnd('\u0000')
            index = textEnd + if (doubleByteTerminator) 2 else 1
            if (index + 4 > raw.size) break
            val timestamp = ((raw[index].toLong() and 0xFFL) shl 24) or
                ((raw[index + 1].toLong() and 0xFFL) shl 16) or
                ((raw[index + 2].toLong() and 0xFFL) shl 8) or
                (raw[index + 3].toLong() and 0xFFL)
            index += 4
            lines += "[%02d:%02d.%02d]".format(
                timestamp / 60_000,
                timestamp % 60_000 / 1_000,
                timestamp % 1_000 / 10,
            ) + text
        }
        if (lines.isEmpty()) null else lines.joinToString("\n") + "\n"
    }.getOrNull()

    /**
     * Embedded synced lyrics for the preview page. MP3 only, and only timed
     * content yields a timeline, matching the desktop preview loader.
     */
    fun embeddedSyncedLyricsText(file: File): String? {
        if (file.extension.lowercase() != "mp3") return null
        return runCatching {
            val id3 = AudioFileIO.read(file).tag as? AbstractID3v2Tag ?: return null
            readId3Lyrics(id3)?.takeIf { it.second }?.first
        }.getOrNull()
    }

    /** Apply changes in place on a scratch copy of the audio file. */
    fun writeChanges(file: File, changes: TagChanges) {
        val extension = file.extension.lowercase()
        check(extension in writableExtensions) { "format_not_writable" }
        val audio = AudioFileIO.read(file)
        when (extension) {
            "mp3" -> writeMp3(audio, changes)
            "m4a" -> writeMp4(audio, changes)
            else -> writeVorbisStyle(audio, changes)
        }
        audio.commit()
    }

    private fun setOrRemoveText(tag: Tag, key: FieldKey, value: String?) {
        if (value == null) return
        runCatching { tag.deleteField(key) }
        if (value.isNotBlank()) {
            tag.addField(key, value.trim())
        }
    }

    private fun writeMp3(audio: AudioFile, changes: TagChanges) {
        val id3 = audio.tag as? AbstractID3v2Tag ?: ID3v23Tag().also { audio.tag = it }
        setOrRemoveText(id3, FieldKey.TITLE, changes.title)
        setOrRemoveText(id3, FieldKey.ARTIST, changes.artist)
        setOrRemoveText(id3, FieldKey.ALBUM, changes.album)

        if (changes.removeLyrics) {
            runCatching { id3.deleteField("USLT") }
            runCatching { id3.deleteField("SYLT") }
        } else if (changes.lyricsLrc != null) {
            // Keep lyrics frames written by other tools, replacing only ours.
            val foreign = id3.getFields("USLT").orEmpty()
                .filterIsInstance<AbstractID3v2Frame>()
                .filter { (it.body as? FrameBodyUSLT)?.description != LYRICS_DESCRIPTION }
            runCatching { id3.deleteField("USLT") }
            foreign.forEach { runCatching { id3.addField(it) } }
            val frame = id3.createFrame("USLT")
            frame.body = FrameBodyUSLT(
                TextEncoding.UTF_16,
                "und",
                LYRICS_DESCRIPTION,
                changes.lyricsLrc,
            )
            id3.addField(frame)
        }

        if (changes.removeCover) {
            runCatching { id3.deleteField("APIC") }
        } else if (changes.coverData != null) {
            val frame = id3.createFrame("APIC")
            frame.body = FrameBodyAPIC(
                TextEncoding.UTF_16,
                changes.coverMime ?: sniffImageMime(changes.coverData),
                3.toByte(),
                COVER_DESCRIPTION,
                changes.coverData,
            )
            runCatching { id3.deleteField("APIC") }
            id3.addField(frame)
        }
    }

    private fun writeMp4(audio: AudioFile, changes: TagChanges) {
        val tag = audio.tag ?: audio.tagOrCreateDefault
        setOrRemoveText(tag, FieldKey.TITLE, changes.title)
        setOrRemoveText(tag, FieldKey.ARTIST, changes.artist)
        setOrRemoveText(tag, FieldKey.ALBUM, changes.album)
        if (changes.removeLyrics) {
            runCatching { tag.deleteField(FieldKey.LYRICS) }
        } else if (changes.lyricsLrc != null) {
            setOrRemoveText(tag, FieldKey.LYRICS, changes.lyricsLrc)
        }
        writeCover(tag, changes)
    }

    private fun writeVorbisStyle(audio: AudioFile, changes: TagChanges) {
        val tag = audio.tag ?: audio.tagOrCreateDefault
        setOrRemoveText(tag, FieldKey.TITLE, changes.title)
        setOrRemoveText(tag, FieldKey.ARTIST, changes.artist)
        setOrRemoveText(tag, FieldKey.ALBUM, changes.album)
        if (changes.removeLyrics) {
            runCatching { tag.deleteField(FieldKey.LYRICS) }
            runCatching { tag.deleteField("UNSYNCEDLYRICS") }
        } else if (changes.lyricsLrc != null) {
            setOrRemoveText(tag, FieldKey.LYRICS, changes.lyricsLrc)
        }
        writeCover(tag, changes)
    }

    private fun writeCover(tag: Tag, changes: TagChanges) {
        if (changes.removeCover) {
            runCatching { tag.deleteArtworkField() }
        } else if (changes.coverData != null) {
            val artwork: Artwork = ArtworkFactory.getNew()
            artwork.binaryData = changes.coverData
            artwork.setMimeType(changes.coverMime ?: sniffImageMime(changes.coverData))
            artwork.pictureType = 3
            runCatching { tag.deleteArtworkField() }
            tag.addField(artwork)
        }
    }

    fun sniffImageMime(data: ByteArray): String = when {
        data.size >= 3 && data[0] == 0xFF.toByte() && data[1] == 0xD8.toByte() -> "image/jpeg"
        data.size >= 4 && data[0] == 0x89.toByte() && data[1] == 0x50.toByte() &&
            data[2] == 0x4E.toByte() && data[3] == 0x47.toByte() -> "image/png"
        else -> "image/png"
    }
}
