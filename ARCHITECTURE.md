# 代码维护入口

界面在 `mediaanvil_qt/`，业务处理在 `core/` 和 `sub2lrc/`。新增功能时先确定职责，避免把后台处理或专用控件继续堆进页面文件。

| 职责 | 文件 |
| --- | --- |
| 主窗口组装、导航、设置和预设 | `mediaanvil_qt/app.py` |
| 后台任务执行、取消和队列调度 | `mediaanvil_qt/task_execution.py` |
| 任务记录持久化、展示、重试和报告入口 | `mediaanvil_qt/task_history.py` |
| 文件夹导入、拖放和分批加载 | `mediaanvil_qt/file_imports.py` |
| 文件对话框目录和筛选器记忆 | `mediaanvil_qt/file_dialogs.py` |
| 通用按钮、卡片、响应式布局、分段页签 | `mediaanvil_qt/layouts.py` |
| 页面标题和文件工具栏 | `mediaanvil_qt/page.py` |
| 文件列表、勾选、排序和输出路径控件 | `mediaanvil_qt/file_widgets.py` |
| 表格填充和单元格显示 | `mediaanvil_qt/table_widgets.py` |
| 图片预览和缩略图缓存 | `mediaanvil_qt/image_widgets.py` |
| 封面显示和裁剪交互 | `mediaanvil_qt/cover_widgets.py` |
| 波形绘制和选区交互 | `mediaanvil_qt/waveform.py` |
| 后台线程、进度和取消令牌适配 | `mediaanvil_qt/workers.py` |
| 播放进度和音量滑块交互 | `mediaanvil_qt/sliders.py` |
| 预览页面布局、播放器生命周期和播放控制 | `mediaanvil_qt/preview.py` |
| 预览播放队列、顺序和随机播放 | `mediaanvil_qt/preview_queue.py` |
| 歌词显示、偏移预览和保存 | `mediaanvil_qt/preview_lyrics.py` |
| 语言切换和翻译逻辑 | `mediaanvil_qt/i18n.py` |
| 英文界面文案 | `mediaanvil_qt/translations_en.py` |
| 统一色彩、字体、控件样式 | `mediaanvil_qt/theme.py` |
| 预览页封面、歌词和固定播放控制布局 | `mediaanvil_qt/preview_layout.py` |
| 工具页布局、响应式操作区和按钮网格 | `mediaanvil_qt/tool_layouts.py` |
| 任务中心与关于页面的组装 | `mediaanvil_qt/utility_pages.py` |

`common.py` 保留原有导入入口，已有页面可以继续使用。新增公共组件应写入相应职责模块，新模块之间直接导入实际实现，避免通过兼容入口形成循环依赖。

主窗口和预览页面的 mixin 复用宿主初始化的状态及控件，不另建 QObject 或重复维护任务、播放器状态。Qt 控件更新留在 GUI 线程；提交后台任务时先捕获路径、参数和待保存内容，避免后台任务读取后来被用户修改的界面状态。

回归检查使用现有 unittest 测试集和 Ruff。`tests/test_refactor_regressions.py` 覆盖拆分过程中发现的多选排序、双语状态颜色和歌词保存快照问题。
