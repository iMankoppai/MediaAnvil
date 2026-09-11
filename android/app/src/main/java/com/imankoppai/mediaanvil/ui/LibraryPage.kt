package com.imankoppai.mediaanvil.ui

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
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.MusicNote
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.QueueMusic
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.imankoppai.mediaanvil.R
import com.imankoppai.mediaanvil.model.AudioTrack
import com.imankoppai.mediaanvil.subtitles.PreviewLyrics
import com.imankoppai.mediaanvil.subtitles.SubtitleLoader
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext

private val libraryTabs = listOf(
    R.string.tab_music,
    R.string.tab_folders,
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun LibraryPage(
    library: LibraryState,
    controller: androidx.media3.session.MediaController?,
    onPickFolder: () -> Unit,
    onOpenNowPlaying: () -> Unit,
    onOpenEditor: (AudioTrack) -> Unit,
) {
    val context = LocalContext.current
    var selectedTab by remember { mutableStateOf(0) }
    var searchOpen by remember { mutableStateOf(false) }
    var searchQuery by remember { mutableStateOf("") }
    var menuOpen by remember { mutableStateOf(false) }
    var isPlaying by remember { mutableStateOf(false) }
    var toolsTrack by remember { mutableStateOf<AudioTrack?>(null) }
    var openFolder by remember { mutableStateOf<String?>(null) }
    var queueOpen by remember { mutableStateOf(false) }

    LaunchedEffect(controller) {
        while (true) {
            delay(500)
            controller?.let { player ->
                isPlaying = player.isPlaying
                if (player.currentMediaItem != null && player.currentMediaItemIndex in library.tracks.indices) {
                    library.selectedIndex = player.currentMediaItemIndex
                    library.preferences.savePosition(
                        library.tracks[player.currentMediaItemIndex].uri,
                        player.currentPosition,
                    )
                }
            }
        }
    }

    var sortMode by remember { mutableStateOf(library.preferences.librarySort) }

    val filtered = remember(library.tracks, searchQuery, sortMode) {
        val matched = library.tracks.filter { track ->
            val query = searchQuery.trim()
            query.isEmpty() ||
                track.title.contains(query, ignoreCase = true) ||
                track.artist?.contains(query, ignoreCase = true) == true ||
                track.fileName.contains(query, ignoreCase = true)
        }
        when (sortMode) {
            "title" -> matched.sortedBy { it.title.lowercase() }
            "duration" -> matched.sortedBy { it.durationMs }
            else -> matched.sortedBy { it.fileName.lowercase() }
        }
    }

    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        Column(Modifier.fillMaxSize()) {
        TopBar(
            searchOpen = searchOpen,
            searchQuery = searchQuery,
            onSearchOpenChange = { searchOpen = it },
            onSearchQueryChange = { searchQuery = it },
            menuOpen = menuOpen,
            onMenuOpenChange = { menuOpen = it },
            onPickFolder = onPickFolder,
            onRescan = { library.rescan() },
            sortLabelText = sortLabel(sortMode),
            onSortCycle = {
                sortMode = when (sortMode) {
                    "fileName" -> "title"
                    "title" -> "duration"
                    else -> "fileName"
                }
                library.preferences.librarySort = sortMode
            },
        )

        TabRow(
            selectedTabIndex = selectedTab,
            containerColor = MaterialTheme.colorScheme.background,
            contentColor = MaterialTheme.colorScheme.primary,
            modifier = Modifier.padding(horizontal = 8.dp),
        ) {
            libraryTabs.forEachIndexed { index, titleRes ->
                Tab(
                    selected = selectedTab == index,
                    onClick = { selectedTab = index },
                    text = { Text(stringResource(titleRes), fontWeight = FontWeight.SemiBold) },
                )
            }
        }

        if (selectedTab == 1) {
            FolderView(
                library = library,
                openFolder = openFolder,
                onOpenFolder = { openFolder = it },
                onOpenTrackTools = { toolsTrack = it },
                controller = controller,
            )
        } else {
            Column(Modifier.fillMaxSize()) {
                if (library.loading) {
                    LinearProgressIndicator(Modifier.fillMaxWidth().padding(top = 8.dp))
                }
                library.message?.let {
                    Text(
                        it,
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                    )
                }
                library.playbackError?.let {
                    Text(
                        it,
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                    )
                }

                when {
                    library.tracks.isEmpty() && !library.loading -> EmptyLibrary(onPickFolder)
                    filtered.isEmpty() -> SectionPlaceholder(stringResource(R.string.no_tracks))
                    else -> {
                        LazyColumn(Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
                            itemsIndexed(filtered, key = { _, track -> track.uri.toString() }) { _, track ->
                                TrackRow(
                                    track = track,
                                    current = track.uri == library.selectedTrack?.uri,
                                    onClick = {
                                        val index = filtered.indexOf(track)
                                        playFromLibrary(library, controller, index, filtered)
                                    },
                                    onOpenTools = { toolsTrack = track },
                                )
                            }
                            item { Spacer(Modifier.height(96.dp)) }
                        }
                    }
                }
            }
        }
    }

    val currentTrack = library.selectedTrack
    currentTrack?.let {
        MiniPlayer(
            track = it,
            isPlaying = isPlaying,
            onToggle = {
                val player = controller
                if (player?.isPlaying == true) player.pause() else player?.play()
            },
            onOpen = onOpenNowPlaying,
            onQueue = { queueOpen = true },
            modifier = Modifier.align(Alignment.BottomCenter),
        )
    }
    }

    if (queueOpen) {
        QueueSheet(library, controller, onDismiss = { queueOpen = false })
    }

    toolsTrack?.let { selected ->
        ToolsSheet(
            library = library,
            track = selected,
            onDismiss = { toolsTrack = null },
            onOpenEditor = {
                toolsTrack = null
                onOpenEditor(it)
            },
        )
    }
}

@Composable
private fun TopBar(
    searchOpen: Boolean,
    searchQuery: String,
    onSearchOpenChange: (Boolean) -> Unit,
    onSearchQueryChange: (String) -> Unit,
    menuOpen: Boolean,
    onMenuOpenChange: (Boolean) -> Unit,
    onPickFolder: () -> Unit,
    onRescan: () -> Unit,
    onSortCycle: () -> Unit,
    sortLabelText: String,
) {
    Surface(color = MaterialTheme.colorScheme.background) {
        Column {
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text(
                        "MediaAnvil",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                    )
                    Text(
                        "Your Media. Your Tools. Locally.",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.secondary,
                    )
                }
                IconButton(onClick = { onSearchOpenChange(!searchOpen) }) {
                    Icon(Icons.Filled.Search, contentDescription = stringResource(R.string.search))
                }
                Box {
                    IconButton(onClick = { onMenuOpenChange(true) }) {
                        Icon(Icons.Filled.MoreVert, contentDescription = null)
                    }
                    DropdownMenu(expanded = menuOpen, onDismissRequest = { onMenuOpenChange(false) }) {
                        DropdownMenuItem(
                            text = { Text(stringResource(R.string.sort_menu_label, sortLabelText)) },
                            onClick = {
                                onMenuOpenChange(false)
                                onSortCycle()
                            },
                        )
                        DropdownMenuItem(
                            text = { Text(stringResource(R.string.choose_folder)) },
                            onClick = {
                                onMenuOpenChange(false)
                                onPickFolder()
                            },
                        )
                        DropdownMenuItem(
                            text = { Text(stringResource(R.string.rescan)) },
                            onClick = {
                                onMenuOpenChange(false)
                                onRescan()
                            },
                        )
                    }
                }
            }
            if (searchOpen) {
                OutlinedTextField(
                    value = searchQuery,
                    onValueChange = onSearchQueryChange,
                    placeholder = { Text(stringResource(R.string.search_hint)) },
                    singleLine = true,
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp).padding(bottom = 8.dp),
                )
            }
        }
    }
}

@Composable
private fun FolderView(
    library: LibraryState,
    openFolder: String?,
    onOpenFolder: (String?) -> Unit,
    onOpenTrackTools: (AudioTrack) -> Unit,
    controller: androidx.media3.session.MediaController?,
) {
    if (openFolder == null) {
        val folders = remember(library.tracks) {
            library.tracks.groupBy { it.parentPath }
                .map { (path, tracks) -> path to tracks }
                .sortedBy { it.first }
        }
        if (folders.isEmpty()) {
            SectionPlaceholder(stringResource(R.string.no_tracks))
        } else {
            LazyColumn(Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
                itemsIndexed(folders) { _, folder ->
                    val (path, tracks) = folder
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(14.dp))
                            .clickable { onOpenFolder(path) }
                            .padding(horizontal = 8.dp, vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Icon(Icons.Filled.Folder, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text(
                                path.ifEmpty { stringResource(R.string.folder_root) },
                                style = MaterialTheme.typography.bodyLarge,
                                fontWeight = FontWeight.SemiBold,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                            Text(
                                stringResource(R.string.folder_track_count, tracks.size),
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        Icon(
                            Icons.Filled.KeyboardArrowRight,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                item { Spacer(Modifier.height(96.dp)) }
            }
        }
    } else {
        Column(Modifier.fillMaxSize()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onOpenFolder(null) }
                    .padding(horizontal = 16.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(
                    Icons.Filled.ArrowBack,
                    contentDescription = stringResource(R.string.back),
                    tint = MaterialTheme.colorScheme.primary,
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    openFolder.ifEmpty { stringResource(R.string.folder_root) },
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            val folderTracks = library.tracks.filter { it.parentPath == openFolder }
            LazyColumn(Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
                itemsIndexed(folderTracks, key = { _, track -> track.uri.toString() }) { _, track ->
                    TrackRow(
                        track = track,
                        current = track.uri == library.selectedTrack?.uri,
                        onClick = { playFromLibrary(library, controller, folderTracks.indexOf(track), folderTracks) },
                        onOpenTools = { onOpenTrackTools(track) },
                    )
                }
                item { Spacer(Modifier.height(96.dp)) }
            }
        }
    }
}

@Composable
private fun TrackRow(
    track: AudioTrack,
    current: Boolean,
    onClick: () -> Unit,
    onOpenTools: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(if (current) MaterialTheme.colorScheme.primaryContainer else Color.Transparent)
            .clickable(onClick = onClick)
            .padding(horizontal = 8.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        TrackCover(track, size = 52.dp)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(
                track.title,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                track.artist ?: stringResource(R.string.unknown_artist),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.secondary,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                "${formatLabel(track)} · ${formatTime(track.durationMs)}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        IconButton(onClick = onOpenTools) {
            Icon(
                Icons.Filled.MoreVert,
                contentDescription = stringResource(R.string.media_tools),
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
internal fun TrackCover(track: AudioTrack, size: androidx.compose.ui.unit.Dp, corner: Int = 12) {
    val context = LocalContext.current
    var cover by remember(track.uri) { mutableStateOf<androidx.compose.ui.graphics.ImageBitmap?>(null) }
    LaunchedEffect(track.uri) {
        cover = CoverLoader.load(context, track.uri)
    }
    Box(
        modifier = Modifier
            .size(size)
            .clip(RoundedCornerShape(corner.dp))
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
                Icons.Filled.MusicNote,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
            )
        }
    }
}

@Composable
private fun MiniPlayer(
    track: AudioTrack,
    isPlaying: Boolean,
    onToggle: () -> Unit,
    onOpen: () -> Unit,
    onQueue: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Surface(
        color = MaterialTheme.colorScheme.surface,
        shadowElevation = 10.dp,
        shape = RoundedCornerShape(22.dp),
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 8.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable(onClick = onOpen)
                .padding(horizontal = 10.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TrackCover(track, size = 44.dp)
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    track.title,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    track.artist ?: stringResource(R.string.unknown_artist),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.secondary,
                    maxLines = 1,
                )
            }
            IconButton(onClick = onToggle) {
                Icon(
                    if (isPlaying) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                    contentDescription = stringResource(if (isPlaying) R.string.pause else R.string.play),
                    tint = MaterialTheme.colorScheme.primary,
                )
            }
            IconButton(onClick = onQueue) {
                Icon(
                    Icons.Filled.QueueMusic,
                    contentDescription = stringResource(R.string.play_queue),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun EmptyLibrary(onPickFolder: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Icon(
            Icons.Filled.MusicNote,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.primary,
            modifier = Modifier.size(64.dp),
        )
        Spacer(Modifier.height(12.dp))
        Text(stringResource(R.string.choose_folder_hint), style = MaterialTheme.typography.bodyMedium)
        Spacer(Modifier.height(16.dp))
        Button(onClick = onPickFolder) { Text(stringResource(R.string.choose_folder)) }
    }
}

@Composable
internal fun SectionPlaceholder(text: String) {
    Box(Modifier.fillMaxSize().padding(32.dp), contentAlignment = Alignment.Center) {
        Text(text, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

internal fun formatLabel(track: AudioTrack): String =
    track.fileName.substringAfterLast('.', "").uppercase().ifEmpty { "AUDIO" }

@Composable
internal fun sortLabel(mode: String): String = when (mode) {
    "title" -> stringResource(R.string.sort_title)
    "duration" -> stringResource(R.string.sort_duration)
    else -> stringResource(R.string.sort_file_name)
}

internal fun formatTime(milliseconds: Long): String {
    val totalSeconds = milliseconds.coerceAtLeast(0L) / 1_000
    val hours = totalSeconds / 3_600
    val minutes = (totalSeconds % 3_600) / 60
    val seconds = totalSeconds % 60
    return if (hours > 0) "%d:%02d:%02d".format(hours, minutes, seconds)
    else "%d:%02d".format(minutes, seconds)
}


internal fun playFromLibrary(
    library: LibraryState,
    controller: androidx.media3.session.MediaController?,
    index: Int,
    queue: List<AudioTrack>,
    shuffle: Boolean = false,
) {
    val player = controller ?: return
    library.playbackError = null
    if (queue.isEmpty() || index !in queue.indices) return
    val mediaItems = queue.map { track ->
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
    val resumePosition = library.preferences.position(queue[index].uri)
    player.setMediaItems(mediaItems, index, resumePosition)
    player.shuffleModeEnabled = shuffle
    player.prepare()
    player.play()
    library.selectedIndex = library.tracks.indexOfFirst { it.uri == queue[index].uri }
}
