package com.imankoppai.mediaanvil.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.media3.session.MediaController
import com.imankoppai.mediaanvil.R
import com.imankoppai.mediaanvil.data.DocumentOps
import com.imankoppai.mediaanvil.model.AudioTrack
import com.imankoppai.mediaanvil.tags.TagIO
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun TagEditorPage(
    library: LibraryState,
    controller: MediaController?,
    track: AudioTrack,
    onBack: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val writable = TagIO.isWritable(track.fileName)
    var title by remember(track.uri) { mutableStateOf(track.title) }
    var artist by remember(track.uri) { mutableStateOf(track.artist.orEmpty()) }
    var loading by remember(track.uri) { mutableStateOf(false) }
    var saving by remember(track.uri) { mutableStateOf(false) }
    var message by remember(track.uri) { mutableStateOf<String?>(null) }

    LaunchedEffect(track.uri, writable) {
        if (!writable) return@LaunchedEffect
        loading = true
        val result = withContext(Dispatchers.IO) {
            runCatching {
                val cache = DocumentOps.copyToCache(context, track.uri, track.fileName)
                try {
                    TagIO.read(cache)
                } finally {
                    DocumentOps.deleteCache(cache)
                }
            }
        }
        result.onSuccess {
            title = it.title.ifEmpty { track.title }
            artist = it.artist
        }.onFailure {
            message = context.getString(R.string.tag_read_failed)
        }
        loading = false
    }

    fun save() {
        if (!writable || saving) return
        saving = true
        message = null
        controller?.pause()
        scope.launch {
            var recoveryKept = false
            val result = withContext(Dispatchers.IO) {
                runCatching {
                    val original = DocumentOps.copyToCache(context, track.uri, track.fileName)
                    val edited = File(original.parentFile, "${original.nameWithoutExtension}-edited.${original.extension}")
                    try {
                        original.copyTo(edited, overwrite = true)
                        TagIO.write(edited, title, artist)
                        try {
                            DocumentOps.overwriteInPlace(context, track.uri, edited, original)
                        } catch (failure: Throwable) {
                            // Both the write and the automatic restore may have
                            // failed; keep the cached original as a recovery copy
                            // before the cache is cleaned up.
                            recoveryKept = true
                            throw failure
                        }
                    } finally {
                        if (recoveryKept) {
                            runCatching {
                                val recoveryDir = File(context.filesDir, "tag-edit-recovery").apply { mkdirs() }
                                original.copyTo(
                                    File(recoveryDir, "${System.currentTimeMillis()}-${track.fileName}"),
                                    overwrite = true,
                                )
                            }
                        }
                        DocumentOps.deleteCache(original)
                        DocumentOps.deleteCache(edited)
                    }
                }
            }
            saving = false
            result.fold(
                onSuccess = {
                    library.rescan(quiet = true)
                    message = context.getString(R.string.tag_saved)
                    onBack()
                },
                onFailure = { failure ->
                    message = context.getString(R.string.tag_save_failed) +
                        (failure.message?.let { ": $it" } ?: "") +
                        if (recoveryKept) context.getString(R.string.tag_recovery_kept) else ""
                },
            )
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.tag_editor_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = stringResource(R.string.back),
                        )
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .imePadding()
                .padding(padding)
                .padding(horizontal = 20.dp, vertical = 16.dp),
        ) {
            Text(
                track.fileName,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
            )
            Spacer(Modifier.height(16.dp))
            if (!writable) {
                Text(
                    stringResource(R.string.tag_unsupported_format),
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodyMedium,
                )
                Spacer(Modifier.height(12.dp))
            }
            OutlinedTextField(
                value = title,
                onValueChange = { title = it },
                enabled = writable && !loading && !saving,
                label = { Text(stringResource(R.string.tag_title)) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = artist,
                onValueChange = { artist = it },
                enabled = writable && !loading && !saving,
                label = { Text(stringResource(R.string.tag_artist)) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
            )
            Text(
                stringResource(R.string.tag_editor_hint),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 12.dp),
            )
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 20.dp),
                horizontalArrangement = Arrangement.End,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (loading || saving) {
                    CircularProgressIndicator(modifier = Modifier.padding(end = 16.dp).height(24.dp))
                }
                Button(onClick = ::save, enabled = writable && !loading && !saving) {
                    Text(stringResource(R.string.tag_save))
                }
            }
            message?.let {
                Text(
                    it,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(top = 12.dp),
                )
            }
        }
    }
}
