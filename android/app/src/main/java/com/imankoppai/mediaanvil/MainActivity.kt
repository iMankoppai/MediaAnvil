package com.imankoppai.mediaanvil

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.core.view.WindowCompat
import com.imankoppai.mediaanvil.ui.MediaAnvilApp
import com.imankoppai.mediaanvil.ui.theme.MediaAnvilTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        setContent {
            MediaAnvilTheme {
                MediaAnvilApp()
            }
        }
    }
}
