package com.imankoppai.mediaanvil.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.view.KeyEvent
import android.widget.RemoteViews
import androidx.media3.common.MediaMetadata
import com.imankoppai.mediaanvil.R
import com.imankoppai.mediaanvil.playback.PlaybackService

/** Home-screen widget mirroring the playback service state. */
class PlayerWidgetProvider : AppWidgetProvider() {
    override fun onUpdate(context: Context, appWidgetManager: AppWidgetManager, appWidgetIds: IntArray) {
        refresh(context, null, false)
    }

    companion object {
        fun refresh(context: Context, metadata: MediaMetadata?, playing: Boolean) {
            val manager = AppWidgetManager.getInstance(context) ?: return
            val ids = manager.getAppWidgetIds(ComponentName(context, PlayerWidgetProvider::class.java))
            if (ids.isEmpty()) return
            val views = RemoteViews(context.packageName, R.layout.widget_player)
            views.setTextViewText(
                R.id.widget_title,
                metadata?.title?.toString() ?: context.getString(R.string.app_name),
            )
            views.setTextViewText(
                R.id.widget_artist,
                metadata?.artist?.toString() ?: context.getString(R.string.local_only),
            )
            views.setImageViewResource(
                R.id.widget_play_pause,
                if (playing) android.R.drawable.ic_media_pause else android.R.drawable.ic_media_play,
            )
            views.setOnClickPendingIntent(
                R.id.widget_prev,
                mediaButtonPendingIntent(context, KeyEvent.KEYCODE_MEDIA_PREVIOUS),
            )
            views.setOnClickPendingIntent(
                R.id.widget_play_pause,
                mediaButtonPendingIntent(context, KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE),
            )
            views.setOnClickPendingIntent(
                R.id.widget_next,
                mediaButtonPendingIntent(context, KeyEvent.KEYCODE_MEDIA_NEXT),
            )
            manager.updateAppWidget(ids, views)
        }

        /** Media key events delivered to the service are handled by MediaSessionService. */
        private fun mediaButtonPendingIntent(context: Context, keyCode: Int): PendingIntent =
            PendingIntent.getService(
                context,
                keyCode,
                Intent(context, PlaybackService::class.java)
                    .setAction(Intent.ACTION_MEDIA_BUTTON)
                    .putExtra(Intent.EXTRA_KEY_EVENT, KeyEvent(KeyEvent.ACTION_DOWN, keyCode)),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
    }
}
