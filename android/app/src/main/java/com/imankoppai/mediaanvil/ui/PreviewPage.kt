package com.imankoppai.mediaanvil.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
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
internal fun PreviewPage(
    library: LibraryState,
    controller: MediaController?,
    onPickFolder: () -> Unit,
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val tracks = library.tracks
    val selectedTrack = library.selectedTrack
    var isPlaying by remember { mutableStateOf(false) }
    var positionMs by remember { mutableLongStateOf(0L) }
    var durationMs by remember { mutableLongStateOf(0L) }
    var volume by remember { mutableFloatStateOf(1f) }
    var cues by remember { mutableStateOf<List<SubtitleCue>>(emptyList()) }
    var fromEmbedded by remember { mutableStateOf(false) }
    var preferEmbedded by remember { mutableStateOf(library.preferences.preferEmbeddedLyrics) }

    LaunchedEffect(controller) {
        controller?.let {
            isPlaying = it.isPlaying
            volume = it.volume
        }
    }

    LaunchedEffect(selectedTrack?.uri, preferEmbedded) {
        val track = selectedTrack
        cues = emptyList()
        fromEmbedded = false
        if (track != null) {
            val result = withContext(Dispatchers.IO) {
                runCatching { PreviewLyrics.load(context, track, preferEmbedded) }.getOrElse {
                    PreviewLyrics.Timeline(emptyList(), false)
                }
            }
            cues = result.cues
            fromEmbedded = result.fromEmbedded
        }
    }

    LaunchedEffect(controller, tracks) {
        while (true) {
            delay(500)
            controller?.let { player ->
                isPlaying = player.isPlaying
                positionMs = player.currentPosition.coerceAtLeast(0L)
                durationMs = player.duration.coerceAtLeast(0L)
                if (player.currentMediaItemIndex in tracks.indices) {
                    library.selectedIndex = player.currentMediaItemIndex
                    library.preferences.savePosition(tracks[player.currentMediaItemIndex].uri, positionMs)
                }
            }
        }
    }

    Scaffold(
        modifier = Modifier.fillMaxSize(),
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("MediaAnvil", fontWeight = FontWeight.Bold)
                        Text(
                            stringResource(R.string.local_only),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.secondary,
                        )
                    }
                },
                modifier = Modifier.statusBarsPadding(),
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .padding(horizontal = 16.dp)
                .navigationBarsPadding()
                .fillMaxSize(),
        ) {
            Button(onClick = onPickFolder, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.choose_folder))
            }
            Text(
                stringResource(R.string.choose_folder_hint),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.secondary,
                modifier = Modifier.padding(vertical = 8.dp),
            )
            if (library.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            library.message?.let { Text(it, color = MaterialTheme.colorScheme.error) }

            Text(
                stringResource(R.string.tracks),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.padding(vertical = 8.dp),
            )
            LazyColumn(modifier = Modifier.weight(1f)) {
                itemsIndexed(tracks, key = { _, track -> track.uri.toString() }) { index, track ->
                    TrackRow(track, selected = index == library.selectedIndex, onClick = { playTrack(library, controller, index) })
                    HorizontalDivider()
                }
            }

            selectedTrack?.let { track ->
                LyricsPanel(
                    cues = cues,
                    positionMs = positionMs,
                    fromEmbedded = fromEmbedded,
                    preferEmbedded = preferEmbedded,
                    onPreferEmbeddedChange = {
                        preferEmbedded = it
                        library.preferences.preferEmbeddedLyrics = it
                    },
                    onSeekTo = { cue -> controller?.seekTo(cue.startMs) },
                )
                PlayerCard(
                    track = track,
                    isPlaying = isPlaying,
                    positionMs = positionMs,
                    durationMs = durationMs.takeIf { it > 0 } ?: track.durationMs,
                    volume = volume,
                    onVolumeChange = { value ->
                        volume = value
                        controller?.volume = value
                    },
                    onPlayPause = {
                        controller?.let { if (it.isPlaying) it.pause() else it.play() }
                    },
                    onPrevious = { controller?.seekToPreviousMediaItem() },
                    onNext = { controller?.seekToNextMediaItem() },
                    onSeekBack = { controller?.seekTo((controller.currentPosition - 30_000).coerceAtLeast(0L)) },
                    onSeekForward = {
                        val duration = controller?.duration ?: 0L
                        controller?.seekTo((controller.currentPosition + 30_000).coerceAtMost(duration))
                    },
                    onSeek = { controller?.seekTo(it) },
                )
            } ?: Text(
                stringResource(R.string.choose_track_hint),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.secondary,
                modifier = Modifier.padding(vertical = 12.dp),
            )
        }
    }
}

private fun playTrack(library: LibraryState, controller: MediaController?, index: Int) {
    val player = controller ?: return
    val tracks = library.tracks
    if (index !in tracks.indices) return
    val mediaItems = tracks.map { track ->
        androidx.media3.common.MediaItem.Builder()
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
    }
    val resumePosition = library.preferences.position(tracks[index].uri)
    player.setMediaItems(mediaItems, index, resumePosition)
    player.prepare()
    player.play()
    library.selectedIndex = index
}

@Composable
private fun TrackRow(track: AudioTrack, selected: Boolean, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(vertical = 12.dp, horizontal = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(if (selected) "▶" else "♪", color = MaterialTheme.colorScheme.primary)
        Column(Modifier.padding(start = 12.dp).weight(1f)) {
            Text(track.title, maxLines = 1, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.Medium)
            Text(
                listOfNotNull(track.artist, formatTime(track.durationMs)).joinToString(" · "),
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.secondary,
            )
        }
        if (track.subtitleUri != null || track.fileName.endsWith(".mp3", ignoreCase = true)) {
            Text("LRC", style = MaterialTheme.typography.labelSmall)
        }
    }
}

@Composable
private fun LyricsPanel(
    cues: List<SubtitleCue>,
    positionMs: Long,
    fromEmbedded: Boolean,
    preferEmbedded: Boolean,
    onPreferEmbeddedChange: (Boolean) -> Unit,
    onSeekTo: (SubtitleCue) -> Unit,
) {
    val currentIndex = cues.indexOfLast { cue ->
        positionMs >= cue.startMs && (cue.endMs == PreviewLyrics.NO_END || positionMs < cue.endMs)
    }
    val listState = rememberLazyListState()
    LaunchedEffect(currentIndex) {
        if (currentIndex >= 0) listState.animateScrollToItem(currentIndex)
    }
    Column(Modifier.fillMaxWidth().height(180.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                if (cues.isEmpty()) stringResource(R.string.no_lyrics) else if (fromEmbedded) {
                    stringResource(R.string.lyrics_source_embedded)
                } else {
                    stringResource(R.string.lyrics_source_external)
                },
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.secondary,
                modifier = Modifier.weight(1f),
            )
            Text(
                stringResource(R.string.prefer_embedded),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.secondary,
            )
            Switch(
                checked = preferEmbedded,
                onCheckedChange = onPreferEmbeddedChange,
                modifier = Modifier.padding(start = 8.dp),
            )
        }
        if (cues.isEmpty()) {
            Spacer(Modifier.height(24.dp))
            Text(
                stringResource(R.string.click_lyric_hint),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.secondary,
            )
        } else {
            LazyColumn(state = listState, modifier = Modifier.weight(1f)) {
                itemsIndexed(cues) { index, cue ->
                    val active = index == currentIndex
                    Text(
                        cue.text.ifEmpty { " " },
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = if (active) FontWeight.Bold else FontWeight.Normal,
                        color = if (active) {
                            MaterialTheme.colorScheme.primary
                        } else {
                            MaterialTheme.colorScheme.onSurface.copy(alpha = 0.72f)
                        },
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { onSeekTo(cue) }
                            .padding(vertical = 4.dp, horizontal = 4.dp),
                    )
                }
            }
        }
    }
}

@Composable
private fun PlayerCard(
    track: AudioTrack,
    isPlaying: Boolean,
    positionMs: Long,
    durationMs: Long,
    volume: Float,
    onVolumeChange: (Float) -> Unit,
    onPlayPause: () -> Unit,
    onPrevious: () -> Unit,
    onNext: () -> Unit,
    onSeekBack: () -> Unit,
    onSeekForward: () -> Unit,
    onSeek: (Long) -> Unit,
) {
    val safeDuration = durationMs.coerceAtLeast(1L)
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
        modifier = Modifier.fillMaxWidth().padding(top = 8.dp, bottom = 12.dp),
    ) {
        Column(Modifier.padding(16.dp)) {
            Text(track.title, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
            track.artist?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
            Spacer(Modifier.height(8.dp))
            Slider(
                value = positionMs.coerceIn(0L, safeDuration).toFloat(),
                onValueChange = { onSeek(it.toLong()) },
                valueRange = 0f..safeDuration.toFloat(),
            )
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(formatTime(positionMs), style = MaterialTheme.typography.labelSmall)
                Text(formatTime(durationMs), style = MaterialTheme.typography.labelSmall)
            }
            Text(
                stringResource(R.string.volume),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.secondary,
            )
            Slider(
                value = volume.coerceIn(0f, 1f),
                onValueChange = onVolumeChange,
                valueRange = 0f..1f,
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                OutlinedButton(onClick = onPrevious) { Text("⏮") }
                OutlinedButton(onClick = onSeekBack) { Text("−30s") }
                Button(onClick = onPlayPause) {
                    Text(if (isPlaying) stringResource(R.string.pause) else stringResource(R.string.play))
                }
                OutlinedButton(onClick = onSeekForward) { Text("+30s") }
                OutlinedButton(onClick = onNext) { Text("⏭") }
            }
        }
    }
}

private fun formatTime(milliseconds: Long): String {
    val totalSeconds = milliseconds.coerceAtLeast(0L) / 1_000
    val hours = totalSeconds / 3_600
    val minutes = (totalSeconds % 3_600) / 60
    val seconds = totalSeconds % 60
    return if (hours > 0) "%d:%02d:%02d".format(hours, minutes, seconds)
    else "%d:%02d".format(minutes, seconds)
}
