import json
import os
import sys
import threading
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QObject, QPropertyAnimation, QSize, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent, QFont, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import transcribe

APP_DIR = Path(__file__).resolve().parent
CONFIG_FILE = APP_DIR / "config.json"
ICON_SOURCE = APP_DIR / "assets" / "app_icon_source.png"

DEFAULT_PROMPT = (
    "Umpisahan natin ang recording. This is a conversation between speakers who are fluent "
    "in Tagalog and English. So expect natural code-switching throughout the discussion."
)

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".ogg", ".flac", ".aac", ".wma"}

LANGUAGE_MAP = {
    "Tagalog (tl)": "tl",
    "English (en)": "en",
    "Auto detect": None,
    "Spanish (es)": "es",
    "French (fr)": "fr",
    "German (de)": "de",
    "Japanese (ja)": "ja",
    "Korean (ko)": "ko",
    "Chinese (zh)": "zh",
}

MODEL_OPTIONS = ["turbo", "tiny", "base", "small", "medium", "large", "large-v3"]

THEME = {
    "bg": "#f7f3ec",
    "surface": "#fdf9f2",
    "surface_elevated": "#fffdf9",
    "panel": "#f8f1e6",
    "line": "#e8dfd0",
    "line_strong": "#d9cdb9",
    "text": "#1f1a14",
    "text_soft": "#5f5548",
    "text_muted": "#8c8170",
    "accent": "#b89b60",
    "accent_text": "#7b6638",
    "accent_soft": "#eee1c5",
    "success": "#78966f",
    "danger": "#b96b62",
}


def build_stylesheet(tokens: dict) -> str:
    return f"""
        QMainWindow {{
            background: {tokens['bg']};
        }}

        QWidget {{
            color: {tokens['text']};
            font-family: "Avenir Next", "Helvetica Neue";
            font-size: 13px;
        }}

        QFrame#MainShell {{
            background: transparent;
            border: none;
        }}

        QFrame#TopNav {{
            background: transparent;
            border: none;
        }}

        QPushButton#NavLink {{
            border: none;
            background: transparent;
            color: {tokens['text']};
            padding: 2px 6px;
            font-size: 14px;
            font-weight: 500;
        }}

        QPushButton#NavLink:hover {{
            color: {tokens['text_soft']};
        }}

        QLabel#AvatarPill {{
            min-width: 34px;
            max-width: 34px;
            min-height: 34px;
            max-height: 34px;
            border-radius: 17px;
            background: #ece4d6;
            color: {tokens['text_soft']};
            font-size: 16px;
            font-weight: 620;
        }}

        QLabel#HeroTitle {{
            color: {tokens['text']};
            font-family: "Georgia", "Times New Roman", "Baskerville";
            font-size: 64px;
            font-weight: 560;
        }}

        QLabel#HeroSub {{
            color: {tokens['text_soft']};
            font-family: "Georgia", "Times New Roman", "Baskerville";
            font-size: 28px;
            font-weight: 420;
        }}

        QFrame#DropCard {{
            background: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 {tokens['surface_elevated']},
                stop: 1 {tokens['panel']}
            );
            border: 1px solid {tokens['line']};
            border-radius: 16px;
        }}

        QFrame#DropArea {{
            background: transparent;
            border: none;
            border-radius: 12px;
        }}

        QLabel#DropIcon {{
            color: {tokens['line_strong']};
            font-size: 38px;
            font-family: "Georgia", "Times New Roman", "Baskerville";
            font-weight: 420;
        }}

        QLabel#DropTitle {{
            color: {tokens['text']};
            font-family: "Georgia", "Times New Roman", "Baskerville";
            font-size: 34px;
            font-weight: 510;
        }}

        QLabel#DropBody {{
            color: {tokens['text_soft']};
            font-size: 15px;
            font-weight: 500;
        }}

        QPushButton#BrowseButton {{
            background: {tokens['accent']};
            color: #f8f2e5;
            border: 1px solid {tokens['accent']};
            border-radius: 17px;
            font-size: 14px;
            font-weight: 580;
            padding: 8px 20px;
        }}

        QPushButton#BrowseButton:hover {{
            background: #a88c55;
            border-color: #a88c55;
        }}

        QFrame#MetaStatus {{
            background: transparent;
            border: none;
        }}

        QLabel#Meta {{
            color: {tokens['text_muted']};
            font-size: 13px;
        }}

        QLabel#RecentTitle {{
            color: {tokens['text']};
            font-family: "Georgia", "Times New Roman", "Baskerville";
            font-size: 40px;
            font-weight: 540;
        }}

        QFrame#RecentList {{
            background: transparent;
            border: none;
        }}

        QFrame#RecentRow {{
            background: {tokens['surface_elevated']};
            border: 1px solid {tokens['line']};
            border-radius: 12px;
        }}

        QLabel#RecentName {{
            color: {tokens['text']};
            font-size: 14px;
            font-weight: 520;
        }}

        QLabel#RecentState {{
            color: {tokens['text_soft']};
            font-size: 14px;
        }}

        QLabel#RecentState[state="completed"] {{
            color: {tokens['success']};
            font-weight: 580;
        }}

        QLabel#RecentState[state="processing"] {{
            color: {tokens['accent_text']};
            font-weight: 580;
        }}

        QLabel#RecentState[state="draft"] {{
            color: {tokens['text_muted']};
        }}

        QPushButton#RecentViewButton {{
            border: none;
            background: transparent;
            color: {tokens['accent_text']};
            font-size: 14px;
            font-weight: 540;
        }}

        QPushButton#RecentViewButton:hover {{
            color: {tokens['text']};
        }}

        QFrame#ControlsPane {{
            background: {tokens['surface']};
            border: 1px solid {tokens['line']};
            border-radius: 12px;
        }}

        QLabel#ControlsTitle {{
            color: {tokens['text']};
            font-size: 20px;
            font-weight: 620;
        }}

        QLabel#FieldLabel {{
            color: {tokens['text_muted']};
            font-size: 12px;
            font-weight: 560;
        }}

        QFrame#AdvancedPane {{
            border-top: 1px solid {tokens['line']};
            background: transparent;
        }}

        QLineEdit,
        QComboBox,
        QTextEdit {{
            border: 1px solid {tokens['line_strong']};
            border-radius: 9px;
            background: {tokens['surface_elevated']};
            color: {tokens['text']};
            padding: 8px 10px;
            selection-background-color: {tokens['accent']};
            selection-color: #ffffff;
        }}

        QComboBox {{
            padding-right: 26px;
        }}

        QComboBox::drop-down {{
            width: 22px;
            border: none;
        }}

        QComboBox::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {tokens['text_muted']};
            margin-right: 6px;
        }}

        QComboBox QAbstractItemView {{
            border: 1px solid {tokens['line_strong']};
            background: {tokens['surface_elevated']};
            color: {tokens['text']};
        }}

        QLineEdit:focus,
        QComboBox:focus,
        QTextEdit:focus,
        QPushButton:focus {{
            border: 1px solid {tokens['accent']};
            outline: none;
        }}

        QCheckBox {{
            color: {tokens['text_soft']};
            spacing: 8px;
            font-size: 13px;
        }}

        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 4px;
            border: 1px solid {tokens['line_strong']};
            background: {tokens['surface_elevated']};
        }}

        QCheckBox::indicator:checked {{
            border: 1px solid {tokens['accent']};
            background: {tokens['accent']};
        }}

        QPushButton {{
            border: 1px solid {tokens['line_strong']};
            border-radius: 9px;
            padding: 9px 14px;
            background: {tokens['surface_elevated']};
            color: {tokens['text']};
            font-size: 13px;
            font-weight: 560;
        }}

        QPushButton:hover {{
            background: {tokens['surface']};
        }}

        QPushButton#PrimaryButton {{
            border: 1px solid {tokens['accent']};
            background: {tokens['accent']};
            color: #f9f2e3;
            font-weight: 620;
            padding: 9px 14px;
        }}

        QPushButton#PrimaryButton:disabled {{
            border-color: #d5c6a8;
            background: #d5c6a8;
            color: #f3ede0;
        }}

        QPushButton#SecondaryButton {{
            border: 1px solid {tokens['line_strong']};
            background: {tokens['surface_elevated']};
            color: {tokens['text_soft']};
        }}

        QPushButton#SecondaryButton:hover {{
            background: {tokens['surface']};
        }}

        QPushButton#GhostButton {{
            border: none;
            border-radius: 6px;
            color: {tokens['accent_text']};
            text-align: left;
            padding: 2px 0px;
            background: transparent;
            font-weight: 580;
        }}

        QPushButton#GhostButton:hover {{
            color: {tokens['text']};
            background: transparent;
        }}

        QFrame#ProcessingPane,
        QFrame#ResultPane {{
            background: {tokens['surface_elevated']};
            border: 1px solid {tokens['line']};
            border-radius: 14px;
        }}

        QLabel#StatusHeadline {{
            color: {tokens['text']};
            font-family: "Georgia", "Times New Roman", "Baskerville";
            font-size: 40px;
            font-weight: 540;
        }}

        QLabel#StatusText {{
            color: {tokens['text_soft']};
            font-size: 14px;
        }}

        QLabel#SectionTitle {{
            color: {tokens['text']};
            font-size: 21px;
            font-weight: 620;
        }}

        QLabel#StageChip {{
            color: {tokens['text_muted']};
            font-size: 12px;
            border: 1px solid {tokens['line']};
            border-radius: 11px;
            padding: 4px 9px;
            background: {tokens['surface']};
        }}

        QLabel#StageChip[state="active"] {{
            color: {tokens['accent_text']};
            border-color: {tokens['accent']};
            background: {tokens['accent_soft']};
            font-weight: 620;
        }}

        QLabel#StageChip[state="done"] {{
            color: {tokens['success']};
            border-color: #c8d8bf;
            background: #f1f8ed;
            font-weight: 620;
        }}

        QLabel#StageChip[state="pending"] {{
            color: {tokens['text_muted']};
        }}

        QTextEdit#ActivityLog {{
            background: {tokens['surface']};
            border-radius: 12px;
            padding: 10px;
        }}

        QProgressBar {{
            border: 1px solid {tokens['line']};
            border-radius: 9px;
            background: {tokens['surface']};
            color: {tokens['text']};
            text-align: center;
            height: 15px;
            font-size: 11px;
        }}

        QProgressBar::chunk {{
            border-radius: 9px;
            background: {tokens['accent']};
        }}
    """


class TranscriptionWorker(QObject):
    status = pyqtSignal(str)
    log = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, audio_path: str, settings: dict, output_root: str, move_source_file: bool):
        super().__init__()
        self.audio_path = audio_path
        self.settings = settings
        self.output_root = output_root
        self.move_source_file = move_source_file
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        def on_progress(message: str):
            self.status.emit(message)
            self.log.emit(message)

        try:
            result = transcribe.run_pipeline(
                audio_file=self.audio_path,
                model=self.settings.get("model", "turbo"),
                prompt=self.settings.get("prompt", DEFAULT_PROMPT),
                language=self.settings.get("language", "tl"),
                hf_token=self.settings.get("hf_token", ""),
                clean_audio=self.settings.get("clean_audio", True),
                diarization=self.settings.get("diarization", False),
                move_original_file=self.move_source_file,
                output_root_dir=self.output_root or None,
                verbose=False,
                progress_callback=on_progress,
            )
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class DropArea(QFrame):
    fileDropped = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("DropArea")
        self.setAcceptDrops(True)
        self.setProperty("state", "idle")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)

        self.icon_label = QLabel("~  🎙  ~")
        self.icon_label.setObjectName("DropIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel("Drag & drop your audio file here.")
        self.title_label.setObjectName("DropTitle")
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.body_label = QLabel("Supports MP3, WAV, M4A, OGG, FLAC, AAC, WMA.")
        self.body_label.setObjectName("DropBody")
        self.body_label.setWordWrap(True)
        self.body_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.browse_button = QPushButton("Browse Files")
        self.browse_button.setObjectName("BrowseButton")
        self.browse_button.clicked.connect(self.browse_for_file)

        layout.addStretch()
        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)
        layout.addWidget(self.browse_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()

    def _refresh(self):
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def reset(self):
        self.setProperty("state", "idle")
        self.icon_label.setText("~  🎙  ~")
        self.title_label.setText("Drag & drop your audio file here.")
        self.body_label.setText("Supports MP3, WAV, M4A, OGG, FLAC, AAC, WMA.")
        self.browse_button.setText("Browse Files")
        self._refresh()

    def set_ready(self, file_name: str):
        self.setProperty("state", "ready")
        self.icon_label.setText("✓")
        self.title_label.setText("File ready")
        self.body_label.setText(file_name)
        self.browse_button.setText("Choose Another")
        self._refresh()

    def set_error(self, message: str):
        self.setProperty("state", "error")
        self.icon_label.setText("!")
        self.title_label.setText("Unsupported file")
        self.body_label.setText(message)
        self._refresh()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(Path(url.toLocalFile()).suffix.lower() in AUDIO_EXTENSIONS for url in urls):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        valid_files = [f for f in files if Path(f).suffix.lower() in AUDIO_EXTENSIONS]
        if valid_files:
            self.fileDropped.emit(valid_files[0])
        else:
            self.set_error("Please use a supported audio file format")

    def browse_for_file(self):
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio File",
            str(Path.home()),
            "Audio Files (*.mp3 *.wav *.m4a *.ogg *.flac *.aac *.wma)",
        )
        if selected:
            self.fileDropped.emit(selected)

    def mousePressEvent(self, event):
        self.browse_for_file()
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    PAGE_SETUP = 0
    PAGE_PROCESSING = 1
    PAGE_RESULT = 2

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Whisper Canvas")
        self.resize(1120, 760)
        self.setMinimumSize(860, 620)

        self.config = self.load_config()

        self.selected_file = ""
        self.last_output_folder = ""
        self.activity_lines = []

        self.loading_frames = ["● ○ ○", "○ ● ○", "○ ○ ●"]
        self.loading_index = 0

        self.stage_order = ["Preparing", "Transcribing", "Diarizing", "Finalizing"]
        self.stage_labels = {}
        self.current_stage_index = 0

        self.worker = None

        self.loading_timer = QTimer(self)
        self.loading_timer.setInterval(300)
        self.loading_timer.timeout.connect(self._tick_loading)

        self._setup_ui()
        self._apply_theme()
        self.restore_settings()

    def _setup_ui(self):
        root = QWidget()
        self.setCentralWidget(root)

        page = QVBoxLayout(root)
        page.setContentsMargins(24, 16, 24, 16)
        page.setSpacing(0)

        shell = QFrame()
        shell.setObjectName("MainShell")
        self.shell = shell

        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(10)

        top_nav = QFrame()
        top_nav.setObjectName("TopNav")
        nav_layout = QHBoxLayout(top_nav)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(16)
        nav_layout.addStretch()

        self.pricing_button = QPushButton("Pricing")
        self.pricing_button.setObjectName("NavLink")
        self.pricing_button.setFlat(True)
        self.pricing_button.clicked.connect(lambda: self.show_setup_page())

        self.about_button = QPushButton("About")
        self.about_button.setObjectName("NavLink")
        self.about_button.setFlat(True)
        self.about_button.clicked.connect(
            lambda: self.show_dialog(
                "Transcription Studio",
                "Local Whisper transcription with optional diarization and export tools.",
                QMessageBox.Icon.Information,
            )
        )

        avatar = QLabel("AZ")
        avatar.setObjectName("AvatarPill")
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_pill = avatar

        nav_layout.addWidget(self.pricing_button)
        nav_layout.addWidget(self.about_button)
        nav_layout.addWidget(avatar)

        hero = QFrame()
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(0, 8, 0, 12)
        hero_layout.setSpacing(4)

        self.header_title = QLabel("Transcription Studio")
        self.header_title.setObjectName("HeroTitle")
        self.header_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.header_subtitle = QLabel("Premium AI-Powered Accuracy. Effortless Flow.")
        self.header_subtitle.setObjectName("HeroSub")
        self.header_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hero_layout.addWidget(self.header_title)
        hero_layout.addWidget(self.header_subtitle)

        self.stack = QStackedWidget()
        self.stack_wrap = QWidget()
        self.stack_wrap.setMaximumWidth(980)
        wrap_layout = QVBoxLayout(self.stack_wrap)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.addWidget(self.stack)

        self.recent_items = [
            {"name": "Interview_with_CEO.mp3", "status": "completed"},
            {"name": "Team_Meeting_Oct24.wav", "status": "processing"},
            {"name": "Podcast_Episode_05.mp3", "status": "draft"},
        ]

        self.setup_page = self._build_setup_page()
        self.processing_page = self._build_processing_page()
        self.result_page = self._build_result_page()

        self.stack.addWidget(self.setup_page)
        self.stack.addWidget(self.processing_page)
        self.stack.addWidget(self.result_page)

        shell_layout.addWidget(top_nav)
        shell_layout.addWidget(hero)
        shell_layout.addWidget(self.stack_wrap, alignment=Qt.AlignmentFlag.AlignHCenter, stretch=1)

        page.addWidget(shell, stretch=1)

    def _set_brand_icon(self, target: QLabel, size: int):
        if ICON_SOURCE.exists():
            pixmap = QPixmap(str(ICON_SOURCE))
            if not pixmap.isNull():
                target.setPixmap(
                    pixmap.scaled(
                        size,
                        size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                return
        target.setText("🎙")

    def _build_stepper(self, layout: QHBoxLayout):
        # Kept for backward compatibility with older layout versions.
        self.wizard_steps = []
        self.wizard_step_nodes = {}
        self.wizard_connectors = []

    def _make_step_node(self, label: str, symbol: str):
        node = QWidget()
        node.setObjectName("StepNode")
        box = QVBoxLayout(node)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(7)

        dot = QLabel(symbol)
        dot.setObjectName("StepDot")
        dot.setProperty("state", "pending")

        text = QLabel(label)
        text.setObjectName("StepText")
        text.setProperty("state", "pending")

        box.addWidget(dot, alignment=Qt.AlignmentFlag.AlignHCenter)
        box.addWidget(text, alignment=Qt.AlignmentFlag.AlignHCenter)
        return node, dot, text

    def _set_wizard_step(self, step_key: str):
        if not hasattr(self, "wizard_steps") or not self.wizard_steps:
            return

        active_index = self.wizard_steps.index(step_key)
        for idx, key in enumerate(self.wizard_steps):
            if idx < active_index:
                state = "done"
                symbol = "✓"
            elif idx == active_index:
                state = "active"
                symbol = self.wizard_step_symbols[key]
            else:
                state = "pending"
                symbol = self.wizard_step_symbols[key]

            node = self.wizard_step_nodes[key]
            node["dot"].setProperty("state", state)
            node["dot"].setText(symbol)
            node["text"].setProperty("state", state)
            self._refresh_widget_style(node["dot"])
            self._refresh_widget_style(node["text"])

        for idx, connector in enumerate(self.wizard_connectors):
            connector.setProperty("state", "done" if idx < active_index else "pending")
            self._refresh_widget_style(connector)

    def _refresh_widget_style(self, widget: QWidget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def _recent_status_icon(self, status: str) -> str:
        return {
            "completed": "●",
            "processing": "◌",
            "draft": "◦",
        }.get(status, "◦")

    def _recent_status_text(self, status: str) -> str:
        return {
            "completed": "Completed",
            "processing": "Processing",
            "draft": "Draft",
        }.get(status, status.title())

    def _refresh_recent_list(self):
        if not hasattr(self, "recent_rows_layout"):
            return

        while self.recent_rows_layout.count():
            item = self.recent_rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for entry in self.recent_items[:6]:
            row = QFrame()
            row.setObjectName("RecentRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(14, 9, 14, 9)
            row_layout.setSpacing(10)

            name = QLabel(f"{self._recent_status_icon(entry['status'])}  {entry['name']}")
            name.setObjectName("RecentName")

            state = QLabel(self._recent_status_text(entry["status"]))
            state.setObjectName("RecentState")
            state.setProperty("state", entry["status"])

            view = QPushButton("View")
            view.setObjectName("RecentViewButton")
            view.clicked.connect(self.show_result_page)

            row_layout.addWidget(name, stretch=1)
            row_layout.addWidget(state)
            row_layout.addWidget(view)

            self.recent_rows_layout.addWidget(row)

    def _build_setup_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(14)

        drop_card = QFrame()
        drop_card.setObjectName("DropCard")
        drop_card.setMinimumHeight(330)
        drop_layout = QVBoxLayout(drop_card)
        drop_layout.setContentsMargins(24, 18, 24, 16)
        drop_layout.setSpacing(6)

        self.drop_area = DropArea()
        self.drop_area.setMinimumHeight(250)
        self.drop_area.fileDropped.connect(self.on_file_selected)

        self.file_label = QLabel("No file selected")
        self.file_label.setObjectName("Meta")
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_label.setWordWrap(True)

        self.setup_status_label = QLabel("Drop a file to begin.")
        self.setup_status_label.setObjectName("Meta")
        self.setup_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setup_status_label.setWordWrap(True)

        self.start_button = QPushButton("Start Transcription")
        self.start_button.setObjectName("PrimaryButton")
        self.start_button.setEnabled(False)
        self.start_button.setVisible(False)
        self.start_button.setFixedHeight(38)
        self.start_button.clicked.connect(self.start_transcription)

        drop_layout.addWidget(self.drop_area)

        meta_row = QFrame()
        meta_row.setObjectName("MetaStatus")
        meta_layout = QVBoxLayout(meta_row)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(2)
        meta_layout.addWidget(self.file_label)
        meta_layout.addWidget(self.setup_status_label)

        drop_layout.addWidget(meta_row)
        layout.addWidget(drop_card)

        self.controls_toggle_button = QPushButton("Show Studio Controls")
        self.controls_toggle_button.setObjectName("GhostButton")
        self.controls_toggle_button.setCheckable(True)
        self.controls_toggle_button.toggled.connect(self.on_controls_toggled)
        layout.addWidget(self.controls_toggle_button, alignment=Qt.AlignmentFlag.AlignLeft)

        controls = QFrame()
        controls.setObjectName("ControlsPane")
        self.controls_pane = controls
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(14, 14, 14, 14)
        controls_layout.setSpacing(10)

        controls_title = QLabel("Studio Controls")
        controls_title.setObjectName("ControlsTitle")
        controls_layout.addWidget(controls_title)

        output_label = QLabel("Output folder")
        output_label.setObjectName("FieldLabel")
        controls_layout.addWidget(output_label)

        self.output_dir_input = QLineEdit()
        self.output_dir_input.setReadOnly(True)
        self.output_dir_input.setPlaceholderText("Default: same folder as source file")
        controls_layout.addWidget(self.output_dir_input)

        output_buttons = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.output_buttons_layout = output_buttons
        output_buttons.setSpacing(8)

        self.pick_output_button = QPushButton("Choose")
        self.pick_output_button.setObjectName("SecondaryButton")
        self.pick_output_button.clicked.connect(self.pick_output_folder)

        self.clear_output_button = QPushButton("Use source")
        self.clear_output_button.setObjectName("SecondaryButton")
        self.clear_output_button.clicked.connect(self.reset_output_folder)

        output_buttons.addWidget(self.pick_output_button)
        output_buttons.addWidget(self.clear_output_button)
        output_buttons.addStretch()
        controls_layout.addLayout(output_buttons)

        self.move_source_check = QCheckBox("Move source file to output folder when done")
        controls_layout.addWidget(self.move_source_check)

        options_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.options_row_layout = options_row
        options_row.setSpacing(12)

        self.clean_check = QCheckBox("Audio cleaning")
        self.diarize_check = QCheckBox("Speaker diarization")
        self.diarize_check.toggled.connect(self.on_diarization_toggled)

        options_row.addWidget(self.clean_check)
        options_row.addWidget(self.diarize_check)
        options_row.addStretch()
        controls_layout.addLayout(options_row)

        self.advanced_toggle_button = QPushButton("Show advanced options")
        self.advanced_toggle_button.setObjectName("GhostButton")
        self.advanced_toggle_button.setCheckable(True)
        self.advanced_toggle_button.toggled.connect(self.on_advanced_toggled)
        controls_layout.addWidget(self.advanced_toggle_button)

        advanced = QFrame()
        advanced.setObjectName("AdvancedPane")
        self.advanced_pane = advanced

        advanced_layout = QVBoxLayout(advanced)
        advanced_layout.setContentsMargins(0, 10, 0, 0)
        advanced_layout.setSpacing(9)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        model_label = QLabel("Model")
        model_label.setObjectName("FieldLabel")
        grid.addWidget(model_label, 0, 0)
        self.model_combo = QComboBox()
        self.model_combo.addItems(MODEL_OPTIONS)
        self.model_combo.setView(QListView())
        grid.addWidget(self.model_combo, 0, 1)

        language_label = QLabel("Language")
        language_label.setObjectName("FieldLabel")
        grid.addWidget(language_label, 1, 0)
        self.language_combo = QComboBox()
        self.language_combo.addItems(list(LANGUAGE_MAP.keys()))
        self.language_combo.setView(QListView())
        grid.addWidget(self.language_combo, 1, 1)

        advanced_layout.addLayout(grid)

        prompt_label = QLabel("Initial prompt")
        prompt_label.setObjectName("FieldLabel")
        advanced_layout.addWidget(prompt_label)

        self.prompt_input = QTextEdit()
        self.prompt_input.setMinimumHeight(88)
        self.prompt_input.setMaximumHeight(150)
        self.prompt_input.setPlaceholderText("Optional context to improve transcript quality")
        advanced_layout.addWidget(self.prompt_input)

        token_label = QLabel("Hugging Face token (required for diarization)")
        token_label.setObjectName("FieldLabel")
        advanced_layout.addWidget(token_label)

        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setPlaceholderText("Enter token")
        advanced_layout.addWidget(self.token_input)

        self.advanced_pane.setVisible(False)
        controls_layout.addWidget(self.advanced_pane)
        self.controls_pane.setVisible(False)
        layout.addWidget(self.controls_pane)

        run_row = QHBoxLayout()
        run_row.setContentsMargins(0, 0, 0, 0)
        run_row.addStretch()
        run_row.addWidget(self.start_button)
        run_row.addStretch()
        layout.addLayout(run_row)

        recent_title = QLabel("Recent Transcriptions")
        recent_title.setObjectName("RecentTitle")
        layout.addWidget(recent_title)

        recent_list = QFrame()
        recent_list.setObjectName("RecentList")
        recent_layout = QVBoxLayout(recent_list)
        recent_layout.setContentsMargins(0, 0, 0, 0)
        recent_layout.setSpacing(10)
        self.recent_rows_layout = recent_layout
        self._refresh_recent_list()
        layout.addWidget(recent_list)
        layout.addStretch()
        return page

    def _build_processing_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 6, 0, 2)
        layout.setSpacing(0)

        self.loading_label = QLabel("● ○ ○")
        self.loading_label.setObjectName("StatusHeadline")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Processing Transcript")
        title.setObjectName("StatusHeadline")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.processing_status_label = QLabel("Preparing...")
        self.processing_status_label.setObjectName("StatusText")
        self.processing_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.processing_status_label.setWordWrap(True)

        pane = QFrame()
        pane.setObjectName("ProcessingPane")
        pane_layout = QVBoxLayout(pane)
        pane_layout.setContentsMargins(18, 18, 18, 18)
        pane_layout.setSpacing(10)

        pane_layout.addWidget(self.loading_label)
        pane_layout.addWidget(title)
        pane_layout.addWidget(self.processing_status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        pane_layout.addWidget(self.progress_bar)

        stage_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.stage_row_layout = stage_row
        stage_row.setSpacing(12)

        for stage in self.stage_order:
            chip = QLabel(stage)
            chip.setObjectName("StageChip")
            chip.setProperty("state", "pending")
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.stage_labels[stage] = chip
            stage_row.addWidget(chip)

        pane_layout.addLayout(stage_row)

        activity_label = QLabel("Activity")
        activity_label.setObjectName("SectionTitle")
        pane_layout.addWidget(activity_label)

        self.processing_log_text = QTextEdit()
        self.processing_log_text.setObjectName("ActivityLog")
        self.processing_log_text.setReadOnly(True)
        self.processing_log_text.setMinimumHeight(260)
        pane_layout.addWidget(self.processing_log_text)

        layout.addWidget(pane)
        return page

    def _build_result_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 6, 0, 2)
        layout.setSpacing(0)

        pane = QFrame()
        pane.setObjectName("ResultPane")
        pane_layout = QVBoxLayout(pane)
        pane_layout.setContentsMargins(18, 18, 18, 18)
        pane_layout.setSpacing(10)

        title = QLabel("Transcript Ready")
        title.setObjectName("StatusHeadline")
        pane_layout.addWidget(title)

        self.result_status_label = QLabel("Completed")
        self.result_status_label.setObjectName("Meta")
        self.result_status_label.setWordWrap(True)
        pane_layout.addWidget(self.result_status_label)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMinimumHeight(300)
        pane_layout.addWidget(self.output_text)

        actions = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.result_actions_layout = actions
        actions.setSpacing(8)

        self.copy_button = QPushButton("Copy")
        self.copy_button.setObjectName("SecondaryButton")
        self.copy_button.clicked.connect(self.copy_output_text)

        self.open_output_button = QPushButton("Open folder")
        self.open_output_button.setObjectName("SecondaryButton")
        self.open_output_button.setEnabled(False)
        self.open_output_button.clicked.connect(self.open_last_output_folder)

        self.new_run_button = QPushButton("New transcription")
        self.new_run_button.setObjectName("PrimaryButton")
        self.new_run_button.clicked.connect(self.show_setup_page)

        actions.addWidget(self.copy_button)
        actions.addWidget(self.open_output_button)
        actions.addStretch()
        actions.addWidget(self.new_run_button)

        pane_layout.addLayout(actions)

        log_label = QLabel("Activity")
        log_label.setObjectName("SectionTitle")
        pane_layout.addWidget(log_label)

        self.result_log_text = QTextEdit()
        self.result_log_text.setObjectName("ActivityLog")
        self.result_log_text.setReadOnly(True)
        self.result_log_text.setMinimumHeight(170)
        pane_layout.addWidget(self.result_log_text)

        layout.addWidget(pane)
        return page

    def _apply_theme(self):
        self.setStyleSheet(build_stylesheet(THEME))

    def load_config(self) -> dict:
        if not CONFIG_FILE.exists():
            return {}
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def save_config(self):
        config = {
            "model": self.model_combo.currentText(),
            "language": LANGUAGE_MAP.get(self.language_combo.currentText(), "tl"),
            "prompt": self.prompt_input.toPlainText().strip(),
            "clean_audio": self.clean_check.isChecked(),
            "diarization": self.diarize_check.isChecked(),
            "hf_token": self.token_input.text().strip(),
            "output_dir": self.output_dir_input.text().strip(),
            "move_source_file": self.move_source_check.isChecked(),
        }
        with CONFIG_FILE.open("w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=4)
        self.config = config

    def restore_settings(self):
        self.model_combo.setCurrentText(self.config.get("model", "turbo"))

        saved_language = self.config.get("language", "tl")
        for name, code in LANGUAGE_MAP.items():
            if code == saved_language:
                self.language_combo.setCurrentText(name)
                break

        self.prompt_input.setPlainText(self.config.get("prompt", DEFAULT_PROMPT))
        self.clean_check.setChecked(self.config.get("clean_audio", True))
        self.diarize_check.setChecked(self.config.get("diarization", False))
        self.token_input.setText(self.config.get("hf_token", ""))
        self.output_dir_input.setText(self.config.get("output_dir", ""))
        self.move_source_check.setChecked(self.config.get("move_source_file", False))

        self.on_diarization_toggled(self.diarize_check.isChecked())

        show_advanced = (
            self.model_combo.currentText() != "turbo"
            or self.language_combo.currentText() != "Tagalog (tl)"
            or self.prompt_input.toPlainText().strip() != DEFAULT_PROMPT
            or self.diarize_check.isChecked()
            or bool(self.token_input.text().strip())
            or not self.clean_check.isChecked()
        )
        self.advanced_toggle_button.setChecked(show_advanced)
        self.controls_toggle_button.setChecked(False)

        self.drop_area.reset()
        self._reset_stage_progress()
        self._refresh_recent_list()
        self.show_setup_page()

    def on_file_selected(self, file_path: str):
        if Path(file_path).suffix.lower() not in AUDIO_EXTENSIONS:
            self.drop_area.set_error("Please choose a supported audio format")
            self.start_button.setEnabled(False)
            self.start_button.setVisible(False)
            self.setup_status_label.setText("Unsupported format.")
            return

        self.selected_file = file_path
        name = Path(file_path).name
        self.file_label.setText(f"Selected: {name}")
        self.setup_status_label.setText("Ready to run.")
        self.drop_area.set_ready(name)
        self.start_button.setEnabled(True)
        self.start_button.setVisible(True)

    def pick_output_folder(self):
        start_dir = self.output_dir_input.text().strip() or str(Path.home())
        selected_dir = QFileDialog.getExistingDirectory(self, "Select Output Folder", start_dir)
        if selected_dir:
            self.output_dir_input.setText(str(Path(selected_dir).expanduser().resolve()))
            self.setup_status_label.setText("Output folder selected.")

    def reset_output_folder(self):
        self.output_dir_input.clear()
        self.setup_status_label.setText("Using source folder for outputs.")

    def on_diarization_toggled(self, checked: bool):
        self.token_input.setEnabled(checked)
        self.token_input.setPlaceholderText(
            "Required for diarization" if checked else "Optional: only needed for diarization"
        )

    def on_controls_toggled(self, checked: bool):
        self.controls_pane.setVisible(checked)
        self.controls_toggle_button.setText(
            "Hide Studio Controls" if checked else "Show Studio Controls"
        )

    def on_advanced_toggled(self, checked: bool):
        self.advanced_pane.setVisible(checked)
        self.advanced_toggle_button.setText(
            "Hide advanced options" if checked else "Show advanced options"
        )

    def start_transcription(self):
        if not self.selected_file:
            self.show_dialog("No file selected", "Select an audio file before starting.", QMessageBox.Icon.Warning)
            return

        if not Path(self.selected_file).exists():
            self.show_dialog("Missing file", "The selected file no longer exists.", QMessageBox.Icon.Critical)
            self.selected_file = ""
            self.drop_area.reset()
            self.file_label.setText("No file selected")
            self.setup_status_label.setText("Drop a file to begin.")
            self.start_button.setEnabled(False)
            self.start_button.setVisible(False)
            return

        output_root = self.output_dir_input.text().strip()
        if output_root:
            try:
                Path(output_root).expanduser().resolve().mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                self.show_dialog(
                    "Invalid output folder",
                    f"Could not use output folder:\n{exc}",
                    QMessageBox.Icon.Critical,
                )
                return

        if self.diarize_check.isChecked() and not self.token_input.text().strip():
            self.show_dialog(
                "Token required",
                "Speaker diarization is enabled but token is empty.",
                QMessageBox.Icon.Warning,
            )
            return

        source_name = Path(self.selected_file).name
        self.recent_items.insert(0, {"name": source_name, "status": "processing"})
        self._refresh_recent_list()

        self.save_config()

        self.output_text.clear()
        self.activity_lines = []
        self._refresh_activity_views()
        self.append_log("Pipeline started")

        self._reset_stage_progress()
        self.set_running_state(True)

        self.worker = TranscriptionWorker(
            audio_path=self.selected_file,
            settings=self.config,
            output_root=output_root,
            move_source_file=self.move_source_check.isChecked(),
        )
        self.worker.status.connect(self.update_status)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self.on_process_finished)
        self.worker.error.connect(self.on_process_error)
        self.worker.start()

    def set_running_state(self, running: bool):
        widgets = [
            self.drop_area,
            self.controls_toggle_button,
            self.pick_output_button,
            self.clear_output_button,
            self.move_source_check,
            self.clean_check,
            self.diarize_check,
            self.model_combo,
            self.language_combo,
            self.prompt_input,
            self.advanced_toggle_button,
        ]
        for widget in widgets:
            widget.setEnabled(not running)

        self.token_input.setEnabled((not running) and self.diarize_check.isChecked())
        self.start_button.setEnabled((not running) and bool(self.selected_file))

        if running:
            self.progress_bar.setValue(0)
            self.processing_status_label.setText("Preparing...")
            self.show_processing_page()
            self.loading_index = 0
            self._tick_loading()
            self.loading_timer.start()
        else:
            self.loading_timer.stop()
            self.loading_label.setText("● ● ●")

    def update_status(self, message: str):
        self.processing_status_label.setText(message)
        self._set_stage(self._infer_stage_from_message(message))

    def append_log(self, message: str):
        self.activity_lines.append(message)
        self._refresh_activity_views()

    def _refresh_activity_views(self):
        rendered = "\n".join(f"- {line}" for line in self.activity_lines)
        self.processing_log_text.setPlainText(rendered)
        self.result_log_text.setPlainText(rendered)

    def on_process_finished(self, result: dict):
        self.set_running_state(False)
        self._set_stage("Finalizing")
        self._mark_all_stages_done()

        self.last_output_folder = result.get("output_folder", "")
        self.open_output_button.setEnabled(bool(self.last_output_folder))

        if result.get("is_diarized"):
            lines = [f"[{seg['speaker']}] {str(seg.get('text', '')).strip()}" for seg in result.get("segments", [])]
            self.output_text.setPlainText("\n".join(lines))
        else:
            self.output_text.setPlainText(result.get("text", ""))

        if self.last_output_folder:
            self.result_status_label.setText(f"Completed. Output folder: {self.last_output_folder}")
        else:
            self.result_status_label.setText("Completed.")

        finished_name = Path(self.selected_file).name if self.selected_file else "Transcript"
        for item in self.recent_items:
            if item["name"] == finished_name and item["status"] == "processing":
                item["status"] = "completed"
                break
        self._refresh_recent_list()

        self.processing_status_label.setText("Completed")
        self.append_log(f"Done. Output folder: {self.last_output_folder}")
        self.show_result_page()

    def on_process_error(self, error_message: str):
        self.set_running_state(False)
        self.processing_status_label.setText("Failed")
        self._set_stage("Finalizing")
        self.append_log(f"Error: {error_message}")
        failed_name = Path(self.selected_file).name if self.selected_file else "Transcript"
        for item in self.recent_items:
            if item["name"] == failed_name and item["status"] == "processing":
                item["status"] = "draft"
                break
        self._refresh_recent_list()
        self.show_dialog("Processing failed", error_message, QMessageBox.Icon.Critical)
        self.show_setup_page()

    def copy_output_text(self):
        text = self.output_text.toPlainText().strip()
        if not text:
            self.result_status_label.setText("No transcript text to copy yet.")
            return

        QApplication.clipboard().setText(text)
        self.result_status_label.setText("Transcript copied.")

    def open_last_output_folder(self):
        if not self.last_output_folder:
            self.result_status_label.setText("No output folder available yet.")
            return

        folder = Path(self.last_output_folder)
        if not folder.exists():
            self.show_dialog("Missing folder", "Output folder could not be found.", QMessageBox.Icon.Warning)
            return

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def show_setup_page(self):
        self._set_wizard_step("setup")
        self.stack.setCurrentIndex(self.PAGE_SETUP)
        if self.selected_file:
            self.setup_status_label.setText("Ready to run.")
            self.start_button.setVisible(True)
        else:
            self.setup_status_label.setText("Drop a file to begin.")
            self.start_button.setVisible(False)

    def show_processing_page(self):
        self._set_wizard_step("processing")
        self.stack.setCurrentIndex(self.PAGE_PROCESSING)

    def show_result_page(self):
        self._set_wizard_step("result")
        self.stack.setCurrentIndex(self.PAGE_RESULT)

    def _reset_stage_progress(self):
        self.current_stage_index = 0
        for stage in self.stage_order:
            self.stage_labels[stage].setProperty("state", "pending")
        self._set_stage("Preparing")

    def _set_stage(self, stage_name: str):
        if stage_name not in self.stage_labels:
            return

        target_index = self.stage_order.index(stage_name)
        self.current_stage_index = max(self.current_stage_index, target_index)

        for idx, stage in enumerate(self.stage_order):
            if idx < self.current_stage_index:
                state = "done"
            elif idx == self.current_stage_index:
                state = "active"
            else:
                state = "pending"
            self.stage_labels[stage].setProperty("state", state)

        self._refresh_stage_styles()

        denominator = max(1, len(self.stage_order) - 1)
        progress = int((self.current_stage_index / denominator) * 100)
        self.progress_bar.setValue(progress)

    def _mark_all_stages_done(self):
        self.current_stage_index = len(self.stage_order) - 1
        for stage in self.stage_order:
            self.stage_labels[stage].setProperty("state", "done")
        self._refresh_stage_styles()
        self.progress_bar.setValue(100)

    def _refresh_stage_styles(self):
        for label in self.stage_labels.values():
            self._refresh_widget_style(label)

    def _infer_stage_from_message(self, message: str) -> str:
        text = message.lower()
        if "clean" in text or "loading whisper" in text or "convert" in text:
            return "Preparing"
        if "transcrib" in text:
            return "Transcribing"
        if "diariz" in text:
            return "Diarizing"
        if "saving" in text or "moving original" in text or "pipeline complete" in text:
            return "Finalizing"
        return self.stage_order[self.current_stage_index]

    def _tick_loading(self):
        self.loading_label.setText(self.loading_frames[self.loading_index])
        self.loading_index = (self.loading_index + 1) % len(self.loading_frames)

    def _set_responsive_layout(self):
        width = self.width()

        self.output_buttons_layout.setDirection(
            QBoxLayout.Direction.TopToBottom if width < 720 else QBoxLayout.Direction.LeftToRight
        )
        self.options_row_layout.setDirection(
            QBoxLayout.Direction.TopToBottom if width < 780 else QBoxLayout.Direction.LeftToRight
        )
        self.result_actions_layout.setDirection(
            QBoxLayout.Direction.TopToBottom if width < 780 else QBoxLayout.Direction.LeftToRight
        )
        self.stage_row_layout.setDirection(
            QBoxLayout.Direction.TopToBottom if width < 760 else QBoxLayout.Direction.LeftToRight
        )

        self.pricing_button.setVisible(width >= 560)
        self.about_button.setVisible(width >= 560)
        self.avatar_pill.setVisible(width >= 680)
        self.stack_wrap.setMaximumWidth(760 if width < 860 else 980)

        title_font = self.header_title.font()
        if width < 760:
            title_font.setPointSize(38)
        elif width < 980:
            title_font.setPointSize(48)
        else:
            title_font.setPointSize(64)
        self.header_title.setFont(title_font)

        subtitle_font = self.header_subtitle.font()
        if width < 760:
            subtitle_font.setPointSize(20)
        elif width < 980:
            subtitle_font.setPointSize(24)
        else:
            subtitle_font.setPointSize(28)
        self.header_subtitle.setFont(subtitle_font)

        drop_title_font = self.drop_area.title_label.font()
        if width < 760:
            drop_title_font.setPointSize(24)
        elif width < 980:
            drop_title_font.setPointSize(30)
        else:
            drop_title_font.setPointSize(34)
        self.drop_area.title_label.setFont(drop_title_font)
        self.drop_area.setMinimumHeight(170 if width < 760 else 210)

    def _animate_entry(self):
        targets = [self.shell]
        self._entry_animations = []

        for idx, widget in enumerate(targets):
            effect = QGraphicsOpacityEffect(widget)
            effect.setOpacity(0.0)
            widget.setGraphicsEffect(effect)

            animation = QPropertyAnimation(effect, b"opacity", self)
            animation.setStartValue(0.0)
            animation.setEndValue(1.0)
            animation.setDuration(220 + idx * 120)
            animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
            self._entry_animations.append((animation, widget))

        for idx, (animation, _) in enumerate(self._entry_animations):
            QTimer.singleShot(65 * idx, animation.start)

        def clear_effects():
            for _, widget in self._entry_animations:
                widget.setGraphicsEffect(None)

        QTimer.singleShot(620, clear_effects)

    def show_dialog(self, title: str, message: str, icon: QMessageBox.Icon):
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setText(message)
        dialog.setIcon(icon)
        dialog.exec()

    def showEvent(self, event):
        super().showEvent(event)
        self._set_responsive_layout()
        if not hasattr(self, "_entry_animation_ran"):
            self._entry_animation_ran = True
            self._animate_entry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._set_responsive_layout()
        QTimer.singleShot(0, self._set_responsive_layout)


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Avenir Next", 11))

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
