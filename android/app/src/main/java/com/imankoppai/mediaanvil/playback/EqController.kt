package com.imankoppai.mediaanvil.playback

import android.media.audiofx.Equalizer
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.imankoppai.mediaanvil.data.PlaybackPreferences

/**
 * Process-wide Equalizer wrapper. The playback service attaches it to the
 * player's audio session; the settings UI flips state through the same object
 * so changes apply immediately and persist.
 */
object EqController {
    private var preferences: PlaybackPreferences? = null
    private var equalizer: Equalizer? = null

    var enabled by mutableStateOf(false)
        private set
    var presets by mutableStateOf<List<String>>(emptyList())
        private set
    var selectedPreset by mutableStateOf(-1)
        private set

    fun init(preferences: PlaybackPreferences) {
        this.preferences = preferences
        enabled = preferences.eqEnabled
        selectedPreset = preferences.eqPreset
    }

    /** Attach to a player audio session; later calls are no-ops. */
    fun attach(audioSessionId: Int) {
        if (audioSessionId == 0 || equalizer != null) return
        val prefs = preferences ?: return
        runCatching {
            val effect = Equalizer(0, audioSessionId)
            equalizer = effect
            presets = (0 until effect.numberOfPresets).map { effect.getPresetName(it.toShort()) }
            runCatching { effect.enabled = prefs.eqEnabled }
            runCatching {
                if (prefs.eqPreset in 0 until effect.numberOfPresets) {
                    effect.usePreset(prefs.eqPreset.toShort())
                }
            }
            enabled = prefs.eqEnabled
            selectedPreset = prefs.eqPreset.takeIf { it in presets.indices } ?: -1
        }
    }

    fun applyEnabled(value: Boolean) {
        enabled = value
        preferences?.eqEnabled = value
        runCatching { equalizer?.enabled = value }
    }

    fun setPreset(index: Int) {
        selectedPreset = index
        preferences?.eqPreset = index
        runCatching { equalizer?.usePreset(index.toShort()) }
    }

    fun release() {
        runCatching { equalizer?.enabled = false }
        runCatching { equalizer?.release() }
        equalizer = null
        presets = emptyList()
    }
}
