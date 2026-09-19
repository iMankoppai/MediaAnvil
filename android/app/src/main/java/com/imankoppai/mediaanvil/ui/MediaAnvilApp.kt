package com.imankoppai.mediaanvil.ui

import android.annotation.SuppressLint
import android.content.ComponentName
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.Settings
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.LibraryMusic
import androidx.compose.material.icons.filled.PlayCircle
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import com.imankoppai.mediaanvil.R
import com.imankoppai.mediaanvil.playback.PlaybackService

private enum class MainTab(val titleRes: Int) {
    Media(R.string.tab_media),
    Player(R.string.tab_player),
    Settings(R.string.tab_settings),
}

@Composable
@SuppressLint("UnsafeOptInUsageError")
fun MediaAnvilApp() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val library = remember { LibraryState(context, scope) }
    var controller by remember { mutableStateOf<MediaController?>(null) }
    // Survives the activity recreation a system locale change triggers, so
    // switching language stays on the current tab instead of resetting to Media.
    var tab by androidx.compose.runtime.saveable.rememberSaveable { mutableStateOf(MainTab.Media) }
    var editingTrack by remember { mutableStateOf<com.imankoppai.mediaanvil.model.AudioTrack?>(null) }

    BackHandler(enabled = editingTrack != null || tab != MainTab.Media) {
        if (editingTrack != null) editingTrack = null else tab = MainTab.Media
    }

    val legacyStoragePermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { library.rescan() }
    val allFilesPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult(),
    ) { library.rescan() }

    fun requestStorageAccess() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            if (!Environment.isExternalStorageManager()) {
                val appSettings = Intent(
                    Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                    Uri.parse("package:${context.packageName}"),
                )
                runCatching { allFilesPermission.launch(appSettings) }
                    .onFailure { allFilesPermission.launch(Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION)) }
            } else {
                library.rescan()
            }
        } else {
            val permissions = buildList {
                if (androidx.core.content.ContextCompat.checkSelfPermission(
                        context,
                        android.Manifest.permission.READ_EXTERNAL_STORAGE,
                    ) != PackageManager.PERMISSION_GRANTED
                ) add(android.Manifest.permission.READ_EXTERNAL_STORAGE)
                if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.Q &&
                    androidx.core.content.ContextCompat.checkSelfPermission(
                        context,
                        android.Manifest.permission.WRITE_EXTERNAL_STORAGE,
                    ) != PackageManager.PERMISSION_GRANTED
                ) add(android.Manifest.permission.WRITE_EXTERNAL_STORAGE)
            }
            if (permissions.isEmpty()) library.rescan() else legacyStoragePermission.launch(permissions.toTypedArray())
        }
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
        val granted = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            Environment.isExternalStorageManager()
        } else {
            androidx.core.content.ContextCompat.checkSelfPermission(
                context,
                android.Manifest.permission.READ_EXTERNAL_STORAGE,
            ) == PackageManager.PERMISSION_GRANTED
        }
        if (!granted) requestStorageAccess()
    }

    Scaffold(
        containerColor = androidx.compose.material3.MaterialTheme.colorScheme.background,
        bottomBar = {
            if (editingTrack == null) NavigationBar(
                containerColor = androidx.compose.material3.MaterialTheme.colorScheme.surface,
                modifier = Modifier.height(104.dp),
            ) {
                Row(Modifier.fillMaxWidth()) {
                    MainTab.entries.forEach { entry ->
                        val selected = tab == entry
                        val icon = when (entry) {
                            MainTab.Media -> androidx.compose.material.icons.Icons.Filled.LibraryMusic
                            MainTab.Player -> androidx.compose.material.icons.Icons.Filled.PlayCircle
                            MainTab.Settings -> androidx.compose.material.icons.Icons.Filled.Settings
                        }
                        Box(Modifier.weight(1f), contentAlignment = Alignment.Center) {
                            Surface(
                                shape = CircleShape,
                                color = if (selected) {
                                    androidx.compose.material3.MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.55f)
                                } else {
                                    androidx.compose.ui.graphics.Color.Transparent
                                },
                                modifier = Modifier
                                    .size(68.dp)
                                    .clickable { tab = entry },
                            ) {
                                Column(
                                    horizontalAlignment = Alignment.CenterHorizontally,
                                    verticalArrangement = androidx.compose.foundation.layout.Arrangement.Center,
                                ) {
                                    Icon(
                                        icon,
                                        contentDescription = null,
                                        tint = if (selected) {
                                            androidx.compose.material3.MaterialTheme.colorScheme.onPrimaryContainer
                                        } else {
                                            androidx.compose.material3.MaterialTheme.colorScheme.onSurfaceVariant
                                        },
                                        modifier = Modifier.size(28.dp),
                                    )
                                    Text(
                                        stringResource(entry.titleRes),
                                        style = androidx.compose.material3.MaterialTheme.typography.labelMedium,
                                        color = if (selected) {
                                            androidx.compose.material3.MaterialTheme.colorScheme.onPrimaryContainer
                                        } else {
                                            androidx.compose.material3.MaterialTheme.colorScheme.onSurfaceVariant
                                        },
                                    )
                                }
                            }
                        }
                    }
                }
            }
        },
    ) { padding ->
        Box(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .consumeWindowInsets(padding),
        ) {
            if (editingTrack != null) {
                TagEditorPage(
                    library = library,
                    controller = controller,
                    track = editingTrack!!,
                    onBack = { editingTrack = null },
                )
            } else when (tab) {
                MainTab.Media -> LibraryPage(
                    library = library,
                    controller = controller,
                    onRequestStorageAccess = ::requestStorageAccess,
                    onOpenPlayer = { tab = MainTab.Player },
                    onEditTrack = { editingTrack = it },
                )
                MainTab.Player -> NowPlayingPage(
                    library = library,
                    controller = controller,
                    onOpenLibrary = { tab = MainTab.Media },
                )
                MainTab.Settings -> SettingsPage(library = library, controller = controller)
            }
        }
    }
}
