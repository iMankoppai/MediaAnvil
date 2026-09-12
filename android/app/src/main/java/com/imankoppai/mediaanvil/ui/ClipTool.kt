package com.imankoppai.mediaanvil.ui

import android.content.Context
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.systemGestureExclusion
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.transformer.Composition
import androidx.media3.transformer.ExportException
import androidx.media3.transformer.ExportResult
import androidx.media3.transformer.Transformer
import com.imankoppai.mediaanvil.R
import com.imankoppai.mediaanvil.data.DocumentOps
import com.imankoppai.mediaanvil.data.LibraryCache
import com.imankoppai.mediaanvil.data.ScannedFile
import com.imankoppai.mediaanvil.tags.TagIO
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.nio.ByteOrder
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlin.math.abs

/** Match a picked SAF document against scanned files, tolerating uri-encoding differences. */
internal fun resolveScannedFile(context: Context, files: List<ScannedFile>?, uri: Uri): ScannedFile? {
    files?.firstOrNull { it.uri == uri }?.let { return it }
    val pickedId = runCatching { android.provider.DocumentsContract.getDocumentId(uri) }.getOrNull()
    if (pickedId != null) {
        files?.firstOrNull { file ->
            runCatching { android.provider.DocumentsContract.getDocumentId(file.uri) }.getOrNull() == pickedId
        }?.let { return it }
    }
    // Some pickers (e.g. the Recents tab) hand back a uri whose document id does
    // not line up with the scanned tree document; fall back to the display name,
    // which is unique inside the granted folder. Downstream work uses the scanned
    // file's own tree uri, so rights are unaffected.
    val name = runCatching {
        context.contentResolver.query(uri, arrayOf(android.provider.OpenableColumns.DISPLAY_NAME), null, null, null)
            ?.use { cursor -> if (cursor.moveToFirst()) cursor.getString(0) else null }
    }.getOrNull() ?: return null
    return files?.firstOrNull { it.name == name }
}

/** Audio clipping tool: pick a range on the waveform, preview it, export as M4A. */
@Composable
internal fun ClipTool(library: LibraryState) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var picked by remember { mutableStateOf<ScannedFile?>(null) }
    var durationMs by remember { mutableLongStateOf(0L) }
    var peaks by remember { mutableStateOf<FloatArray?>(null) }
    var computing by remember { mutableStateOf(false) }
    var waveProgress by remember { mutableFloatStateOf(0f) }
    var startFraction by remember { mutableFloatStateOf(0f) }
    var endFraction by remember { mutableFloatStateOf(1f) }
    var running by remember { mutableStateOf(false) }
    var results by remember { mutableStateOf<List<String>>(emptyList()) }
    var lossless by remember { mutableStateOf(false) }
    var fadeInSec by remember { mutableFloatStateOf(0f) }
    var fadeOutSec by remember { mutableFloatStateOf(0f) }
    val isWav = picked?.name?.endsWith(".wav", ignoreCase = true) == true

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        val known = uri?.let { candidate -> resolveScannedFile(context, library.files?.files, candidate) }
        picked = known
        if (known == null) {
            // Stale selection state would disable every button with no visible
            // reason; fall back to an empty slate.
            durationMs = 0L
            peaks = null
            startFraction = 0f
            endFraction = 1f
            results = listOf(context.getString(R.string.outside_tree_hint))
        } else {
            results = emptyList()
        }
    }

    LaunchedEffect(picked) {
        val file = picked ?: return@LaunchedEffect
        peaks = null
        startFraction = 0f
        endFraction = 1f
        lossless = file.name.endsWith(".wav", ignoreCase = true)
        fadeInSec = 0f
        fadeOutSec = 0f
        durationMs = withContext(Dispatchers.IO) {
            runCatching {
                val retriever = android.media.MediaMetadataRetriever()
                retriever.setDataSource(context, file.uri)
                val ms = retriever.extractMetadata(android.media.MediaMetadataRetriever.METADATA_KEY_DURATION)
                    ?.toLongOrNull() ?: 0L
                retriever.release()
                ms
            }.getOrDefault(0L)
        }
        if (durationMs <= 0L) return@LaunchedEffect
        computing = true
        waveProgress = 0f
        peaks = computePeaks(context, file.uri, durationMs) { fraction -> waveProgress = fraction }
        computing = false
    }

    val startMs = (startFraction * durationMs).toLong()
    val endMs = (endFraction * durationMs).toLong()
    val valid = picked != null && durationMs > 0 && endMs - startMs >= 200

    val previewPlayer = remember { ExoPlayer.Builder(context).build() }
    var previewing by remember { mutableStateOf(false) }
    var playheadMs by remember { mutableLongStateOf(-1L) }
    DisposableEffect(Unit) {
        val listener = object : Player.Listener {
            override fun onPlaybackStateChanged(playbackState: Int) {
                if (playbackState == Player.STATE_ENDED || playbackState == Player.STATE_IDLE) {
                    previewing = false
                }
            }
        }
        previewPlayer.addListener(listener)
        onDispose {
            previewPlayer.removeListener(listener)
            previewPlayer.release()
        }
    }
    // The selection moved on: whatever is previewing no longer matches it.
    LaunchedEffect(picked, startMs, endMs) {
        if (previewing) {
            previewPlayer.stop()
            previewing = false
        }
    }
    LaunchedEffect(previewing) {
        while (previewing) {
            playheadMs = previewPlayer.currentPosition
            delay(80)
        }
        playheadMs = -1L
    }

    fun startPreview(fromMs: Long) {
        val file = picked ?: return
        previewPlayer.setMediaItem(
            MediaItem.Builder()
                .setUri(file.uri)
                .setClippingConfiguration(
                    MediaItem.ClippingConfiguration.Builder()
                        .setStartPositionMs(startMs)
                        .setEndPositionMs(endMs)
                        .build(),
                )
                .build(),
        )
        previewPlayer.prepare()
        if (fromMs > startMs) previewPlayer.seekTo(fromMs - startMs)
        previewPlayer.play()
        previewing = true
    }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp),
    ) {
        ToolHeaderNote(stringResource(R.string.clip_note))
        OutlinedButton(onClick = { picker.launch(arrayOf("audio/*")) }) { Text(stringResource(R.string.pick_files)) }
        picked?.let {
            Text(
                stringResource(R.string.picked_count, 1) + ": " + it.name,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(vertical = 4.dp),
            )
        }
        WaveformSelection(
            peaks = peaks,
            computing = computing,
            progress = waveProgress,
            startFraction = startFraction,
            endFraction = endFraction,
            playheadFraction = if (playheadMs >= 0 && durationMs > 0) (startMs + playheadMs) / durationMs.toFloat() else null,
            durationMs = durationMs,
            onChange = { start, end ->
                startFraction = start
                endFraction = end
            },
            onTap = { fraction ->
                if (previewing) {
                    val target = (fraction * durationMs).toLong().coerceIn(startMs, (endMs - 200).coerceAtLeast(startMs))
                    previewPlayer.seekTo(target - startMs)
                } else {
                    val minGap = 200f / durationMs.coerceAtLeast(1)
                    if (abs(fraction - startFraction) <= abs(fraction - endFraction)) {
                        startFraction = fraction.coerceAtMost(endFraction - minGap).coerceAtLeast(0f)
                    } else {
                        endFraction = fraction.coerceAtLeast(startFraction + minGap).coerceAtMost(1f)
                    }
                }
            },
            modifier = Modifier.padding(top = 8.dp),
        )
        if (computing) {
            Text(
                stringResource(R.string.clip_computing) + " " + (waveProgress * 100).toInt() + "%",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 6.dp),
            )
        } else {
            Text(
                stringResource(R.string.clip_waveform_hint),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 6.dp),
            )
        }
        if (picked != null && durationMs > 0) {
            Text(
                stringResource(R.string.clip_selection_label, formatTime(startMs), formatTime(endMs)),
                style = MaterialTheme.typography.bodySmall,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.padding(top = 8.dp),
            )
            val rangeValid = endMs - startMs >= 200
            Text(
                stringResource(R.string.clip_duration_label, formatTime((endMs - startMs).coerceAtLeast(0)), formatTime(durationMs)),
                style = MaterialTheme.typography.bodySmall,
                color = if (rangeValid) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(top = 4.dp),
            )
            if (!rangeValid) {
                Text(
                    stringResource(R.string.clip_invalid_range),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }
        }
        if (isWav) {
            Text(
                stringResource(R.string.clip_output),
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 8.dp),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(
                    selected = lossless,
                    onClick = { lossless = true },
                    label = { Text(stringResource(R.string.clip_lossless)) },
                )
                FilterChip(
                    selected = !lossless,
                    onClick = { lossless = false },
                    label = { Text("M4A") },
                )
            }
            if (lossless) {
                Text(
                    stringResource(R.string.clip_fade_in, formatFade(fadeInSec)),
                    style = MaterialTheme.typography.labelSmall,
                    modifier = Modifier.padding(top = 4.dp),
                )
                androidx.compose.material3.Slider(
                    value = fadeInSec,
                    onValueChange = { fadeInSec = (it * 2).toInt() / 2f },
                    valueRange = 0f..5f,
                    modifier = Modifier.fillMaxWidth(),
                )
                Text(stringResource(R.string.clip_fade_out, formatFade(fadeOutSec)), style = MaterialTheme.typography.labelSmall)
                androidx.compose.material3.Slider(
                    value = fadeOutSec,
                    onValueChange = { fadeOutSec = (it * 2).toInt() / 2f },
                    valueRange = 0f..5f,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(vertical = 8.dp)) {
            OutlinedButton(
                onClick = {
                    if (previewing) {
                        previewPlayer.stop()
                        previewing = false
                    } else {
                        startPreview(startMs)
                    }
                },
                enabled = valid && !running,
            ) { Text(stringResource(if (previewing) R.string.stop_preview else R.string.preview_clip)) }
            Button(
                onClick = {
                    val file = picked ?: return@Button
                    running = true
                    scope.launch {
                        results = if (lossless) {
                            withContext(Dispatchers.IO) {
                                runLossless(
                                    context, library, file, startMs, endMs,
                                    (fadeInSec * 1000).toLong(), (fadeOutSec * 1000).toLong(),
                                )
                            }
                        } else {
                            withContext(Dispatchers.IO) {
                                runClip(context, library, file, startMs, endMs)
                            }
                        }
                        running = false
                        library.rescan(quiet = true)
                    }
                },
                enabled = valid && !running,
            ) { Text(stringResource(R.string.start_clip)) }
        }
        if (running) {
            LinearProgressIndicator(Modifier.fillMaxWidth())
        }
        ResultLines(results)
    }
}

@Composable
private fun WaveformSelection(
    peaks: FloatArray?,
    computing: Boolean,
    progress: Float,
    startFraction: Float,
    endFraction: Float,
    playheadFraction: Float?,
    durationMs: Long,
    onChange: (Float, Float) -> Unit,
    onTap: (Float) -> Unit,
    modifier: Modifier = Modifier,
) {
    val minGap = if (durationMs > 0) 200f / durationMs else 0f
    // 'S' drag start handle, 'E' drag end handle, 'P' pan the whole selection.
    var mode by remember { mutableStateOf('S') }
    val inRangeColor = MaterialTheme.colorScheme.primary
    val dimmedColor = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.35f)
    val shadeColor = Color.Black.copy(alpha = 0.16f)
    val playheadColor = MaterialTheme.colorScheme.error

    Box(
        modifier
            .fillMaxWidth()
            .height(148.dp)
            // Selection handles reach both screen edges; without excluding the
            // gesture-navigator zones, edge drags would trigger system BACK.
            .systemGestureExclusion()
            .clip(RoundedCornerShape(14.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .pointerInput(durationMs, minGap) {
                if (durationMs <= 0L) return@pointerInput
                detectTapGestures { offset ->
                    onTap((offset.x / size.width).coerceIn(0f, 1f))
                }
            }
            .pointerInput(durationMs, minGap) {
                if (durationMs <= 0L) return@pointerInput
                detectDragGestures(
                    onDragStart = { offset ->
                        // NB: this offset arrives after the touch slop is crossed,
                        // so it can sit a few dozen pixels past the real touch down.
                        val x = (offset.x / size.width).coerceIn(0f, 1f)
                        val nearStart = abs(x - startFraction)
                        val nearEnd = abs(x - endFraction)
                        mode = when {
                            nearStart <= nearEnd && nearStart <= 0.12f -> 'S'
                            nearEnd < nearStart && nearEnd <= 0.12f -> 'E'
                            x > startFraction + 0.12f && x < endFraction - 0.12f -> 'P'
                            nearStart <= nearEnd -> 'S'
                            else -> 'E'
                        }
                    },
                    onDrag = { change, dragAmount ->
                        change.consume()
                        // Delta-driven: absolute positions include the touch-slop
                        // pre-travel and would make handles jump on grab.
                        val dx = dragAmount.x / size.width
                        when (mode) {
                            'S' -> onChange((startFraction + dx).coerceIn(0f, endFraction - minGap), endFraction)
                            'E' -> onChange(startFraction, (endFraction + dx).coerceIn(startFraction + minGap, 1f))
                            else -> {
                                val len = endFraction - startFraction
                                val start = (startFraction + dx).coerceIn(0f, 1f - len)
                                onChange(start, start + len)
                            }
                        }
                    },
                )
            },
    ) {
        Canvas(Modifier.fillMaxSize()) {
            val width = size.width
            val height = size.height
            val data = peaks
            if (data == null || data.isEmpty()) {
                // Placeholder bars so selection works before decode finishes.
                val barCount = 64
                val barWidth = width / barCount
                for (i in 0 until barCount) {
                    val h = height * 0.22f
                    drawRect(
                        dimmedColor,
                        topLeft = Offset(i * barWidth + barWidth * 0.2f, (height - h) / 2f),
                        size = Size(barWidth * 0.6f, h),
                    )
                }
            } else {
                val barWidth = width / data.size
                for (i in data.indices) {
                    val h = (data[i] * height * 0.9f).coerceAtLeast(2.dp.toPx())
                    val center = (i + 0.5f) / data.size
                    val color = if (center >= startFraction && center <= endFraction) inRangeColor else dimmedColor
                    drawRect(
                        color,
                        topLeft = Offset(i * barWidth + barWidth * 0.18f, (height - h) / 2f),
                        size = Size(barWidth * 0.64f, h),
                    )
                }
            }
            // Dim everything outside the selection.
            val startX = startFraction * width
            val endX = endFraction * width
            drawRect(shadeColor, topLeft = Offset(0f, 0f), size = Size(startX, height))
            drawRect(shadeColor, topLeft = Offset(endX, 0f), size = Size(width - endX, height))
            // Selection handles.
            val stroke = 2.5.dp.toPx()
            drawLine(inRangeColor, Offset(startX, 0f), Offset(startX, height), strokeWidth = stroke)
            drawLine(inRangeColor, Offset(endX, 0f), Offset(endX, height), strokeWidth = stroke)
            playheadFraction?.let { fraction ->
                val x = (fraction.coerceIn(0f, 1f)) * width
                drawLine(playheadColor, Offset(x, 0f), Offset(x, height), strokeWidth = stroke)
            }
        }
        if (computing) {
            LinearProgressIndicator(
                progress = { progress.coerceIn(0f, 1f) },
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

/**
 * Decode the audio into [buckets] normalized peak amplitudes (0..1) for the
 * waveform display. Returns null when the file has no decodable audio track.
 */
private suspend fun computePeaks(
    context: Context,
    uri: Uri,
    durationMs: Long,
    buckets: Int = 480,
    onProgress: (Float) -> Unit,
): FloatArray? = withContext(Dispatchers.Default) {
    runCatching {
        val extractor = MediaExtractor()
        extractor.setDataSource(context, uri, null)
        var trackIndex = -1
        var format: MediaFormat? = null
        for (i in 0 until extractor.trackCount) {
            val candidate = extractor.getTrackFormat(i)
            if (candidate.getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true) {
                trackIndex = i
                format = candidate
                break
            }
        }
        if (trackIndex < 0 || format == null) {
            extractor.release()
            return@withContext null
        }
        extractor.selectTrack(trackIndex)
        val mime = format.getString(MediaFormat.KEY_MIME)!!
        val codec = MediaCodec.createDecoderByType(mime)
        codec.configure(format, null, null, 0)
        codec.start()
        val peaks = FloatArray(buckets)
        var durationUs = if (format.containsKey(MediaFormat.KEY_DURATION)) format.getLong(MediaFormat.KEY_DURATION) else 0L
        if (durationUs <= 0L && durationMs > 0) durationUs = durationMs * 1000L
        var inputDone = false
        var outputDone = false
        val info = MediaCodec.BufferInfo()
        while (!outputDone) {
            if (!inputDone) {
                val index = codec.dequeueInputBuffer(10_000L)
                if (index >= 0) {
                    val buffer = codec.getInputBuffer(index)!!
                    val size = extractor.readSampleData(buffer, 0)
                    if (size < 0) {
                        codec.queueInputBuffer(index, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                        inputDone = true
                    } else {
                        codec.queueInputBuffer(index, 0, size, extractor.sampleTime, 0)
                        extractor.advance()
                        if (durationUs > 0) onProgress((extractor.sampleTime.toFloat() / durationUs).coerceIn(0f, 1f))
                    }
                }
            }
            val outIndex = codec.dequeueOutputBuffer(info, 10_000L)
            if (outIndex >= 0) {
                val buffer = codec.getOutputBuffer(outIndex)
                if (buffer != null && info.size > 0 && durationUs > 0) {
                    val samples = buffer.order(ByteOrder.LITTLE_ENDIAN).asShortBuffer()
                    val count = samples.remaining()
                    if (count > 0) {
                        var peak = 0
                        // Sampling every 16th frame is plenty for a display envelope.
                        var i = 0
                        while (i < count) {
                            val v = abs(samples.get(i).toInt())
                            if (v > peak) peak = v
                            i += 16
                        }
                        val fraction = (info.presentationTimeUs.toFloat() / durationUs).coerceIn(0f, 0.9999f)
                        val bucket = (fraction * buckets).toInt().coerceIn(0, buckets - 1)
                        val normalized = peak / 32767f
                        if (normalized > peaks[bucket]) peaks[bucket] = normalized
                    }
                }
                codec.releaseOutputBuffer(outIndex, false)
                if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) outputDone = true
            }
        }
        codec.stop()
        codec.release()
        extractor.release()
        // Fill silent gaps from neighbours, then normalize to the loudest peak.
        for (i in 1 until peaks.size) if (peaks[i] == 0f) peaks[i] = peaks[i - 1] * 0.9f
        val max = peaks.max()
        if (max > 0.05f) {
            for (i in peaks.indices) peaks[i] = (peaks[i] / max).coerceIn(0f, 1f)
        } else {
            for (i in peaks.indices) peaks[i] = 0.3f
        }
        onProgress(1f)
        peaks
    }.getOrNull()
}

@UnstableApi
private suspend fun runClip(
    context: Context,
    library: LibraryState,
    file: ScannedFile,
    startMs: Long,
    endMs: Long,
): List<String> {
    val parent = library.resolveFolderFor(context, file)
        ?: return listOf(context.getString(R.string.need_folder_grant))
    val sourceCache = DocumentOps.copyToCache(context, file.uri, file.name)
    val output = File(context.cacheDir, "clip-${System.nanoTime()}.m4a")
    try {
        val latch = CountDownLatch(1)
        var failure: ExportException? = null
        val clipped = MediaItem.Builder()
            .setUri(android.net.Uri.fromFile(sourceCache))
            .setClippingConfiguration(
                MediaItem.ClippingConfiguration.Builder()
                    .setStartPositionMs(startMs)
                    .setEndPositionMs(endMs)
                    .build(),
            )
            .build()
        withContext(Dispatchers.Main) {
            // Transformer must be created on a Looper thread; callbacks arrive there too.
            // Force AAC output: without it, PCM/WAV input is passed through to the
            // MP4 muxer, which cannot write raw PCM and fails the export.
            val transformer = Transformer.Builder(context)
                .setAudioMimeType(androidx.media3.common.MimeTypes.AUDIO_AAC)
                .addListener(object : Transformer.Listener {
                    override fun onCompleted(composition: Composition, exportResult: ExportResult) {
                        latch.countDown()
                    }

                    override fun onError(composition: Composition, exportResult: ExportResult, exportException: ExportException) {
                        failure = exportException
                        latch.countDown()
                    }
                })
                .build()
            transformer.start(clipped, output.path)
        }
        if (!latch.await(10, TimeUnit.MINUTES) || failure != null) {
            val detail = failure?.let { " — ${it.errorCode} ${it.message ?: ""}" }.orEmpty()
            android.util.Log.e("ClipTool", "export failed", failure)
            return listOf(context.getString(R.string.convert_failed) + ": " + file.name + detail)
        }
        runCatching { TagIO.preserveTags(sourceCache, output) }
        DocumentOps.saveConvertedDocument(context, parent, file.name, "m4a", output)
        output.delete()
        return listOf(context.getString(R.string.clip_done) + ": " + file.name)
    } catch (error: Exception) {
        output.delete()
        return listOf(context.getString(R.string.convert_failed) + ": " + file.name + " — " + error.message)
    } finally {
        DocumentOps.deleteCache(sourceCache)
    }
}

/** Lossless WAV trim: byte-slice the PCM between the marks with optional fades. */
private suspend fun runLossless(
    context: Context,
    library: LibraryState,
    file: ScannedFile,
    startMs: Long,
    endMs: Long,
    fadeInMs: Long,
    fadeOutMs: Long,
): List<String> {
    val parent = library.resolveFolderFor(context, file)
        ?: return listOf(context.getString(R.string.need_folder_grant))
    val output = File(context.cacheDir, "trim-${System.nanoTime()}.wav")
    return try {
        val format = com.imankoppai.mediaanvil.tools.WavTrimmer.parseFormat(context, file.uri)
        com.imankoppai.mediaanvil.tools.WavTrimmer.trim(
            context, file.uri, format, startMs, endMs, fadeInMs, fadeOutMs, output,
        )
        DocumentOps.saveConvertedDocument(context, parent, file.name, "wav", output)
        output.delete()
        listOf(context.getString(R.string.clip_done) + ": " + file.name)
    } catch (error: Exception) {
        output.delete()
        listOf(context.getString(R.string.clip_failed_lossless) + " — " + (error.message ?: ""))
    }
}

private fun formatFade(seconds: Float): String =
    if (seconds <= 0f) "0" else java.lang.String.format(java.util.Locale.US, "%.1f", seconds)
