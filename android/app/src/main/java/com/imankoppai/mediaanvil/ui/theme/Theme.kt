package com.imankoppai.mediaanvil.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = Color(0xFF1677FF),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFD8E8FF),
    onPrimaryContainer = Color(0xFF082B62),
    secondary = Color(0xFF43536D),
    background = Color(0xFFF4F8FF),
    surface = Color.White,
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF9AC2FF),
    primaryContainer = Color(0xFF0B438C),
    secondary = Color(0xFFBAC6DB),
)

@Composable
fun MediaAnvilTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors,
        content = content,
    )
}
