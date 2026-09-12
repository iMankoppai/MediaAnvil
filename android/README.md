# MediaAnvil Android

MediaAnvil Android 是面向本地 ASMR、广播剧、有声内容和音乐文件的 Android 播放器 MVP。它与现有 Windows 客户端相互独立，不会改变桌面版的构建或运行方式。

## 当前功能

- 使用 Android 系统文件选择器授权一个本地文件夹，无需申请宽泛的存储权限。
- 递归扫描 MP3、WAV、FLAC、M4A、AAC、OGG 和 Opus。
- 读取音频标题、作者、专辑和时长。
- 使用 Media3 ExoPlayer 播放本地音频。
- 通过 `MediaSessionService` 支持后台播放、锁屏控制和系统媒体通知。
- 记住每个音频的播放位置以及上次选择的文件夹。
- 自动匹配同名和双后缀 LRC、SRT、VTT 字幕。
- 解析 UTF-8、UTF-16 和 GB18030 字幕，并跟随播放进度显示当前文本。
- 简体中文与英文界面。

所有文件都通过 Android Storage Access Framework 在设备本地读取，不上传到服务器。

## 音频预览页

- 播放、暂停、上一首 / 下一首、进度拖动、音量调节，以及后退 / 前进 30 秒按钮。
- 同步歌词整篇滚动显示，当前句高亮并自动居中，点击任意歌词行跳转到对应时间。
- 字幕候选识别顺序为 LRC、SRT、VTT、MP3 内嵌同步歌词；同格式下 `歌曲.wav.vtt` 这类保留完整音频文件名的命名优先。
- "优先使用 MP3 内嵌歌词"开关会记住选择；内嵌同步歌词（SYLT）与内嵌 LRC 文本（USLT）都会被读取。

## 标签编辑页

- 编辑歌名、歌手、专辑；格式支持情况与桌面版一致：MP3、FLAC、M4A、OGG、Opus 可写，WAV 与 AAC 只读。
- 歌词：导入 LRC / SRT / VTT（SRT/VTT 在内存中转换为 LRC 后写入，不修改原字幕）、导出当前内嵌歌词、移除歌词（保存时生效）。写入统一使用 LRC 时间歌词，与桌面版内嵌格式互通。
- 封面：选择图片后进入自由矩形裁剪（拖拽创建 / 移动裁剪框，默认完整图片），裁剪结果统一转为 PNG 写入；导出当前内嵌封面；移除封面（保存时生效）。支持 JPG、PNG、WebP、BMP。
- 保存方式默认"另存为"（生成 `歌名_tagged.扩展名` 副本，自动避开已有文件），也可明确选择"覆盖原文件"；覆盖前会先写入并校验新文档，再替换原文件。

## 工具页

- **歌词 / 字幕转换**：LRC、SRT、VTT 互转，结果以新扩展名保存在各自源文件旁边（UTF-8 带 BOM）；与源格式相同的文件自动跳过。
- **音频格式转换**：批量转换为 M4A（AAC）、原生 FLAC 或 Ogg Opus，结果保存在源文件旁边。FLAC 使用系统编码器并写入原生 `fLaC` 容器（当前统一输出 16-bit PCM 精度）；Opus 使用系统编码器和开放的 Ogg 容器（Android 10+）。转换在后台执行，支持取消、临时空间预检和失败缓存清理。系统没有提供 Vorbis/MP3 编码器，暂不导出这两种格式。
- **图片格式转换**：JPG、PNG、WebP、BMP 互转，可调质量（JPG/WebP）；透明区域转 JPG/BMP 时填白。
- 标签编辑入口与每首歌的"媒体工具"抽屉保持不变。

## 尚未实现

**批量重命名**与标签编辑中的**智能匹配关联文件**为桌面版独占功能（触屏交互下体验不佳，暂不移植）。此外与桌面版相比仍缺少：封面裁剪的数值输入框、音频转换导出 MP3/Vorbis、设置页的部分高级选项。这些会随后续版本逐步评估。

## 本地构建

需要 JDK 17、Android SDK 36（Build Tools 36.0.0）和 Gradle 9.6：

```text
cd android
gradle :app:testDebugUnitTest :app:assembleDebug
```

调试 APK 位于：

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

如果本机没有 Android 开发环境，可以推送分支后在 GitHub Actions 的 `Android` 工作流中构建并下载 `MediaAnvil-Android-debug` artifact。

## 主要技术

- Kotlin 2.3.21
- Jetpack Compose BOM 2025.08.00
- Android Gradle Plugin 9.4.0
- Media3 1.11.0
- Kaned1as jAudiotagger 2.3.15 fork（含 Opus 标签读写，LGPL，见 THIRD_PARTY_NOTICES）
- minSdk 26 / targetSdk 36
