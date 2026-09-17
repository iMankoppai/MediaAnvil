package com.imankoppai.mediaanvil.data

import android.content.ContentUris
import android.content.Context
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import com.imankoppai.mediaanvil.model.AudioTrack
import com.imankoppai.mediaanvil.tags.WavInfoTagIO
import java.io.File

/** Reads supported audio files indexed on shared storage, optionally restricted to folders. */
object DeviceAudioLibrary {
    private val audioExtensions = setOf("mp3", "wav", "flac", "m4a", "aac", "ogg", "opus")
    private val subtitleExtensions = listOf("lrc", "srt", "vtt")

    /** A folder that contains audio files, keyed by its storage-relative path. */
    data class AudioFolder(val path: String, val trackCount: Int)

    @Suppress("DEPRECATION")
    fun scan(context: Context, allowedFolders: Set<String> = emptySet()): LibraryScan {
        val storageRoot = storageRoot()
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
                    val file = dataColumn.takeIf { it >= 0 }?.let { cursor.getString(it) }?.let(::File)
                    val parentPath = file?.parent.orEmpty()
                    if (!isFolderAllowed(parentPath, allowedFolders, storageRoot)) continue
                    val uri = ContentUris.withAppendedId(collection, cursor.getLong(idColumn))
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
                        parentPath = parentPath,
                    )
                }
            }
        }
        return LibraryScan(
            tracks = tracks.distinctBy { it.uri }.sortedWith(compareBy(String.CASE_INSENSITIVE_ORDER) { it.fileName }),
            files = emptyList(),
        )
    }

    /** Folders that directly contain at least one supported audio file, sorted by path. */
    @Suppress("DEPRECATION")
    fun listFolders(context: Context): List<AudioFolder> {
        val storageRoot = storageRoot()
        val counts = mutableMapOf<String, Int>()
        audioCollections(context).forEach { collection ->
            val projection = arrayOf(MediaStore.Audio.Media.DISPLAY_NAME, MediaStore.Audio.Media.DATA)
            context.contentResolver.query(collection, projection, null, null, null)?.use { cursor ->
                val nameColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.DISPLAY_NAME)
                val dataColumn = cursor.getColumnIndex(MediaStore.Audio.Media.DATA)
                while (cursor.moveToNext()) {
                    val name = cursor.getString(nameColumn).orEmpty()
                    if (name.substringAfterLast('.', "").lowercase() !in audioExtensions) continue
                    val parentPath = dataColumn.takeIf { it >= 0 }
                        ?.let { cursor.getString(it) }
                        ?.let { File(it).parent }
                        .orEmpty()
                    val folder = relativeFolder(parentPath, storageRoot)
                    counts[folder] = (counts[folder] ?: 0) + 1
                }
            }
        }
        return counts.map { AudioFolder(it.key, it.value) }
            .sortedWith(compareBy(String.CASE_INSENSITIVE_ORDER) { it.path })
    }

    private fun audioCollections(context: Context): List<Uri> =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            MediaStore.getExternalVolumeNames(context).map(MediaStore.Audio.Media::getContentUri)
        } else {
            listOf(MediaStore.Audio.Media.EXTERNAL_CONTENT_URI)
        }

    private fun storageRoot(): String =
        runCatching { Environment.getExternalStorageDirectory()?.absolutePath }
            .getOrNull()
            ?.trimEnd('/')
            .orEmpty()

    /** Directory of [parentPath] relative to shared storage, with a trailing slash. */
    internal fun relativeFolder(parentPath: String, storageRoot: String): String {
        val prefix = storageRoot.trimEnd('/')
        val relative = when {
            prefix.isNotEmpty() && parentPath.startsWith("$prefix/") -> parentPath.removePrefix("$prefix/")
            parentPath.startsWith("/storage/") -> parentPath.removePrefix("/storage/")
            parentPath.startsWith("/") -> parentPath.removePrefix("/")
            else -> parentPath
        }
        return relative.trimEnd('/') + "/"
    }

    /** Empty [folders] scans everything; otherwise the track's own folder must be selected exactly. */
    internal fun isFolderAllowed(parentPath: String, folders: Set<String>, storageRoot: String): Boolean {
        if (folders.isEmpty()) return true
        return relativeFolder(parentPath, storageRoot) in folders
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
