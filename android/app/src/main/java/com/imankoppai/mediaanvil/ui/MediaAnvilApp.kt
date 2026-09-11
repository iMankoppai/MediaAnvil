package com.imankoppai.mediaanvil.ui

import android.content.ComponentName
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.PlayArrow
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import com.imankoppai.mediaanvil.R
import com.imankoppai.mediaanvil.playback.PlaybackService

@Composable
fun MediaAnvilApp() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val library = remember { LibraryState(context, scope) }
    var controller by remember { mutableStateOf<MediaController?>(null) }
    var tab by remember { mutableStateOf(0) }

    val folderPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        uri?.let { library.loadFolder(it) }
    }

    DisposableEffect(Unit) {
        val token = SessionToken(context, ComponentName(context, PlaybackService::class.java))
        val future = MediaController.Builder(context, token).buildAsync()
        future.addListener({
            runCatching { future.get() }.onSuccess { mediaController ->
                controller = mediaController
            }
        }, androidx.core.content.ContextCompat.getMainExecutor(context))
        onDispose { MediaController.releaseFuture(future) }
    }

    androidx.compose.runtime.LaunchedEffect(Unit) {
        library.rescan()
    }

    Scaffold(
        bottomBar = {
            NavigationBar {
                NavigationBarItem(
                    selected = tab == 0,
                    onClick = { tab = 0 },
                    icon = { Icon(Icons.Filled.PlayArrow, contentDescription = null) },
                    label = { Text(stringResource(R.string.tab_playback)) },
                )
                NavigationBarItem(
                    selected = tab == 1,
                    onClick = { tab = 1 },
                    icon = { Icon(Icons.Filled.Edit, contentDescription = null) },
                    label = { Text(stringResource(R.string.tab_tag_editor)) },
                )
            }
        },
    ) { padding ->
        androidx.compose.foundation.layout.Box(Modifier.padding(padding)) {
            when (tab) {
                0 -> PreviewPage(library, controller, onPickFolder = { folderPicker.launch(null) })
                else -> TagEditorPage(library)
            }
        }
    }
}
