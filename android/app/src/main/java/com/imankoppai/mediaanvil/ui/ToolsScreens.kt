package com.imankoppai.mediaanvil.ui

import android.content.Context
import android.net.Uri
import android.provider.DocumentsContract
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.imankoppai.mediaanvil.R
import com.imankoppai.mediaanvil.data.DocumentOps
import com.imankoppai.mediaanvil.data.LibraryCache
import com.imankoppai.mediaanvil.data.ScannedFile
import com.imankoppai.mediaanvil.model.AudioTrack
import com.imankoppai.mediaanvil.subtitles.SubtitleFormats
import com.imankoppai.mediaanvil.subtitles.SubtitleLoader
import com.imankoppai.mediaanvil.tools.AudioConverter
import com.imankoppai.mediaanvil.tools.AudioRenamer
import com.imankoppai.mediaanvil.tools.ImageConverter
import com.imankoppai.mediaanvil.tools.ImageTarget
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import kotlin.math.roundToInt

internal enum class ToolKind { LyricsConvert, AudioConvert, ImageConvert, Rename }

@Composable
internal fun ToolScreenHost(library: LibraryState, onOpenEditor: (AudioTrack?) -> Unit) {
    var active by remember { mutableStateOf<ToolKind?>(null) }
    val onBack = { active = null }
    BackHandler(enabled = active != null, onBack = onBack)
    val activeTool = active
    if (activeTool == null) {
        ToolsHubPage(
            library = library,
            onOpenEditor = onOpenEditor,
            onOpenTool = { active = it },
        )
    } else {
        Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onBack) {
                    Icon(Icons.Filled.ArrowBack, contentDescription = stringResource(R.string.back))
                }
                Text(
                    stringResource(
                        when (activeTool) {
                            ToolKind.LyricsConvert -> R.string.tool_lyrics_convert
                            ToolKind.AudioConvert -> R.string.tool_audio_convert
                            ToolKind.ImageConvert -> R.string.tool_image_convert
                            ToolKind.Rename -> R.string.tool_rename
                        },
                    ),
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            Box(Modifier.fillMaxSize()) {
                when (activeTool) {
                    ToolKind.LyricsConvert -> LyricsConvertTool(library)
                    ToolKind.AudioConvert -> AudioConvertTool(library)
                    ToolKind.ImageConvert -> ImageConvertTool(library)
                    ToolKind.Rename -> RenameTool(library)
                }
            }
        }
    }
}

@Composable
private fun ToolHeaderNote(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(bottom = 8.dp),
    )
}

@Composable
private fun ResultLines(lines: List<String>) {
    if (lines.isEmpty()) return
    Column(
        Modifier
            .fillMaxWidth()
            .padding(top = 8.dp)
            .background(MaterialTheme.colorScheme.surface, RoundedCornerShape(12.dp))
            .padding(12.dp)
            .heightIn(max = 260.dp)
            .verticalScroll(rememberScrollState()),
    ) {
        lines.forEach { line ->
            Text(
                line,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(vertical = 2.dp),
            )
        }
    }
}

private fun utf8Bom(text: String): ByteArray =
    byteArrayOf(0xEF.toByte(), 0xBB.toByte(), 0xBF.toByte()) + text.toByteArray(Charsets.UTF_8)

private fun readAll(context: Context, uri: Uri): ByteArray? =
    context.contentResolver.openInputStream(uri)?.use { it.readBytes() }

@Composable
private fun FormatChips(options: List<String>, selected: String, onSelect: (String) -> Unit) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(vertical = 4.dp)) {
        options.forEach { option ->
            FilterChip(
                selected = selected == option,
                onClick = { onSelect(option) },
                label = { Text(option.uppercase()) },
            )
        }
    }
}

/** ---------- 歌词 / 字幕转换 ---------- */

@Composable
private fun LyricsConvertTool(library: LibraryState) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var target by remember { mutableStateOf("lrc") }
    var picked by remember { mutableStateOf<List<ScannedFile>>(emptyList()) }
    var running by remember { mutableStateOf(false) }
    var results by remember { mutableStateOf<List<String>>(emptyList()) }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        val known = uris.mapNotNull { uri -> library.files?.files?.firstOrNull { it.uri == uri } }
        picked = known
        if (known.size < uris.size) {
            results = listOf(context.getString(R.string.outside_tree_hint))
        } else {
            results = emptyList()
        }
    }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp)) {
        ToolHeaderNote(stringResource(R.string.lyrics_convert_hint))
        Text(stringResource(R.string.convert_target_label), style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
        FormatChips(listOf("lrc", "srt", "vtt"), target) { target = it }
        OutlinedButton(onClick = {
            picker.launch(arrayOf("text/plain", "application/octet-stream"))
        }) { Text(stringResource(R.string.pick_files)) }
        if (picked.isNotEmpty()) {
            Text(
                stringResource(R.string.picked_count, picked.size),
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(vertical = 4.dp),
            )
        }
        Button(
            onClick = {
                running = true
                scope.launch {
                    results = withContext(Dispatchers.IO) { runSubtitleConvert(context, library, picked, target) }
                    running = false
                    library.rescan(quiet = true)
                }
            },
            enabled = picked.isNotEmpty() && !running,
            modifier = Modifier.padding(vertical = 8.dp),
        ) { Text(stringResource(R.string.start_convert)) }
        if (running) LinearProgressIndicator(Modifier.fillMaxWidth())
        ResultLines(results)
    }
}

private fun runSubtitleConvert(
    context: Context,
    library: LibraryState,
    picked: List<ScannedFile>,
    target: String,
): List<String> {
    val lines = mutableListOf<String>()
    for (file in picked) {
        val sourceExt = file.name.substringAfterLast('.', "").lowercase()
        val line = runCatching {
            if (sourceExt == target) error(context.getString(R.string.skip_same_format, file.name))
            val text = SubtitleLoader.decode(readAll(context, file.uri) ?: error("read_failed"))
            val sourceFormat = when {
                SubtitleFormats.looksLikeTimed(text) -> if (sourceExt == "vtt") "vtt" else "srt"
                SubtitleFormats.hasLrcTimestamp(text) -> "lrc"
                else -> error(context.getString(R.string.invalid_lyrics))
            }
            val converted = SubtitleFormats.convertSubtitle(
                            text,
                            sourceFormat,
                            target,
                            library.preferences.lrcTailSeconds * 1000L,
                        )
            val parent = LibraryCache.resolveFolder(context, library.preferences.lastFolder, file.parentPath)
                ?: error(context.getString(R.string.need_folder_grant))
            val tmp = File.createTempFile("sub", ".tmp", context.cacheDir)
            tmp.writeBytes(utf8Bom(converted))
            try {
                DocumentOps.saveConvertedDocument(context, parent, file.name, target, tmp)
            } finally {
                tmp.delete()
            }
        }.fold(
            onSuccess = { context.getString(R.string.convert_done) + ": " + file.name },
            onFailure = { context.getString(R.string.convert_failed) + ": " + file.name + " — " + it.message },
        )
        lines += line
    }
    return lines
}

/** ---------- 音频格式转换 ---------- */

@Composable
private fun AudioConvertTool(library: LibraryState) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var targetExt by remember { mutableStateOf(library.preferences.audioConvertTarget) }
    var picked by remember { mutableStateOf<List<ScannedFile>>(emptyList()) }
    var running by remember { mutableStateOf(false) }
    var progress by remember { mutableStateOf("") }
    var results by remember { mutableStateOf<List<String>>(emptyList()) }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        val known = uris.mapNotNull { uri -> library.files?.files?.firstOrNull { it.uri == uri } }
        picked = known
        if (known.size < uris.size) results = listOf(context.getString(R.string.outside_tree_hint)) else results = emptyList()
    }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp)) {
        ToolHeaderNote(stringResource(R.string.audio_convert_note))
        Text(stringResource(R.string.convert_target_label), style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
        FormatChips(AudioConverter.targets.map { it.extension }, targetExt) {
            targetExt = it
            library.preferences.audioConvertTarget = it
        }
        OutlinedButton(onClick = { picker.launch(arrayOf("audio/*")) }) { Text(stringResource(R.string.pick_files)) }
        if (picked.isNotEmpty()) {
            Text(stringResource(R.string.picked_count, picked.size), style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(vertical = 4.dp))
        }
        Button(
            onClick = {
                running = true
                scope.launch {
                    val files = picked
                    val lines = mutableListOf<String>()
                    files.forEachIndexed { index, file ->
                        progress = "${index + 1}/${files.size}: ${file.name}"
                        val sourceExt = file.name.substringAfterLast('.', "").lowercase()
                        val line = runCatching {
                            if (sourceExt == targetExt) error(context.getString(R.string.skip_same_format, file.name))
                            val parent = LibraryCache.resolveFolder(context, library.preferences.lastFolder, file.parentPath)
                                ?: error(context.getString(R.string.need_folder_grant))
                            val target = AudioConverter.targetFor(targetExt) ?: error("unknown_target")
                            val converted = AudioConverter.convert(context, file.uri, target)
                            try {
                                DocumentOps.saveConvertedDocument(context, parent, file.name, target.extension, converted)
                            } finally {
                                converted.delete()
                            }
                        }.fold(
                            onSuccess = { context.getString(R.string.convert_done) + ": " + file.name },
                            onFailure = { context.getString(R.string.convert_failed) + ": " + file.name + " — " + it.message },
                        )
                        lines += line
                        results = lines.toList()
                    }
                    progress = ""
                    running = false
                    library.rescan(quiet = true)
                }
            },
            enabled = picked.isNotEmpty() && !running,
            modifier = Modifier.padding(vertical = 8.dp),
        ) { Text(stringResource(R.string.start_convert)) }
        if (running) {
            LinearProgressIndicator(Modifier.fillMaxWidth())
            progress.let { if (it.isNotEmpty()) Text(it, style = MaterialTheme.typography.labelSmall, modifier = Modifier.padding(top = 4.dp)) }
        }
        ResultLines(results)
    }
}

/** ---------- 图片格式转换 ---------- */

@Composable
private fun ImageConvertTool(library: LibraryState) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var target by remember { mutableStateOf(ImageTarget.entries.first { it.extension == library.preferences.imageConvertTarget }) }
    var quality by remember { mutableStateOf(library.preferences.imageQuality.toFloat()) }
    var picked by remember { mutableStateOf<List<ScannedFile>>(emptyList()) }
    var running by remember { mutableStateOf(false) }
    var results by remember { mutableStateOf<List<String>>(emptyList()) }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        val known = uris.mapNotNull { uri -> library.files?.files?.firstOrNull { it.uri == uri } }
        picked = known
        if (known.size < uris.size) results = listOf(context.getString(R.string.outside_tree_hint)) else results = emptyList()
    }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp)) {
        Text(stringResource(R.string.convert_target_label), style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
        FormatChips(ImageTarget.entries.map { it.extension }, target.extension) { selected ->
            target = ImageTarget.entries.first { it.extension == selected }
            library.preferences.imageConvertTarget = selected
        }
        if (target.lossy) {
            Text(
                stringResource(R.string.image_quality) + " — " + quality.roundToInt().toString(),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Slider(
                value = quality,
                onValueChange = {
                    quality = it
                    library.preferences.imageQuality = it.roundToInt()
                },
                valueRange = 1f..100f,
                modifier = Modifier.fillMaxWidth(),
            )
        }
        OutlinedButton(onClick = { picker.launch(arrayOf("image/*")) }) { Text(stringResource(R.string.pick_files)) }
        if (picked.isNotEmpty()) {
            Text(stringResource(R.string.picked_count, picked.size), style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(vertical = 4.dp))
        }
        Button(
            onClick = {
                running = true
                scope.launch {
                    results = withContext(Dispatchers.IO) { runImageConvert(context, library, picked, target, quality.roundToInt()) }
                    running = false
                    library.rescan(quiet = true)
                }
            },
            enabled = picked.isNotEmpty() && !running,
            modifier = Modifier.padding(vertical = 8.dp),
        ) { Text(stringResource(R.string.start_convert)) }
        if (running) LinearProgressIndicator(Modifier.fillMaxWidth())
        ResultLines(results)
    }
}

private fun runImageConvert(
    context: Context,
    library: LibraryState,
    picked: List<ScannedFile>,
    target: ImageTarget,
    quality: Int,
): List<String> {
    val lines = mutableListOf<String>()
    for (file in picked) {
        val sourceExt = file.name.substringAfterLast('.', "").lowercase()
        val line = runCatching {
            if (sourceExt == target.extension) error(context.getString(R.string.skip_same_format, file.name))
            val parent = LibraryCache.resolveFolder(context, library.preferences.lastFolder, file.parentPath)
                ?: error(context.getString(R.string.need_folder_grant))
            val converted = ImageConverter.convert(readAll(context, file.uri) ?: error("read_failed"), target, quality)
            val tmp = File.createTempFile("img", ".tmp", context.cacheDir)
            tmp.writeBytes(converted)
            try {
                DocumentOps.saveConvertedDocument(context, parent, file.name, target.extension, tmp)
            } finally {
                tmp.delete()
            }
        }.fold(
            onSuccess = { context.getString(R.string.convert_done) + ": " + file.name },
            onFailure = { context.getString(R.string.convert_failed) + ": " + file.name + " — " + it.message },
        )
        lines += line
    }
    return lines
}

/** ---------- 批量重命名 ---------- */

@Composable
private fun RenameTool(library: LibraryState) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var template by remember { mutableStateOf("{artist} - {title}") }
    var fallbackMissing by remember { mutableStateOf(true) }
    var folderPath by remember { mutableStateOf<String?>(null) }
    var folderMenuOpen by remember { mutableStateOf(false) }
    var preview by remember { mutableStateOf<List<AudioRenamer.PlanItem>?>(null) }
    var executing by remember { mutableStateOf(false) }
    var results by remember { mutableStateOf<List<String>>(emptyList()) }
    var undoRecords by remember { mutableStateOf<List<Triple<String, String, String>>>(emptyList()) }

    val folders = remember(library.tracks) { library.tracks.map { it.parentPath }.distinct().sorted() }
    LaunchedEffect(library.tracks) {
        if (folderPath == null) {
            folderPath = library.selectedTrack?.parentPath ?: folders.firstOrNull()
        }
    }

    val folderTracks = folderPath?.let { path -> library.tracks.filter { it.parentPath == path } }.orEmpty()
    val siblings = library.files?.files?.filter { it.parentPath == folderPath }.orEmpty()

    fun buildPreview() {
        val fields = folderTracks
            .filter { it.fileName.substringAfterLast('.', "").lowercase() in AudioRenamer.supportedExtensions }
            .map { track ->
                AudioRenamer.Fields(
                    originalName = track.fileName,
                    artist = track.artist.orEmpty(),
                    title = track.title,
                    album = track.album.orEmpty(),
                )
            }
        val existing = siblings.map { it.name.lowercase() }.toSet()
        runCatching { AudioRenamer.buildPlan(fields, template, fallbackMissing, existing) }.fold(
            onSuccess = { plan ->
                preview = plan
                results = emptyList()
            },
            onFailure = { failure ->
                preview = emptyList()
                results = listOf(context.getString(R.string.save_failed) + ": " + failure.message)
            },
        )
    }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp)) {
        Text(stringResource(R.string.rename_range), style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
        Box {
            OutlinedButton(onClick = { folderMenuOpen = true }, modifier = Modifier.fillMaxWidth()) {
                Text(
                    folderPath?.ifEmpty { stringResource(R.string.folder_root) } ?: stringResource(R.string.settings_no_folder),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            DropdownMenu(expanded = folderMenuOpen, onDismissRequest = { folderMenuOpen = false }) {
                folders.forEach { folder ->
                    DropdownMenuItem(
                        text = { Text(folder.ifEmpty { stringResource(R.string.folder_root) }, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                        onClick = {
                            folderMenuOpen = false
                            folderPath = folder
                            preview = null
                        },
                    )
                }
            }
        }

        Text(stringResource(R.string.rename_template), style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 12.dp))
        OutlinedTextField(
            value = template,
            onValueChange = { template = it },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.padding(vertical = 6.dp)) {
            listOf("{artist}", "{title}", "{album}", "{track}", "{year}").forEach { variable ->
                OutlinedButton(onClick = { template += variable }, contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 10.dp, vertical = 0.dp)) {
                    Text(variable, style = MaterialTheme.typography.labelSmall)
                }
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = fallbackMissing, onCheckedChange = { fallbackMissing = it })
            Text(stringResource(R.string.rename_fallback), style = MaterialTheme.typography.bodySmall)
        }
        ToolHeaderNote(stringResource(R.string.track_year_hint))

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = ::buildPreview, enabled = folderTracks.isNotEmpty()) { Text(stringResource(R.string.rename_preview)) }
            Button(
                onClick = {
                    val plan = preview ?: return@Button
                    executing = true
                    scope.launch {
                        val outcome = withContext(Dispatchers.IO) { executeRenames(context, library, folderPath.orEmpty(), plan) }
                        results = outcome.lines
                        undoRecords = outcome.records
                        executing = false
                        library.rescan(quiet = true)
                    }
                },
                enabled = preview?.any { it.canRename } == true && !executing,
            ) { Text(stringResource(R.string.rename_execute)) }
        }
        if (executing) LinearProgressIndicator(Modifier.fillMaxWidth().padding(vertical = 8.dp))

        preview?.let { plan ->
            val ready = plan.count { it.canRename }
            Text(
                stringResource(R.string.ready_count, ready),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(vertical = 6.dp),
            )
            plan.forEach { item ->
                Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(item.originalName, style = MaterialTheme.typography.bodySmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Text(
                            "→ " + item.newName,
                            style = MaterialTheme.typography.bodySmall,
                            fontWeight = FontWeight.SemiBold,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    Text(
                        statusLabel(item),
                        style = MaterialTheme.typography.labelSmall,
                        color = when (item.status) {
                            AudioRenamer.Status.READY, AudioRenamer.Status.READY_AVOIDED -> MaterialTheme.colorScheme.primary
                            AudioRenamer.Status.CONFLICT, AudioRenamer.Status.MISSING_TAGS -> MaterialTheme.colorScheme.error
                            AudioRenamer.Status.NO_CHANGE -> MaterialTheme.colorScheme.onSurfaceVariant
                        },
                    )
                }
            }
        }

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(vertical = 8.dp)) {
            OutlinedButton(
                onClick = {
                    if (undoRecords.isEmpty()) {
                        results = listOf(context.getString(R.string.undo_none))
                        return@OutlinedButton
                    }
                    executing = true
                    scope.launch {
                        val undone = withContext(Dispatchers.IO) { undoRenames(context, library, undoRecords) }
                        results = listOf(context.getString(R.string.undo_done, undone))
                        undoRecords = emptyList()
                        executing = false
                        library.rescan(quiet = true)
                    }
                },
                enabled = undoRecords.isNotEmpty() && !executing,
            ) { Text(stringResource(R.string.rename_undo)) }
        }
        if (executing) LinearProgressIndicator(Modifier.fillMaxWidth())
        ResultLines(results)
    }
}

@Composable
private fun statusLabel(item: AudioRenamer.PlanItem): String = when (item.status) {
    AudioRenamer.Status.READY -> stringResource(R.string.status_ready)
    AudioRenamer.Status.READY_AVOIDED -> stringResource(R.string.status_avoided)
    AudioRenamer.Status.NO_CHANGE -> stringResource(R.string.status_no_change)
    AudioRenamer.Status.MISSING_TAGS -> stringResource(R.string.status_missing_tags)
    AudioRenamer.Status.CONFLICT -> stringResource(R.string.status_conflict)
}

private fun executeRenames(
    context: Context,
    library: LibraryState,
    folderPath: String,
    plan: List<AudioRenamer.PlanItem>,
): RenameOutcome {
    val lines = mutableListOf<String>()
    val records = mutableListOf<Triple<String, String, String>>()
    var done = 0
    var failed = 0
    for (item in plan) {
        if (!item.canRename) continue
        val file = library.files?.files
            ?.firstOrNull { it.parentPath == folderPath && it.name == item.originalName }
        val result = runCatching {
            DocumentsContract.renameDocument(
                context.contentResolver,
                file?.uri ?: error("file_missing"),
                item.newName,
            ) ?: error("rename_failed")
        }
        result.fold(
            onSuccess = {
                records += Triple(folderPath, item.originalName, item.newName)
                done++
            },
            onFailure = {
                failed++
                lines += context.getString(R.string.convert_failed) + ": " + item.originalName + " — " + it.message
            },
        )
    }
    lines += context.getString(R.string.rename_done_summary, done, failed)
    return RenameOutcome(records, lines)
}

private data class RenameOutcome(val records: List<Triple<String, String, String>>, val lines: List<String>)

private fun undoRenames(
    context: Context,
    library: LibraryState,
    records: List<Triple<String, String, String>>,
): Int {
    var undone = 0
    for ((parentPath, oldName, newName) in records.reversed()) {
        val run = runCatching {
            val parent = LibraryCache.resolveFolder(context, library.preferences.lastFolder, parentPath)
                ?: error("no_parent")
            val current = parent.findFile(newName) ?: error("missing_new")
            DocumentsContract.renameDocument(context.contentResolver, current.uri, oldName)
            undone++
        }
        run.getOrNull()
    }
    return undone
}
