package com.imankoppai.mediaanvil.ui

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import com.imankoppai.mediaanvil.R
import java.io.ByteArrayOutputStream
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

/**
 * Free rectangular cover crop. Drag to create or move the selection rectangle;
 * the default selection is the full image, matching the desktop crop dialog.
 */
@Composable
fun CropDialog(
    imageBytes: ByteArray,
    onConfirm: (pngBytes: ByteArray) -> Unit,
    onDismiss: () -> Unit,
) {
    val bitmap = remember(imageBytes) {
        BitmapFactory.decodeByteArray(imageBytes, 0, imageBytes.size)
    } ?: run {
        onDismiss()
        return
    }
    var selection by remember(bitmap) {
        mutableStateOf(Rect(0f, 0f, bitmap.width.toFloat(), bitmap.height.toFloat()))
    }
    var dragMode by remember { mutableStateOf<DragMode>(DragMode.None) }
    var canvasSize by remember { mutableStateOf(IntSize.Zero) }

    fun displayRect(): Pair<Float, Rect> {
        if (canvasSize.width == 0 || canvasSize.height == 0) return 1f to Rect.Zero
        val scale = min(
            canvasSize.width.toFloat() / bitmap.width,
            canvasSize.height.toFloat() / bitmap.height,
        )
        val width = bitmap.width * scale
        val height = bitmap.height * scale
        val offset = Offset((canvasSize.width - width) / 2f, (canvasSize.height - height) / 2f)
        return scale to Rect(offset, Size(width, height))
    }

    fun imagePoint(position: Offset): Offset {
        val (scale, display) = displayRect()
        if (display == Rect.Zero) return Offset.Zero
        val x = ((position.x - display.left) / scale).roundToInt().coerceIn(0, bitmap.width - 1)
        val y = ((position.y - display.top) / scale).roundToInt().coerceIn(0, bitmap.height - 1)
        return Offset(x.toFloat(), y.toFloat())
    }

    fun clampSelection(anchor: Offset, position: Offset) {
        val left = min(anchor.x, position.x).coerceIn(0f, bitmap.width - 1f)
        val top = min(anchor.y, position.y).coerceIn(0f, bitmap.height - 1f)
        val right = max(anchor.x, position.x).coerceIn(1f, bitmap.width.toFloat())
        val bottom = max(anchor.y, position.y).coerceIn(1f, bitmap.height.toFloat())
        selection = Rect(left, top, right, bottom)
    }

    fun moveSelection(startDisplay: Offset, positionDisplay: Offset) {
        val (scale, display) = displayRect()
        if (display == Rect.Zero) return
        val width = selection.width
        val height = selection.height
        val left = (selection.left + (positionDisplay.x - startDisplay.x) / scale)
            .coerceIn(0f, bitmap.width - width)
        val top = (selection.top + (positionDisplay.y - startDisplay.y) / scale)
            .coerceIn(0f, bitmap.height - height)
        selection = Rect(left, top, left + width, top + height)
    }

    Dialog(onDismissRequest = onDismiss) {        Surface(shape = MaterialTheme.shapes.medium, color = MaterialTheme.colorScheme.surface) {
            Column(Modifier.padding(16.dp)) {
                Text(stringResource(R.string.crop_title), style = MaterialTheme.typography.titleMedium)
                Text(
                    stringResource(R.string.click_lyric_hint),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.secondary,
                )
                val image: ImageBitmap = bitmap.asImageBitmap()
                Canvas(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(320.dp)
                        .padding(vertical = 8.dp)
                        .onSizeChanged { canvasSize = it }
                        .pointerInput(bitmap) {
                            detectDragGestures(
                                onDragStart = { position ->
                                    val point = imagePoint(position)
                                    dragMode = if (selection.contains(point) &&
                                        selection != Rect(0f, 0f, bitmap.width.toFloat(), bitmap.height.toFloat())
                                    ) {
                                        DragMode.Move(position)
                                    } else {
                                        DragMode.Resize(point)
                                    }
                                },
                                onDrag = { change, _ ->
                                    change.consume()
                                    val point = imagePoint(change.position)
                                    when (val mode = dragMode) {
                                        is DragMode.Move -> moveSelection(mode.startDisplay, change.position)
                                        is DragMode.Resize -> clampSelection(mode.start, point)
                                        DragMode.None -> {}
                                    }
                                },
                                onDragEnd = { dragMode = DragMode.None },
                            )
                        },
                ) {
                    val (scale, display) = displayRect()
                    if (display != Rect.Zero) {
                        drawImage(
                            image = image,
                            dstOffset = IntOffset(display.left.roundToInt(), display.top.roundToInt()),
                            dstSize = IntSize(display.width.roundToInt(), display.height.roundToInt()),
                        )
                        val crop = Rect(
                            display.left + selection.left * scale,
                            display.top + selection.top * scale,
                            display.left + selection.right * scale,
                            display.top + selection.bottom * scale,
                        )
                        val shade = Color(0f, 0.12f, 0.22f, 0.5f)
                        drawRect(shade, Offset(display.left, display.top), Size(display.width, max(0f, crop.top - display.top)))
                        drawRect(shade, Offset(display.left, crop.bottom), Size(display.width, max(0f, display.bottom - crop.bottom)))
                        drawRect(shade, Offset(display.left, crop.top), Size(max(0f, crop.left - display.left), crop.height))
                        drawRect(shade, Offset(crop.right, crop.top), Size(max(0f, display.right - crop.right), crop.height))
                        drawRect(
                            Color(0xFF2B70F3),
                            crop.topLeft,
                            crop.size,
                            style = Stroke(width = 2.dp.toPx()),
                        )
                    }
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = androidx.compose.foundation.layout.Arrangement.SpaceEvenly) {
                    OutlinedButton(onClick = {
                        selection = Rect(0f, 0f, bitmap.width.toFloat(), bitmap.height.toFloat())
                    }) { Text(stringResource(R.string.crop_reset)) }
                    OutlinedButton(onClick = onDismiss) { Text(stringResource(R.string.crop_cancel)) }
                    Button(onClick = {
                        val x = selection.left.roundToInt()
                        val y = selection.top.roundToInt()
                        val width = max(1, abs(selection.width).roundToInt()).coerceAtMost(bitmap.width - x)
                        val height = max(1, abs(selection.height).roundToInt()).coerceAtMost(bitmap.height - y)
                        val cropped = Bitmap.createBitmap(bitmap, x, y, width, height)
                        val bytes = ByteArrayOutputStream().use { output ->
                            cropped.compress(Bitmap.CompressFormat.PNG, 100, output)
                            output.toByteArray()
                        }
                        if (cropped != bitmap) cropped.recycle()
                        onConfirm(bytes)
                    }) { Text(stringResource(R.string.crop_confirm)) }
                }
            }
        }
    }
}

private sealed class DragMode {
    data object None : DragMode()
    data class Move(val startDisplay: Offset) : DragMode()
    data class Resize(val start: Offset) : DragMode()
}
