package com.imankoppai.mediaanvil

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.core.view.WindowCompat
import com.imankoppai.mediaanvil.data.PlaybackPreferences
import com.imankoppai.mediaanvil.ui.MediaAnvilApp
import com.imankoppai.mediaanvil.ui.theme.MediaAnvilTheme
import com.imankoppai.mediaanvil.ui.theme.ThemeController
import com.imankoppai.mediaanvil.ui.theme.ThemeSeed

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        ThemeController.load(PlaybackPreferences(this))
        setContent {
            val darkTheme = when (ThemeController.mode) {
                "light" -> false
                "dark" -> true
                else -> isSystemInDarkTheme()
            }
            val seed = if (ThemeController.useCoverColor) ThemeSeed.coverColor else null
            WindowCompat.getInsetsController(window, window.decorView).apply {
                isAppearanceLightStatusBars = !darkTheme
                isAppearanceLightNavigationBars = !darkTheme
            }
            MediaAnvilTheme(
                darkTheme = darkTheme,
                useDynamicColor = ThemeController.useDynamicColor,
                seedColor = seed,
            ) {
                MediaAnvilApp()
            }
        }
    }
}
