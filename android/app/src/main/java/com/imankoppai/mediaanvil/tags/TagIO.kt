package com.imankoppai.mediaanvil.tags

import org.jaudiotagger.audio.AudioFileIO
import org.jaudiotagger.audio.mp3.MP3File
import org.jaudiotagger.tag.FieldKey
import org.jaudiotagger.tag.Tag
import org.jaudiotagger.tag.id3.AbstractID3v2Frame
import org.jaudiotagger.tag.id3.AbstractID3v2Tag
import org.jaudiotagger.tag.id3.ID3v23Tag
import org.jaudiotagger.tag.id3.valuepair.TextEncoding
import java.io.File

/** Minimal title/artist reader and writer for the mobile tag editor. */
object TagIO {
    val writableExtensions = setOf("mp3", "wav", "flac", "m4a", "ogg", "opus")

    data class Tags(val title: String, val artist: String)

    fun isWritable(fileName: String): Boolean =
        fileName.substringAfterLast('.', "").lowercase() in writableExtensions

    fun read(file: File): Tags {
        if (file.extension.equals("wav", ignoreCase = true)) {
            val riff = WavInfoTagIO.read(file)
            val fallback = runCatching { readWithJAudioTagger(file) }.getOrDefault(Tags("", ""))
            return Tags(
                title = riff.title ?: fallback.title,
                artist = riff.artist ?: fallback.artist,
            )
        }
        return readWithJAudioTagger(file)
    }

    private fun readWithJAudioTagger(file: File): Tags {
        val tag = AudioFileIO.read(file).tag
        return Tags(
            title = text(tag, FieldKey.TITLE),
            artist = text(tag, FieldKey.ARTIST),
        )
    }

    fun write(file: File, title: String, artist: String) {
        check(file.extension.lowercase() in writableExtensions) { "format_not_writable" }
        if (file.extension.equals("wav", ignoreCase = true)) {
            WavInfoTagIO.write(file, title, artist)
            return
        }
        if (file.extension.equals("mp3", ignoreCase = true)) {
            writeMp3(file, title, artist)
            return
        }
        val audio = AudioFileIO.read(file)
        val tag = audio.tag ?: audio.tagOrCreateDefault
        setText(tag, FieldKey.TITLE, title)
        setText(tag, FieldKey.ARTIST, artist)
        audio.commit()
    }

    /** ID3v1 cannot represent CJK text, so migrate it to a Unicode ID3v2.3 tag. */
    private fun writeMp3(file: File, title: String, artist: String) {
        val audio = AudioFileIO.read(file) as? MP3File ?: error("invalid_mp3")
        val id3 = audio.getID3v2Tag() ?: audio.getID3v1Tag()?.let(::ID3v23Tag) ?: ID3v23Tag()
        audio.setID3v2Tag(id3)
        setId3Text(id3, FieldKey.TITLE, title)
        setId3Text(id3, FieldKey.ARTIST, artist)
        audio.commit()
    }

    private fun text(tag: Tag?, key: FieldKey): String =
        runCatching { tag?.getFirst(key).orEmpty() }.getOrDefault("")

    private fun setText(tag: Tag, key: FieldKey, value: String) {
        runCatching { tag.deleteField(key) }
        value.trim().takeIf(String::isNotEmpty)?.let { tag.addField(key, it) }
    }

    private fun setId3Text(tag: AbstractID3v2Tag, key: FieldKey, value: String) {
        runCatching { tag.deleteField(key) }
        val text = value.trim().takeIf(String::isNotEmpty) ?: return
        val field = tag.createField(key, text)
        (field as? AbstractID3v2Frame)?.body?.textEncoding = TextEncoding.UTF_16
        tag.addField(field)
    }
}
