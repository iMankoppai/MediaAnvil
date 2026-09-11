package com.imankoppai.mediaanvil.ui

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.media.MediaMetadataRetriever
import android.net.Uri
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Cheap embedded-cover display for the UI: reads artwork through
 * MediaMetadataRetriever directly from the SAF document, without copying or
 * parsing tags. Full-fidelity cover editing lives in the tag tools.
 */
object CoverLoader {
    /** Bounded memory cache so fling-scrolling the library stops re-parsing artwork. */
    private val cache = object : android.util.LruCache<String, ImageBitmap>(128) {
        override fun sizeOf(key: String, value: ImageBitmap): Int = 1
    }

    suspend fun load(context: Context, uri: Uri): ImageBitmap? {
        cache.get(uri.toString())?.let { return it }
        val loaded = withContext(Dispatchers.IO) {
            runCatching {
                val retriever = MediaMetadataRetriever()
                try {
                    retriever.setDataSource(context, uri)
                    retriever.embeddedPicture?.let { bytes ->
                        val bitmap = decodeScaled(bytes)
                        bitmap?.asImageBitmap()
                    }
                } finally {
                    retriever.release()
                }
            }.getOrNull()
        }
        if (loaded != null) cache.put(uri.toString(), loaded)
        return loaded
    }

    /** Decode near display size to keep list thumbnails and artwork views light. */
    private fun decodeScaled(bytes: ByteArray, target: Int = 1024): Bitmap? {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
        var sample = 1
        while (bounds.outWidth / (sample * 2) >= target && bounds.outHeight / (sample * 2) >= target) {
            sample *= 2
        }
        val options = BitmapFactory.Options().apply { inSampleSize = sample }
        return BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options)
    }
}
