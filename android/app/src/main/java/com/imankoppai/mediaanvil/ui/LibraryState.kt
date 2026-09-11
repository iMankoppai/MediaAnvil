package com.imankoppai.mediaanvil.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.imankoppai.mediaanvil.data.DocumentLibrary
import com.imankoppai.mediaanvil.data.LibraryScan
import com.imankoppai.mediaanvil.data.PlaybackPreferences
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
        scan(uri, onLoaded)
    }

    fun rescan(onLoaded: (Int) -> Unit = {}) {
        preferences.lastFolder?.let { scan(it, onLoaded) }
    }

    private fun scan(uri: Uri, onLoaded: (Int) -> Unit) {
        loading = true
        message = null
        scope.launch {
            val result = withContext(Dispatchers.IO) {
                runCatching { DocumentLibrary.scan(appContext, uri) }.getOrElse { LibraryScan(emptyList(), emptyList()) }
            }
            files = result
            tracks = result.tracks
            selectedIndex = -1
            loading = false
            if (result.tracks.isEmpty()) message = appContext.getString(com.imankoppai.mediaanvil.R.string.no_tracks)
            onLoaded(result.tracks.size)
        }
    }
}
