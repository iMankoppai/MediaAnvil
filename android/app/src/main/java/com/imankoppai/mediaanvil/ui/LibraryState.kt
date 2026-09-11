package com.imankoppai.mediaanvil.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.imankoppai.mediaanvil.data.DocumentLibrary
import com.imankoppai.mediaanvil.data.LibraryCache
import com.imankoppai.mediaanvil.data.LibraryScan
import com.imankoppai.mediaanvil.data.PlaybackPreferences
import com.imankoppai.mediaanvil.data.ScannedFile
import com.imankoppai.mediaanvil.model.AudioTrack
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** Shared folder library state used by both the playback and tag editor pages. */
class LibraryState(context: Context, private val scope: CoroutineScope) {
    private val appContext = context.applicationContext

    val preferences = PlaybackPreferences(appContext)

    var tracks by mutableStateOf<List<AudioTrack>>(emptyList())
        private set
    var files by mutableStateOf<LibraryScan?>(null)
        private set
    var selectedIndex by mutableStateOf(-1)
    var loading by mutableStateOf(false)
        private set
    var message by mutableStateOf<String?>(null)

    val selectedTrack: AudioTrack? get() = tracks.getOrNull(selectedIndex)

    fun loadFolder(uri: Uri, onLoaded: (Int) -> Unit = {}) {
        runCatching {
            appContext.contentResolver.takePersistableUriPermission(
                uri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
            )
        }.recoverCatching {
            appContext.contentResolver.takePersistableUriPermission(
                uri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION,
            )
        }
        preferences.lastFolder = uri
        scan(uri, quiet = false, onLoaded = onLoaded)
    }

    /** Show the cached library instantly, then refresh quietly in the background. */
    fun startup() {
        val snapshot = LibraryCache.load(appContext)
        val last = preferences.lastFolder
        if (snapshot != null && last != null && last == snapshot.treeUri) {
            tracks = snapshot.tracks.map { record ->
                com.imankoppai.mediaanvil.model.AudioTrack(
                    uri = record.uri,
                    fileName = record.fileName,
                    title = record.title,
                    artist = record.artist,
                    album = record.album,
                    durationMs = record.durationMs,
                    subtitleUri = record.subtitleUri,
                    subtitleExtension = record.subtitleExtension,
                    parent = null,
                    parentPath = record.parentPath,
                )
            }
            files = LibraryScan(
                tracks = emptyList(),
                files = snapshot.files.map { ScannedFile(it.uri, it.name, it.parentPath) },
            )
            if (!LibraryCache.isFresh(snapshot)) {
                rescan(quiet = true)
            }
        } else if (last != null) {
            scan(last, quiet = false)
        }
    }

    fun rescan(quiet: Boolean = false, onLoaded: (Int) -> Unit = {}) {
        preferences.lastFolder?.let { scan(it, quiet, onLoaded) }
    }

    private fun scan(uri: Uri, quiet: Boolean, onLoaded: (Int) -> Unit = {}) {
        loading = !quiet
        if (!quiet) message = null
        scope.launch {
            val previousUri = tracks.getOrNull(selectedIndex)?.uri
            val result = withContext(Dispatchers.IO) {
                runCatching {
                    DocumentLibrary.scan(appContext, uri, preferences.includeSubfolders)
                }.getOrElse { LibraryScan(emptyList(), emptyList()) }
            }
            files = result
            tracks = result.tracks
            selectedIndex = result.tracks.indexOfFirst { it.uri == previousUri }
            loading = false
            LibraryCache.save(appContext, uri, result)
            if (result.tracks.isEmpty() && !quiet) {
                message = appContext.getString(com.imankoppai.mediaanvil.R.string.no_tracks)
            }
            onLoaded(result.tracks.size)
        }
    }
}
