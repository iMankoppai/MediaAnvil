package com.imankoppai.mediaanvil.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.basicMarquee
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.animateScrollBy
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
import androidx.compose.material.icons.filled.Lyrics
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Repeat
import androidx.compose.material.icons.filled.RepeatOne
import androidx.compose.material.icons.filled.Shuffle
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.SkipPrevious
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
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
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
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
    onOpenEditor: (AudioTrack) -> Unit,
) {
    val context = LocalContext.current
    val track = library.selectedTrack
    var isPlaying by remember { mutableStateOf(false) }
    var positionMs by remember { mutableLongStateOf(0L) }
    var durationMs by remember { mutableLongStateOf(0L) }
    var queueOpen by remember { mutableStateOf(false) }
    var toolsOpen by remember { mutableStateOf(false) }
    var menuOpen by remember { mutableStateOf(false) }
    val pagerState = rememberPagerState(initialPage = 0) { 2 }

    LaunchedEffect(controller) {
        while (true) {
            delay(300)
            controller?.let { player ->
                isPlaying = player.isPlaying
                positionMs = player.currentPosition.coerceAtLeast(0L)
                durationMs = player.duration.coerceAtLeast(0L)
                if (player.currentMediaItem != null && player.currentMediaItemIndex in library.tracks.indices) {
                    library.selectedIndex = player.currentMediaItemIndex
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
                actions = {
                    Box {
                        IconButton(onClick = { menuOpen = true }) {
                            Icon(Icons.Filled.MoreVert, contentDescription = null)
                        }
                        DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
                            DropdownMenuItem(
                                text = { Text(stringResource(R.string.play_queue)) },
                                onClick = {
                                    menuOpen = false
                                    queueOpen = true
                                },
                            )
                            DropdownMenuItem(
                                text = { Text(stringResource(R.string.media_tools)) },
                                onClick = {
                                    menuOpen = false
                                    toolsOpen = true
                                },
                            )
                        }
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
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(formatTime(positionMs), style = MaterialTheme.typography.labelSmall)
                Text(formatTime(durationMs), style = MaterialTheme.typography.labelSmall)
            }
            Spacer(Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = { controller?.shuffleModeEnabled = !(controller?.shuffleModeEnabled ?: false) }) {
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

    if (queueOpen) {
        QueueSheet(library, controller, onDismiss = { queueOpen = false })
    }
    if (toolsOpen && track != null) {
        ToolsSheet(
            library = library,
            track = track,
            onDismiss = { toolsOpen = false },
            onOpenEditor = {
                toolsOpen = false
                onOpenEditor(it)
            },
        )
    }
}

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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun QueueSheet(library: LibraryState, controller: MediaController?, onDismiss: () -> Unit) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Text(
            stringResource(R.string.play_queue),
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.padding(horizontal = 20.dp, vertical = 8.dp),
        )
        LazyColumn(Modifier.fillMaxWidth().padding(bottom = 24.dp)) {
            itemsIndexed(library.tracks, key = { _, track -> track.uri.toString() }) { index, track ->
                val current = index == library.selectedIndex
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable {
                            controller?.seekTo(index, 0)
                            controller?.play()
                            onDismiss()
                        }
                        .background(
                            if (current) MaterialTheme.colorScheme.primaryContainer else Color.Transparent,
                        )
                        .padding(horizontal = 20.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    TrackCover(track, size = 40.dp)
                    Spacer(Modifier.width(10.dp))
                    Column(Modifier.weight(1f)) {
                        Text(
                            track.title,
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = if (current) FontWeight.Bold else FontWeight.Normal,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                        Text(
                            track.artist ?: stringResource(R.string.unknown_artist),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.secondary,
                        )
                    }
                    Text(
                        formatTime(track.durationMs),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

