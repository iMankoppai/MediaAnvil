package com.imankoppai.mediaanvil.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.widthIn
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/** At or above this width the bottom bar becomes a side rail. */
internal val RailLayoutMinWidth = 600.dp

/** At or above this width the player splits into cover and lyrics panes. */
internal val PlayerTwoPaneMinWidth = 840.dp

/** Widest a single-column page grows before it is centered on a tablet. */
internal val PageContentMaxWidth = 960.dp

/** Widest the single-column player grows: a player stretched over a whole tablet is unreadable. */
internal val PlayerSinglePaneMaxWidth = 680.dp

/** Centres a single-column page and caps its width so tablet lists do not stretch edge to edge. */
@Composable
internal fun CenteredPageContent(
    maxWidth: Dp = PageContentMaxWidth,
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    Box(modifier.fillMaxSize(), contentAlignment = Alignment.TopCenter) {
        Box(
            Modifier
                .fillMaxHeight()
                .widthIn(max = maxWidth)
                .fillMaxWidth(),
        ) {
            content()
        }
    }
}
