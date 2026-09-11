package com.imankoppai.mediaanvil.ui

import android.content.Context
import android.net.Uri
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
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import com.imankoppai.mediaanvil.tags.TagIO
import com.imankoppai.mediaanvil.tools.AudioConverter
import com.imankoppai.mediaanvil.tools.ImageConverter
import com.imankoppai.mediaanvil.tools.ImageTarget
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import kotlin.math.roundToInt

internal enum class ToolKind { LyricsConvert, AudioConvert, ImageConvert }

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
                            val sourceCache = DocumentOps.copyToCache(context, file.uri, file.name)
                            try {
                                val converted = AudioConverter.convert(context, android.net.Uri.fromFile(sourceCache), target)
                                try {
                                    TagIO.preserveTags(sourceCache, converted)
                                    DocumentOps.saveConvertedDocument(context, parent, file.name, target.extension, converted)
                                } finally {
                                    converted.delete()
                                }
                            } finally {
                                DocumentOps.deleteCache(sourceCache)
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
