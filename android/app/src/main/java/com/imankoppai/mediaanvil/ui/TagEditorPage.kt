package com.imankoppai.mediaanvil.ui

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.AudioFile
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.imankoppai.mediaanvil.R
import com.imankoppai.mediaanvil.data.DocumentOps
import com.imankoppai.mediaanvil.data.LibraryCache
import com.imankoppai.mediaanvil.data.MediaMatcher
import com.imankoppai.mediaanvil.data.ScannedFile
import com.imankoppai.mediaanvil.model.AudioTrack
import com.imankoppai.mediaanvil.subtitles.SubtitleFormats
import com.imankoppai.mediaanvil.subtitles.SubtitleLoader
import com.imankoppai.mediaanvil.tags.TagIO
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream

@OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
@Composable
internal fun TagEditorScreen(library: LibraryState, track: AudioTrack?, onBack: () -> Unit) {
    val context = LocalContext.current
    var current by remember { mutableStateOf<AudioTrack?>(track) }
    val audioPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        uri?.let { picked ->
            val name = DocumentOps.queryDisplayName(context, picked)
                ?: picked.lastPathSegment?.substringAfterLast('/')
                ?: context.getString(R.string.select_audio_file)
            current = AudioTrack(
                uri = picked,
                fileName = name,
                title = name.substringBeforeLast('.', name),
                artist = null,
                album = null,
                durationMs = 0,
                subtitleUri = null,
                subtitleExtension = null,
                parent = null,
                parentPath = "",
            )
        }
    }
    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.tab_tag_editor), fontWeight = FontWeight.SemiBold) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.Filled.ArrowBack,
                            contentDescription = stringResource(R.string.back),
                        )
                    }
                },
                actions = {
                    IconButton(onClick = { audioPicker.launch(arrayOf("audio/*")) }) {
                        Icon(
                            Icons.Filled.AudioFile,
                            contentDescription = stringResource(R.string.select_audio_file),
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background,
                ),
            )
        },
    ) { padding ->
        val active = current
        Box(Modifier.padding(padding)) {
            if (active == null) {
                Column(
                    Modifier.fillMaxSize().padding(32.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = androidx.compose.foundation.layout.Arrangement.Center,
                ) {
                    Icon(
                        Icons.Filled.AudioFile,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(64.dp),
                    )
                    Spacer(Modifier.height(12.dp))
                    Text(
                        stringResource(R.string.editor_empty_hint),
                        style = MaterialTheme.typography.bodyMedium,
                        textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                    )
                    Spacer(Modifier.height(16.dp))
                    Button(onClick = { audioPicker.launch(arrayOf("audio/*")) }) {
                        Text(stringResource(R.string.select_audio_file))
                    }
                }
            } else {
                TagEditorPage(library, active)
            }
        }
    }
}

@Composable
internal fun TagEditorPage(library: LibraryState, track: AudioTrack) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var snapshot by remember { mutableStateOf<TagIO.TagSnapshot?>(null) }
    var title by remember { mutableStateOf("") }
    var artist by remember { mutableStateOf("") }
    var album by remember { mutableStateOf("") }
    var pendingLyrics by remember { mutableStateOf<String?>(null) }
    var removeLyrics by remember { mutableStateOf(false) }
    var pendingCover by remember { mutableStateOf<ByteArray?>(null) }
    var removeCover by remember { mutableStateOf(false) }
    var overwrite by remember(track.uri) { mutableStateOf(library.preferences.defaultOverwrite) }
    var cropSource by remember { mutableStateOf<ByteArray?>(null) }
    var working by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }
    var matcherExpanded by remember { mutableStateOf(false) }
    var batchSummary by remember { mutableStateOf<String?>(null) }

    fun setCoverFromBytes(bytes: ByteArray, alreadyNormalized: Boolean) {
        pendingCover = if (alreadyNormalized) bytes else normalizeToPng(bytes)
        removeCover = false
    }

    fun importLyricsFrom(bytes: ByteArray): Boolean {
        val text = SubtitleLoader.decode(bytes)
        val converted = if (SubtitleFormats.looksLikeTimed(text)) {
            runCatching { SubtitleFormats.timedTextToLrc(text) }.getOrElse { return false }
        } else {
            text
        }
        return runCatching { SubtitleFormats.validateEmbeddableLyrics(converted) }.fold(
            onSuccess = {
                pendingLyrics = converted
                removeLyrics = false
                true
            },
            onFailure = { false },
        )
    }

    LaunchedEffect(track.uri) {
        if (track.fileName.substringAfterLast('.', "").lowercase() == "opus") {
            snapshot = null
            message = context.getString(R.string.opus_unsupported)
            return@LaunchedEffect
        }
        working = true
        message = null
        val result = withContext(Dispatchers.IO) {
            runCatching {
                val cache = DocumentOps.copyToCache(context, track.uri, track.fileName)
                try {
                    TagIO.readSnapshot(cache)
                } finally {
                    DocumentOps.deleteCache(cache)
                }
            }
        }
        working = false
        result.onSuccess { loaded ->
            snapshot = loaded
            title = loaded.title
            artist = loaded.artist
            album = loaded.album
            pendingLyrics = null
            pendingCover = null
            removeLyrics = false
            removeCover = false
            batchSummary = null
        }.onFailure { failure ->
            snapshot = null
            message = failure.message ?: context.getString(R.string.save_failed)
        }
    }

    val lyricMatcher = remember(track.uri, library.files) {
        MediaMatcher.bestCandidates(
            track.fileName,
            siblingFiles(library, track),
            MediaMatcher.lyricExtensions,
        )
    }
    val coverMatcher = remember(track.uri, library.files) {
        MediaMatcher.bestCandidates(
            track.fileName,
            siblingFiles(library, track),
            MediaMatcher.coverExtensions,
        )
    }

    fun resolve(ref: MediaMatcher.FileRef): ScannedFile? =
        library.files?.files?.firstOrNull { it.name == ref.name && it.parentPath == ref.parent }

    fun readBytes(file: ScannedFile): ByteArray? =
        context.contentResolver.openInputStream(file.uri)?.use { it.readBytes() }

    val importLyricsLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) {
            val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
            if (bytes == null || !importLyricsFrom(bytes)) {
                message = context.getString(R.string.invalid_lyrics)
            }
        }
    }

    val importCoverLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) {
            val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
            if (bytes != null && BitmapFactory.decodeByteArray(bytes, 0, bytes.size) != null) {
                cropSource = bytes
            } else {
                message = context.getString(R.string.invalid_image)
            }
        }
    }

    var pendingExport by remember { mutableStateOf<Pair<ByteArray, String>?>(null) }
    val exportLauncher = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/octet-stream")) { uri ->
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
                result.onSuccess { message = context.getString(R.string.export_done) }
                    .onFailure { failure -> message = context.getString(R.string.save_failed) + ": " + failure.message }
            }
        }
    }

    fun exportLyrics() {
        val text = pendingLyrics ?: snapshot?.lyrics
        if (text.isNullOrBlank()) {
            message = context.getString(R.string.nothing_to_export)
            return
        }
        val stem = track.fileName.substringBeforeLast('.', track.fileName)
        val extension = if (SubtitleFormats.hasLrcTimestamp(text)) ".lrc" else ".txt"
        val bytes = byteArrayOf(0xEF.toByte(), 0xBB.toByte(), 0xBF.toByte()) + text.toByteArray(Charsets.UTF_8)
        pendingExport = bytes to "text/plain"
        exportLauncher.launch(stem + extension)
    }

    fun exportCover() {
        val data = pendingCover ?: snapshot?.coverData
        if (data == null) {
            message = context.getString(R.string.nothing_to_export)
            return
        }
        val mime = snapshot?.coverMime ?: TagIO.sniffImageMime(data)
        val extension = if (mime == "image/jpeg") ".jpg" else ".png"
        val stem = track.fileName.substringBeforeLast('.', track.fileName)
        pendingExport = data to mime
        exportLauncher.launch(stem + extension)
    }

    /** Save-as target handed off to the system save dialog for out-of-tree files. */
    var pendingSaveFile by remember { mutableStateOf<File?>(null) }
    val saveAsLauncher = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/octet-stream")) { uri ->
        val file = pendingSaveFile
        pendingSaveFile = null
        if (uri != null && file != null) {
            scope.launch {
                val result = withContext(Dispatchers.IO) {
                    runCatching {
                        context.contentResolver.openOutputStream(uri, "wt")?.use { output ->
                            file.inputStream().use { input -> input.copyTo(output) }
                        } ?: error("open_output_failed")
                    }
                }
                file.delete()
                result.fold(
                    onSuccess = { message = context.getString(R.string.saved_to) + ": " + lastSegment(uri.toString()) },
                    onFailure = { failure -> message = context.getString(R.string.save_failed) + ": " + failure.message },
                )
            }
        } else {
            file?.delete()
        }
    }

    fun saveEdits(track: AudioTrack) {
        val current = snapshot ?: return
        if (!current.writable) {
            message = context.getString(R.string.read_only_hint)
            return
        }
        working = true
        message = null
        scope.launch {
            val result = withContext(Dispatchers.IO) {
                runCatching {
                    val cache = DocumentOps.copyToCache(context, track.uri, track.fileName)
                    var handoff: File? = null
                    try {
                        val changes = TagIO.TagChanges(
                            title = title,
                            artist = artist,
                            album = album,
                            lyricsLrc = pendingLyrics,
                            removeLyrics = removeLyrics,
                            coverData = pendingCover,
                            coverMime = pendingCover?.let { "image/png" },
                            removeCover = removeCover,
                        )
                        TagIO.writeChanges(cache, changes)
                        val parent = track.parent
                            ?: LibraryCache.resolveFolder(context, library.preferences.lastFolder, track.parentPath)
                        when {
                            parent != null && overwrite ->
                                DocumentOps.overwriteDocument(context, parent, track.fileName, cache)
                            parent != null ->
                                DocumentOps.saveAsDocument(context, parent, track.fileName, cache)
                            overwrite ->
                                DocumentOps.overwriteInPlace(context, track.uri, cache)
                            else -> {
                                handoff = File(context.cacheDir, "saveas-${System.nanoTime()}.${track.fileName.substringAfterLast('.', "bin")}")
                                cache.copyTo(handoff!!, overwrite = true)
                            }
                        }
                    } finally {
                        if (handoff == null) DocumentOps.deleteCache(cache)
                    }
                    handoff
                }
            }
            working = false
            result.fold(
                onSuccess = { handoff ->
                    if (handoff != null) {
                        pendingSaveFile = handoff
                        saveAsLauncher.launch(track.fileName)
                        message = context.getString(R.string.save_pick_location)
                    } else {
                        message = context.getString(R.string.saved_to) + ": " + track.fileName
                        if (track.parent != null) library.rescan()
                    }
                },
                onFailure = { failure ->
                    message = context.getString(R.string.save_failed) + ": " + (failure.message ?: failure.toString())
                },
            )
        }
    }

    fun applyMatches(lyricRef: MediaMatcher.FileRef?, coverRef: MediaMatcher.FileRef?) {
        lyricRef?.let { ref ->
            resolve(ref)?.let { file ->
                val bytes = readBytes(file)
                if (bytes == null || !importLyricsFrom(bytes)) {
                    message = context.getString(R.string.invalid_lyrics)
                }
            }
        }
        coverRef?.let { ref ->
            resolve(ref)?.let { file ->
                readBytes(file)?.let { setCoverFromBytes(it, alreadyNormalized = false) }
            }
        }
    }

    fun batchWrite(writeLyrics: Boolean, writeCovers: Boolean) {
        val siblings = library.tracks.filter { it.parentPath == track.parentPath }
        if (siblings.isEmpty()) return
        working = true
        batchSummary = null
        scope.launch {
            val summary = withContext(Dispatchers.IO) {
                var written = 0
                var skipped = 0
                var failed = 0
                for (item in siblings) {
                    if (!TagIO.isWritable(item.fileName)) {
                        skipped++
                        continue
                    }
                    val lyric = if (writeLyrics) {
                        MediaMatcher.bestCandidates(item.fileName, siblingFiles(library, item), MediaMatcher.lyricExtensions).single
                    } else {
                        null
                    }
                    val cover = if (writeCovers) {
                        MediaMatcher.bestCandidates(item.fileName, siblingFiles(library, item), MediaMatcher.coverExtensions).single
                    } else {
                        null
                    }
                    if (lyric == null && cover == null) {
                        skipped++
                        continue
                    }
                    val outcome = runCatching {
                        val cache = DocumentOps.copyToCache(context, item.uri, item.fileName)
                        try {
                            var changes = TagIO.TagChanges()
                            if (lyric != null) {
                                val bytes = resolve(lyric)?.let(::readBytes)
                                if (bytes == null) error("lyrics_unreadable")
                                val text = SubtitleLoader.decode(bytes)
                                val converted = if (SubtitleFormats.looksLikeTimed(text)) {
                                    SubtitleFormats.timedTextToLrc(text)
                                } else {
                                    text
                                }
                                SubtitleFormats.validateEmbeddableLyrics(converted)
                                changes = changes.copy(lyricsLrc = converted)
                            }
                            if (cover != null) {
                                val bytes = resolve(cover)?.let(::readBytes)
                                if (bytes == null) error("cover_unreadable")
                                changes = changes.copy(coverData = normalizeToPng(bytes), coverMime = "image/png")
                            }
                            TagIO.writeChanges(cache, changes)
                            val parent = item.parent
                                ?: LibraryCache.resolveFolder(context, library.preferences.lastFolder, item.parentPath)
                                ?: error(context.getString(R.string.need_folder_grant))
                            DocumentOps.saveAsDocument(context, parent, item.fileName, cache)
                        } finally {
                            DocumentOps.deleteCache(cache)
                        }
                    }
                    if (outcome.isSuccess) written++ else failed++
                }
                context.getString(R.string.batch_done, written, skipped, failed)
            }
            working = false
            batchSummary = summary
            library.rescan()
        }
    }

    cropSource?.let { bytes ->
        CropDialog(
            imageBytes = bytes,
            onConfirm = { png ->
                setCoverFromBytes(png, alreadyNormalized = true)
                cropSource = null
            },
            onDismiss = { cropSource = null },
        )
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp),
    ) {
        Text(
            track.fileName,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(vertical = 8.dp),
        )

        snapshot?.let { current ->
            Spacer(Modifier.height(8.dp))
            Text(
                detailsLine(current),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.secondary,
            )
            if (!current.writable) {
                Text(
                    stringResource(R.string.read_only_hint),
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                )
            }

            Text(
                stringResource(R.string.basic_info),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.padding(top = 12.dp, bottom = 4.dp),
            )
            OutlinedTextField(
                value = title,
                onValueChange = { title = it },
                label = { Text(stringResource(R.string.title_label)) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = artist,
                onValueChange = { artist = it },
                label = { Text(stringResource(R.string.artist_label)) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            )
            OutlinedTextField(
                value = album,
                onValueChange = { album = it },
                label = { Text(stringResource(R.string.album_label)) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp, bottom = 4.dp),
            )

            Card(Modifier.fillMaxWidth().padding(top = 8.dp)) {
                Column(Modifier.padding(12.dp)) {
                    Text(
                        stringResource(R.string.lyrics_section),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        pendingLyrics ?: current.lyrics.ifEmpty { stringResource(R.string.no_lyrics) },
                        style = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace),
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 96.dp, max = 220.dp)
                            .verticalScroll(rememberScrollState())
                            .padding(vertical = 8.dp),
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(onClick = {
                            importLyricsLauncher.launch(arrayOf("text/plain", "application/octet-stream"))
                        }) { Text(stringResource(R.string.import_lyrics), maxLines = 1) }
                        OutlinedButton(onClick = ::exportLyrics) { Text(stringResource(R.string.export_lyrics), maxLines = 1) }
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = removeLyrics, onCheckedChange = { checked ->
                            removeLyrics = checked
                            if (checked) pendingLyrics = null
                        })
                        Text(stringResource(R.string.remove_lyrics))
                    }
                }
            }

            Card(Modifier.fillMaxWidth().padding(top = 8.dp)) {
                Column(Modifier.padding(12.dp)) {
                    Text(
                        stringResource(R.string.cover_section),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    val coverBytes = pendingCover ?: current.coverData
                    if (coverBytes == null) {
                        Box(
                            Modifier.fillMaxWidth().height(140.dp).background(MaterialTheme.colorScheme.surfaceVariant),
                            contentAlignment = Alignment.Center,
                        ) { Text(stringResource(R.string.no_cover)) }
                    } else {
                        val decoded = remember(coverBytes) {
                            BitmapFactory.decodeByteArray(coverBytes, 0, coverBytes.size)
                        }
                        decoded?.asImageBitmap()?.let { image ->
                            Image(
                                bitmap = image,
                                contentDescription = stringResource(R.string.cover_section),
                                contentScale = ContentScale.Fit,
                                modifier = Modifier.fillMaxWidth().height(180.dp).padding(vertical = 4.dp),
                            )
                        }
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(onClick = {
                            importCoverLauncher.launch(arrayOf("image/png", "image/jpeg", "image/webp", "image/bmp"))
                        }) { Text(stringResource(R.string.import_cover), maxLines = 1) }
                        OutlinedButton(onClick = ::exportCover) { Text(stringResource(R.string.export_cover), maxLines = 1) }
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = removeCover, onCheckedChange = { checked ->
                            removeCover = checked
                            if (checked) pendingCover = null
                        })
                        Text(stringResource(R.string.remove_cover))
                    }
                }
            }

            Card(Modifier.fillMaxWidth().padding(top = 8.dp, bottom = 8.dp)) {
                Column(Modifier.padding(12.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            stringResource(R.string.smart_matching),
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                            modifier = Modifier.weight(1f),
                        )
                        TextButton(onClick = { matcherExpanded = !matcherExpanded }) {
                            Text(if (matcherExpanded) "−" else "+")
                        }
                    }
                    if (matcherExpanded) {
                        Text(
                            stringResource(R.string.ambiguous_hint),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.secondary,
                        )
                        val lyricOptions = lyricMatcher?.files.orEmpty()
                        val coverOptions = coverMatcher?.files.orEmpty()
                        var chosenLyric by remember(track.uri) {
                            mutableStateOf(if (lyricMatcher?.ambiguous == false) lyricMatcher.single else null)
                        }
                        var chosenCover by remember(track.uri) {
                            mutableStateOf(if (coverMatcher?.ambiguous == false) coverMatcher.single else null)
                        }
                        CandidateRow(
                            label = stringResource(R.string.lyric_candidates),
                            options = lyricOptions,
                            chosen = chosenLyric,
                            onChoose = { chosenLyric = it },
                        )
                        CandidateRow(
                            label = stringResource(R.string.cover_candidates),
                            options = coverOptions,
                            chosen = chosenCover,
                            onChoose = { chosenCover = it },
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                            OutlinedButton(onClick = { applyMatches(chosenLyric, chosenCover) }) {
                                Text(stringResource(R.string.apply_matches))
                            }
                        }
                        HorizontalDivider(Modifier.padding(vertical = 8.dp))
                        Text(
                            stringResource(R.string.batch_hint),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.secondary,
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 4.dp)) {
                            OutlinedButton(onClick = { batchWrite(writeLyrics = true, writeCovers = false) }) {
                                Text(stringResource(R.string.batch_write_lyrics), maxLines = 1)
                            }
                            OutlinedButton(onClick = { batchWrite(writeLyrics = false, writeCovers = true) }) {
                                Text(stringResource(R.string.batch_write_cover), maxLines = 1)
                            }
                        }
                        batchSummary?.let {
                            Text(it, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 4.dp))
                        }
                    }
                }
            }

            Text(
                stringResource(R.string.save_mode_label),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 4.dp)) {
                FilterChip(
                    selected = !overwrite,
                    onClick = { overwrite = false },
                    label = { Text(stringResource(R.string.save_as)) },
                )
                FilterChip(
                    selected = overwrite,
                    onClick = { overwrite = true },
                    label = { Text(stringResource(R.string.overwrite_original)) },
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(vertical = 12.dp)) {
                OutlinedButton(onClick = {
                    title = current.title
                    artist = current.artist
                    album = current.album
                    pendingLyrics = null
                    pendingCover = null
                    removeLyrics = false
                    removeCover = false
                }) { Text(stringResource(R.string.reset_edits)) }
                Button(
                    onClick = { saveEdits(track) },
                    enabled = current.writable && !working,
                ) { Text(stringResource(R.string.save_tags)) }
            }
        } ?: Text(
            stringResource(R.string.editor_empty_hint),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.secondary,
            modifier = Modifier.padding(vertical = 16.dp),
        )

        if (working) LinearProgressIndicator(Modifier.fillMaxWidth().padding(vertical = 8.dp))
        if (message != null) {
            Text(
                message.orEmpty(),
                color = MaterialTheme.colorScheme.primary,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(bottom = 16.dp),
            )
        } else {
            Spacer(Modifier.height(16.dp))
        }
    }
}

@Composable
private fun CandidateRow(
    label: String,
    options: List<MediaMatcher.FileRef>,
    chosen: MediaMatcher.FileRef?,
    onChoose: (MediaMatcher.FileRef?) -> Unit,
) {
    var open by remember { mutableStateOf(false) }
    Row(
        modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(label, style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(0.35f))
        Box(Modifier.weight(0.65f)) {
            Text(
                chosen?.name ?: stringResource(R.string.no_candidates),
                style = MaterialTheme.typography.bodySmall,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { if (options.isNotEmpty()) open = true }
                    .padding(vertical = 8.dp),
            )
            DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
                DropdownMenuItem(text = { Text(stringResource(R.string.no_candidates)) }, onClick = {
                    onChoose(null)
                    open = false
                })
                options.forEach { option ->
                    DropdownMenuItem(
                        text = { Text(option.name, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                        onClick = {
                            onChoose(option)
                            open = false
                        },
                    )
                }
            }
        }
    }
}

private fun siblingFiles(library: LibraryState, track: AudioTrack): List<MediaMatcher.FileRef> =
    library.files?.files
        ?.filter { it.parentPath == track.parentPath }
        ?.map { MediaMatcher.FileRef(it.name, it.parentPath) }
        .orEmpty()

private fun lastSegment(value: String): String = value.substringAfterLast('/').ifEmpty { value }

internal fun detailsLine(snapshot: TagIO.TagSnapshot): String {
    val info = snapshot.info
    return buildString {
        append(info.formatLabel)
        append(" · ").append("%.1f".format(info.durationSeconds)).append(" s")
        append(" · ").append(info.bitrateKbps).append(" kbps")
        append(" · ").append(info.sampleRateHz).append(" Hz")
        append(" · ").append(info.channels)
        append(" · ").append("%.2f".format(info.fileSizeBytes / 1024.0 / 1024.0)).append(" MB")
        append(" · ").append(info.tagCount)
    }
}

private fun normalizeToPng(bytes: ByteArray): ByteArray {
    val decoded = BitmapFactory.decodeByteArray(bytes, 0, bytes.size) ?: return bytes
    val output = ByteArrayOutputStream().use { stream ->
        decoded.compress(Bitmap.CompressFormat.PNG, 100, stream)
        stream.toByteArray()
    }
    decoded.recycle()
    return output
}
