package com.imankoppai.mediaanvil.ui

import android.content.Intent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AddPhotoAlternate
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.EditNote
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Sell
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.SyncAlt
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.imankoppai.mediaanvil.R
import com.imankoppai.mediaanvil.data.DocumentOps
import com.imankoppai.mediaanvil.model.AudioTrack
import com.imankoppai.mediaanvil.tags.TagIO
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private data class ToolAction(
    val icon: ImageVector,
    val titleRes: Int,
    val subtitleRes: Int,
    val available: Boolean,
)

private val toolActions = listOf(
    ToolAction(Icons.Filled.Sell, R.string.tool_edit_tags, R.string.tool_edit_tags_sub, true),
    ToolAction(Icons.Filled.SyncAlt, R.string.tool_convert, R.string.tool_convert_sub, false),
    ToolAction(Icons.Filled.Image, R.string.tool_export_cover, R.string.tool_export_cover_sub, true),
    ToolAction(Icons.Filled.AddPhotoAlternate, R.string.tool_replace_cover, R.string.tool_replace_cover_sub, true),
    ToolAction(Icons.Filled.EditNote, R.string.tool_edit_lyrics, R.string.tool_edit_lyrics_sub, true),
    ToolAction(Icons.Filled.Info, R.string.tool_file_info, R.string.tool_file_info_sub, true),
    ToolAction(Icons.Filled.Folder, R.string.tool_reveal, R.string.tool_reveal_sub, false),
    ToolAction(Icons.Filled.Share, R.string.share_export, R.string.tool_share_sub, true),
)

/**
 * Per-song action sheet, mirroring the desktop editor page's per-file
 * operations in a mobile idiom.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun ToolsSheet(
    library: LibraryState,
    track: AudioTrack,
    onDismiss: () -> Unit,
    onOpenEditor: (AudioTrack) -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var snapshot by remember(track.uri) { mutableStateOf<TagIO.TagSnapshot?>(null) }
    var loading by remember(track.uri) { mutableStateOf(true) }
    var message by remember { mutableStateOf<String?>(null) }
    var infoDialog by remember { mutableStateOf(false) }
    var pendingExport by remember { mutableStateOf<Pair<ByteArray, String>?>(null) }

    LaunchedEffect(track.uri) {
        loading = true
        snapshot = withContext(Dispatchers.IO) {
            runCatching {
                val cache = DocumentOps.copyToCache(context, track.uri, track.fileName)
                try {
                    TagIO.readSnapshot(cache)
                } finally {
                    DocumentOps.deleteCache(cache)
                }
            }.getOrNull()
        }
        loading = false
    }

    val exportCoverLauncher = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/octet-stream")) { uri ->
        val payload = pendingExport
        pendingExport = null
        if (uri != null && payload != null) {
            scope.launch {
                val result = withContext(Dispatchers.IO) {
                    runCatching {
                        context.contentResolver.openOutputStream(uri, "wt")?.use { output ->
                            output.write(payload.first)
                        } ?: error("open_output_failed")
                    }
                }
                message = result.fold(
                    onSuccess = { context.getString(R.string.export_done) },
                    onFailure = { context.getString(R.string.save_failed) + ": " + it.message },
                )
            }
        }
    }

    fun exportCover() {
        val data = snapshot?.coverData
        if (data == null) {
            message = context.getString(R.string.nothing_to_export)
            return
        }
        val mime = snapshot?.coverMime ?: TagIO.sniffImageMime(data)
        val stem = track.fileName.substringBeforeLast('.', track.fileName)
        pendingExport = data to mime
        exportCoverLauncher.launch(stem + if (mime == "image/jpeg") ".jpg" else ".png")
    }

    fun shareTrack() {
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "audio/*"
            putExtra(Intent.EXTRA_STREAM, track.uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        runCatching {
            context.startActivity(Intent.createChooser(intent, context.getString(R.string.share_export)))
        }.onFailure { message = context.getString(R.string.not_available) }
    }

    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp)
                .heightIn(max = 560.dp)
                .verticalScroll(rememberScrollState()),
        ) {
            Surface(
                shape = RoundedCornerShape(16.dp),
                color = MaterialTheme.colorScheme.surfaceVariant,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth().clickable {
                        onDismiss()
                        onOpenEditor(track)
                    }.padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    TrackCover(track, size = 52.dp)
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(
                            track.title,
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.SemiBold,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                        Text(
                            track.artist ?: stringResource(R.string.unknown_artist),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.secondary,
                        )
                        Text(
                            "${formatLabel(track)} · ${formatTime(track.durationMs)}",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }

            if (loading) {
                Row(Modifier.fillMaxWidth().padding(vertical = 16.dp), horizontalArrangement = androidx.compose.foundation.layout.Arrangement.Center) {
                    CircularProgressIndicator(Modifier.size(24.dp), strokeWidth = 2.dp)
                }
            }

            toolActions.forEach { tool ->
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable {
                            when (tool.titleRes) {
                                R.string.tool_edit_tags, R.string.tool_replace_cover, R.string.tool_edit_lyrics -> {
                                    onDismiss()
                                    onOpenEditor(track)
                                }
                                R.string.tool_export_cover -> exportCover()
                                R.string.tool_file_info -> if (snapshot != null) infoDialog = true else message = context.getString(R.string.not_available)
                                R.string.share_export -> shareTrack()
                                else -> message = context.getString(R.string.coming_soon)
                            }
                        }
                        .padding(horizontal = 6.dp, vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(
                        tool.icon,
                        contentDescription = null,
                        tint = if (tool.available) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.size(24.dp),
                    )
                    Spacer(Modifier.width(16.dp))
                    Column(Modifier.weight(1f)) {
                        Text(stringResource(tool.titleRes), style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Medium)
                        Text(
                            stringResource(tool.subtitleRes),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    if (!tool.available) {
                        Text(
                            stringResource(R.string.coming_soon_short),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    } else {
                        Icon(
                            Icons.Filled.KeyboardArrowRight,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }

            message?.let {
                Text(
                    it,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.padding(vertical = 8.dp),
                )
            }
            Spacer(Modifier.height(24.dp))
        }
    }

    snapshot?.let { current ->
        if (infoDialog) {
            AlertDialog(
                onDismissRequest = { infoDialog = false },
                confirmButton = {
                    TextButton(onClick = { infoDialog = false }) { Text(stringResource(R.string.crop_confirm)) }
                },
                title = { Text(stringResource(R.string.tool_file_info)) },
                text = {
                    Column {
                        Text(detailsLine(current), style = MaterialTheme.typography.bodySmall)
                        Spacer(Modifier.height(8.dp))
                        Text(
                            if (track.parentPath.isEmpty()) track.fileName else "${track.parentPath}/${track.fileName}",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                },
            )
        }
    }
}
