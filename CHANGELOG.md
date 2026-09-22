# Changelog

## 1.1.0

- Added an in-app read-only Markdown reader for the bundled guides, replacing the
  external "open with the default app" behaviour. It renders headings, lists, code
  blocks and tables, offers outline navigation and in-document search, and never
  follows a link automatically: a network address is only copied to the clipboard.
- Localised Qt's own standard dialog buttons, so the Chinese interface shows
  "关闭 / 取消 / 确定" instead of "Close / Cancel / OK".
- File dialogs now remember the last used folder per category (audio, image,
  subtitle, output) and restore it on the next launch, falling back to the matching
  Windows user folder when the remembered path no longer exists. The last used
  filter is remembered as well.
- Imports that find nothing now explain why: unsupported extensions are listed with
  their counts next to the formats the page accepts, and missing files are named.
- Added a local task log under `%APPDATA%\MediaAnvilQt\logs`. It records the task
  type, input count, success count and failure reasons only — never file names,
  lyrics or media content — rotates at 1 MB keeping five files, and is never
  uploaded. Settings gained an "Open Log Folder" button.
- Message dialogs gained a "Copy Details" button so an error can be pasted into a
  bug report, and conversions now verify that the output folder is writable before
  the task starts.
- Clearer failure reporting: FFmpeg timeouts name the input file and the stalled
  stage, and moving or deleting the file being played now pauses playback with an
  explicit message.
- Interface polish: expanding the smart-matching area scrolls it into view, and
  switching pages returns to the top so navigation stays predictable.
- Changed the default window target from 1440 × 900 (16:10) to 1440 × 960 (3:2) and
  relaxed the screen-edge allowance from 90% to 95%, so that size is reachable on a
  1920 × 1080 desktop at 125% scaling. Numeric controls on the Settings page now
  share one aligned width.
- The release folder now ships `THIRD_PARTY_NOTICES.md` and `licenses/qt` next to
  the executable, and the build fails if any required document is missing.
- Fixed a shadowed loop variable in `tools/codex_ghost_scan.py` that printed a
  memory address instead of the sidebar field name in its error message.
- Widened the Ruff rule set to the full "F" (pyflakes) group and cleared the unused
  imports it found. Style rules stay off on purpose. The test suite grew from 186
  to 223 tests.

### 中文说明

- 内置只读 Markdown 阅读器，用于查看随附的使用说明与第三方组件说明，不再调用系统
  关联程序打开。支持标题、列表、代码块与表格渲染，提供目录导航和文档内搜索；链接不会
  自动打开，网络地址只会复制到剪贴板。
- 加载 Qt 自带的中文语言包，中文界面下的标准按钮不再显示英文，现为「关闭 / 取消 / 确定」。
- 文件选择对话框按音频、图片、字幕、输出四类分别记住上次所在目录，下次启动继续沿用；
  目录已不存在时自动回退到对应的 Windows 用户文件夹。同时记住上次使用的文件筛选器。
- 导入未找到文件时说明原因：列出被拒的扩展名及数量，并对照本页支持的格式；文件不存在
  时给出具体文件名。
- 新增本地任务日志，位于 `%APPDATA%\MediaAnvilQt\logs`。只记录任务类型、输入数量、
  成功数量与失败原因，不记录文件名、歌词或媒体内容；单文件 1 MB、保留 5 份自动轮换，
  绝不上传。设置页新增「打开日志目录」。
- 提示对话框新增「复制详情」按钮，便于把错误信息粘贴到反馈中；转换任务开始前先检查
  输出目录是否可写。
- 失败提示更清晰：FFmpeg 超时会指出输入文件名与卡住的阶段；正在播放的文件被移动或删除
  时会暂停播放并给出明确提示。
- 界面细节：展开「智能匹配关联文件」后自动滚动到该区域；切换页面回到顶部，导航更可预期。
- 默认窗口目标由 1440 × 900（16:10）改为 1440 × 960（3:2），屏幕边缘安全余量由 90%
  放宽到 95%，使该尺寸在 1920 × 1080、125% 缩放的桌面上能够真正达到。设置页数值控件
  统一为等宽对齐。
- 发布目录现在把 `THIRD_PARTY_NOTICES.md` 与 `licenses/qt` 放在可执行文件旁边；
  缺少任一必需文档时构建直接失败。
- 修复 `tools/codex_ghost_scan.py` 中循环变量遮蔽导入名的问题，该缺陷会让错误提示
  打印内存地址而不是字段名。
- Ruff 规则集扩展到完整的 "F"（pyflakes）组，并清理了它发现的未使用导入；风格类规则
  仍有意保持关闭。测试数量由 186 项增加到 223 项。

## 1.0.3

- Fixed Windows startup failure caused by an incompatible bundled ICU DLL.
- Strengthened the frozen-app smoke test so an error dialog can no longer be mistaken for a successful launch.

### 中文说明

- 修复因随附的 ICU DLL 不兼容而导致的 Windows 启动失败。
- 强化冻结版烟雾测试：错误弹窗不再被误判为启动成功。

## 1.0.2

- Added cooperative cancellation for background work, including active FFmpeg processes.
- Added FFmpeg timeouts and reliable cleanup of incomplete output files.
- Improved recursive folder scanning by indexing each directory once.
- Added Windows reserved-name and invalid-filename protection.
- Removed settings that had no effect.
- Locked Python dependencies and added Ruff checks to CI.

### 中文说明

- 为后台任务增加协作式取消，包括正在运行的 FFmpeg 进程。
- 增加 FFmpeg 超时控制，并可靠清理未完成的输出文件。
- 改进递归文件夹扫描：每个目录只索引一次。
- 增加 Windows 保留文件名与非法文件名的保护。
- 移除没有任何实际作用的设置项。
- 锁定 Python 依赖版本，并在 CI 中加入 Ruff 检查。

## 1.0.1

- Pinned the bundled FFmpeg to 9.0.2 and refreshed the third-party notice.
- Added a workflow that vendors FFmpeg into this repository's own release, so the
  pinned download no longer breaks when the upstream build disappears.
- Added the ghost-scan helper script with its own test coverage and notes.

### 中文说明

- 将随附的 FFmpeg 固定为 9.0.2，并更新第三方组件说明。
- 新增工作流把 FFmpeg 固化到本仓库的 Release 中，上游构建消失时固定版本的下载不再失效。
- 加入 ghost-scan 辅助脚本，并配套测试与说明文档。

## 1.0

- First Windows release: audio preview with synchronized lyrics, tag and artwork
  editing, lyrics/subtitle conversion, audio and image conversion, and
  metadata-based batch renaming, all processed locally.

### 中文说明

- 首个 Windows 版本：音频预览与同步歌词、标签与封面编辑、歌词/字幕转换、音频与图片
  格式转换，以及基于标签的批量重命名；全部在本机处理。
