package com.imankoppai.mediaanvil.data

import android.content.Context
import android.net.Uri
import org.json.JSONArray
import org.json.JSONObject
import androidx.documentfile.provider.DocumentFile

/**
 * Persisted snapshot of the last folder scan so the library opens instantly;
 * a background rescan keeps it fresh afterwards. Only paths and tags are
 * cached — never audio bytes.
 */
object LibraryCache {
    private const val FILE_NAME = "library_snapshot.json"
    private const val MAX_AGE_MS = 5 * 60 * 1000L

    data class TrackRecord(
        val uri: Uri,
        val fileName: String,
        val title: String,
        val artist: String?,
        val album: String?,
        val durationMs: Long,
        val parentPath: String,
        val subtitleUri: Uri?,
        val subtitleExtension: String?,
    )

    data class FileRecord(
        val uri: Uri,
        val name: String,
        val parentPath: String,
    )

    data class Snapshot(
        val treeUri: Uri,
        val tracks: List<TrackRecord>,
        val files: List<FileRecord>,
        val savedAt: Long,
    )

    fun save(context: Context, treeUri: Uri, scan: LibraryScan) {
        runCatching {
            val root = JSONObject()
                .put("treeUri", treeUri.toString())
                .put("savedAt", System.currentTimeMillis())
            val tracks = JSONArray()
            scan.tracks.forEach { track ->
                tracks.put(
                    JSONObject()
                        .put("uri", track.uri.toString())
                        .put("fileName", track.fileName)
                        .put("title", track.title)
                        .put("artist", track.artist.orEmpty())
                        .put("album", track.album.orEmpty())
                        .put("durationMs", track.durationMs)
                        .put("parentPath", track.parentPath)
                        .put("subtitleUri", track.subtitleUri?.toString().orEmpty())
                        .put("subtitleExtension", track.subtitleExtension.orEmpty()),
                )
            }
            root.put("tracks", tracks)
            val files = JSONArray()
            scan.files.forEach { file ->
                files.put(
                    JSONObject()
                        .put("uri", file.uri.toString())
                        .put("name", file.name)
                        .put("parentPath", file.parentPath),
                )
            }
            root.put("files", files)
            context.cacheDir.mkdirs()
            val target = java.io.File(context.cacheDir, FILE_NAME)
            val tmp = java.io.File(context.cacheDir, "$FILE_NAME.tmp")
            tmp.writeText(root.toString())
            if (!tmp.renameTo(target)) {
                target.delete()
                tmp.renameTo(target)
            }
        }
    }

    fun load(context: Context): Snapshot? = runCatching {
        val file = java.io.File(context.cacheDir, FILE_NAME)
        if (!file.isFile) return null
        val root = JSONObject(file.readText())
        val treeUri = Uri.parse(root.getString("treeUri"))
        val tracks = mutableListOf<TrackRecord>()
        val tracksArray = root.optJSONArray("tracks") ?: JSONArray()
        for (i in 0 until tracksArray.length()) {
            val item = tracksArray.getJSONObject(i)
            val subtitleUri = item.optString("subtitleUri").ifEmpty { null }?.let(Uri::parse)
            tracks += TrackRecord(
                uri = Uri.parse(item.getString("uri")),
                fileName = item.getString("fileName"),
                title = item.getString("title"),
                artist = item.optString("artist").ifEmpty { null },
                album = item.optString("album").ifEmpty { null },
                durationMs = item.optLong("durationMs"),
                parentPath = item.optString("parentPath"),
                subtitleUri = subtitleUri,
                subtitleExtension = item.optString("subtitleExtension").ifEmpty { null },
            )
        }
        val files = mutableListOf<FileRecord>()
        val filesArray = root.optJSONArray("files") ?: JSONArray()
        for (i in 0 until filesArray.length()) {
            val item = filesArray.getJSONObject(i)
            files += FileRecord(
                uri = Uri.parse(item.getString("uri")),
                name = item.getString("name"),
                parentPath = item.optString("parentPath"),
            )
        }
        Snapshot(
            treeUri = treeUri,
            tracks = tracks,
            files = files,
            savedAt = root.optLong("savedAt"),
        )
    }.getOrNull()

    fun isFresh(snapshot: Snapshot): Boolean =
        System.currentTimeMillis() - snapshot.savedAt < MAX_AGE_MS

    /** Resolve the DocumentFile of a cached track's folder on demand. */
    fun resolveFolder(context: Context, treeUri: Uri?, parentPath: String): DocumentFile? {
        if (treeUri == null) return null
        var folder = DocumentFile.fromTreeUri(context, treeUri) ?: return null
        if (parentPath.isEmpty()) return folder
        for (segment in parentPath.split('/').filter { it.isNotEmpty() }) {
            folder = folder.findFile(segment)?.takeIf { it.isDirectory } ?: return null
        }
        return folder
    }
}
