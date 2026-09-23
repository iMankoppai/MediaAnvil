# Changelog

## 1.4.0

- Lyrics can now be shifted in bulk. The offset that the editor and preview pages
  already applied to one file at a time can be applied to every file in a scanned
  folder, which suits a whole batch that is consistently early or late. Files
  without embedded lyrics are listed as skipped rather than failed, a negative
  shift still clamps at `00:00.00` instead of dropping lines, and one broken file
  does not stop the batch.
- Artwork can now be written in bulk in a second way. Matching already paired each
  track with the image beside it; in addition, one chosen image can now be written
  to every scanned file, which is what replacing the cover of a whole album needs.
  Formats other than JPG and PNG are converted before writing, and a missing image
  stops the batch without touching any file.
- Rename templates accept `{genre}`, handled exactly like the other fields: an
  empty genre is refused unless the fallback for missing fields is enabled, and
  illegal characters such as the slash in `Rock/Pop` are replaced so that a genre
  cannot move a file out of its folder.
- Fixed a layout fault that hid the track-number box in bulk tag editing behind the
  batch button. The batch fields now occupy two rows and the buttons sit below
  them.
- Fixed the Later/Earlier box being too narrow for its own text. The box left an
  18-pixel text field for a 26-pixel label, so `延后` appeared clipped as `延丿`,
  and the English `Earlier` was cut off as well. This affected all three places the
  box appears: the tag editor, bulk tag editing and the audio preview.

### 中文说明

- 歌词现在可以批量偏移。编辑页和预览页原本一次只能处理一个文件，现在可以把扫描到的
  整个文件夹统一提前或延后，适合整批歌词都偏了同样秒数的情况。没有内嵌歌词的文件会
  列为"跳过"而不是失败；负向偏移仍在 `00:00.00` 截断，不会丢行；个别文件损坏也不会
  中断整批处理。
- 封面新增第二种批量写法。原有的"智能匹配"会为每首歌配好它旁边的图片；现在还可以
  指定一张图片写入所有已扫描的文件，这正是整张专辑统一换封面需要的。JPG、PNG 之外的
  格式会在写入前自动转换；图片不存在时会中止整批，且不碰任何文件。
- 重命名模板支持 `{genre}`，处理方式与其他字段完全一致：流派为空时默认拒绝，除非开启
  "缺少字段时使用原文件名代替"；`Rock/Pop` 里的斜杠等非法字符会被替换，流派无法把文件
  移到别的文件夹。
- 修复了批量标签编辑中"曲目号"输入框被"批量写入标签"按钮遮住的问题。现在批量字段占
  两行，按钮位于它们下方。
- 修复了"延后/提前"下拉框太窄导致文字显示不全的问题。该下拉框只给文字留出 18 像素，
  而"延后"需要 26 像素，因此显示成"延丿"，英文的 `Earlier` 同样被裁。标签编辑页、
  批量标签编辑和音频预览三处都受影响，现已全部修正。

## 1.3.0

- The audio preview page can offset the lyric timeline. Choose a direction and a
  number of seconds, and the highlighted line moves immediately so the offset can
  be judged while listening; Reset restores the file's own timing. Nothing is
  written until "Save to Audio" is pressed, and that always produces a new file,
  so the preview page never modifies the source. LRC timestamps are rewritten in
  place, keeping metadata lines such as `[ti:]`, while SRT and VTT are re-rendered
  from shifted cues because their timestamps are ranges rather than points.
- Joining and splitting can now fade the audio in and out and normalise its
  loudness. Both are off by default. Loudness is levelled per input before the
  join, so tracks recorded at different volumes end up at a similar level; a fade
  longer than the clip is shortened to half its length rather than fading the
  audio back up at the end.
- The join list can be reordered by dragging an entry or with the new Move Up and
  Move Down buttons. The order shown is the order used for the merge.
- Genre can now be read and written for MP3, FLAC, M4A and OGG, and the tag
  editor can change it alongside the other basic fields. Bulk tag editing gained
  genre and track number; as before, a blank box never erases an existing value.

### 中文说明

- 音频预览页现在可以整体偏移歌词时间轴。选择方向并填入秒数后，高亮行会立即移动，
  可以一边播放一边判断偏移是否合适；“重置”可恢复文件原本的时间轴。在点击
  “保存到音频”之前不会写入任何内容，而保存始终生成新文件，因此预览页不会修改源文件。
  LRC 采用原文本替换时间戳，`[ti:]` 等元数据行会被保留；SRT 与 VTT 的时间是区间而非
  单点，因此由偏移后的字幕重新渲染。
- 音频合并与分割新增淡入淡出和音量标准化，两项默认关闭。音量标准化在拼接前逐个输入
  处理，因此音量不同的录音可以得到接近的响度；淡入淡出时长超过音频本身时会缩短为
  音频的一半，不会出现结尾反而变响的情况。
- 合并列表可以拖动条目调整顺序，也可以使用新增的“上移”“下移”按钮。列表显示的顺序
  就是实际拼接的顺序。
- 现在可以读写 MP3、FLAC、M4A 和 OGG 的流派，标签编辑器可在基本信息中修改。批量标签
  编辑新增流派与曲目号；与之前一致，留空的输入框不会清掉已有标签。

## 1.2.0

- The tag editor can now change the track number and the year, not just title,
  artist and album. Both were already read and used by batch rename, but there
  was no way to correct them. The year is written to `TDRC` on ID3v2.4 and
  `TYER` on ID3v2.3, matching how the reader already looks them up, and the other
  spelling is removed so a file never carries two conflicting years.
- Added an audio join / split page. Several files can be concatenated in list
  order, or one file can be cut into equal parts or fixed-length pieces. Output
  is always a new file; sources are never modified or deleted.
- Added bulk tag editing: after scanning a music folder, fill in any of album,
  artist or year and write the same values to every scanned file. Blank boxes are
  left untouched, so an untouched field never erases an existing tag, and one
  failing file does not stop the rest.
- Added whole-timeline lyric offsetting on the tag editor. Choose a direction and
  a number of seconds to move every timestamp, then save to write it into the
  audio. Timestamps are rewritten in place, so metadata lines such as `[ti:]` and
  `[ar:]` are preserved, and a negative shift clamps at zero instead of dropping
  lines.

### 中文说明

- 标签编辑器现在可以修改曲目号与年份，不再只有歌名、歌手和专辑。这两项此前能被读取、
  也被批量重命名使用，却没有任何办法修正。年份在 ID3v2.4 写入 `TDRC`、在 ID3v2.3
  写入 `TYER`，与读取端的查找顺序一致；写入时会删除另一种写法，避免一个文件带有两个
  互相冲突的年份。
- 新增「音频合并 / 分割」页面。可以把多个文件按列表顺序拼接，也可以把单个文件按段数
  等分或按每段时长切分。输出始终是新文件，源文件不会被修改或删除。
- 新增批量标签编辑：扫描音乐文件夹后，填写专辑、歌手或年份中的任意项，即可把相同的值
  写入全部已扫描文件。留空的输入框不会改动原值，因此未填写的字段绝不会清掉已有标签；
  单个文件失败也不会中断其余文件。
- 标签编辑器新增歌词时间轴整体偏移。选择提前或延后并填入秒数，即可整体调整所有时间戳，
  保存后写入音频。时间戳采用原文本替换，`[ti:]`、`[ar:]` 等元数据行会被保留；负向偏移
  在 0 秒处截断，不会丢弃歌词行。

## ffmpeg-vendor-9.0.2

- Vendored FFmpeg 9.0.2. Verified essentials build from gyan.dev, published as an
  asset of this repository so the pinned download in `tools/download_ffmpeg.ps1`
  never breaks when gyan.dev drops an old version.

### 中文说明

- 固化 FFmpeg 9.0.2。来自 gyan.dev 的官方 essentials 构建，经校验后作为本仓库的
  Release 资源发布，使 `tools/download_ffmpeg.ps1` 中固定版本的下载在 gyan.dev
  下线旧版本时不会失效。

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
  The 1.0.1 vendoring of ICU was reverted: the frozen application now loads ICU
  from Windows instead of shipping a copy beside Qt6Core.dll.
- Strengthened the frozen-app smoke test so an error dialog can no longer be mistaken for a successful launch.
  This is why the failure reached a release: startup reported the problem through
  a dialog, the smoke test still exited successfully, and a green run was read as
  a working build. The test now treats any error dialog as a failure, and the
  build rejects a bundled ICU outright, so the same regression cannot ship again.

### 中文说明

- 修复因随附的 ICU DLL 不兼容而导致的 Windows 启动失败。1.0.1 引入的 ICU 随包方案已
  回退：冻结版改为使用 Windows 自带的 ICU，不再在 Qt6Core.dll 旁边附带一份副本。
- 强化冻结版烟雾测试：错误弹窗不再被误判为启动成功。这正是该问题流入正式版本的原因
  ——启动失败是通过弹窗报告的，而烟雾测试仍然正常退出，于是一次「全绿」被当成了可用
  的构建。现在测试把任何错误弹窗都视为失败，构建也会直接拒绝随包的 ICU，同类回归
  无法再次发布出去。

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

- First Windows release. MediaAnvil is a local, offline toolbox: media files are
  processed on this computer and source files are preserved by default.
- Audio preview: play MP3, WAV, FLAC, M4A, AAC, OGG and Opus with play/pause
  (Space), 30-second skip, volume and a seekable progress bar.
- Synchronized lyrics: read a matching LRC, SRT or VTT beside the audio,
  including double-suffix names such as `song.wav.vtt` and embedded MP3 lyrics,
  with an option to prefer the embedded copy. Clicking a line seeks to it.
- Tag editor: change title, artist and album, and import or remove lyrics and
  artwork. SRT/VTT are converted to LRC in memory before being written, and
  saving defaults to "save as" so the source file stays untouched.
- Artwork handling: preview, import, export and remove cover images, with a free
  rectangular crop when importing.
- Smart matching: scan a music folder for same-name lyrics and artwork, including
  double-suffix names, and batch-write the chosen matches.
- Lyrics and subtitle conversion between LRC, SRT and VTT, preserving multi-line
  content and avoiding existing files.
- Audio conversion between MP3, WAV, FLAC, M4A/AAC and OGG, with bitrate,
  quality, sample rate, channel and metadata-preservation options.
- Image conversion between JPG, PNG, WebP and BMP, with quality settings and
  transparent-background handling.
- Batch rename from audio tags, with a conflict preview before executing and an
  undo for the most recent batch.
- Simplified Chinese and English interfaces, switchable at runtime.

### 中文说明

- 首个 Windows 版本。MediaAnvil 是一款本地、离线的多媒体工具箱：媒体文件全部在本机
  处理，默认保留原文件。
- 音频预览：播放 MP3、WAV、FLAC、M4A、AAC、OGG、Opus，支持空格播放/暂停、
  前后 30 秒跳转、音量调节与可拖动进度条。
- 同步歌词：读取音频旁同名的 LRC、SRT 或 VTT，也支持 `歌曲.wav.vtt` 这类双后缀
  命名以及 MP3 内嵌歌词，并可设置优先使用内嵌歌词。点击任意歌词行可跳转到对应时间。
- 标签编辑：修改歌名、歌手与专辑，导入或移除歌词和封面。SRT/VTT 会在内存中转换为
  LRC 后再写入；默认使用「另存为」，源文件保持不变。
- 封面处理：预览、导入、导出、移除封面图片，导入时提供自由矩形裁剪。
- 智能匹配：扫描音乐文件夹寻找同名的歌词与封面（含双后缀命名），可批量写入所选关联
  文件。
- 歌词与字幕转换：LRC、SRT、VTT 三种格式互转，保留多行内容并自动避开已有文件。
- 音频格式转换：MP3、WAV、FLAC、M4A/AAC、OGG 互转，支持码率、质量、采样率、
  声道与元数据保留设置。
- 图片格式转换：JPG、PNG、WebP、BMP 互转，支持质量设置与透明背景处理。
- 批量重命名：根据音频标签生成文件名，执行前预览冲突，支持撤销最近一次批量重命名。
- 提供简体中文与英文界面，可在运行时切换。
