package com.imankoppai.mediaanvil.ui

import android.annotation.SuppressLint
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.basicMarquee
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.animateScrollBy
import androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.PlaylistAdd
import androidx.compose.material.icons.automirrored.filled.QueueMusic
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Lyrics
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Repeat
import androidx.compose.material.icons.filled.RepeatOne
import androidx.compose.material.icons.filled.Replay
import androidx.compose.material.icons.filled.Shuffle
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.SkipPrevious
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.media3.common.Player
import androidx.media3.session.MediaController
import com.imankoppai.mediaanvil.R
import com.imankoppai.mediaanvil.model.AudioTrack
import com.imankoppai.mediaanvil.model.SubtitleCue
import com.imankoppai.mediaanvil.subtitles.PreviewLyrics
import com.imankoppai.mediaanvil.subtitles.LyricsFileStore
import com.imankoppai.mediaanvil.subtitles.OnlineLyricsCandidate
import com.imankoppai.mediaanvil.subtitles.OnlineLyricsClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun NowPlayingPage(
    library: LibraryState,
    controller: MediaController?,
    onOpenLibrary: () -> Unit,
) {
    val context = LocalContext.current
    val track = library.selectedTrack
    var isPlaying by remember { mutableStateOf(false) }
    var positionMs by remember { mutableLongStateOf(0L) }
    var durationMs by remember { mutableLongStateOf(0L) }
    // A/B loop points in ms, shared with the seek bar markers; -1 means unset.
    var loopA by remember { mutableLongStateOf(-1L) }
    var loopB by remember { mutableLongStateOf(-1L) }
    LaunchedEffect(controller?.currentMediaItemIndex) {
        loopA = -1L
        loopB = -1L
    }
    var speed by remember { mutableStateOf(library.preferences.playbackSpeed) }
    var queueOpen by remember { mutableStateOf(false) }
    var pendingCoverTrack by remember { mutableStateOf<android.net.Uri?>(null) }
    var customCoverUri by remember(track?.uri) {
        mutableStateOf(track?.uri?.let(library.preferences::customCoverFor))
    }
    val coverPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { imageUri ->
        if (imageUri != null) {
            pendingCoverTrack?.let { trackUri ->
                runCatching {
                    context.contentResolver.takePersistableUriPermission(
                        imageUri,
                        android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION,
                    )
                }
                library.preferences.setCustomCover(trackUri, imageUri)
                if (track?.uri == trackUri) customCoverUri = imageUri
                android.widget.Toast.makeText(context, R.string.custom_cover_saved, android.widget.Toast.LENGTH_SHORT).show()
            }
        }
        pendingCoverTrack = null
    }
    val pagerState = rememberPagerState(initialPage = 0) { 2 }

    LaunchedEffect(controller) {
        controller?.playbackParameters = androidx.media3.common.PlaybackParameters(speed)
        while (true) {
            delay(300)
            controller?.let { player ->
                isPlaying = player.isPlaying
                positionMs = player.currentPosition.coerceAtLeast(0L)
                durationMs = player.duration.coerceAtLeast(0L)
                // The player queue may be a filtered subset (group, search,
                // album groups, shuffle order); map by media id instead of
                // treating its index as an index into the full track list.
                val currentId = player.currentMediaItem?.mediaId
                val mapped = currentId?.let { id -> library.tracks.indexOfFirst { it.uri.toString() == id } } ?: -1
                if (mapped >= 0) {
                    library.selectedIndex = mapped
                }
            }
        }
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
    ) { padding ->
        if (track == null) {
            Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(stringResource(R.string.choose_track_hint), color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(Modifier.height(16.dp))
                    Button(onClick = onOpenLibrary) {
                        Text(stringResource(R.string.open_library))
                    }
                }
            }
            return@Scaffold
        }
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            library.playbackError?.let {
                Text(
                    it,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.fillMaxWidth().padding(bottom = 4.dp),
                )
            }
            Spacer(Modifier.height(8.dp))
            BoxWithConstraints(Modifier.fillMaxWidth()) {
                val pageHeight = maxWidth / 1.1f + 194.dp
                HorizontalPager(
                    state = pagerState,
                    modifier = Modifier.fillMaxWidth().height(pageHeight),
                ) { page ->
                    if (page == 0) {
                        Column(Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally) {
                            Spacer(Modifier.height(64.dp))
                            Box(Modifier.fillMaxWidth().aspectRatio(1.1f), contentAlignment = Alignment.Center) {
                                NowPlayingCover(
                                    track = track,
                                    customCoverUri = customCoverUri,
                                    onChooseCover = {
                                        pendingCoverTrack = track.uri
                                        coverPicker.launch(arrayOf("image/*"))
                                    },
                                )
                            }
                            Spacer(Modifier.height(74.dp))
                            Column(
                                modifier = Modifier.fillMaxWidth().height(56.dp),
                                horizontalAlignment = Alignment.CenterHorizontally,
                            ) {
                                Text(
                                    track.title,
                                    style = MaterialTheme.typography.titleLarge,
                                    fontWeight = FontWeight.Bold,
                                    maxLines = 1,
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .basicMarquee(iterations = Int.MAX_VALUE),
                                    textAlign = TextAlign.Center,
                                )
                                Text(
                                    track.artist ?: stringResource(R.string.unknown_artist),
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.secondary,
                                    maxLines = 1,
                                    modifier = Modifier.fillMaxWidth().padding(top = 2.dp),
                                    textAlign = TextAlign.Center,
                                )
                            }
                        }
                    } else {
                        LyricsView(
                            library = library,
                            track = track,
                            positionMs = positionMs,
                            onSeek = { controller?.seekTo(it) },
                            autoLoadExternal = library.autoLoadLyrics,
                        )
                    }
                }
            }
            Spacer(Modifier.height(0.dp))
            Slider(
                value = positionMs.coerceIn(0L, durationMs.coerceAtLeast(1L)).toFloat(),
                onValueChange = { controller?.seekTo(it.toLong()) },
                valueRange = 0f..durationMs.coerceAtLeast(1L).toFloat(),
                thumb = {
                    Box(
                        Modifier
                            .size(16.dp)
                            .clip(CircleShape)
                            .background(MaterialTheme.colorScheme.primary),
                    )
                },
                track = { state ->
                    val fraction = if (state.valueRange.endInclusive > state.valueRange.start) {
                        ((state.value - state.valueRange.start) / (state.valueRange.endInclusive - state.valueRange.start))
                            .coerceIn(0f, 1f)
                    } else {
                        0f
                    }
                    BoxWithConstraints(
                        Modifier
                            .fillMaxWidth()
                            .height(8.dp),
                    ) {
                        val trackWidth = maxWidth
                        Box(
                            Modifier
                                .fillMaxWidth()
                                .height(4.dp)
                                .align(Alignment.CenterStart)
                                .clip(RoundedCornerShape(2.dp))
                                .background(MaterialTheme.colorScheme.surfaceVariant),
                        )
                        Box(
                            Modifier
                                .fillMaxWidth(fraction)
                                .height(4.dp)
                                .align(Alignment.CenterStart)
                                .clip(RoundedCornerShape(2.dp))
                                .background(MaterialTheme.colorScheme.primary),
                        )
                        val loopSpan = durationMs.coerceAtLeast(1L).toFloat()
                        val tickFractions = buildList {
                            if (loopA >= 0L) add((loopA / loopSpan).coerceIn(0f, 1f))
                            if (loopB > loopA) add((loopB / loopSpan).coerceIn(0f, 1f))
                        }
                        if (tickFractions.size == 2) {
                            Box(
                                Modifier
                                    .offset(x = trackWidth * tickFractions[0])
                                    .width(trackWidth * (tickFractions[1] - tickFractions[0]))
                                    .height(4.dp)
                                    .align(Alignment.CenterStart)
                                    .clip(RoundedCornerShape(2.dp))
                                    .background(MaterialTheme.colorScheme.tertiary.copy(alpha = 0.45f)),
                            )
                        }
                        tickFractions.forEach { tickFraction ->
                            Box(
                                Modifier
                                    .offset(x = trackWidth * tickFraction - 1.dp)
                                    .width(2.dp)
                                    .height(8.dp)
                                    .align(Alignment.CenterStart)
                                    .clip(RoundedCornerShape(1.dp))
                                    .background(MaterialTheme.colorScheme.tertiary),
                            )
                        }
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            )
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(formatTime(positionMs), style = MaterialTheme.typography.labelSmall)
                Text(formatTime(durationMs), style = MaterialTheme.typography.labelSmall)
            }
            Spacer(Modifier.height(0.dp))
            PlaybackModeRow(
                controller = controller,
                positionMs = positionMs,
                speed = speed,
                loopA = loopA,
                loopB = loopB,
                onLoopA = { loopA = it },
                onLoopB = { loopB = it },
                onSpeedChange = { option ->
                    speed = option
                    library.preferences.playbackSpeed = option
                    controller?.playbackParameters = androidx.media3.common.PlaybackParameters(option)
                },
                onShuffleChange = { library.preferences.shuffleEnabled = it },
                onRepeatChange = { library.preferences.repeatMode = it },
                onOpenQueue = { queueOpen = true },
            )
            Spacer(Modifier.height(0.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box(Modifier.weight(1f), contentAlignment = Alignment.Center) {
                    IconButton(
                        onClick = { controller?.seekToPreviousMediaItem() },
                        modifier = Modifier.size(56.dp),
                    ) {
                        Icon(
                            Icons.Filled.SkipPrevious,
                            contentDescription = stringResource(R.string.previous),
                            modifier = Modifier.size(36.dp),
                        )
                    }
                }
                Box(Modifier.weight(1f), contentAlignment = Alignment.Center) {
                    SeekIntervalButton(
                        seconds = library.preferences.seekBackSeconds,
                        backward = true,
                        modifier = Modifier.offset(x = (-10).dp),
                        onClick = {
                            controller?.let { player ->
                                player.seekTo(seekBackTarget(player.currentPosition, library.preferences.seekBackSeconds))
                            }
                        },
                    )
                }
                Box(Modifier.weight(1f), contentAlignment = Alignment.Center) {
                    FilledIconButton(
                        onClick = {
                            val player = controller
                            if (player?.isPlaying == true) player.pause() else player?.play()
                        },
                        modifier = Modifier.size(52.dp),
                        shape = CircleShape,
                        colors = IconButtonDefaults.filledIconButtonColors(containerColor = MaterialTheme.colorScheme.primary),
                    ) {
                        Icon(
                            if (isPlaying) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                            contentDescription = stringResource(if (isPlaying) R.string.pause else R.string.play),
                            tint = MaterialTheme.colorScheme.onPrimary,
                            modifier = Modifier.size(30.dp),
                        )
                    }
                }
                Box(Modifier.weight(1f), contentAlignment = Alignment.Center) {
                    SeekIntervalButton(
                        seconds = library.preferences.seekForwardSeconds,
                        backward = false,
                        modifier = Modifier.offset(x = 10.dp),
                        onClick = {
                            controller?.let { player ->
                                player.seekTo(
                                    seekForwardTarget(
                                        player.currentPosition,
                                        player.duration,
                                        library.preferences.seekForwardSeconds,
                                    ),
                                )
                            }
                        },
                    )
                }
                Box(Modifier.weight(1f), contentAlignment = Alignment.Center) {
                    IconButton(
                        onClick = { controller?.seekToNextMediaItem() },
                        modifier = Modifier.size(56.dp),
                    ) {
                        Icon(
                            Icons.Filled.SkipNext,
                            contentDescription = stringResource(R.string.next),
                            modifier = Modifier.size(36.dp),
                        )
                    }
                }
            }
        }
    }

    if (queueOpen) {
        QueueSheet(library, controller, onDismiss = { queueOpen = false })
    }
}

private fun speedLabel(speed: Float): String =
    if (speed % 1f == 0f) "${speed.toInt()}×" else "${speed}×"

/** Hold the cover this long to open the cover picker. */
private const val COVER_LONG_PRESS_MS = 600L

@Composable
private fun NowPlayingCover(
    track: AudioTrack,
    customCoverUri: android.net.Uri?,
    onChooseCover: () -> Unit,
) {
    val context = LocalContext.current
    val haptics = androidx.compose.ui.platform.LocalHapticFeedback.current
    var cover by remember(track.uri) { mutableStateOf<androidx.compose.ui.graphics.ImageBitmap?>(null) }
    LaunchedEffect(track.uri, customCoverUri) {
        cover = customCoverUri?.let { CoverLoader.loadImage(context, it) }
            ?: CoverLoader.load(context, track.uri)
    }
    Box(
        modifier = Modifier
            .fillMaxSize()
            .clip(RoundedCornerShape(24.dp))
            .background(MaterialTheme.colorScheme.primaryContainer)
            .pointerInput(track.uri, customCoverUri) {
                detectTapGestures(
                    onPress = {
                        val releasedBeforeThreshold = withTimeoutOrNull(COVER_LONG_PRESS_MS) {
                            tryAwaitRelease()
                        }
                        if (releasedBeforeThreshold == null) {
                            haptics.performHapticFeedback(
                                androidx.compose.ui.hapticfeedback.HapticFeedbackType.LongPress,
                            )
                            onChooseCover()
                        }
                    },
                )
            },
        contentAlignment = Alignment.Center,
    ) {
        val image = cover
        if (image != null) {
            Image(
                bitmap = image,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
            )
        } else {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Icon(
                    Icons.Filled.Lyrics,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.size(72.dp),
                )
                Spacer(Modifier.height(12.dp))
                Text(
                    text = stringResource(R.string.cover_long_press_hint),
                    color = MaterialTheme.colorScheme.onPrimaryContainer,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
    }
}

@Composable
private fun LyricsView(
    library: LibraryState,
    track: AudioTrack,
    positionMs: Long,
    onSeek: (Long) -> Unit,
    autoLoadExternal: Boolean,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var cues by remember(track.uri) { mutableStateOf<List<SubtitleCue>>(emptyList()) }
    var candidates by remember(track.uri) { mutableStateOf<List<OnlineLyricsCandidate>>(emptyList()) }
    var searching by remember(track.uri) { mutableStateOf(false) }
    var searchFinished by remember(track.uri) { mutableStateOf(false) }
    var statusMessage by remember(track.uri) { mutableStateOf<String?>(null) }
    var savingId by remember(track.uri) { mutableStateOf<Long?>(null) }
    var previewCandidate by remember(track.uri) { mutableStateOf<OnlineLyricsCandidate?>(null) }
    var managingLyrics by remember(track.uri) { mutableStateOf(false) }
    var managementMenu by remember(track.uri) { mutableStateOf(false) }
    var confirmDelete by remember(track.uri) { mutableStateOf(false) }
    var lyricsOffsetMs by remember(track.uri) {
        mutableLongStateOf(library.preferences.lyricsOffsetFor(track.uri))
    }
    var queryTitle by remember(track.uri) { mutableStateOf(track.title) }
    var queryArtist by remember(track.uri) { mutableStateOf(track.artist.orEmpty()) }
    val lyricsPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        uri ?: return@rememberLauncherForActivityResult
        scope.launch {
            val result = withContext(Dispatchers.IO) {
                runCatching {
                    val bytes = checkNotNull(context.contentResolver.openInputStream(uri)).use { it.readBytes() }
                    val extension = uri.lastPathSegment.orEmpty().substringAfterLast('.', "").lowercase()
                    LyricsFileStore.import(track, bytes, extension)
                }
            }
            result.onSuccess { file ->
                library.attachLyrics(track.uri, file)
                cues = withContext(Dispatchers.IO) {
                    PreviewLyrics.load(context, library.selectedTrack ?: track, true)
                }
                managingLyrics = false
                statusMessage = null
                android.widget.Toast.makeText(context, R.string.lyrics_imported, android.widget.Toast.LENGTH_SHORT).show()
            }.onFailure {
                statusMessage = context.getString(R.string.lyrics_import_failed)
            }
        }
    }

    fun searchOnline() {
        if (searching) return
        searching = true
        previewCandidate = null
        statusMessage = null
        scope.launch {
            val result = withContext(Dispatchers.IO) {
                runCatching {
                    OnlineLyricsClient.search(
                        track = track,
                        queryTitle = queryTitle,
                        queryArtist = queryArtist.takeIf(String::isNotBlank),
                    )
                }
            }
            searching = false
            searchFinished = true
            candidates = result.getOrDefault(emptyList())
            statusMessage = when {
                result.isFailure -> context.getString(R.string.online_lyrics_search_failed)
                candidates.isEmpty() -> context.getString(R.string.online_lyrics_not_found)
                else -> null
            }
        }
    }

    fun saveCandidate(candidate: OnlineLyricsCandidate) {
        if (savingId != null) return
        savingId = candidate.id
        statusMessage = null
        scope.launch {
            val saved = withContext(Dispatchers.IO) {
                runCatching { LyricsFileStore.save(track, candidate.syncedLyrics) }
            }
            savingId = null
            saved.onSuccess { file ->
                library.attachLyrics(track.uri, file)
                cues = PreviewLyrics.parseLrcTimeline(candidate.syncedLyrics)
                candidates = emptyList()
                previewCandidate = null
                managingLyrics = false
                android.widget.Toast.makeText(
                    context,
                    R.string.online_lyrics_saved,
                    android.widget.Toast.LENGTH_SHORT,
                ).show()
            }.onFailure {
                statusMessage = context.getString(R.string.online_lyrics_save_failed)
            }
        }
    }

    LaunchedEffect(track.uri, autoLoadExternal) {
        val loaded = withContext(Dispatchers.IO) {
            runCatching { PreviewLyrics.load(context, track, autoLoadExternal) }
                .getOrDefault(emptyList())
        }
        cues = loaded
        candidates = emptyList()
        previewCandidate = null
        managingLyrics = false
        statusMessage = null
        searchFinished = false
        if (loaded.isEmpty() && track.subtitleUri == null && autoLoadExternal) searchOnline()
    }
    val currentIndex = cues.indexOfLast { cue ->
        val start = (cue.startMs + lyricsOffsetMs).coerceAtLeast(0L)
        val end = if (cue.endMs == PreviewLyrics.NO_END) cue.endMs else (cue.endMs + lyricsOffsetMs).coerceAtLeast(0L)
        positionMs >= start && (end == PreviewLyrics.NO_END || positionMs < end)
    }
    val listState = rememberLazyListState()
    LaunchedEffect(currentIndex) {
        if (currentIndex < 0) return@LaunchedEffect
        fun centerDelta(): Float? {
            val info = listState.layoutInfo
            if (info.viewportEndOffset <= info.viewportStartOffset) return null
            val viewportCenter = (info.viewportStartOffset + info.viewportEndOffset) / 2
            val item = info.visibleItemsInfo.firstOrNull { it.index == currentIndex } ?: return null
            return (item.offset + item.size / 2f) - viewportCenter
        }
        // Jump first when the target line is off-screen, then settle it in the middle.
        if (centerDelta() == null) {
            listState.scrollToItem(currentIndex)
        }
        centerDelta()?.let { delta ->
            if (kotlin.math.abs(delta) > 2f) {
                listState.animateScrollBy(delta)
            }
        }
    }
    if (cues.isEmpty() || managingLyrics) {
        Column(
            modifier = Modifier.fillMaxSize().padding(horizontal = 8.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            when {
                searching -> {
                    CircularProgressIndicator(modifier = Modifier.size(32.dp))
                    Spacer(Modifier.height(12.dp))
                    Text(
                        stringResource(R.string.online_lyrics_searching),
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                previewCandidate != null -> {
                    val candidate = requireNotNull(previewCandidate)
                    val previewCues = remember(candidate.id, candidate.syncedLyrics) {
                        PreviewLyrics.parseLrcTimeline(candidate.syncedLyrics)
                    }
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Text(
                            stringResource(R.string.online_lyrics_preview),
                            style = MaterialTheme.typography.titleMedium,
                        )
                        androidx.compose.material3.TextButton(
                            enabled = savingId == null,
                            onClick = {
                                previewCandidate = null
                                statusMessage = null
                            },
                        ) {
                            Text(stringResource(R.string.online_lyrics_back_to_results))
                        }
                    }
                    Text(
                        listOf(candidate.trackName, candidate.artistName)
                            .filter(String::isNotBlank)
                            .joinToString(" · "),
                        style = MaterialTheme.typography.bodyMedium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    if (candidate.possibleMismatch) {
                        Text(
                            stringResource(R.string.online_lyrics_possible_mismatch),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.error,
                        )
                    }
                    statusMessage?.let {
                        Text(it, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.error)
                    }
                    Spacer(Modifier.height(4.dp))
                    LazyColumn(modifier = Modifier.fillMaxWidth().weight(1f)) {
                        itemsIndexed(
                            previewCues,
                            key = { index, cue -> "${cue.startMs}-$index" },
                        ) { _, cue ->
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { onSeek(cue.startMs) }
                                    .padding(vertical = 5.dp),
                                verticalAlignment = Alignment.Top,
                            ) {
                                Text(
                                    formatTime(cue.startMs),
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.primary,
                                    modifier = Modifier.width(52.dp),
                                )
                                Text(
                                    cue.text.ifEmpty { " " },
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    modifier = Modifier.weight(1f),
                                )
                            }
                        }
                    }
                    Button(
                        enabled = savingId == null && previewCues.isNotEmpty(),
                        onClick = { saveCandidate(candidate) },
                    ) {
                        Text(
                            stringResource(
                                if (savingId == null) R.string.online_lyrics_confirm_save
                                else R.string.online_lyrics_saving,
                            ),
                        )
                    }
                }
                candidates.isNotEmpty() -> {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Text(
                            stringResource(R.string.online_lyrics_choose),
                            style = MaterialTheme.typography.titleMedium,
                        )
                        androidx.compose.material3.TextButton(
                            onClick = {
                                candidates = emptyList()
                                previewCandidate = null
                                statusMessage = null
                                searchFinished = false
                            },
                        ) {
                            Text(stringResource(R.string.online_lyrics_edit_query))
                        }
                    }
                    Text(
                        stringResource(R.string.online_lyrics_source),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.height(4.dp))
                    LazyColumn(modifier = Modifier.fillMaxWidth().weight(1f)) {
                        itemsIndexed(candidates, key = { _, item -> item.id }) { _, candidate ->
                            androidx.compose.material3.Surface(
                                shape = RoundedCornerShape(16.dp),
                                color = MaterialTheme.colorScheme.surfaceVariant,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 4.dp)
                                    .clickable(enabled = savingId == null) {
                                        previewCandidate = candidate
                                        statusMessage = null
                                    },
                            ) {
                                Column(Modifier.padding(horizontal = 16.dp, vertical = 10.dp)) {
                                    Text(candidate.trackName, style = MaterialTheme.typography.bodyLarge)
                                    Text(
                                        listOf(candidate.artistName, candidate.albumName)
                                            .filter(String::isNotBlank)
                                            .joinToString(" · "),
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis,
                                    )
                                    Text(
                                        stringResource(
                                            R.string.online_lyrics_duration,
                                            formatTime(candidate.durationSeconds * 1_000L),
                                        ),
                                        style = MaterialTheme.typography.labelSmall,
                                        color = MaterialTheme.colorScheme.primary,
                                    )
                                    if (candidate.possibleMismatch) {
                                        Text(
                                            stringResource(R.string.online_lyrics_possible_mismatch),
                                            style = MaterialTheme.typography.labelSmall,
                                            color = MaterialTheme.colorScheme.error,
                                        )
                                    }
                                }
                            }
                        }
                    }
                    if (cues.isNotEmpty()) {
                        OutlinedButton(onClick = {
                            managingLyrics = false
                            candidates = emptyList()
                            previewCandidate = null
                            statusMessage = null
                        }) { Text(stringResource(R.string.lyrics_keep_current)) }
                    }
                }
                else -> {
                    Text(
                        statusMessage ?: stringResource(R.string.no_lyrics),
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        textAlign = TextAlign.Center,
                    )
                    Spacer(Modifier.height(8.dp))
                    androidx.compose.material3.OutlinedTextField(
                        value = queryTitle,
                        onValueChange = { queryTitle = it },
                        label = { Text(stringResource(R.string.online_lyrics_query_title)) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Spacer(Modifier.height(6.dp))
                    androidx.compose.material3.OutlinedTextField(
                        value = queryArtist,
                        onValueChange = { queryArtist = it },
                        label = { Text(stringResource(R.string.online_lyrics_query_artist)) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Spacer(Modifier.height(8.dp))
                    Button(
                        enabled = queryTitle.isNotBlank(),
                        onClick = { searchOnline() },
                    ) {
                        Text(
                            stringResource(
                                if (searchFinished) R.string.online_lyrics_retry else R.string.online_lyrics_search,
                            ),
                        )
                    }
                    Spacer(Modifier.height(8.dp))
                    Text(
                        stringResource(R.string.online_lyrics_windows_hint),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        textAlign = TextAlign.Center,
                    )
                    if (cues.isNotEmpty()) {
                        OutlinedButton(
                            onClick = {
                                managingLyrics = false
                                statusMessage = null
                            },
                            modifier = Modifier.padding(top = 8.dp),
                        ) { Text(stringResource(R.string.lyrics_keep_current)) }
                    }
                }
            }
        }
    } else {
        Column(Modifier.fillMaxSize()) {
            Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.CenterEnd) {
                TextButton(onClick = { managementMenu = true }) {
                    Text(stringResource(R.string.lyrics_manage))
                }
                DropdownMenu(
                    expanded = managementMenu,
                    onDismissRequest = { managementMenu = false },
                ) {
                    DropdownMenuItem(
                        text = { Text(stringResource(R.string.lyrics_search_again)) },
                        onClick = {
                            managementMenu = false
                            managingLyrics = true
                            searchFinished = false
                            candidates = emptyList()
                            searchOnline()
                        },
                    )
                    DropdownMenuItem(
                        text = { Text(stringResource(R.string.lyrics_choose_local)) },
                        onClick = {
                            managementMenu = false
                            lyricsPicker.launch(arrayOf("text/plain", "application/x-subrip"))
                        },
                    )
                    DropdownMenuItem(
                        text = { Text(stringResource(R.string.lyrics_earlier)) },
                        onClick = {
                            managementMenu = false
                            lyricsOffsetMs = (lyricsOffsetMs - 500L).coerceAtLeast(-60_000L)
                            library.preferences.setLyricsOffset(track.uri, lyricsOffsetMs)
                        },
                    )
                    DropdownMenuItem(
                        text = { Text(stringResource(R.string.lyrics_later)) },
                        onClick = {
                            managementMenu = false
                            lyricsOffsetMs = (lyricsOffsetMs + 500L).coerceAtMost(60_000L)
                            library.preferences.setLyricsOffset(track.uri, lyricsOffsetMs)
                        },
                    )
                    if (lyricsOffsetMs != 0L) {
                        DropdownMenuItem(
                            text = { Text(stringResource(R.string.lyrics_offset_reset)) },
                            onClick = {
                                managementMenu = false
                                lyricsOffsetMs = 0L
                                library.preferences.setLyricsOffset(track.uri, 0L)
                            },
                        )
                    }
                    DropdownMenuItem(
                        text = { Text(stringResource(R.string.lyrics_delete)) },
                        onClick = {
                            managementMenu = false
                            confirmDelete = true
                        },
                    )
                }
            }
            if (lyricsOffsetMs != 0L) {
                Text(
                    stringResource(R.string.lyrics_offset_value, lyricsOffsetMs / 1000f),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.align(Alignment.CenterHorizontally),
                )
            }
            LazyColumn(state = listState, modifier = Modifier.fillMaxWidth().weight(1f)) {
                itemsIndexed(cues) { index, cue ->
                    val active = index == currentIndex
                    Text(
                        cue.text.ifEmpty { " " },
                        style = MaterialTheme.typography.bodyLarge,
                        fontWeight = if (active) FontWeight.Bold else FontWeight.Normal,
                        color = if (active) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                        textAlign = TextAlign.Center,
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { onSeek((cue.startMs + lyricsOffsetMs).coerceAtLeast(0L)) }
                            .padding(vertical = 6.dp, horizontal = 4.dp),
                    )
                }
            }
        }
    }

    if (confirmDelete) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text(stringResource(R.string.lyrics_delete_confirm_title)) },
            text = { Text(stringResource(R.string.lyrics_delete_confirm_body)) },
            confirmButton = {
                Button(onClick = {
                    confirmDelete = false
                    scope.launch {
                        val deleted = withContext(Dispatchers.IO) {
                            runCatching { LyricsFileStore.delete(track) }.getOrDefault(false)
                        }
                        if (deleted) {
                            library.detachLyrics(track.uri)
                            library.preferences.setLyricsOffset(track.uri, 0L)
                            lyricsOffsetMs = 0L
                            cues = emptyList()
                            statusMessage = context.getString(R.string.lyrics_deleted)
                        } else {
                            statusMessage = context.getString(R.string.lyrics_delete_failed)
                        }
                    }
                }) { Text(stringResource(R.string.lyrics_delete)) }
            },
            dismissButton = {
                OutlinedButton(onClick = { confirmDelete = false }) {
                    Text(stringResource(R.string.cancel))
                }
            },
        )
    }
}

private val QueueRowHeight = 64.dp

private data class QueueEntry(val index: Int, val mediaId: String, val title: String, val artist: String?)

private fun queueEntries(controller: MediaController?): List<QueueEntry> {
    val player = controller ?: return emptyList()
    return (0 until player.mediaItemCount).map { index ->
        val item = player.getMediaItemAt(index)
        QueueEntry(
            index = index,
            mediaId = item.mediaId,
            title = item.mediaMetadata.title?.toString().orEmpty(),
            artist = item.mediaMetadata.artist?.toString(),
        )
    }
}

private fun playNextAfterCurrent(controller: MediaController?, track: AudioTrack, afterIndex: Int) {
    val player = controller ?: return
    val item = androidx.media3.common.MediaItem.Builder()
        .setUri(track.uri)
        .setMediaId(track.uri.toString())
        .setMediaMetadata(
            androidx.media3.common.MediaMetadata.Builder()
                .setTitle(track.title)
                .setArtist(track.artist)
                .setAlbumTitle(track.album)
                .build(),
        )
        .build()
    player.addMediaItems((afterIndex + 1).coerceAtMost(player.mediaItemCount), listOf(item))
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun QueueSheet(library: LibraryState, controller: MediaController?, onDismiss: () -> Unit) {
    var entries by remember { mutableStateOf(queueEntries(controller)) }
    var currentIndex by remember { mutableIntStateOf(controller?.currentMediaItemIndex ?: -1) }
    LaunchedEffect(controller) {
        while (true) {
            delay(400)
            entries = queueEntries(controller)
            currentIndex = controller?.currentMediaItemIndex ?: -1
        }
    }
    var draggingIndex by remember { mutableStateOf(-1) }
    var dragOffsetY by remember { mutableStateOf(0f) }
    val rowHeightPx = with(LocalDensity.current) { QueueRowHeight.toPx() }
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Text(
            stringResource(R.string.play_queue) + " · " + stringResource(R.string.queue_count, entries.size),
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.padding(horizontal = 20.dp, vertical = 8.dp),
        )
        LazyColumn(Modifier.fillMaxWidth().padding(bottom = 24.dp)) {
            itemsIndexed(entries) { position, entry ->
                val track = library.tracks.firstOrNull { it.uri.toString() == entry.mediaId }
                val dragging = draggingIndex == position
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(QueueRowHeight)
                        .graphicsLayer { if (dragging) translationY = dragOffsetY }
                        .pointerInput(Unit) {
                            detectDragGesturesAfterLongPress(
                                onDragStart = {
                                    draggingIndex = position
                                    dragOffsetY = 0f
                                },
                                onDrag = { change, amount ->
                                    change.consume()
                                    dragOffsetY += amount.y
                                },
                                onDragEnd = {
                                    val from = draggingIndex
                                    if (from in entries.indices && dragOffsetY != 0f) {
                                        val to = (from + kotlin.math.round(dragOffsetY / rowHeightPx).toInt())
                                            .coerceIn(0, entries.size - 1)
                                        if (to != from) controller?.moveMediaItem(from, to)
                                    }
                                    draggingIndex = -1
                                    dragOffsetY = 0f
                                },
                                onDragCancel = {
                                    draggingIndex = -1
                                    dragOffsetY = 0f
                                },
                            )
                        }
                        .clickable {
                            controller?.seekTo(entry.index, 0)
                            controller?.play()
                            onDismiss()
                        }
                        .background(
                            if (entry.index == currentIndex) MaterialTheme.colorScheme.primaryContainer else Color.Transparent,
                        )
                        .padding(horizontal = 12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    track?.let { TrackCover(it, size = 40.dp) }
                    Spacer(Modifier.width(10.dp))
                    Column(Modifier.weight(1f)) {
                        Text(
                            entry.title.ifEmpty { stringResource(R.string.unknown_artist) },
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = if (entry.index == currentIndex) FontWeight.Bold else FontWeight.Normal,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                        Text(
                            entry.artist ?: stringResource(R.string.unknown_artist),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.secondary,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    track?.let {
                        IconButton(onClick = { playNextAfterCurrent(controller, it, entry.index) }) {
                            Icon(
                                Icons.AutoMirrored.Filled.PlaylistAdd,
                                contentDescription = stringResource(R.string.play_next),
                                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                    IconButton(onClick = { controller?.removeMediaItem(entry.index) }) {
                        Icon(
                            Icons.Filled.Close,
                            contentDescription = stringResource(R.string.remove_from_queue),
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
    }
}


@Composable
private fun SeekIntervalButton(
    seconds: Int,
    backward: Boolean,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
) {
    val description = stringResource(
        if (backward) R.string.seek_back_action else R.string.seek_forward_action,
        seconds,
    )
    IconButton(onClick = onClick, modifier = modifier.size(52.dp)) {
        Box(Modifier.size(40.dp), contentAlignment = Alignment.Center) {
            Icon(
                Icons.Filled.Replay,
                contentDescription = description,
                tint = MaterialTheme.colorScheme.onSurface,
                modifier = Modifier
                    .fillMaxSize()
                    .graphicsLayer(scaleX = if (backward) 1f else -1f),
            )
            Text(
                seconds.toString(),
                color = MaterialTheme.colorScheme.onSurface,
                fontSize = 9.sp,
                fontWeight = FontWeight.Bold,
            )
        }
    }
}

internal fun seekBackTarget(currentMs: Long, seconds: Int): Long =
    (currentMs - seconds.coerceIn(1, 300) * 1_000L).coerceAtLeast(0L)

internal fun seekForwardTarget(currentMs: Long, durationMs: Long, seconds: Int): Long {
    val target = currentMs.coerceAtLeast(0L) + seconds.coerceIn(1, 300) * 1_000L
    return if (durationMs > 0L) target.coerceAtMost(durationMs) else target
}

/** Playback modes laid out as shuffle, A, speed, B and repeat. */
@Composable
@SuppressLint("UnsafeOptInUsageError")
private fun PlaybackModeRow(
    controller: androidx.media3.session.MediaController?,
    positionMs: Long,
    speed: Float,
    loopA: Long,
    loopB: Long,
    onLoopA: (Long) -> Unit,
    onLoopB: (Long) -> Unit,
    onSpeedChange: (Float) -> Unit,
    onShuffleChange: (Boolean) -> Unit,
    onRepeatChange: (Int) -> Unit,
    onOpenQueue: () -> Unit,
) {
    val context = LocalContext.current
    var speedMenu by remember { mutableStateOf(false) }
    var shuffleEnabled by remember(controller) { mutableStateOf(controller?.shuffleModeEnabled == true) }
    var repeatMode by remember(controller) { mutableIntStateOf(controller?.repeatMode ?: Player.REPEAT_MODE_OFF) }
    fun send(action: String) {
        runCatching {
            controller?.sendCustomCommand(
                androidx.media3.session.SessionCommand(action, android.os.Bundle.EMPTY),
                android.os.Bundle.EMPTY,
            )
        }
    }
    Row(
        Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.weight(1f), contentAlignment = Alignment.Center) {
            IconButton(onClick = {
                val player = controller ?: return@IconButton
                player.shuffleModeEnabled = !player.shuffleModeEnabled
                shuffleEnabled = player.shuffleModeEnabled
                onShuffleChange(shuffleEnabled)
            }) {
                Icon(
                    Icons.Filled.Shuffle,
                    contentDescription = stringResource(R.string.shuffle_play),
                    tint = if (shuffleEnabled) MaterialTheme.colorScheme.primary
                    else MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        Box(
            Modifier.weight(1f).offset(x = (-10).dp),
            contentAlignment = Alignment.Center,
        ) {
            androidx.compose.material3.TextButton(onClick = {
                when {
                    loopA < 0L -> {
                        onLoopA(positionMs)
                        send(com.imankoppai.mediaanvil.playback.PlaybackService.COMMAND_LOOP_A)
                        android.widget.Toast.makeText(
                            context,
                            context.getString(R.string.loop_a_saved, formatTime(positionMs)),
                            android.widget.Toast.LENGTH_SHORT,
                        ).show()
                    }
                    loopB <= loopA && positionMs > loopA -> {
                        onLoopB(positionMs)
                        send(com.imankoppai.mediaanvil.playback.PlaybackService.COMMAND_LOOP_B)
                        android.widget.Toast.makeText(
                            context,
                            context.getString(R.string.loop_b_saved, formatTime(positionMs)),
                            android.widget.Toast.LENGTH_SHORT,
                        ).show()
                    }
                    loopB <= loopA -> {
                        android.widget.Toast.makeText(
                            context,
                            R.string.loop_b_after_a,
                            android.widget.Toast.LENGTH_SHORT,
                        ).show()
                    }
                    else -> {
                        onLoopA(-1L)
                        onLoopB(-1L)
                        send(com.imankoppai.mediaanvil.playback.PlaybackService.COMMAND_LOOP_CLEAR)
                        android.widget.Toast.makeText(
                            context,
                            R.string.loop_cleared,
                            android.widget.Toast.LENGTH_SHORT,
                        ).show()
                    }
                }
            }) {
                Text(
                    "A/B",
                    color = if (loopA >= 0) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 18.sp,
                )
            }
        }
        Box(Modifier.weight(1f), contentAlignment = Alignment.Center) {
            Box {
                Text(
                    speedLabel(speed),
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .clickable { speedMenu = true }
                        .padding(horizontal = 10.dp, vertical = 6.dp),
                )
                DropdownMenu(expanded = speedMenu, onDismissRequest = { speedMenu = false }) {
                    listOf(0.75f, 1f, 1.25f, 1.5f, 2f, 3f).forEach { option ->
                        DropdownMenuItem(
                            text = { Text(speedLabel(option)) },
                            onClick = {
                                onSpeedChange(option)
                                speedMenu = false
                            },
                        )
                    }
                }
            }
        }
        Box(
            Modifier.weight(1f).offset(x = 10.dp),
            contentAlignment = Alignment.Center,
        ) {
            IconButton(onClick = onOpenQueue) {
                Icon(
                    Icons.AutoMirrored.Filled.QueueMusic,
                    contentDescription = stringResource(R.string.play_queue),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        Box(Modifier.weight(1f), contentAlignment = Alignment.Center) {
            IconButton(onClick = {
                val player = controller ?: return@IconButton
                player.repeatMode = when (player.repeatMode) {
                    Player.REPEAT_MODE_OFF -> Player.REPEAT_MODE_ALL
                    Player.REPEAT_MODE_ALL -> Player.REPEAT_MODE_ONE
                    else -> Player.REPEAT_MODE_OFF
                }
                repeatMode = player.repeatMode
                onRepeatChange(repeatMode)
            }) {
                Icon(
                    if (repeatMode == Player.REPEAT_MODE_ONE) Icons.Filled.RepeatOne else Icons.Filled.Repeat,
                    contentDescription = stringResource(R.string.repeat),
                    tint = if (repeatMode != Player.REPEAT_MODE_OFF) MaterialTheme.colorScheme.primary
                    else MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}
