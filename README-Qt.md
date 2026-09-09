# MediaAnvil Qt 1.0.0

**[English →](README-Qt.en.md)**

全新 Qt 桌面界面，使用系统装饰的标准窗口。没有 Tk/TkDND、无边框窗口、自定义标题栏拖动或鼠标捕获钩子。

## 启动

打开 `dist/MediaAnvilQt/MediaAnvilQt.exe`。无需安装 Python。

请保留整个 `MediaAnvilQt` 文件夹（包括 `_internal`），不要只复制 EXE。

## 功能

所有页面统一采用浅蓝背景、白色圆角卡片与线条图标。转换页左侧为勾选文件和参数，右侧为结果列表、图片详情或字幕全文；窄窗口自动改为上下排列。结果支持另存、再次转换与打开所在目录。设置页支持中英文即时切换，开关可用键盘空格操作。标签编辑并排显示基本信息、歌词和封面，下方可展开匹配区域，分别批量写入歌词或封面。普通用户操作方法见 [USER_GUIDE.md](USER_GUIDE.md)。

音频预览载入当前选择的音频，提供后退 30 秒、播放/暂停和前进 30 秒按钮。同步歌词高亮并定位当前句。重命名支持勾选执行项、搜索文件名、导出 CSV 预览与撤销；搜索只过滤显示，不改变已有勾选。

- 音频预览：播放、暂停、前后跳转、音量、空格快捷键；读取同名 LRC/SRT/VTT 与 MP3 内嵌同步歌词，居中显示并可点击跳转。
- 标签编辑：MP3、FLAC、M4A、OGG、Opus；歌名、歌手、专辑、LRC/SRT/VTT 导入、封面自由矩形裁剪、歌词/封面导出。WAV 仅显示信息。
- 同目录歌词/封面匹配与文件夹扫描，支持 `歌曲.wav.vtt`、`歌曲.wav.png` 等双后缀命名。多候选默认不选，由用户明确选择后写入。
- 歌词/字幕：LRC、SRT、VTT 互转，末句持续时间可设置，文本结果可预览。
- 音频转换：MP3、WAV、FLAC、M4A/AAC、OGG；码率/质量、采样率、声道、保留标签。
- 图片转换：JPG、PNG、WebP、BMP；质量、透明通道处理、图片预览。
- 批量重命名：按标签生成预览，显示冲突，执行与撤销最近一批。
- 文件和文件夹可直接拖入当前页面；后台扫描、转换和标签处理期间仍可移动窗口。为避免同时修改任务输入，任务进行时暂时禁用内容区，完成后自动恢复。

默认另存为。转换输出自动避开已有文件；标签保存可明确选择覆盖。重命名只执行预览中可重命名的条目，撤销遇到被占用的旧文件名时不会覆盖。

媒体处理模块位于 `sub2lrc/` 与 `core/`，界面代码位于 `mediaanvil_qt/`。设置保存在 `%APPDATA%/MediaAnvilQt/settings.json`。

## 源码运行与构建

使用官方 Windows Python（不是 MSYS2 Python）：

```powershell
.build-venv-windows\Scripts\python.exe -m pip install -r requirements-qt.txt
.\tools\download_icu.ps1
.build-venv-windows\Scripts\python.exe main_qt.py
.\build-qt.ps1
```

`build-qt.ps1` 使用项目内 `.build-venv-windows`，隔离 DLL 搜索路径后打包 Qt DLL 和 FFmpeg/FFplay，避免混入其他软件的同名依赖。构建完成后会检查 DLL 来源，并实际启动 EXE、转换测试音频及检查 FFplay；任何一步失败都不会报告构建成功。运行测试：

```powershell
.build-venv-windows\Scripts\python.exe -m unittest discover -s tests -p test_qt_rewrite.py -v
```

## 验证范围

集成测试覆盖界面线程响应、转换、源文件保护、标签另存、重命名与撤销、歌词跳转、设置、裁剪等。自动测试不能证明用户机器上的原生标题栏视觉跳位已消失；需要对最终 Qt 版进行实际拖动验收。

## 第三方组件

Qt/PySide6/Shiboken 6.11.2 以独立动态库随附。Qt 需要的 ICU 78.3 运行时通过 `tools/download_icu.ps1` 下载，许可文本见 `licenses/ICU-LICENSE.txt`。Qt/PySide 的开源许可信息见 `licenses/qt/`，源码与构建信息：

- https://code.qt.io/cgit/pyside/pyside-setup.git/tree/?h=6.11.2
- https://code.qt.io/cgit/qt/qtbase.git/tree/?h=v6.11.2
- https://doc.qt.io/qtforpython-6/building_from_source/index.html

Qt/PySide 的许可证不改变本项目其他代码的版权归属。第三方库可在兼容 ABI 的前提下单独替换；请保留随附许可。FFmpeg/FFplay 说明见 `THIRD_PARTY_NOTICES.md`。
