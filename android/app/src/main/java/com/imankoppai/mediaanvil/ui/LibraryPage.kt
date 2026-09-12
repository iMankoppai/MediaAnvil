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
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Album
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.MusicNote
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.QueueMusic
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
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
import androidx.compose.ui.graphics.vector.ImageVector
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
    R.string.tab_recent,
    R.string.tab_favorites,
    R.string.tab_folders,
)

private enum class MusicView { Songs, Albums, Artists }

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
    var musicView by remember { mutableStateOf(MusicView.Songs) }
    var openGroup by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(controller) {
        while (true) {
            delay(500)
            controller?.let { player ->
                isPlaying = player.isPlaying
                if (player.currentMediaItem != null && player.currentMediaItemIndex in library.tracks.indices) {
                    library.selectedIndex = player.currentMediaItemIndex
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

    val recentTracks = remember(library.recentUris, library.tracks) {
        library.recentUris.mapNotNull { uri -> library.tracks.firstOrNull { it.uri.toString() == uri } }
    }
    val favoriteTracks = remember(library.favorites, library.tracks) {
        library.tracks.filter { it.uri.toString() in library.favorites }
    }
    val unknownAlbumLabel = stringResource(R.string.unknown_album)
    val unknownArtistLabel = stringResource(R.string.unknown_artist)
    val albumGroups = remember(library.tracks, unknownAlbumLabel) {
        library.tracks.groupBy { track -> track.album?.takeIf { album -> album.isNotBlank() } ?: unknownAlbumLabel }
            .map { (name, tracks) -> name to tracks }
            .sortedBy { it.first.lowercase() }
    }
    val artistGroups = remember(library.tracks, unknownArtistLabel) {
        library.tracks.groupBy { track -> track.artist?.takeIf { artist -> artist.isNotBlank() } ?: unknownArtistLabel }
            .map { (name, tracks) -> name to tracks }
            .sortedBy { it.first.lowercase() }
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

        when (selectedTab) {
            3 -> FolderView(
                library = library,
                onPickFolder = onPickFolder,
                openFolder = openFolder,
                onOpenFolder = { openFolder = it },
                onOpenTrackTools = { toolsTrack = it },
                controller = controller,
            )
            1 -> TrackListView(
                tracks = recentTracks,
                library = library,
                controller = controller,
                emptyText = stringResource(R.string.recent_empty),
                onOpenTools = { toolsTrack = it },
            )
            2 -> TrackListView(
                tracks = favoriteTracks,
                library = library,
                controller = controller,
                emptyText = stringResource(R.string.favorites_empty),
                onOpenTools = { toolsTrack = it },
            )
            else -> Column(Modifier.fillMaxSize()) {
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
                    else -> {
                        Row(
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                        ) {
                            FilterChip(
                                selected = musicView == MusicView.Songs,
                                onClick = {
                                    musicView = MusicView.Songs
                                    openGroup = null
                                },
                                label = { Text(stringResource(R.string.view_songs)) },
                            )
                            FilterChip(
                                selected = musicView == MusicView.Albums,
                                onClick = {
                                    musicView = MusicView.Albums
                                    openGroup = null
                                },
                                label = { Text(stringResource(R.string.view_albums)) },
                            )
                            FilterChip(
                                selected = musicView == MusicView.Artists,
                                onClick = {
                                    musicView = MusicView.Artists
                                    openGroup = null
                                },
                                label = { Text(stringResource(R.string.view_artists)) },
                            )
                        }
                        when (musicView) {
                            MusicView.Songs -> if (filtered.isEmpty()) {
                                SectionPlaceholder(stringResource(R.string.no_tracks))
                            } else {
                                LazyColumn(Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
                                    itemsIndexed(filtered, key = { _, track -> track.uri.toString() }) { _, track ->
                                        TrackRow(
                                            track = track,
                                            current = track.uri == library.selectedTrack?.uri,
                                            favorite = library.isFavorite(track.uri),
                                            onToggleFavorite = { library.toggleFavorite(track.uri) },
                                            onClick = { playFromLibrary(library, controller, filtered.indexOf(track), filtered) },
                                            onOpenTools = { toolsTrack = track },
                                        )
                                    }
                                    item { Spacer(Modifier.height(96.dp)) }
                                }
                            }
                            MusicView.Albums -> GroupBrowser(
                                groups = albumGroups,
                                openGroup = openGroup,
                                onOpenGroup = { openGroup = it },
                                groupIcon = Icons.Filled.Album,
                                library = library,
                                controller = controller,
                                onOpenTools = { toolsTrack = it },
                            )
                            MusicView.Artists -> GroupBrowser(
                                groups = artistGroups,
                                openGroup = openGroup,
                                onOpenGroup = { openGroup = it },
                                groupIcon = Icons.Filled.Person,
                                library = library,
                                controller = controller,
                                onOpenTools = { toolsTrack = it },
                            )
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
    onPickFolder: () -> Unit,
    openFolder: String?,
    onOpenFolder: (String?) -> Unit,
    onOpenTrackTools: (AudioTrack) -> Unit,
    controller: androidx.media3.session.MediaController?,
) {
    if (openFolder == null) {
        Column(Modifier.fillMaxSize()) {
        Row(
            verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp),
        ) {
            Text(
                stringResource(R.string.folder_roots),
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.weight(1f),
            )
            androidx.compose.material3.TextButton(onClick = onPickFolder) {
                Icon(Icons.Filled.Add, contentDescription = null)
                Spacer(Modifier.width(4.dp))
                Text(stringResource(R.string.folder_add))
            }
        }
        library.folders.forEach { root ->
            Row(
                verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
            ) {
                Icon(
                    Icons.Filled.Folder,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.padding(end = 8.dp),
                )
                Text(
                    root.lastPathSegment ?: root.toString(),
                    style = MaterialTheme.typography.labelMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f),
                )
                IconButton(onClick = { library.removeFolder(root) }) {
                    Icon(
                        Icons.Filled.Close,
                        contentDescription = stringResource(R.string.folder_remove),
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
        Spacer(Modifier.height(8.dp))
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
                        favorite = library.isFavorite(track.uri),
                        onToggleFavorite = { library.toggleFavorite(track.uri) },
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
private fun TrackListView(
    tracks: List<AudioTrack>,
    library: LibraryState,
    controller: androidx.media3.session.MediaController?,
    emptyText: String,
    onOpenTools: (AudioTrack) -> Unit,
) {
    if (tracks.isEmpty()) {
        SectionPlaceholder(emptyText)
    } else {
        LazyColumn(Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
            itemsIndexed(tracks, key = { _, track -> track.uri.toString() }) { _, track ->
                TrackRow(
                    track = track,
                    current = track.uri == library.selectedTrack?.uri,
                    favorite = library.isFavorite(track.uri),
                    onToggleFavorite = { library.toggleFavorite(track.uri) },
                    onClick = { playFromLibrary(library, controller, tracks.indexOf(track), tracks) },
                    onOpenTools = { onOpenTools(track) },
                )
            }
            item { Spacer(Modifier.height(96.dp)) }
        }
    }
}

@Composable
private fun GroupBrowser(
    groups: List<Pair<String, List<AudioTrack>>>,
    openGroup: String?,
    onOpenGroup: (String?) -> Unit,
    groupIcon: ImageVector,
    library: LibraryState,
    controller: androidx.media3.session.MediaController?,
    onOpenTools: (AudioTrack) -> Unit,
) {
    if (openGroup == null) {
        LazyColumn(Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
            itemsIndexed(groups, key = { _, group -> group.first }) { _, group ->
                val (name, tracks) = group
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(14.dp))
                        .clickable { onOpenGroup(name) }
                        .padding(horizontal = 8.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(groupIcon, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(
                            name,
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
    } else {
        Column(Modifier.fillMaxSize()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onOpenGroup(null) }
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
                    openGroup,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            val groupTracks = groups.firstOrNull { it.first == openGroup }?.second ?: emptyList()
            LazyColumn(Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
                itemsIndexed(groupTracks, key = { _, track -> track.uri.toString() }) { _, track ->
                    TrackRow(
                        track = track,
                        current = track.uri == library.selectedTrack?.uri,
                        favorite = library.isFavorite(track.uri),
                        onToggleFavorite = { library.toggleFavorite(track.uri) },
                        onClick = { playFromLibrary(library, controller, groupTracks.indexOf(track), groupTracks) },
                        onOpenTools = { onOpenTools(track) },
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
    favorite: Boolean,
    onToggleFavorite: (() -> Unit)?,
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
        onToggleFavorite?.let { toggle ->
            IconButton(onClick = toggle) {
                Icon(
                    if (favorite) Icons.Filled.Favorite else Icons.Filled.FavoriteBorder,
                    contentDescription = stringResource(if (favorite) R.string.unfavorite else R.string.favorite),
                    tint = if (favorite) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
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
    player.setMediaItems(mediaItems, index, androidx.media3.common.C.TIME_UNSET)
    player.shuffleModeEnabled = shuffle
    player.prepare()
    player.play()
    library.selectedIndex = library.tracks.indexOfFirst { it.uri == queue[index].uri }
}
