package com.imankoppai.mediaanvil.playback

import android.media.audiofx.LoudnessEnhancer

/** Session loudness boost; gain in whole dB, 0 = bypassed. */
object LoudnessGain {
    private var enhancer: LoudnessEnhancer? = null

    fun attach(audioSessionId: Int, gainDb: Int) {
        if (audioSessionId == 0) return
        release()
        runCatching {
            val effect = LoudnessEnhancer(audioSessionId)
            effect.setTargetGain(gainDb * 100) // millibels
            effect.enabled = gainDb > 0
            enhancer = effect
        }
    }

    fun setGain(gainDb: Int) {
        val effect = enhancer ?: return
        runCatching {
            effect.setTargetGain(gainDb * 100)
            effect.enabled = gainDb > 0
        }
    }

    fun release() {
        val effect = enhancer ?: return
        runCatching { effect.enabled = false }
        runCatching { effect.release() }
        enhancer = null
    }
}
