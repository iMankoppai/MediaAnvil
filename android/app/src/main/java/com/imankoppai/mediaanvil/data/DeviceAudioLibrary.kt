package com.imankoppai.mediaanvil.data

import android.content.ContentUris
import android.content.Context
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import com.imankoppai.mediaanvil.model.AudioTrack
import com.imankoppai.mediaanvil.tags.WavInfoTagIO
import java.io.File

/** Reads every supported audio file indexed on shared storage. */
object DeviceAudioLibrary {
    private val audioExtensions = setOf("mp3", "wav", "flac", "m4a", "aac", "ogg", "opus")
    private val subtitleExtensions = listOf("lrc", "srt", "vtt")

    @Suppress("DEPRECATION")
    fun scan(context: Context): LibraryScan {
        val tracks = mutableListOf<AudioTrack>()
        audioCollections(context).forEach { collection ->
            val projection = arrayOf(
                MediaStore.Audio.Media._ID,
                MediaStore.Audio.Media.DISPLAY_NAME,
                MediaStore.Audio.Media.TITLE,
                MediaStore.Audio.Media.ARTIST,
                MediaStore.Audio.Media.ALBUM,
                MediaStore.Audio.Media.DURATION,
                MediaStore.Audio.Media.DATA,
            )
            context.contentResolver.query(collection, projection, null, null, null)?.use { cursor ->
                val idColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media._ID)
                val nameColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.DISPLAY_NAME)
                val titleColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.TITLE)
                val artistColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.ARTIST)
                val albumColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.ALBUM)
                val durationColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.DURATION)
                val dataColumn = cursor.getColumnIndex(MediaStore.Audio.Media.DATA)
                while (cursor.moveToNext()) {
                    val name = cursor.getString(nameColumn).orEmpty()
                    val extension = name.substringAfterLast('.', "").lowercase()
                    if (extension !in audioExtensions) continue
                    val uri = ContentUris.withAppendedId(collection, cursor.getLong(idColumn))
                    val file = dataColumn.takeIf { it >= 0 }?.let { cursor.getString(it) }?.let(::File)
                    val subtitle = file?.let(::findSubtitle)
                    var title = cursor.getString(titleColumn).cleanMetadata()
                    var artist = cursor.getString(artistColumn).cleanMetadata()
                    if (extension == "wav") {
                        val riff = runCatching {
                            context.contentResolver.openInputStream(uri)?.use(WavInfoTagIO::read)
                        }.getOrNull()
                        title = riff?.title?.takeIf(String::isNotBlank) ?: title
                        artist = riff?.artist?.takeIf(String::isNotBlank) ?: artist
                    }
                    tracks += AudioTrack(
                        uri = uri,
                        fileName = name,
                        title = title ?: name.substringBeforeLast('.', name),
                        artist = artist,
                        album = cursor.getString(albumColumn).cleanMetadata(),
                        durationMs = cursor.getLong(durationColumn).coerceAtLeast(0L),
                        subtitleUri = subtitle?.let(Uri::fromFile),
                        subtitleExtension = subtitle?.extension?.lowercase(),
                        parentPath = file?.parent.orEmpty(),
                    )
                }
            }
        }
        return LibraryScan(
            tracks = tracks.distinctBy { it.uri }.sortedWith(compareBy(String.CASE_INSENSITIVE_ORDER) { it.fileName }),
            files = emptyList(),
        )
    }

    private fun audioCollections(context: Context): List<Uri> =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            MediaStore.getExternalVolumeNames(context).map(MediaStore.Audio.Media::getContentUri)
        } else {
            listOf(MediaStore.Audio.Media.EXTERNAL_CONTENT_URI)
        }

    private fun findSubtitle(audio: File): File? {
        val siblings = audio.parentFile?.listFiles()?.associateBy { it.name.lowercase() } ?: return null
        val base = audio.name.substringBeforeLast('.', audio.name)
        subtitleExtensions.forEach { extension ->
            siblings["${audio.name}.$extension".lowercase()]?.let { return it }
            siblings["$base.$extension".lowercase()]?.let { return it }
        }
        return null
    }

    private fun String?.cleanMetadata(): String? =
        this?.takeIf { it.isNotBlank() && it != "<unknown>" }
}
