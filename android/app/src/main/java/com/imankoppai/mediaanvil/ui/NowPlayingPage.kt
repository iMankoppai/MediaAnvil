package com.imankoppai.mediaanvil.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.basicMarquee
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.animateScrollBy
import androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Lyrics
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.PlaylistAdd
import androidx.compose.material.icons.filled.Repeat
import androidx.compose.material.icons.filled.RepeatOne
import androidx.compose.material.icons.filled.Shuffle
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.SkipPrevious
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
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
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun NowPlayingPage(
    library: LibraryState,
    controller: MediaController?,
    onBack: () -> Unit,
) {
    val context = LocalContext.current
    val track = library.selectedTrack
    var isPlaying by remember { mutableStateOf(false) }
    var positionMs by remember { mutableLongStateOf(0L) }
    var durationMs by remember { mutableLongStateOf(0L) }
    var speed by remember { mutableStateOf(library.preferences.playbackSpeed) }
    var speedMenu by remember { mutableStateOf(false) }
    val pagerState = rememberPagerState(initialPage = 0) { 2 }

    LaunchedEffect(controller) {
        controller?.playbackParameters = androidx.media3.common.PlaybackParameters(speed)
        while (true) {
            delay(300)
            controller?.let { player ->
                isPlaying = player.isPlaying
                positionMs = player.currentPosition.coerceAtLeast(0L)
                durationMs = player.duration.coerceAtLeast(0L)
                // The player queue may be a filtered subset (favorites, search,
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
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.now_playing), fontWeight = FontWeight.SemiBold) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = stringResource(R.string.back))
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
            )
        },
    ) { padding ->
        if (track == null) {
            Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                Text(stringResource(R.string.choose_track_hint), color = MaterialTheme.colorScheme.onSurfaceVariant)
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
            HorizontalPager(
                state = pagerState,
                modifier = Modifier.fillMaxWidth().weight(1f),
            ) { page ->
                if (page == 0) {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        NowPlayingCover(track)
                    }
                } else {
                    LyricsView(
                        track = track,
                        positionMs = positionMs,
                        onSeek = { controller?.seekTo(it) },
                        preferEmbedded = library.preferences.preferEmbeddedLyrics,
                        autoLoadExternal = library.preferences.autoLoadLyrics,
                    )
                }
            }
            if (pagerState.currentPage == 0) {
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
            Spacer(Modifier.height(16.dp))
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
                    Box(
                        Modifier
                            .fillMaxWidth()
                            .height(4.dp)
                            .clip(RoundedCornerShape(2.dp))
                            .background(MaterialTheme.colorScheme.surfaceVariant),
                    ) {
                        Box(
                            Modifier
                                .fillMaxWidth(fraction)
                                .height(4.dp)
                                .clip(RoundedCornerShape(2.dp))
                                .background(MaterialTheme.colorScheme.primary),
                        )
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            )
            AbLoopRow(controller = controller, positionMs = positionMs)
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(formatTime(positionMs), style = MaterialTheme.typography.labelSmall)
                Box {
                    Text(
                        speedLabel(speed),
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary,
                        modifier = Modifier
                            .clip(RoundedCornerShape(8.dp))
                            .clickable { speedMenu = true }
                            .padding(horizontal = 12.dp, vertical = 4.dp),
                    )
                    DropdownMenu(expanded = speedMenu, onDismissRequest = { speedMenu = false }) {
                        listOf(0.75f, 1f, 1.25f, 1.5f, 2f, 3f).forEach { option ->
                            DropdownMenuItem(
                                text = { Text(speedLabel(option)) },
                                onClick = {
                                    speed = option
                                    library.preferences.playbackSpeed = option
                                    controller?.playbackParameters = androidx.media3.common.PlaybackParameters(option)
                                    speedMenu = false
                                },
                            )
                        }
                    }
                }
                Text(formatTime(durationMs), style = MaterialTheme.typography.labelSmall)
            }
            Spacer(Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = {
                    val player = controller ?: return@IconButton
                    player.shuffleModeEnabled = !player.shuffleModeEnabled
                    library.preferences.shuffleEnabled = player.shuffleModeEnabled
                }) {
                    Icon(
                        Icons.Filled.Shuffle,
                        contentDescription = stringResource(R.string.shuffle_play),
                        tint = if (controller?.shuffleModeEnabled == true) {
                            MaterialTheme.colorScheme.primary
                        } else {
                            MaterialTheme.colorScheme.onSurfaceVariant
                        },
                    )
                }
                IconButton(
                    onClick = { controller?.seekToPreviousMediaItem() },
                    modifier = Modifier.size(60.dp),
                ) {
                    Icon(
                        Icons.Filled.SkipPrevious,
                        contentDescription = stringResource(R.string.previous),
                        modifier = Modifier.size(36.dp),
                    )
                }
                FilledIconButton(
                    onClick = {
                        val player = controller
                        if (player?.isPlaying == true) player.pause() else player?.play()
                    },
                    modifier = Modifier.size(72.dp),
                    colors = IconButtonDefaults.filledIconButtonColors(containerColor = MaterialTheme.colorScheme.primary),
                ) {
                    Icon(
                        if (isPlaying) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                        contentDescription = stringResource(if (isPlaying) R.string.pause else R.string.play),
                        tint = MaterialTheme.colorScheme.onPrimary,
                        modifier = Modifier.size(36.dp),
                    )
                }
                IconButton(
                    onClick = { controller?.seekToNextMediaItem() },
                    modifier = Modifier.size(60.dp),
                ) {
                    Icon(
                        Icons.Filled.SkipNext,
                        contentDescription = stringResource(R.string.next),
                        modifier = Modifier.size(36.dp),
                    )
                }
                IconButton(onClick = {
                    val player = controller ?: return@IconButton
                    player.repeatMode = when (player.repeatMode) {
                        Player.REPEAT_MODE_OFF -> Player.REPEAT_MODE_ALL
                        Player.REPEAT_MODE_ALL -> Player.REPEAT_MODE_ONE
                        else -> Player.REPEAT_MODE_OFF
                    }
                    library.preferences.repeatMode = player.repeatMode
                }) {
                    Icon(
                        if (controller?.repeatMode == Player.REPEAT_MODE_ONE) Icons.Filled.RepeatOne else Icons.Filled.Repeat,
                        contentDescription = stringResource(R.string.repeat),
                        tint = if (controller?.repeatMode != Player.REPEAT_MODE_OFF) {
                            MaterialTheme.colorScheme.primary
                        } else {
                            MaterialTheme.colorScheme.onSurfaceVariant
                        },
                    )
                }
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}

private fun speedLabel(speed: Float): String =
    if (speed % 1f == 0f) "${speed.toInt()}×" else "${speed}×"

@Composable
private fun NowPlayingCover(track: AudioTrack) {
    val context = LocalContext.current
    var cover by remember(track.uri) { mutableStateOf<androidx.compose.ui.graphics.ImageBitmap?>(null) }
    LaunchedEffect(track.uri) {
        cover = CoverLoader.load(context, track.uri)
    }
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(320.dp)
            .clip(RoundedCornerShape(24.dp))
            .background(MaterialTheme.colorScheme.primaryContainer),
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
            Icon(
                Icons.Filled.Lyrics,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(72.dp),
            )
        }
    }
}

@Composable
private fun LyricsView(
    track: AudioTrack,
    positionMs: Long,
    onSeek: (Long) -> Unit,
    preferEmbedded: Boolean,
    autoLoadExternal: Boolean,
) {
    val context = LocalContext.current
    var cues by remember { mutableStateOf<List<SubtitleCue>>(emptyList()) }
    LaunchedEffect(track.uri, preferEmbedded, autoLoadExternal) {
        cues = withContext(Dispatchers.IO) {
            runCatching { PreviewLyrics.load(context, track, preferEmbedded, autoLoadExternal) }
                .getOrDefault(PreviewLyrics.Timeline(emptyList(), false))
        }.cues
    }
    val currentIndex = cues.indexOfLast { cue ->
        positionMs >= cue.startMs && (cue.endMs == PreviewLyrics.NO_END || positionMs < cue.endMs)
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
    if (cues.isEmpty()) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Text(stringResource(R.string.no_lyrics), color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    } else {
        LazyColumn(state = listState, modifier = Modifier.fillMaxSize()) {
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
                        .clickable { onSeek(cue.startMs) }
                        .padding(vertical = 6.dp, horizontal = 4.dp),
                )
            }
        }
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
                                Icons.Filled.PlaylistAdd,
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


/** A/B loop controls backed by playback-service custom commands. */
@Composable
private fun AbLoopRow(controller: androidx.media3.session.MediaController?, positionMs: Long) {
    var loopA by remember { mutableLongStateOf(-1L) }
    var loopB by remember { mutableLongStateOf(-1L) }
    androidx.compose.runtime.LaunchedEffect(controller?.currentMediaItemIndex) {
        loopA = -1L
        loopB = -1L
    }
    fun send(action: String) {
        runCatching {
            controller?.sendCustomCommand(
                androidx.media3.session.SessionCommand(action, android.os.Bundle.EMPTY),
                android.os.Bundle.EMPTY,
            )
        }
    }
    androidx.compose.foundation.layout.Row(
        Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        androidx.compose.material3.TextButton(onClick = { loopA = positionMs; send(com.imankoppai.mediaanvil.playback.PlaybackService.COMMAND_LOOP_A) }) {
            Text(
                if (loopA >= 0) stringResource(R.string.loop_a_set, formatTime(loopA))
                else stringResource(R.string.loop_a),
                style = MaterialTheme.typography.labelMedium,
            )
        }
        androidx.compose.material3.TextButton(
            enabled = loopA >= 0,
            onClick = { loopB = positionMs; send(com.imankoppai.mediaanvil.playback.PlaybackService.COMMAND_LOOP_B) },
        ) {
            Text(
                if (loopB > loopA) stringResource(R.string.loop_b_set, formatTime(loopB))
                else stringResource(R.string.loop_b),
                style = MaterialTheme.typography.labelMedium,
            )
        }
        if (loopA >= 0 || loopB >= 0) {
            androidx.compose.material3.TextButton(onClick = { loopA = -1L; loopB = -1L; send(com.imankoppai.mediaanvil.playback.PlaybackService.COMMAND_LOOP_CLEAR) }) {
                Text(stringResource(R.string.loop_clear), style = MaterialTheme.typography.labelMedium)
            }
        }
    }
}
