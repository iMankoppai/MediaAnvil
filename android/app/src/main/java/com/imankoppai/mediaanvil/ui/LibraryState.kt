package com.imankoppai.mediaanvil.ui

import android.content.Context
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.imankoppai.mediaanvil.data.DeviceAudioLibrary
import com.imankoppai.mediaanvil.data.LibraryCache
import com.imankoppai.mediaanvil.data.LibraryScan
import com.imankoppai.mediaanvil.data.PlaybackPreferences
import com.imankoppai.mediaanvil.data.ScannedFile
import com.imankoppai.mediaanvil.model.AudioTrack
import com.imankoppai.mediaanvil.model.TrackGroup
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

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

    /** User-created playlist-like groups, mirrored into preferences. */
    var trackGroups by mutableStateOf(preferences.trackGroups)
        private set

    var hiddenTrackUris by mutableStateOf(preferences.hiddenTrackUris)
        private set

    fun hideTrack(uri: Uri) {
        val key = uri.toString()
        val selectedUri = selectedTrack?.uri
        hiddenTrackUris = hiddenTrackUris + key
        preferences.hiddenTrackUris = hiddenTrackUris
        tracks = tracks.filterNot { it.uri == uri }
        selectedIndex = tracks.indexOfFirst { it.uri == selectedUri }
    }

    fun restoreHiddenTracks() {
        hiddenTrackUris = emptySet()
        preferences.hiddenTrackUris = emptySet()
        rescan(quiet = false)
    }

    fun reloadAfterPreferencesRestore() {
        trackGroups = preferences.trackGroups
        hiddenTrackUris = preferences.hiddenTrackUris
        rescan(quiet = false)
    }

    fun createGroup(name: String): Boolean {
        val clean = name.trim()
        if (clean.isEmpty() || trackGroups.any { it.name.equals(clean, ignoreCase = true) }) return false
        trackGroups = trackGroups + TrackGroup(java.util.UUID.randomUUID().toString(), clean, emptySet())
        preferences.trackGroups = trackGroups
        return true
    }

    fun renameGroup(id: String, name: String): Boolean {
        val clean = name.trim()
        if (clean.isEmpty() || trackGroups.any { it.id != id && it.name.equals(clean, ignoreCase = true) }) return false
        trackGroups = trackGroups.map { if (it.id == id) it.copy(name = clean) else it }
        preferences.trackGroups = trackGroups
        return true
    }

    fun deleteGroup(id: String) {
        trackGroups = trackGroups.filterNot { it.id == id }
        preferences.trackGroups = trackGroups
    }

    fun setGroupTracks(id: String, uris: Set<String>) {
        trackGroups = trackGroups.map { if (it.id == id) it.copy(trackUris = uris) else it }
        preferences.trackGroups = trackGroups
    }

    fun removeTrackFromGroup(id: String, uri: Uri) {
        val group = trackGroups.firstOrNull { it.id == id } ?: return
        setGroupTracks(id, group.trackUris - uri.toString())
    }

    val selectedTrack: AudioTrack? get() = tracks.getOrNull(selectedIndex)

    fun attachLyrics(trackUri: Uri, lyricsFile: File) {
        val selectedUri = selectedTrack?.uri
        tracks = tracks.map { track ->
            if (track.uri == trackUri) {
                track.copy(subtitleUri = Uri.fromFile(lyricsFile), subtitleExtension = lyricsFile.extension.lowercase())
            } else {
                track
            }
        }
        selectedIndex = tracks.indexOfFirst { it.uri == selectedUri }
        val currentFiles = files?.files.orEmpty()
        files = LibraryScan(tracks, currentFiles)
        LibraryCache.save(appContext, DEVICE_LIBRARY_URI, LibraryScan(tracks, currentFiles))
    }

    fun detachLyrics(trackUri: Uri) {
        val selectedUri = selectedTrack?.uri
        tracks = tracks.map { track ->
            if (track.uri == trackUri) track.copy(subtitleUri = null, subtitleExtension = null) else track
        }
        selectedIndex = tracks.indexOfFirst { it.uri == selectedUri }
        val currentFiles = files?.files.orEmpty()
        files = LibraryScan(tracks, currentFiles)
        LibraryCache.save(appContext, DEVICE_LIBRARY_URI, LibraryScan(tracks, currentFiles))
    }

    /** Show the cached library instantly, then refresh quietly in the background. */
    fun startup() {
        val snapshot = LibraryCache.load(appContext)
        if (snapshot != null && snapshot.treeUri == DEVICE_LIBRARY_URI) {
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
                    parentPath = record.parentPath,
                )
            }.filterNot { it.uri.toString() in hiddenTrackUris }
            files = LibraryScan(
                tracks = emptyList(),
                files = snapshot.files.map { ScannedFile(it.uri, it.name, it.parentPath) },
            )
            if (!LibraryCache.isFresh(snapshot)) {
                scanAll(quiet = true)
            }
        } else {
            scanAll(quiet = false)
        }
    }

    fun rescan(quiet: Boolean = false, onLoaded: (Int) -> Unit = {}) {
        scanAll(quiet, onLoaded)
    }

    private fun scanAll(quiet: Boolean, onLoaded: (Int) -> Unit = {}) {
        loading = !quiet
        if (!quiet) message = null
        scope.launch {
            val previousUri = tracks.getOrNull(selectedIndex)?.uri
            val result = withContext(Dispatchers.IO) {
                runCatching { DeviceAudioLibrary.scan(appContext) }
                    .getOrElse { LibraryScan(emptyList(), emptyList()) }
            }
            val visibleResult = result.copy(
                tracks = result.tracks.filterNot { it.uri.toString() in hiddenTrackUris },
            )
            files = visibleResult
            tracks = visibleResult.tracks
            selectedIndex = visibleResult.tracks.indexOfFirst { it.uri == previousUri }
            loading = false
            // Keep the complete scan in cache; hidden tracks are filtered only in the UI state.
            // This makes restoring them reliable even if the app closes during the restore scan.
            LibraryCache.save(appContext, DEVICE_LIBRARY_URI, result)
            if (visibleResult.tracks.isEmpty() && !quiet) {
                message = appContext.getString(com.imankoppai.mediaanvil.R.string.no_tracks)
            }
            onLoaded(visibleResult.tracks.size)
        }
    }

    companion object {
        private val DEVICE_LIBRARY_URI = Uri.parse("mediaanvil://device-library")
    }
}
