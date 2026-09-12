# MediaAnvil 音频转换真机验收报告（2026-09-12）

## 环境与保护范围

- 真机：OPPO RMX3888，Android API 36，ADB serial `5e74fbd1`。
- 测试目录：`/sdcard/Download/MediaAnvilQA_20260912`；原始音频未删除。
- 未提交、未推送、未生成长期签名 APK；`tools/codex_ghost_scan.py` 和 `tools/icuuc_proxy.def` 未触碰。
- 结果已拉回：`qa/device_results_20260912/MediaAnvilQA_20260912`。

## 样本

`tone_16bit.wav`、`tone_24bit.wav`、`tone.mp3`、`tone.m4a`、`tone_vorbis.ogg`、`tone_opus.opus`、`tone.flac`、`tone_tagged.mp3`、`long_120s.wav`，以及 6 个文件的 `batch_input` 组。带标签样本包含标题、艺术家、专辑、PNG 封面和两行歌词。

## 最终转换矩阵

最终有效输出 24/24 通过容器魔数、FFmpeg 解码、时长和音频流检查；全部为 48 kHz、立体声，时长绝对差最大 0.084 秒。

| 输入 → 输出 | 结果 |
|---|---|
| WAV16 → FLAC / OPUS / M4A | 通过 |
| WAV24 → FLAC / OPUS / M4A | 通过（FLAC 为 s16，见 24-bit 结论） |
| MP3 → FLAC / OPUS / M4A | 通过 |
| M4A/AAC → FLAC / OPUS | 通过 |
| OGG/Vorbis → FLAC / OPUS / M4A | 通过 |
| Opus → FLAC / M4A | 通过 |
| FLAC → OPUS / M4A | 通过 |
| 带标签 MP3 → FLAC / OPUS / M4A | 通过，标签/封面/歌词均保留 |
| 120 秒 WAV → FLAC / OPUS / M4A | 通过，未提前截断 |
| 8 文件 M4A 批量转换 | 8/8 完成；同格式 M4A 按设计跳过 |

最终批次输出包括 `long_120s_4.m4a`、`tone_16bit_2.m4a`、`tone_24bit_1.m4a`、`tone_opus_1.m4a`、`tone_tagged_4.m4a`、`tone_vorbis_1.m4a`、`tone_3.m4a`、`tone_4.m4a`。所有最终 M4A 的 `elst` 均为 version 0、size 28、media rate 65536。

## 真机播放/拖动

- `long_120s_3.m4a`：媒体库显示 2:00；播放中从 0:19 拖到 1:46，仍可播放。
- `tone_tagged_3.m4a`：媒体库显示 `QA Tagged Title / QA Artist / M4A · 0:03`；播放和拖到 0:03 均正常。
- `tone_opus.opus`：OPUS · 0:03，播放中拖到 0:02 正常。
- `tone_tagged_1.flac`：此前修复后真机播放、拖动到 0:03 正常。

其余最终输出均完成逐文件容器/编码/FFmpeg 解码/时长检查。

## 已修复问题

1. **FLAC 标签丢失**：首次运行 UI 报“标签未能保留”，直接读取 `tone_tagged.flac` 无 VorbisComment。`TagIO` 现在写入标准 VorbisComment（TITLE/ARTIST/ALBUM/LYRICS/METADATA_BLOCK_PICTURE）；`tone_tagged_1.flac` 复测通过。
2. **M4A malformed `elst`**：首次输出在 RMX3888 播放报“文件可能已损坏或格式不受支持”，logcat 为 `BoxParser.parseEdts` 的 `ArrayIndexOutOfBoundsException`。仅改 version 后又复现 `Unsupported media rate`；最终修复为将截断 version-1 字段重排为合法 version-0 的 segment duration、media time=0、media rate=1.0。最终 M4A 批次和长文件/带标签复测通过。

历史中间失败文件（如 `long_120s_2.m4a`）保留在 QA 目录作为复现证据，不作为最终有效输出。

## 取消、重名和缓存

- 120 秒 WAV 转 M4A 启动后立即点击“取消转换”，UI 显示“转换已取消，已完成的文件会保留”。没有新增半成品；设备目录无 `.part`/`.tmp`/`audio-convert-*`，应用 cache 仅有 `library_snapshot.json`。
- 重名输出观察到 `_1`、`_2`、`_3`、`_4`，源文件未被覆盖。

## 24-bit 判断

在本次可控输入样本（9 个）中只读统计为：24-bit **1**、32-bit **0**。最终 FLAC 输出流全部为 `s16`；当前没有“明显数量”证据支持扩大高位深实现。暂不重写 FLAC 转码器，也不实现 24-bit 输出。该统计范围是本次 QA 样本，不等同于手机上全部私人音源。

## 未解决限制

- MP3/Vorbis 编码器不扩展；界面按系统编码能力只提供 M4A、FLAC、OPUS。
- FLAC 转码目前统一输出 16-bit；如需保留 24/32-bit，需要明确需求后另行评估设备编码能力、内存/存储开销和降级策略。
- M4A 使用设备系统 AAC 编码器，实际码率由系统实现决定。
- 本次真机兼容性证据来自 RMX3888/API 36。

## 构建与 APK

以下命令均 `BUILD SUCCESSFUL`、退出码 0：

```text
:app:lintDebug
:app:testDebugUnitTest
:app:assembleDebug
```

APK：`android/app/build/outputs/apk/debug/app-debug.apk`

本地 APK SHA-256 与手机已安装 `base.apk`（从 `pm path com.imankoppai.mediaanvil` 拉回）一致：

```text
050CC9122A9311E4C835F06B468414230DCB065E8371E9A8C1DE0D567F79B41E
```

这是 debug APK；未自动生成长期签名 APK，未编造密码或提交 keystore。
