package com.imankoppai.mediaanvil.subtitles

import com.imankoppai.mediaanvil.model.AudioTrack
import java.io.File
import java.nio.charset.StandardCharsets

/** Writes a selected online result beside its audio file without touching the audio itself. */
object LyricsFileStore {
    fun save(track: AudioTrack, lyrics: String): File {
        return saveText(track, lyrics, "lrc")
    }

    fun import(track: AudioTrack, bytes: ByteArray, extension: String): File {
        val cleanExtension = extension.lowercase().takeIf { it in setOf("lrc", "srt", "vtt") }
            ?: error("unsupported_lyrics")
        return saveText(track, SubtitleLoader.decode(bytes), cleanExtension)
    }

    private fun saveText(track: AudioTrack, lyrics: String, extension: String): File {
        val parent = File(track.parentPath)
        check(track.parentPath.isNotBlank() && parent.isDirectory) { "audio_folder_unavailable" }
        val baseName = track.fileName.substringBeforeLast('.', track.fileName)
        val target = File(parent, "$baseName.$extension")
        val temporary = File(parent, ".$baseName.${System.nanoTime()}.$extension.tmp")
        val backup = File(parent, ".$baseName.${System.nanoTime()}.$extension.bak")
        try {
            temporary.outputStream().buffered().use { output ->
                output.write(lyrics.trim().toByteArray(StandardCharsets.UTF_8))
                output.write('\n'.code)
            }
            check(temporary.length() > 0L) { "empty_lyrics" }
            val hadOriginal = target.exists()
            if (hadOriginal) check(target.renameTo(backup)) { "lyrics_backup_failed" }
            try {
                check(temporary.renameTo(target)) { "lyrics_replace_failed" }
            } catch (failure: Throwable) {
                if (hadOriginal) backup.renameTo(target)
                throw failure
            }
            backup.delete()
            return target
        } finally {
            temporary.delete()
            if (!target.exists() && backup.exists()) backup.renameTo(target)
        }
    }

    fun delete(track: AudioTrack): Boolean {
        val uri = track.subtitleUri ?: return false
        check(uri.scheme == "file") { "lyrics_not_a_file" }
        val file = File(checkNotNull(uri.path)).canonicalFile
        val audioFolder = File(track.parentPath).canonicalFile
        check(file.parentFile == audioFolder && file.extension.lowercase() in setOf("lrc", "srt", "vtt")) {
            "unsafe_lyrics_path"
        }
        return !file.exists() || file.delete()
    }
}
