package com.imankoppai.mediaanvil.data

import android.content.Context
import android.content.Intent
import android.media.MediaMetadataRetriever
import android.net.Uri
import androidx.documentfile.provider.DocumentFile
import com.imankoppai.mediaanvil.model.AudioTrack

data class ScannedFile(
    val uri: Uri,
    val name: String,
    val parentPath: String,
)

data class LibraryScan(
    val tracks: List<AudioTrack>,
    val files: List<ScannedFile>,
)

object DocumentLibrary {
    private val audioExtensions = setOf("mp3", "wav", "flac", "m4a", "aac", "ogg", "opus")
    private val subtitleExtensions = listOf("lrc", "srt", "vtt")

    fun scan(context: Context, treeUri: Uri, includeSubfolders: Boolean = true): LibraryScan {
        val root = DocumentFile.fromTreeUri(context, treeUri) ?: return LibraryScan(emptyList(), emptyList())
        val directories = mutableListOf<Pair<String, DocumentFile>>()
        val files = mutableListOf<Pair<String, DocumentFile>>()
        collect(root, "", includeSubfolders, directories, files)

        val allFiles = files.map { (path, file) -> ScannedFile(file.uri, file.name.orEmpty(), path) }
        val tracks = files.mapNotNull { (path, file) ->
            file.name ?: return@mapNotNull null
            if (file.extension().lowercase() !in audioExtensions) return@mapNotNull null
            val folder = directories.firstOrNull { it.first == path }?.second ?: root
            file.toTrack(context, path, folder, files.filter { it.first == path })
        }.sortedWith(compareBy(String.CASE_INSENSITIVE_ORDER) { it.fileName })
        return LibraryScan(tracks, allFiles)
    }

    private fun collect(
        directory: DocumentFile,
        path: String,
        includeSubfolders: Boolean,
        directories: MutableList<Pair<String, DocumentFile>>,
        files: MutableList<Pair<String, DocumentFile>>,
    ) {
        directories += path to directory
        directory.listFiles().forEach { file ->
            if (file.isDirectory) {
                if (!includeSubfolders) return@forEach
                val childPath = if (path.isEmpty()) file.name.orEmpty() else "$path/${file.name.orEmpty()}"
                collect(file, childPath, includeSubfolders, directories, files)
            } else {
                files += path to file
            }
        }
    }

    private fun DocumentFile.extension(): String =
        name.orEmpty().substringAfterLast('.', missingDelimiterValue = "").lowercase()

    /**
     * Pick the subtitle exactly like the desktop preview loader: format order
     * LRC, SRT, VTT; within one format the name keeping the full audio file
     * name (`song.wav.vtt`) wins over the plain base name (`song.vtt`).
     */
    private fun findSubtitle(audioName: String, siblings: List<Pair<String, DocumentFile>>): DocumentFile? {
        val baseName = audioName.substringBeforeLast('.', audioName)
        for (extension in subtitleExtensions) {
            val fullName = audioName + "." + extension
            siblings.firstOrNull { it.second.name == fullName }?.let { return it.second }
            siblings.firstOrNull { it.second.name == baseName + "." + extension }?.let { return it.second }
        }
        return null
    }

    private fun DocumentFile.toTrack(
        context: Context,
        parentPath: String,
        parent: DocumentFile,
        siblings: List<Pair<String, DocumentFile>>,
    ): AudioTrack {
        val audioName = name.orEmpty()
        val baseName = audioName.substringBeforeLast('.', audioName)
        val subtitle = findSubtitle(audioName, siblings)
        val metadata = readMetadata(context, uri)
        return AudioTrack(
            uri = uri,
            fileName = audioName,
            title = metadata.title?.takeIf(String::isNotBlank) ?: baseName,
            artist = metadata.artist?.takeIf(String::isNotBlank),
            album = metadata.album?.takeIf(String::isNotBlank),
            durationMs = metadata.durationMs,
            subtitleUri = subtitle?.uri,
            subtitleExtension = subtitle?.extension(),
            parent = parent,
            parentPath = parentPath,
        )
    }

    private data class TrackMetadata(
        val title: String?,
        val artist: String?,
        val album: String?,
        val durationMs: Long,
    )

    private fun readMetadata(context: Context, uri: Uri): TrackMetadata {
        val retriever = MediaMetadataRetriever()
        return try {
            retriever.setDataSource(context, uri)
            TrackMetadata(
                title = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_TITLE),
                artist = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ARTIST),
                album = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ALBUM),
                durationMs = retriever
                    .extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)
                    ?.toLongOrNull()
                    ?: 0L,
            )
        } catch (_: RuntimeException) {
            TrackMetadata(null, null, null, 0L)
        } finally {
            retriever.release()
        }
    }
}
