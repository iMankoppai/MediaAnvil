# MediaAnvil 1.0

MediaAnvil 是一款面向 Windows 的本地多媒体工具箱。它使用 Qt 桌面界面，媒体文件始终在本机处理，默认保留原文件，并提供简体中文与英文界面。

普通用户请阅读 [使用说明](USER_GUIDE.md)，源码运行与打包细节见 [Qt 构建说明](README-Qt.md)。

## 主要功能

- 音频预览：播放 MP3、WAV、FLAC、M4A、AAC、OGG、Opus，支持空格播放/暂停、前后跳转、音量和进度控制。
- 同步歌词：直接读取同名 LRC、SRT、VTT，也支持 `歌曲.wav.vtt` 等双后缀命名和 MP3 内嵌同步歌词；可以设置 MP3 内嵌歌词优先。
- 音频标签编辑：修改歌名、歌手、专辑，导入或移除歌词与封面；SRT/VTT 会在内存中转换为 LRC 后写入。
- 封面处理：预览、导入、导出、移除封面，导入时提供自由矩形裁剪。
- 智能匹配：扫描同目录歌词和封面，支持普通及双后缀命名，可批量写入所选关联文件。
- 歌词/字幕转换：LRC、SRT、VTT 三种格式互转，保留多行内容并安全避开已有文件。
- 音频转换：MP3、WAV、FLAC、M4A/AAC、OGG 批量互转，支持码率、质量、采样率、声道与标签保留设置。
- 图片转换：JPG、PNG、WebP、BMP 批量互转，支持质量和透明背景处理。
- 批量重命名：根据音频标签生成文件名，执行前预览冲突，支持撤销最近一次批量重命名。

## 安全行为

- 标签编辑默认“另存为”，只有明确选择“覆盖原文件”才会替换源文件。
- 转换输出自动使用 `_1`、`_2` 等名称避开已有文件。
- “移除”和“清空”只清理界面列表，不删除磁盘文件。
- SRT/VTT 导入与预览不会修改原字幕，也不会在源目录生成临时 LRC。
- 后台任务结束前会阻止关闭窗口，避免处理中途损坏文件。

## 运行发行版

下载并解压完整的 `MediaAnvilQt` 文件夹，然后运行：

```text
MediaAnvilQt.exe
```

请保留 `_internal` 目录，不要只复制 EXE。发行版已内置 Qt、FFmpeg 和 FFplay，目标电脑不需要安装 Python。

程序默认以 `1440 × 900`（16:10）窗口启动并居中；高 DPI 或较小屏幕会自动按比例适配。

## 从源码运行

使用官方 Windows Python 3.10 或更高版本：

```powershell
python -m venv .build-venv-windows
.build-venv-windows\Scripts\python.exe -m pip install -r requirements-qt.txt
.build-venv-windows\Scripts\python.exe main_qt.py
```

运行全部测试：

```powershell
.build-venv-windows\Scripts\python.exe -m unittest discover -s tests -v
```

构建 Windows 发行版：

```powershell
.\build-qt.ps1
```

构建脚本会生成 `dist\MediaAnvilQt`，并自动验证冻结版程序启动、FFmpeg 实际转换和 FFplay 可用性。

## 支持范围

- 同步歌词与字幕：LRC、SRT、VTT
- 可写音频标签：MP3、FLAC、M4A、OGG、Opus
- WAV 标签：只读
- 音频转换：MP3、WAV、FLAC、M4A/AAC、OGG
- 图片转换：JPG/JPEG、PNG、WebP、BMP
- 文本编码：UTF-8、UTF-16、GB18030；转换输出为带 BOM 的 UTF-8

## 第三方组件

Qt/PySide6、ICU 与 FFmpeg/FFplay 的许可和来源说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与 `licenses/`。
