package com.imankoppai.mediaanvil.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.documentfile.provider.DocumentFile
import com.imankoppai.mediaanvil.data.DocumentLibrary
import com.imankoppai.mediaanvil.data.LibraryCache
import com.imankoppai.mediaanvil.data.LibraryScan
import com.imankoppai.mediaanvil.data.PlaybackPreferences
import com.imankoppai.mediaanvil.data.ScannedFile
import com.imankoppai.mediaanvil.model.AudioTrack
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
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

    /** Human-readable message for the latest playback failure, if any. */
    var playbackError by mutableStateOf<String?>(null)

    /** Epoch-ms deadline of the sleep timer, or null when off. */
    var sleepTimerEndAt by mutableStateOf<Long?>(null)
        private set

    private var sleepJob: kotlinx.coroutines.Job? = null

    /** Pause playback when the deadline passes; [onPause] comes from the player owner. */
    fun startSleepTimer(minutes: Int, onPause: () -> Unit) {
        sleepJob?.cancel()
        sleepTimerEndAt = System.currentTimeMillis() + minutes * 60_000L
        sleepJob = scope.launch {
            delay(minutes * 60_000L)
            sleepTimerEndAt = null
            onPause()
        }
    }

    fun cancelSleepTimer() {
        sleepJob?.cancel()
        sleepJob = null
        sleepTimerEndAt = null
    }

    /** Favorite track URIs (string forms), mirrored into preferences. */
    var favorites by mutableStateOf(preferences.favorites)
        private set

    /** Recently played track URIs, newest first. */
    var recentUris by mutableStateOf(preferences.recentUris)
        private set

    fun recordRecent(uri: String) {
        val updated = (listOf(uri) + recentUris.filterNot { it == uri }).take(50)
        recentUris = updated
        preferences.recentUris = updated
    }

    fun toggleFavorite(uri: Uri) {
        val key = uri.toString()
        favorites = if (key in favorites) favorites - key else favorites + key
        preferences.favorites = favorites
    }

    fun isFavorite(uri: Uri): Boolean = uri.toString() in favorites

    val selectedTrack: AudioTrack? get() = tracks.getOrNull(selectedIndex)

    /** Authorized library roots, aggregated into one library. */
    var folders by mutableStateOf<List<Uri>>(emptyList())
        private set

    fun addFolder(uri: Uri, onLoaded: (Int) -> Unit = {}) {
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
        folders = (folders + uri).distinct()
        preferences.folders = folders
        preferences.lastFolder = uri
        scanAll(quiet = false, onLoaded = onLoaded)
    }

    fun removeFolder(uri: Uri) {
        folders = folders - uri
        preferences.folders = folders
        scanAll(quiet = true)
    }

    /** DocumentFile of the granted folder that contains [file], for saving next to it. */
    fun resolveFolderFor(context: Context, file: ScannedFile): DocumentFile? {
        val root = folders.firstOrNull { folder ->
            val tree = folder.toString().substringBefore('?')
            file.uri.toString().contains(tree)
        } ?: preferences.lastFolder
        return LibraryCache.resolveFolder(context, root, file.parentPath)
    }

    private fun ensureFolders(): List<Uri> {
        if (folders.isEmpty()) {
            val migrated = listOfNotNull(preferences.lastFolder)
            folders = migrated
            preferences.folders = migrated
        }
        return folders
    }

    /** Show the cached library instantly, then refresh quietly in the background. */
    fun startup() {
        val roots = ensureFolders()
        val snapshot = LibraryCache.load(appContext)
        val cacheRoot = roots.firstOrNull()
        if (snapshot != null && cacheRoot != null && cacheRoot == snapshot.treeUri) {
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
                scanAll(quiet = true)
            }
        } else if (roots.isNotEmpty()) {
            scanAll(quiet = false)
        }
    }

    fun rescan(quiet: Boolean = false, onLoaded: (Int) -> Unit = {}) {
        scanAll(quiet, onLoaded)
    }

    private fun scanAll(quiet: Boolean, onLoaded: (Int) -> Unit = {}) {
        val roots = ensureFolders()
        loading = !quiet
        if (!quiet) message = null
        scope.launch {
            val previousUri = tracks.getOrNull(selectedIndex)?.uri
            val result = withContext(Dispatchers.IO) {
                val scans = roots.map { root ->
                    runCatching {
                        DocumentLibrary.scan(appContext, root, preferences.includeSubfolders)
                    }.getOrElse { LibraryScan(emptyList(), emptyList()) }
                }
                LibraryScan(
                    tracks = scans.flatMap { it.tracks }.distinctBy { it.uri },
                    files = scans.flatMap { it.files }.distinctBy { it.uri },
                )
            }
            files = result
            tracks = result.tracks
            selectedIndex = result.tracks.indexOfFirst { it.uri == previousUri }
            loading = false
            roots.firstOrNull()?.let { LibraryCache.save(appContext, it, result) }
            if (result.tracks.isEmpty() && !quiet) {
                message = appContext.getString(com.imankoppai.mediaanvil.R.string.no_tracks)
            }
            onLoaded(result.tracks.size)
        }
    }
}
