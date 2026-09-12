package com.imankoppai.mediaanvil.ui

import android.content.ComponentName
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.LibraryMusic
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import com.imankoppai.mediaanvil.R
import com.imankoppai.mediaanvil.model.AudioTrack
import com.imankoppai.mediaanvil.playback.PlaybackService

private enum class MainTab(val titleRes: Int) {
    Media(R.string.tab_media),
    Tools(R.string.tab_tools),
    Settings(R.string.tab_settings),
}

/** Screens pushed above the tab shell. */
private sealed interface Overlay {
    data object None : Overlay
    data object NowPlaying : Overlay
    data class Editor(val track: AudioTrack?) : Overlay
}

@Composable
fun MediaAnvilApp() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val library = remember { LibraryState(context, scope) }
    var controller by remember { mutableStateOf<MediaController?>(null) }
    var tab by remember { mutableStateOf(MainTab.Media) }
    var overlay by remember { mutableStateOf<Overlay>(Overlay.None) }

    val folderPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        uri?.let { library.loadFolder(it) }
    }

    DisposableEffect(Unit) {
        val token = SessionToken(context, ComponentName(context, PlaybackService::class.java))
        val future = MediaController.Builder(context, token).buildAsync()
        future.addListener({
            runCatching { future.get() }.onSuccess { mediaController ->
                mediaController.playbackParameters =
                    androidx.media3.common.PlaybackParameters(library.preferences.playbackSpeed)
                mediaController.shuffleModeEnabled = library.preferences.shuffleEnabled
                mediaController.repeatMode = library.preferences.repeatMode
                mediaController.addListener(object : androidx.media3.common.Player.Listener {
                    override fun onMediaItemTransition(mediaItem: androidx.media3.common.MediaItem?, reason: Int) {
                        mediaItem?.mediaId?.let(library::recordRecent)
                    }

                    override fun onPlayerError(error: androidx.media3.common.PlaybackException) {
                        library.playbackError = when (error.errorCode) {
                            androidx.media3.common.PlaybackException.ERROR_CODE_IO_FILE_NOT_FOUND,
                            androidx.media3.common.PlaybackException.ERROR_CODE_IO_NO_PERMISSION,
                            androidx.media3.common.PlaybackException.ERROR_CODE_IO_READ_POSITION_OUT_OF_RANGE ->
                                context.getString(R.string.play_error_missing)
                            else -> context.getString(R.string.play_error_generic)
                        }
                    }
                })
                controller = mediaController
            }
        }, androidx.core.content.ContextCompat.getMainExecutor(context))
        onDispose { MediaController.releaseFuture(future) }
    }

    LaunchedEffect(Unit) {
        library.startup()
    }

    BackHandler(enabled = overlay != Overlay.None) {
        overlay = Overlay.None
    }

    Scaffold(
        containerColor = androidx.compose.material3.MaterialTheme.colorScheme.background,
        bottomBar = {
            NavigationBar(containerColor = androidx.compose.material3.MaterialTheme.colorScheme.surface) {
                MainTab.entries.forEach { entry ->
                    val icon = when (entry) {
                        MainTab.Media -> androidx.compose.material.icons.Icons.Filled.LibraryMusic
                        MainTab.Tools -> androidx.compose.material.icons.Icons.Filled.Build
                        MainTab.Settings -> androidx.compose.material.icons.Icons.Filled.Settings
                    }
                    NavigationBarItem(
                        selected = tab == entry,
                        onClick = { tab = entry },
                        icon = { Icon(icon, contentDescription = null) },
                        label = { Text(stringResource(entry.titleRes)) },
                    )
                }
            }
        },
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding)) {
            when (tab) {
                MainTab.Media -> LibraryPage(
                    library = library,
                    controller = controller,
                    onPickFolder = { folderPicker.launch(null) },
                    onOpenNowPlaying = { overlay = Overlay.NowPlaying },
                    onOpenEditor = { overlay = Overlay.Editor(it) },
                )
                MainTab.Tools -> ToolScreenHost(
                    library = library,
                    onOpenEditor = { overlay = Overlay.Editor(it) },
                )
                MainTab.Settings -> SettingsPage(library = library, controller = controller)
            }
        }
    }

    when (val current = overlay) {
        Overlay.None -> {}
        Overlay.NowPlaying -> Box(Modifier.fillMaxSize()) {
            NowPlayingPage(
                library = library,
                controller = controller,
                onBack = { overlay = Overlay.None },
            )
        }
        is Overlay.Editor -> Box(Modifier.fillMaxSize()) {
            TagEditorScreen(library, current.track, onBack = { overlay = Overlay.None })
        }
    }
}
