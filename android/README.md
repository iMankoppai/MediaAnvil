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

- 编辑歌名、歌手、专辑；格式支持情况与桌面版一致：MP3、FLAC、M4A、OGG 可写，WAV 只读，AAC 与 Opus 暂不支持编辑（Opus 播放不受影响）。
- 歌词：导入 LRC / SRT / VTT（SRT/VTT 在内存中转换为 LRC 后写入，不修改原字幕）、导出当前内嵌歌词、移除歌词（保存时生效）。写入统一使用 LRC 时间歌词，与桌面版内嵌格式互通。
- 封面：选择图片后进入自由矩形裁剪（拖拽创建 / 移动裁剪框，默认完整图片），裁剪结果统一转为 PNG 写入；导出当前内嵌封面；移除封面（保存时生效）。支持 JPG、PNG、WebP、BMP。
- 保存方式默认"另存为"（生成 `歌名_tagged.扩展名` 副本，自动避开已有文件），也可明确选择"覆盖原文件"；覆盖前会先写入并校验新文档，再替换原文件。
- 智能匹配：查找同目录歌词与封面候选，规则与桌面版一致（完整音频文件名 > 同名 > 忽略空格 > 去除"副本/括号编号"后缀）；存在多个同等级候选时不自动选择，需要手动确认后"应用到编辑"。
- 批量写入：对本文件夹中唯一匹配的歌词 / 封面一键批量写入，多候选的音频自动跳过。

## 尚未实现

这是 MVP，桌面版中的格式转换（音频/图片/歌词字幕互转）和批量重命名尚未移植。后续应在真机标签写入和文件兼容性稳定后逐步加入这些功能。

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
- jAudiotagger 3.0.1（音频标签读写，LGPL，见 THIRD_PARTY_NOTICES）
- minSdk 26 / targetSdk 36
