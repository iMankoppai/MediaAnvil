package com.imankoppai.mediaanvil.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.snapping.rememberSnapFlingBehavior
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.imankoppai.mediaanvil.R
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.launch
import kotlin.math.abs

/** Sleep timer dialog with wheel pickers for any hours/minutes combination. */
@Composable
internal fun SleepTimerDialog(
    initialMinutes: Int,
    onStart: (Int) -> Unit,
    onDismiss: () -> Unit,
) {
    var hours by remember { mutableStateOf(initialMinutes / 60) }
    var minutes by remember { mutableStateOf(initialMinutes % 60) }
    val total = hours * 60 + minutes
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.sleep_timer)) },
        text = {
            Row(
                horizontalArrangement = Arrangement.spacedBy(24.dp),
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.weight(1f)) {
                    WheelPicker(values = (0..23).toList(), initialIndex = hours, onSelect = { hours = it })
                    Text(
                        stringResource(R.string.sleep_timer_hours),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 6.dp),
                    )
                }
                Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.weight(1f)) {
                    WheelPicker(values = (0..59).toList(), initialIndex = minutes, onSelect = { minutes = it })
                    Text(
                        stringResource(R.string.sleep_timer_minutes),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 6.dp),
                    )
                }
            }
        },
        confirmButton = {
            TextButton(onClick = { onStart(total); onDismiss() }, enabled = total > 0) {
                Text(stringResource(R.string.crop_confirm))
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text(stringResource(R.string.crop_cancel)) }
        },
    )
}

@Composable
internal fun WheelPicker(
    values: List<Int>,
    initialIndex: Int,
    onSelect: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val itemHeight = 38.dp
    val visibleRows = 5
    val state = rememberLazyListState(initialFirstVisibleItemIndex = initialIndex)
    val scope = rememberCoroutineScope()
    val boxHeightPx = with(LocalDensity.current) { (itemHeight * visibleRows).toPx() }
    var reportedIndex by remember { mutableStateOf<Int?>(null) }
    LaunchedEffect(initialIndex) {
        // Scroll only when the change came from outside the wheel (prefill); user
        // scrolls already report their settled index and must not be fought.
        if (reportedIndex != initialIndex) {
            state.scrollToItem(initialIndex)
        }
    }
    Box(modifier.height(itemHeight * visibleRows)) {
        Box(
            Modifier
                .align(Alignment.Center)
                .fillMaxWidth()
                .height(itemHeight)
                .clip(RoundedCornerShape(10.dp))
                .background(MaterialTheme.colorScheme.surfaceVariant),
        )
        LazyColumn(
            state = state,
            flingBehavior = rememberSnapFlingBehavior(lazyListState = state),
            contentPadding = PaddingValues(vertical = itemHeight * ((visibleRows - 1) / 2)),
            modifier = Modifier.fillMaxWidth(),
        ) {
            itemsIndexed(values) { index, value ->
                val itemHeightPx = with(LocalDensity.current) { itemHeight.toPx() }
                val info = state.layoutInfo
                val center = (info.viewportStartOffset + info.viewportEndOffset) / 2f
                val distance = info.visibleItemsInfo.firstOrNull { it.index == index }
                    ?.let { abs(it.offset + it.size / 2f - center) } ?: Float.MAX_VALUE
                val fade = (1f - distance / (itemHeightPx * 2.4f)).coerceIn(0.25f, 1f)
                Box(
                    Modifier
                        .fillMaxWidth()
                        .height(itemHeight)
                        .clickable {
                            reportedIndex = index
                            scope.launch { state.animateScrollToItem(index) }
                        },
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        value.toString(),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = if (fade > 0.9f) FontWeight.Bold else FontWeight.Normal,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = fade),
                    )
                }
            }
        }
    }
    LaunchedEffect(Unit) {
        snapshotFlow { state.isScrollInProgress }
            .distinctUntilChanged()
            .filter { !it }
            .collect {
                val info = state.layoutInfo
                // Widget-center in item coordinates: top edge of the widget sits
                // beforeContentPadding above the first laid-out item's snapped
                // position, so it must be subtracted before halving the height.
                val first = info.visibleItemsInfo
                    .firstOrNull { it.index == state.firstVisibleItemIndex }
                    ?: info.visibleItemsInfo.firstOrNull()
                    ?: return@collect
                val center = first.offset + state.firstVisibleItemScrollOffset -
                    info.beforeContentPadding + boxHeightPx / 2f
                val index = info.visibleItemsInfo
                    .minByOrNull { abs(it.offset + it.size / 2f - center) }
                    ?.index
                    ?: return@collect
                if (index in values.indices) {
                    reportedIndex = index
                    onSelect(index)
                }
            }
    }
}
