"""Application palette and Qt styling for the approved desktop reference design."""
import sys
from pathlib import Path

ACCENT = '#315cff'
INK = '#192338'

STYLE = '''
QWidget { font-family:"Microsoft YaHei UI"; font-size:13px; color:#192338; }
QMainWindow, QWidget#shell { background:#f5f6f8; }
QScrollArea, QScrollArea>QWidget>QWidget { background:transparent; border:none; }
QWidget#sidebar { background:#f1f4f9; border-right:1px solid #e0e5ee; }
QLabel { background:transparent; border:0; }
QLabel#pageTitle { font-size:28px; font-weight:700; color:#141d32; }
QLabel#sectionTitle { font-size:16px; font-weight:600; }
QLabel#trackTitle { font-size:23px; font-weight:700; }
QLabel#brand { font-size:19px; font-weight:700; }
QLabel#muted, QLabel#version { color:#6a7891; font-size:12px; }
QLabel#eyebrow, QLabel#navHeading { color:#697994; font-size:12px; letter-spacing:1px; }
QLabel#navHeading { padding:16px 12px 8px; }
QLabel#localStatus { color:#697994; padding:12px; font-size:12px; }
QLabel#pageBadge { background:transparent; }
QLabel#iconBadge { background:#eef2ff; border-radius:8px; }
QLabel#notice { color:#63718a; background:#f3f6fc; padding:8px; border-radius:7px; }
QLabel#success { background:#eaf8f1; color:#148957; padding:8px; border-radius:7px; }
QLabel#artwork { background:#eef2f9; border:1px solid #e0e6ef; border-radius:10px; font-size:64px; color:#9bb0d4; }
QLabel#coverPreview { background:#f8f9fc; border:1px solid #e8edf5; border-radius:8px; }
QFrame#card { background:white; border:1px solid #e1e7f0; border-radius:10px; }
QWidget#actionFooter { background:white; border-top:1px solid #e0e6ef; }
QWidget#playerDock { background:white; border-top:1px solid #e0e6ef; }
QPushButton { background:white; border:1px solid #d5ddeb; border-radius:7px; padding:7px 12px; min-height:18px; }
QPushButton:hover { background:#f0f4ff; border-color:#9bb0fa; }
QPushButton:pressed { background:#e8eeff; }
QPushButton:focus { border-color:#315cff; }
QPushButton[primary="true"] { background:#315cff; color:white; border-color:#315cff; font-weight:600; }
QPushButton[primary="true"]:hover { background:#224ce9; }
QPushButton[danger="true"] { color:#db4054; border-color:#efbdc5; background:white; }
QPushButton:disabled { color:#a3adbf; background:#f5f7fa; border-color:#e5eaf2; }
QPushButton#roundControl { min-width:38px; max-width:38px; min-height:38px; max-height:38px; border:0; border-radius:19px; padding:0; background:transparent; }
QPushButton#roundControl:hover { background:#edf2ff; }
QPushButton#roundPlay { min-width:54px; max-width:54px; min-height:54px; max-height:54px; border:0; border-radius:27px; padding:0; background:#315cff; }
QPushButton#navItem { background:transparent; border:0; border-radius:8px; text-align:left; padding:10px 12px; min-height:22px; font-size:14px; font-weight:500; }
QPushButton#navItem:hover { background:#e8edf7; }
QPushButton#navItem:checked { background:#dce5ff; color:#315cff; font-weight:600; }
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox { background:white; border:1px solid #d5ddeb; border-radius:6px; padding:6px 10px; min-height:18px; selection-background-color:#dce5ff; selection-color:#192338; }
QLineEdit:read-only { background:#fafbfe; }
QLineEdit:focus,QComboBox:focus,QSpinBox:focus,QDoubleSpinBox:focus { border-color:#315cff; }
QLineEdit:disabled,QComboBox:disabled,QSpinBox:disabled,QDoubleSpinBox:disabled { color:#a3adbf; background:#f5f7fa; }
QComboBox::drop-down { border:0; width:26px; }
QComboBox::down-arrow { image:url("@ASSETS@/chevron-down.svg"); width:12px; height:8px; }
QComboBox QAbstractItemView { background:white; border:1px solid #d5ddeb; selection-background-color:#e8eeff; selection-color:#192338; padding:4px; }
QSpinBox::up-button,QDoubleSpinBox::up-button { subcontrol-origin:border; subcontrol-position:top right; width:22px; border:0; margin:2px 2px 0 0; }
QSpinBox::down-button,QDoubleSpinBox::down-button { subcontrol-origin:border; subcontrol-position:bottom right; width:22px; border:0; margin:0 2px 2px 0; }
QSpinBox::up-arrow,QDoubleSpinBox::up-arrow { image:url("@ASSETS@/chevron-up.svg"); width:10px; height:7px; }
QSpinBox::down-arrow,QDoubleSpinBox::down-arrow { image:url("@ASSETS@/chevron-down.svg"); width:10px; height:7px; }
QListWidget,QPlainTextEdit,QTableWidget,QTableView { background:white; border:1px solid #e1e7f0; border-radius:7px; selection-background-color:#edf2ff; selection-color:#192338; padding:4px; }
QListWidget::item { padding:8px; border-radius:6px; }
QListWidget::item:hover { background:#f4f7ff; }
QHeaderView::section { background:#f3f5fa; color:#61718c; border:0; border-bottom:1px solid #e6ebf3; padding:10px 8px; font-weight:500; }
QTableWidget,QTableView { gridline-color:#edf0f5; }
QCheckBox { spacing:8px; min-height:23px; }
QCheckBox::indicator,QAbstractItemView::indicator { width:16px; height:16px; }
QCheckBox::indicator:unchecked,QAbstractItemView::indicator:unchecked { border:1px solid #bac7db; border-radius:4px; background:white; }
QCheckBox::indicator:checked,QAbstractItemView::indicator:checked { border:1px solid #315cff; border-radius:4px; background:#315cff; image:url("@ASSETS@/check.svg"); }
QTabWidget::pane { border:0; background:transparent; }
QTabBar::tab { color:#63718a; padding:11px 18px; border-bottom:3px solid transparent; }
QTabBar::tab:selected { color:#315cff; border-bottom-color:#315cff; }
QProgressBar { border:0; border-radius:4px; background:#e6ebf5; text-align:center; color:#63718a; }
QProgressBar::chunk { background:#315cff; border-radius:4px; }
QSlider:horizontal { padding:0 8px; }
QSlider::groove:horizontal { height:5px; background:#dfe5ef; border-radius:2px; }
QSlider::sub-page:horizontal { background:#6687ff; border-radius:2px; }
QSlider::handle:horizontal { background:#315cff; border:2px solid white; width:12px; height:12px; margin:-6px 0; border-radius:8px; }
QScrollBar:vertical { background:transparent; width:8px; margin:2px; }
QScrollBar::handle:vertical { background:#cbd4e3; border-radius:3px; min-height:30px; }
QScrollBar::handle:vertical:hover { background:#abbad0; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical { background:transparent; }
QStatusBar { background:white; color:#697994; border-top:1px solid #e4e9f2; font-size:11px; }
QSplitter::handle { background:transparent; width:12px; }
QToolTip { background:white; color:#192338; border:1px solid #d5ddeb; padding:6px; }
'''
STYLE = STYLE.replace('@ASSETS@', (Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / 'assets' / 'qt').as_posix())
