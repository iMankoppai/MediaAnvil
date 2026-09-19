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
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.session.MediaSession
import androidx.media3.session.MediaSessionService
import androidx.media3.session.SessionCommand
import androidx.media3.session.SessionResult
import com.google.common.util.concurrent.Futures
import com.google.common.util.concurrent.ListenableFuture
import com.imankoppai.mediaanvil.data.PlaybackPreferences

@UnstableApi
class PlaybackService : MediaSessionService() {
    private var mediaSession: MediaSession? = null
    private lateinit var preferences: PlaybackPreferences
    private val handler = Handler(Looper.getMainLooper())
    private var loopStartMs = -1L
    private var loopEndMs = -1L
    private var stopAfterTrackEnd = false
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
            }
            handler.postDelayed(this, LOOP_POLL_MS)
        }
    }

    private val wrapAroundListener = object : Player.Listener {
        override fun onPlaybackStateChanged(playbackState: Int) {
            val player = mediaSession?.player ?: return
            // Sequential playback returns to the top of the list after the
            // last track instead of stopping at the end.
            if (playbackState == Player.STATE_ENDED &&
                !stopAfterTrackEnd &&
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
                    if (loopEndMs >= 0 && loopStartMs in 0 until loopEndMs) {
                        handler.removeCallbacks(loopTicker)
                        handler.postDelayed(loopTicker, LOOP_POLL_MS)
                    } else if (loopEndMs < 0) {
                        handler.removeCallbacks(loopTicker)
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

    private fun clearLoop() {
        loopStartMs = -1
        loopEndMs = -1
        handler.removeCallbacks(loopTicker)
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
    }
}
