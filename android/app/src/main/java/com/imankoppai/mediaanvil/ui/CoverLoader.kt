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

    suspend fun loadImage(context: Context, uri: Uri): ImageBitmap? {
        val key = "image:$uri"
        cache.get(key)?.let { return it }
        val loaded = withContext(Dispatchers.IO) {
            runCatching {
                val bitmap = if (android.os.Build.VERSION.SDK_INT >= 28) {
                    val source = android.graphics.ImageDecoder.createSource(context.contentResolver, uri)
                    android.graphics.ImageDecoder.decodeBitmap(source) { decoder, info, _ ->
                        val width = info.size.width.coerceAtLeast(1)
                        val height = info.size.height.coerceAtLeast(1)
                        val longest = maxOf(width, height)
                        if (longest > 1024) {
                            val scale = 1024f / longest
                            decoder.setTargetSize((width * scale).toInt(), (height * scale).toInt())
                        }
                    }
                } else {
                    decodeDocumentImage(context, uri)
                }
                bitmap.asImageBitmap()
            }.getOrNull()
        }
        if (loaded != null) cache.put(key, loaded)
        return loaded
    }

    private fun decodeDocumentImage(context: Context, uri: Uri, target: Int = 1024): Bitmap {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        context.contentResolver.openInputStream(uri).use { BitmapFactory.decodeStream(it, null, bounds) }
        var sample = 1
        while (bounds.outWidth / (sample * 2) >= target && bounds.outHeight / (sample * 2) >= target) {
            sample *= 2
        }
        val options = BitmapFactory.Options().apply { inSampleSize = sample }
        return requireNotNull(
            context.contentResolver.openInputStream(uri).use { BitmapFactory.decodeStream(it, null, options) },
        )
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
