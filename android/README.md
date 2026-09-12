# MediaAnvil Android

MediaAnvil Android 是面向本地 ASMR、广播剧、有声内容和音乐文件的专用播放器。它与 Windows 版各司其职：Android 负责随时播放，标签编辑、封面处理、音频剪辑和格式转换由 Windows 版完成。

## 当前功能

- 通过 Android 系统文件选择器授权一个或多个本地媒体目录，无需申请宽泛的存储权限。
- 递归扫描 MP3、WAV、FLAC、M4A、AAC、OGG 和 Opus，并缓存媒体库以便快速启动。
- 按歌曲、专辑、艺术家、最近播放、收藏和文件夹浏览，支持搜索与排序。
- 使用 Media3 ExoPlayer 播放本地音频，支持播放队列、上一首/下一首、随机、列表循环和单曲循环。
- 播放页支持 0.75×–3× 变速、A-B 循环、进度拖动、封面与同步歌词。
- 自动匹配同名及双后缀 LRC、SRT、VTT 外挂歌词，支持 UTF-8、UTF-16 和 GB18030。
- 支持后台播放、锁屏控制、系统媒体通知和可配置的耳机双击动作。
- 提供睡眠定时、系统均衡器预设、响度增强和后台播放电池设置入口。
- 支持简体中文与英文、深色/浅色主题、Material You 动态配色与封面取色。

所有文件只在设备本地读取，不上传到服务器。Android 版不修改媒体文件。

## 界面结构

- **媒体**：管理媒体库目录，浏览、搜索、收藏并选择歌曲。
- **播放**：独立的一级播放页面，显示封面、歌词、进度、播放模式和队列。
- **设置**：仅保留与播放器、歌词显示、声音、主题和媒体库扫描相关的选项。

## 与 Windows 版的分工

以下功能只保留在 Windows 版，不再由 Android 版提供：

- 音频标签、歌词和封面写入
- 封面裁剪
- 音频剪辑与合并
- 音频、图片、歌词和字幕格式转换
- 批量重命名与智能匹配写入

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

## 主要技术

- Kotlin 2.3.21
- Jetpack Compose BOM 2025.08.00
- Android Gradle Plugin 9.4.0
- Media3 1.11.0
- minSdk 26 / targetSdk 36
