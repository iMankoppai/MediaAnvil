package com.imankoppai.mediaanvil.playback

import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import androidx.core.content.IntentCompat
import android.view.KeyEvent
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.session.MediaSession
import androidx.media3.session.MediaSessionService
import androidx.media3.session.SessionCommand
import androidx.media3.session.SessionResult
import com.google.common.util.concurrent.Futures
import com.google.common.util.concurrent.ListenableFuture
import android.provider.MediaStore
import com.imankoppai.mediaanvil.data.PlaybackPreferences

@UnstableApi
class PlaybackService : MediaSessionService() {
    private var mediaSession: MediaSession? = null
    private lateinit var preferences: PlaybackPreferences
    private val handler = Handler(Looper.getMainLooper())
    private var loopStartMs = -1L
    private var loopEndMs = -1L
    private var stopAfterTrackEnd = false
    private var lastResumeSaveAt = 0L
    private var lastButtonClickAt = 0L
    private var pendingSinglePress: Runnable? = null

    private val loopTicker = object : Runnable {
        override fun run() {
            mediaSession?.player?.let { player ->
                val active = loopEndMs > loopStartMs
                val playing = player.isPlaying && player.currentPosition >= loopEndMs
                // A B point at (or past) the end lets the track finish instead
                // of crossing the marker while playing; rewind that case too.
                val finished = player.playbackState == Player.STATE_ENDED
                if (active && (playing || finished)) {
                    player.seekTo(loopStartMs)
                }
                if (player.isPlaying) {
                    val now = android.os.SystemClock.elapsedRealtime()
                    if (now - lastResumeSaveAt >= POSITION_SAVE_INTERVAL_MS) {
                        lastResumeSaveAt = now
                        saveResumeState(player)
                    }
                }
            }
            handler.postDelayed(this, LOOP_POLL_MS)
        }
    }

    /** Persists the current queue, index and position for "continue where you left off". */
    private fun saveResumeState(player: Player, force: Boolean = false) {
        if (!preferences.resumePlayback) return
        val now = android.os.SystemClock.elapsedRealtime()
        if (!force && now - lastResumeSaveAt < POSITION_SAVE_INTERVAL_MS) return
        lastResumeSaveAt = now
        val id = player.currentMediaItem?.mediaId ?: return
        val pos = player.currentPosition.coerceAtLeast(0L)
        val duration = player.duration.takeIf { it > 0 } ?: Long.MAX_VALUE
        // A track played to within a few seconds of its end counts as finished.
        android.util.Log.d("MediaAnvilSave", "save id=$id pos=$pos dur=$duration")
        if (pos >= duration - 15_000L) preferences.setPlaybackPosition(id, -1L)
        else if (pos > 3_000L) preferences.setPlaybackPosition(id, pos)
        val uris = (0 until player.mediaItemCount).map { player.getMediaItemAt(it).mediaId }
        preferences.lastQueueUris = org.json.JSONArray(uris).toString()
        preferences.lastQueueIndex = player.currentMediaItemIndex
    }

    private val wrapAroundListener = object : Player.Listener {
        override fun onPlaybackStateChanged(playbackState: Int) {
            val player = mediaSession?.player ?: return
            // Sequential playback returns to the top of the list after the
            // last track instead of stopping at the end. An active A/B loop
            // wins: its own ticker rewinds the finished track.
            val loopActive = loopEndMs > loopStartMs
            if (playbackState == Player.STATE_ENDED &&
                !stopAfterTrackEnd &&
                !loopActive &&
                player.repeatMode == Player.REPEAT_MODE_OFF &&
                player.mediaItemCount > 1 &&
                player.currentMediaItemIndex == player.mediaItemCount - 1
            ) {
                player.seekTo(0, 0)
                player.play()
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        preferences = PlaybackPreferences(this)
        val audioAttributes = AudioAttributes.Builder()
            .setContentType(C.AUDIO_CONTENT_TYPE_MUSIC)
            .setUsage(C.USAGE_MEDIA)
            .build()
        val player = ExoPlayer.Builder(this)
            .setAudioAttributes(audioAttributes, true)
            .build()
        player.addListener(object : Player.Listener {
            override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
                clearLoop()
            }
        })
        player.addListener(wrapAroundListener)
        player.addListener(object : Player.Listener {
            override fun onIsPlayingChanged(isPlaying: Boolean) {
                if (!isPlaying) {
                    mediaSession?.player?.let { saveResumeState(it, force = true) }
                }
                updateWidget()
            }

            override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
                updateWidget()
            }
        })
        restoreLastQueue()
        // The ticker doubles as the periodic position saver, so it runs always.
        handler.postDelayed(loopTicker, LOOP_POLL_MS)
        mediaSession = MediaSession.Builder(this, player)
            .setCallback(object : MediaSession.Callback {
                override fun onConnect(
                    session: MediaSession,
                    controllerInfo: MediaSession.ControllerInfo,
                ): MediaSession.ConnectionResult {
                    val sessionCommands = MediaSession.ConnectionResult.DEFAULT_SESSION_COMMANDS.buildUpon()
                        .add(SessionCommand(COMMAND_LOOP_A, Bundle.EMPTY))
                        .add(SessionCommand(COMMAND_LOOP_B, Bundle.EMPTY))
                        .add(SessionCommand(COMMAND_LOOP_CLEAR, Bundle.EMPTY))
                        .add(SessionCommand(COMMAND_STOP_AFTER_ON, Bundle.EMPTY))
                        .add(SessionCommand(COMMAND_STOP_AFTER_OFF, Bundle.EMPTY))
                        .build()
                    return MediaSession.ConnectionResult.accept(
                        sessionCommands,
                        MediaSession.ConnectionResult.DEFAULT_PLAYER_COMMANDS,
                    )
                }

                override fun onMediaButtonEvent(
                    session: MediaSession,
                    controllerInfo: MediaSession.ControllerInfo,
                    intent: Intent,
                ): Boolean {
                    val event = IntentCompat.getParcelableExtra(
                        intent,
                        Intent.EXTRA_KEY_EVENT,
                        KeyEvent::class.java,
                    )
                    if (event?.action == KeyEvent.ACTION_DOWN &&
                        (event.keyCode == KeyEvent.KEYCODE_HEADSETHOOK ||
                            event.keyCode == KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE)
                    ) {
                        handlePlayPauseClick(player)
                        return true
                    }
                    return super.onMediaButtonEvent(session, controllerInfo, intent)
                }

                override fun onCustomCommand(
                    session: MediaSession,
                    controllerInfo: MediaSession.ControllerInfo,
                    command: SessionCommand,
                    args: Bundle,
                ): ListenableFuture<SessionResult> {
                    when (command.customAction) {
                        COMMAND_LOOP_A -> {
                            loopStartMs = player.currentPosition
                            loopEndMs = -1
                        }
                        COMMAND_LOOP_B -> {
                            loopEndMs = player.currentPosition
                            if (loopStartMs < 0) loopStartMs = 0
                        }
                        COMMAND_LOOP_CLEAR -> clearLoop()
                        COMMAND_STOP_AFTER_ON -> stopAfterTrackEnd = true
                        COMMAND_STOP_AFTER_OFF -> stopAfterTrackEnd = false
                    }
                    return Futures.immediateFuture(SessionResult(SessionResult.RESULT_SUCCESS))
                }
            })
            .build()
    }

    /** Single press toggles playback (after the double-press window); double press runs the configured action. */
    private fun handlePlayPauseClick(player: Player) {
        val now = SystemClock.elapsedRealtime()
        if (now - lastButtonClickAt <= DOUBLE_PRESS_WINDOW_MS) {
            lastButtonClickAt = 0
            pendingSinglePress?.let { handler.removeCallbacks(it) }
            pendingSinglePress = null
            when (preferences.doublePressAction) {
                "previous" -> player.seekToPreviousMediaItem()
                "pause" -> player.pause()
                else -> player.seekToNextMediaItem()
            }
            return
        }
        lastButtonClickAt = now
        val toggle = Runnable {
            player.playWhenReady = !player.playWhenReady
            lastButtonClickAt = 0
        }
        pendingSinglePress = toggle
        handler.postDelayed(toggle, DOUBLE_PRESS_WINDOW_MS)
    }

    /** Rebuilds the last queue (paused) after a reboot or process death. */
    private fun restoreLastQueue() {
        android.util.Log.d("MediaAnvilRestore", "restore called, resume=${preferences.resumePlayback} uris=${preferences.lastQueueUris.take(60)} index=${preferences.lastQueueIndex}")
        if (!preferences.resumePlayback) return
        val uris = runCatching {
            val array = org.json.JSONArray(preferences.lastQueueUris)
            (0 until array.length()).map { array.getString(it) }
        }.getOrDefault(emptyList())
        val savedIndex = preferences.lastQueueIndex
        android.util.Log.d("MediaAnvilSave", "restore uris=$uris index=$savedIndex")
        if (uris.isEmpty() || savedIndex !in uris.indices) return
        Thread {
            val metadata = mutableMapOf<String, Triple<String, String?, String?>>()
            runCatching {
                val projection = arrayOf(
                    MediaStore.Audio.Media._ID,
                    MediaStore.Audio.Media.TITLE,
                    MediaStore.Audio.Media.ARTIST,
                    MediaStore.Audio.Media.ALBUM,
                )
                // Same collections the library scanner uses, so restored URIs match saved ones.
                val collections = MediaStore.getExternalVolumeNames(applicationContext)
                    .map(MediaStore.Audio.Media::getContentUri)
                    .ifEmpty { listOf(MediaStore.Audio.Media.EXTERNAL_CONTENT_URI) }
                for (collection in collections) {
                    applicationContext.contentResolver.query(
                        collection, projection, null, null, null,
                    )?.use { cursor ->
                        val idColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media._ID)
                        val titleColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.TITLE)
                        val artistColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.ARTIST)
                        val albumColumn = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.ALBUM)
                        while (cursor.moveToNext()) {
                            val id = collection.buildUpon()
                                .appendPath(cursor.getLong(idColumn).toString())
                                .build()
                                .toString()
                            metadata[id] = Triple(
                                cursor.getString(titleColumn).orEmpty(),
                                cursor.getString(artistColumn)?.takeIf(String::isNotBlank),
                                cursor.getString(albumColumn)?.takeIf(String::isNotBlank),
                            )
                        }
                    }
                }
            }
            handler.post {
                val player = mediaSession?.player ?: return@post
                if (player.currentMediaItem != null) return@post
                val items = mutableListOf<MediaItem>()
                var restoredIndex = -1
                uris.forEachIndexed { position, id ->
                    val found = metadata[id]
                    if (found != null) {
                        if (position == savedIndex) restoredIndex = items.size
                        items += MediaItem.Builder()
                            .setUri(android.net.Uri.parse(id))
                            .setMediaId(id)
                            .setMediaMetadata(
                                MediaMetadata.Builder()
                                    .setTitle(found.first)
                                    .setArtist(found.second)
                                    .setAlbumTitle(found.third)
                                    .build(),
                            )
                            .build()
                    }
                }
                if (items.isEmpty()) return@post
                val start = restoredIndex.coerceIn(0, items.size - 1)
                val savedPos = preferences.playbackPositionFor(uris[savedIndex.coerceAtLeast(0)])
                android.util.Log.d("MediaAnvilRestore", "restoring ${items.size} items at $start pos=$savedPos")
                player.setMediaItems(items, start, savedPos.takeIf { it > 0L } ?: androidx.media3.common.C.TIME_UNSET)
                player.prepare()
                updateWidget()
            }
        }.start()
    }

    private fun updateWidget() {
        val player = mediaSession?.player ?: return
        com.imankoppai.mediaanvil.widget.PlayerWidgetProvider.refresh(
            applicationContext,
            player.currentMediaItem?.mediaMetadata,
            player.isPlaying,
        )
    }

    private fun clearLoop() {
        loopStartMs = -1
        loopEndMs = -1
        // The ticker stays scheduled: it also persists the playback position.
    }

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo): MediaSession? = mediaSession

    override fun onDestroy() {
        clearLoop()
        mediaSession?.run {
            player.release()
            release()
        }
        mediaSession = null
        super.onDestroy()
    }

    companion object {
        const val COMMAND_LOOP_A = "com.imankoppai.mediaanvil.LOOP_A"
        const val COMMAND_LOOP_B = "com.imankoppai.mediaanvil.LOOP_B"
        const val COMMAND_LOOP_CLEAR = "com.imankoppai.mediaanvil.LOOP_CLEAR"
        const val COMMAND_STOP_AFTER_ON = "com.imankoppai.mediaanvil.STOP_AFTER_ON"
        const val COMMAND_STOP_AFTER_OFF = "com.imankoppai.mediaanvil.STOP_AFTER_OFF"
        private const val DOUBLE_PRESS_WINDOW_MS = 350L
        private const val LOOP_POLL_MS = 250L
        private const val POSITION_SAVE_INTERVAL_MS = 5_000L
    }
}
