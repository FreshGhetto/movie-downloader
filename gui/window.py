import logging, sys, datetime
from pathlib import Path
from PySide6.QtCore import Qt, QProcess, QTimer, QSize, QUrl
from PySide6.QtGui import QIcon, QPixmap, QDesktopServices, QAction, QDragEnterEvent, QDropEvent, QPainter, QColor, QFont, QPen
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QListWidget, QListWidgetItem, QTextEdit, QSplitter, QSystemTrayIcon,
    QMenu, QApplication, QStackedWidget, QScrollArea, QFrame, QProgressBar, QGridLayout,
    QFormLayout, QSpacerItem, QSizePolicy,
)
from config.settings import load, save, load_queue, save_queue, load_history, save_history, ROOT
from config.i18n import t, set_language, LANGUAGES, current as current_lang
from config.version import VERSION
from services.core import safe_name, unique_base, validate_url, find_ffmpeg, version, command, progress
from services.workers import Task, analyze, search_tmdb_both, update_ytdlp, check_app_update

BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))

STYLE = '''
* { font-family: "Segoe UI", sans-serif; }
QMainWindow, QWidget#root { background: #0d1117; color: #e6edf3; }
QWidget#sidebar { background: #010409; border-right: 1px solid #21262d; }
QWidget#page { background: #0d1117; }

QPushButton#nav { background: transparent; color: #8b949e; border: none; border-left: 3px solid transparent;
    text-align: left; padding: 12px 20px; font-size: 13px; font-weight: 500; }
QPushButton#nav:hover { background: #161b22; color: #e6edf3; }
QPushButton#nav:checked { background: #161b22; color: #e6edf3; border-left: 3px solid #2f81f7; }

QLabel { color: #e6edf3; }
QLabel#page_title { font-size: 20px; font-weight: 700; color: #e6edf3; padding-bottom: 4px; }
QLabel#section { font-size: 13px; font-weight: 600; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; padding-top: 12px; }
QLabel#hint { color: #8b949e; font-size: 12px; }
QLabel#status_bar { color: #8b949e; font-size: 11px; padding: 6px 16px; }
QLabel#empty { color: #484f58; font-size: 14px; padding: 40px; }
QLabel#version { color: #484f58; font-size: 11px; padding: 8px 20px; }

QLineEdit, QComboBox { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 8px 12px;
    color: #e6edf3; font-size: 13px; selection-background-color: #2f81f7; }
QLineEdit:focus, QComboBox:focus { border-color: #2f81f7; }
QComboBox::drop-down { border: none; padding-right: 8px; }
QComboBox QAbstractItemView { background: #161b22; border: 1px solid #30363d; selection-background-color: #2f81f7; }

QPushButton { background: #21262d; border: 1px solid #30363d; border-radius: 6px; padding: 8px 16px;
    color: #e6edf3; font-size: 13px; font-weight: 500; }
QPushButton:hover { background: #30363d; border-color: #484f58; }
QPushButton:disabled { color: #484f58; background: #161b22; border-color: #21262d; }
QPushButton#primary { background: #238636; border-color: #2ea043; color: #ffffff; }
QPushButton#primary:hover { background: #2ea043; border-color: #3fb950; }
QPushButton#accent { background: #1f6feb; border-color: #388bfd; color: #ffffff; }
QPushButton#accent:hover { background: #388bfd; border-color: #58a6ff; }
QPushButton#danger { background: #21262d; border-color: #f85149; color: #f85149; }
QPushButton#danger:hover { background: #da3633; border-color: #f85149; color: #ffffff; }
QPushButton#small { padding: 4px 10px; font-size: 11px; border-radius: 4px; }

QListWidget { background: #161b22; border: 1px solid #30363d; border-radius: 6px; }
QListWidget::item { padding: 4px; border-radius: 4px; }
QListWidget::item:selected { background: #1f6feb; }
QListWidget::item:hover { background: #21262d; }
QTextEdit { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 8px;
    color: #e6edf3; font-size: 13px; }
QTableWidget { background: #0d1117; border: 1px solid #21262d; border-radius: 6px; gridline-color: #21262d; }
QTableWidget::item { padding: 6px 8px; border-bottom: 1px solid #21262d; }
QTableWidget::item:selected { background: #1f6feb; }
QHeaderView::section { background: #161b22; border: none; border-bottom: 1px solid #30363d;
    padding: 8px 8px; font-weight: 600; color: #8b949e; font-size: 12px; }
QScrollArea { border: none; background: transparent; }

QCheckBox { spacing: 8px; color: #e6edf3; font-size: 13px; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 3px; border: 1px solid #30363d; background: #161b22; }
QCheckBox::indicator:checked { background: #2f81f7; border-color: #2f81f7; }

QProgressBar { background: #21262d; border: none; border-radius: 4px; height: 8px; text-align: center; }
QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1f6feb,stop:1 #58a6ff); border-radius: 4px; }

QFrame#card { background: #161b22; border: 1px solid #21262d; border-radius: 8px; }
QFrame#card_active { background: #161b22; border: 1px solid #1f6feb; border-radius: 8px; }
QFrame#separator { background: #21262d; max-height: 1px; }
'''


class DownloadCard(QFrame):
    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.setObjectName('card')
        self.setFixedHeight(76)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.name_label = QLabel(name)
        self.name_label.setStyleSheet('font-weight:600; font-size:13px;')
        top.addWidget(self.name_label, 1)
        self.status_label = QLabel(t('queued'))
        self.status_label.setStyleSheet('color:#8b949e; font-size:12px;')
        top.addWidget(self.status_label)
        self.info_label = QLabel('')
        self.info_label.setStyleSheet('color:#8b949e; font-size:11px;')
        top.addWidget(self.info_label)
        layout.addLayout(top)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        layout.addWidget(self.bar)

    def update_progress(self, percent, size, speed, eta):
        self.bar.setValue(int(percent * 10))
        parts = []
        if size > 0:
            parts.append(f'{size / 1048576:.1f} MiB')
        if speed > 0:
            parts.append(f'{speed / 1048576:.1f} MiB/s')
        if eta is not None:
            m, s = divmod(int(eta), 60)
            parts.append(f'{m}:{s:02d}')
        self.info_label.setText(' · '.join(parts))
        self.status_label.setText(f'{percent:.0f}%')

    def set_status(self, status):
        self.status_label.setText(status)
        self.info_label.setText('')
        colors = {
            t('completed'): '#3fb950', t('error_log'): '#f85149',
            t('error_start'): '#f85149', t('cancelled'): '#d29922',
            t('paused'): '#d29922', t('downloading'): '#58a6ff',
            t('processing'): '#a371f7',
        }
        color = colors.get(status, '#8b949e')
        self.status_label.setStyleSheet(f'color:{color}; font-size:12px; font-weight:600;')
        if status == t('completed'):
            self.bar.setValue(1000)
            self.bar.setStyleSheet('QProgressBar::chunk{background:#3fb950;border-radius:4px;}')
            self.setObjectName('card')
        elif status in (t('error_log'), t('error_start')):
            self.bar.setStyleSheet('QProgressBar::chunk{background:#f85149;border-radius:4px;}')


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = load()
        set_language(self.settings.get('language', 'en'))
        ROOT.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger('movie_downloader')
        if not self.logger.handlers:
            h = logging.FileHandler(ROOT / 'movie-downloader.log', encoding='utf-8')
            h.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
            self.logger.addHandler(h)
        self.logger.setLevel(logging.INFO)
        self.exe = str(BASE / 'bin' / 'yt-dlp.exe')
        self.tasks, self.jobs, self.cards = [], [], []
        self.history = load_history()
        self.current = None
        self.running = False
        self.buffer = ''
        self.versions_ok = False
        self._build_icon()
        self.setWindowTitle('Movie Downloader')
        ico_path = BASE / 'icon.ico'
        if ico_path.exists():
            self.setWindowIcon(QIcon(str(ico_path)))
        else:
            self.setWindowIcon(self._app_icon)
        self.resize(1060, 740)
        self.setMinimumSize(800, 560)
        self.setAcceptDrops(True)
        self.setStyleSheet(STYLE)

        root = QWidget()
        root.setObjectName('root')
        self.setCentralWidget(root)
        main_layout = QHBoxLayout(root)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(180)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(0, 16, 0, 8)
        sb_layout.setSpacing(0)

        logo = QLabel('  Movie\n  Downloader')
        logo.setStyleSheet('font-size:16px; font-weight:800; color:#e6edf3; padding:0 16px 16px 16px; line-height:1.2;')
        sb_layout.addWidget(logo)

        self.nav_buttons = []
        nav_items = [
            ('nav_download', '⬇'),
            ('nav_queue', '☰'),
            ('nav_history', '⏳'),
            ('nav_paths', '\U0001F4C1'),
            ('nav_settings', '⚙'),
        ]
        for key, icon in nav_items:
            btn = QPushButton(f'  {icon}   {t(key)}')
            btn.setObjectName('nav')
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            idx = len(self.nav_buttons)
            btn.clicked.connect(lambda checked, i=idx: self._switch_page(i))
            sb_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        sb_layout.addStretch()
        self.version_label = QLabel(f'  v{VERSION}')
        self.version_label.setObjectName('version')
        sb_layout.addWidget(self.version_label)
        main_layout.addWidget(sidebar)

        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, 1)

        self._build_download_page()
        self._build_queue_page()
        self._build_history_page()
        self._build_paths_page()
        self._build_settings_page()

        self.status_bar = QLabel(t('checking_tools'))
        self.status_bar.setObjectName('status_bar')

        wrapper = QVBoxLayout()
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.setSpacing(0)
        container = QWidget()
        container.setLayout(wrapper)
        wrapper.addWidget(self.stack, 1)
        sep = QFrame()
        sep.setObjectName('separator')
        sep.setFrameShape(QFrame.Shape.HLine)
        wrapper.addWidget(sep)
        wrapper.addWidget(self.status_bar)

        main_layout.removeWidget(self.stack)
        main_layout.addWidget(container, 1)

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._process_error)

        self._setup_tray()
        self._restore_queue()
        self._switch_page(0)
        QTimer.singleShot(0, self._check_tools)
        if self.settings.get('auto_update', True):
            QTimer.singleShot(3000, self._auto_check_update)

    def _build_icon(self):
        pix = QPixmap(64, 64)
        pix.fill(QColor(0, 0, 0, 0))
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor('#1f6feb'))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(4, 4, 56, 56, 14, 14)
        p.setPen(QPen(QColor('#ffffff'), 3))
        p.setBrush(QColor('#ffffff'))
        pts = [
            (32, 42), (22, 30), (26, 30),
            (26, 18), (38, 18), (38, 30),
            (42, 30),
        ]
        from PySide6.QtGui import QPolygon
        from PySide6.QtCore import QPoint
        poly = QPolygon([QPoint(x, y) for x, y in pts])
        p.drawPolygon(poly)
        p.end()
        self._app_icon = QIcon(pix)

    def _switch_page(self, index):
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        self.stack.setCurrentIndex(index)

    # ---- Download Page ----
    def _build_download_page(self):
        page = QWidget()
        page.setObjectName('page')
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title = QLabel(t('nav_download'))
        title.setObjectName('page_title')
        layout.addWidget(title)

        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        self.url = QLineEdit()
        self.url.setPlaceholderText(t('url_placeholder'))
        self.url.setMinimumHeight(40)
        url_row.addWidget(self.url, 1)
        paste_btn = QPushButton(t('paste'))
        paste_btn.clicked.connect(self._paste_url)
        url_row.addWidget(paste_btn)
        self.analyze_btn = QPushButton(t('analyze'))
        self.analyze_btn.setObjectName('accent')
        self.analyze_btn.clicked.connect(self._analyze_link)
        url_row.addWidget(self.analyze_btn)
        layout.addLayout(url_row)

        self.res_label = QLabel(t('res_hint'))
        self.res_label.setObjectName('hint')
        layout.addWidget(self.res_label)

        tmdb_row = QHBoxLayout()
        tmdb_row.setSpacing(8)
        self.query = QLineEdit()
        self.query.setPlaceholderText(t('tmdb_placeholder'))
        tmdb_row.addWidget(self.query, 1)
        self.search_btn = QPushButton(t('search_tmdb'))
        self.search_btn.clicked.connect(self._search)
        tmdb_row.addWidget(self.search_btn)
        self.query.returnPressed.connect(self.search_btn.click)
        layout.addLayout(tmdb_row)

        splitter = QSplitter()
        self.results = QListWidget()
        self.results.setIconSize(QSize(62, 92))
        self.results.currentItemChanged.connect(self._select_result)
        splitter.addWidget(self.results)
        self.synopsis = QTextEdit()
        self.synopsis.setReadOnly(True)
        self.synopsis.setPlaceholderText(t('synopsis_hint'))
        self.synopsis.setMaximumHeight(160)
        splitter.addWidget(self.synopsis)
        splitter.setSizes([400, 300])
        layout.addWidget(splitter)

        opts_label = QLabel(t('download_options'))
        opts_label.setObjectName('section')
        layout.addWidget(opts_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        grid.addWidget(QLabel(t('title')), 0, 0)
        self.title_input = QLineEdit()
        grid.addWidget(self.title_input, 0, 1, 1, 2)
        grid.addWidget(QLabel(t('year')), 0, 3)
        self.year_input = QLineEdit()
        self.year_input.setMaxLength(4)
        self.year_input.setMaximumWidth(70)
        grid.addWidget(self.year_input, 0, 4)

        grid.addWidget(QLabel(t('category')), 1, 0)
        self.kind = QComboBox()
        self.kind.addItems([t('movie'), t('tv_show')])
        self.kind.currentIndexChanged.connect(self._change_kind)
        grid.addWidget(self.kind, 1, 1)
        grid.addWidget(QLabel(t('quality')), 1, 2)
        self.quality = QComboBox()
        for label, val in [(t('best'),'best'),(t('up_to_1080'),'1080'),(t('up_to_720'),'720'),(t('up_to_480'),'480'),(t('audio_only'),'audio')]:
            self.quality.addItem(label, val)
        grid.addWidget(self.quality, 1, 3, 1, 2)

        grid.addWidget(QLabel(t('destination')), 2, 0)
        dest_row = QHBoxLayout()
        dest_row.setSpacing(6)
        self.path_combo = QComboBox()
        self.path_combo.setMinimumWidth(120)
        self.path_combo.addItem(t('custom'), '')
        for cp in self.settings.get('custom_paths', []):
            self.path_combo.addItem(cp['name'], cp['path'])
        self.path_combo.currentIndexChanged.connect(self._apply_custom_path)
        dest_row.addWidget(self.path_combo)
        self.directory = QLineEdit(self.settings.get('movie_dir', ''))
        self.directory.setPlaceholderText(t('choose_folder'))
        dest_row.addWidget(self.directory, 1)
        browse_btn = QPushButton(t('browse'))
        browse_btn.clicked.connect(self._choose_directory)
        dest_row.addWidget(browse_btn)
        grid.addLayout(dest_row, 2, 1, 1, 4)

        grid.addWidget(QLabel(t('subtitles')), 3, 0)
        sub_row = QHBoxLayout()
        sub_row.setSpacing(8)
        self.subs_check = QCheckBox()
        self.subs_check.setChecked(self.settings.get('subtitles', True))
        sub_row.addWidget(self.subs_check)
        sub_row.addWidget(QLabel(t('sub_langs_label')))
        self.sub_langs = QComboBox()
        self.sub_langs.setEditable(True)
        self.sub_langs.addItems(['en', 'it', 'it,en', 'en,es', 'en,fr', 'en,de'])
        self.sub_langs.setCurrentText(self.settings.get('sub_langs', 'it,en'))
        self.sub_langs.setMinimumWidth(100)
        sub_row.addWidget(self.sub_langs)
        sub_row.addStretch()
        sub_row.addWidget(QLabel(t('fragments')))
        self.fragments = QComboBox()
        self.fragments.addItems(['1', '4', '8', '16'])
        self.fragments.setCurrentText(str(self.settings.get('fragments', 16)))
        sub_row.addWidget(self.fragments)
        grid.addLayout(sub_row, 3, 1, 1, 4)

        layout.addLayout(grid)

        add_btn = QPushButton(t('add_to_queue'))
        add_btn.setObjectName('primary')
        add_btn.setMinimumHeight(42)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._add_job)
        layout.addWidget(add_btn)

        layout.addStretch()
        self.stack.addWidget(scroll)

    # ---- Queue Page ----
    def _build_queue_page(self):
        page = QWidget()
        page.setObjectName('page')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        top = QHBoxLayout()
        title = QLabel(t('nav_queue'))
        title.setObjectName('page_title')
        top.addWidget(title)
        top.addStretch()
        start_btn = QPushButton(t('start_all'))
        start_btn.setObjectName('primary')
        start_btn.clicked.connect(self._start_queue)
        top.addWidget(start_btn)
        pause_btn = QPushButton(t('pause_all'))
        pause_btn.clicked.connect(self._pause)
        top.addWidget(pause_btn)
        resume_btn = QPushButton(t('resume'))
        resume_btn.clicked.connect(self._resume)
        top.addWidget(resume_btn)
        clear_btn = QPushButton(t('clear_completed'))
        clear_btn.clicked.connect(self._clear_completed)
        top.addWidget(clear_btn)
        layout.addLayout(top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.queue_container = QWidget()
        self.queue_layout = QVBoxLayout(self.queue_container)
        self.queue_layout.setContentsMargins(0, 0, 0, 0)
        self.queue_layout.setSpacing(6)
        self.queue_layout.addStretch()
        scroll.setWidget(self.queue_container)
        layout.addWidget(scroll, 1)

        self.queue_empty_label = QLabel(t('queue_empty'))
        self.queue_empty_label.setObjectName('empty')
        self.queue_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.queue_layout.insertWidget(0, self.queue_empty_label)

        self.stack.addWidget(page)

    # ---- History Page ----
    def _build_history_page(self):
        page = QWidget()
        page.setObjectName('page')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        top = QHBoxLayout()
        title = QLabel(t('nav_history'))
        title.setObjectName('page_title')
        top.addWidget(title)
        top.addStretch()
        clear_btn = QPushButton(t('clear_history'))
        clear_btn.setObjectName('danger')
        clear_btn.clicked.connect(self._clear_history)
        top.addWidget(clear_btn)
        log_btn = QPushButton(t('open_log'))
        log_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(ROOT / 'movie-downloader.log'))))
        top.addWidget(log_btn)
        layout.addLayout(top)

        self.history_table = QTableWidget(0, 4)
        self.history_table.setHorizontalHeaderLabels([t('col_file'), t('col_date'), t('quality'), t('col_status')])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history_table.verticalHeader().setVisible(False)
        layout.addWidget(self.history_table, 1)
        self._refresh_history_table()

        self.stack.addWidget(page)

    # ---- Paths Page ----
    def _build_paths_page(self):
        page = QWidget()
        page.setObjectName('page')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        title = QLabel(t('nav_paths'))
        title.setObjectName('page_title')
        layout.addWidget(title)
        hint = QLabel(t('paths_hint'))
        hint.setObjectName('hint')
        layout.addWidget(hint)

        self.paths_table = QTableWidget(0, 2)
        self.paths_table.setHorizontalHeaderLabels([t('col_shortcut'), t('col_folder')])
        self.paths_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.paths_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.paths_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.paths_table.verticalHeader().setVisible(False)
        layout.addWidget(self.paths_table, 1)

        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self.path_name_input = QLineEdit()
        self.path_name_input.setPlaceholderText(t('path_name_hint'))
        add_row.addWidget(self.path_name_input)
        self.path_dir_input = QLineEdit()
        self.path_dir_input.setPlaceholderText(t('folder'))
        add_row.addWidget(self.path_dir_input, 1)
        browse_p = QPushButton(t('browse'))
        browse_p.clicked.connect(self._browse_custom_path)
        add_row.addWidget(browse_p)
        add_p = QPushButton(t('add'))
        add_p.setObjectName('primary')
        add_p.clicked.connect(self._add_custom_path)
        add_row.addWidget(add_p)
        layout.addLayout(add_row)

        rm_row = QHBoxLayout()
        rm_btn = QPushButton(t('remove_selected'))
        rm_btn.setObjectName('danger')
        rm_btn.clicked.connect(self._remove_custom_path)
        rm_row.addWidget(rm_btn)
        rm_row.addStretch()
        layout.addLayout(rm_row)

        self._refresh_paths_table()
        self.stack.addWidget(page)

    # ---- Settings Page ----
    def _build_settings_page(self):
        page = QWidget()
        page.setObjectName('page')
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(10)

        title = QLabel(t('nav_settings'))
        title.setObjectName('page_title')
        layout.addWidget(title)

        section = QLabel(t('section_general'))
        section.setObjectName('section')
        layout.addWidget(section)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        self.s_tmdb = QLineEdit(self.settings.get('tmdb_key', ''))
        self.s_tmdb.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(t('tmdb_key_label'), self.s_tmdb)
        self.s_lang = QComboBox()
        for code, name in LANGUAGES.items():
            self.s_lang.addItem(name, code)
        self.s_lang.setCurrentIndex(list(LANGUAGES.keys()).index(current_lang()))
        form.addRow(t('language_label'), self.s_lang)
        self.s_auto_update = QCheckBox(t('auto_update_label'))
        self.s_auto_update.setChecked(self.settings.get('auto_update', True))
        form.addRow('', self.s_auto_update)
        layout.addLayout(form)

        section2 = QLabel(t('section_directories'))
        section2.setObjectName('section')
        layout.addWidget(section2)

        form2 = QFormLayout()
        form2.setHorizontalSpacing(16)
        form2.setVerticalSpacing(10)
        self.s_movie = QLineEdit(self.settings.get('movie_dir', ''))
        self.s_movie.setPlaceholderText(t('choose_folder'))
        form2.addRow(t('movie_folder'), self.s_movie)
        self.s_tv = QLineEdit(self.settings.get('tv_dir', ''))
        self.s_tv.setPlaceholderText(t('choose_folder'))
        form2.addRow(t('tv_folder'), self.s_tv)
        layout.addLayout(form2)

        section3 = QLabel(t('section_tools'))
        section3.setObjectName('section')
        layout.addWidget(section3)

        form3 = QFormLayout()
        form3.setHorizontalSpacing(16)
        form3.setVerticalSpacing(10)
        self.s_ffmpeg = QLineEdit(self.settings.get('ffmpeg', ''))
        self.s_ffmpeg.setPlaceholderText(t('ffmpeg_hint'))
        form3.addRow(t('ffmpeg_label'), self.s_ffmpeg)
        layout.addLayout(form3)

        tools_row = QHBoxLayout()
        tools_row.setSpacing(8)
        upd_yt = QPushButton(t('update_ytdlp'))
        upd_yt.clicked.connect(self._update_ytdlp_click)
        tools_row.addWidget(upd_yt)
        chk_upd = QPushButton(t('check_updates'))
        chk_upd.clicked.connect(self._check_updates_click)
        tools_row.addWidget(chk_upd)
        self.s_tools_label = QLabel('')
        self.s_tools_label.setObjectName('hint')
        tools_row.addWidget(self.s_tools_label, 1)
        layout.addLayout(tools_row)

        layout.addSpacing(16)
        save_btn = QPushButton(t('save_settings'))
        save_btn.setObjectName('primary')
        save_btn.setMinimumHeight(40)
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn)

        layout.addStretch()
        self.stack.addWidget(scroll)

    # ---- System tray ----
    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self._app_icon)
        self.tray.setToolTip('Movie Downloader')
        menu = QMenu()
        show_a = QAction(t('show'), self)
        show_a.triggered.connect(self.showNormal)
        menu.addAction(show_a)
        quit_a = QAction(t('quit'), self)
        quit_a.triggered.connect(self._quit_app)
        menu.addAction(quit_a)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self.showNormal() if r == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()

    def _quit_app(self):
        self._save_queue()
        self.tray.hide()
        QApplication.quit()

    # ---- Utilities ----
    def _paste_url(self):
        self.url.setText(QApplication.clipboard().text().strip())

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasText() or event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        text = ''
        if event.mimeData().hasUrls():
            text = event.mimeData().urls()[0].toString()
        elif event.mimeData().hasText():
            text = event.mimeData().text().strip()
        if text:
            self.url.setText(text)
            self._analyze_link()

    def _fail(self, message):
        self.logger.error(message)
        QMessageBox.warning(self, 'Movie Downloader', message)

    def _task(self, fn, callback, button=None):
        task = Task(fn)
        self.tasks.append(task)
        if button:
            button.setEnabled(False)
        task.result.connect(callback)
        task.error.connect(self._fail)
        def cleanup():
            if button:
                button.setEnabled(True)
            self.tasks.remove(task)
            task.deleteLater()
        task.finished.connect(cleanup)
        task.start()

    # ---- Download logic ----
    def _check_tools(self):
        self.versions_ok = False
        ff = find_ffmpeg(self.settings['ffmpeg'])
        def done(data):
            self.versions_ok = True
            self.status_bar.setText(f'yt-dlp {data[0]}  ·  {data[1]}')
            self.logger.info(self.status_bar.text())
        self._task(lambda: (version(self.exe), version(ff)), done)

    def _analyze_link(self):
        url = self.url.text().strip()
        def done(data):
            if self.url.text().strip() != url:
                return
            self.title_input.setText(data['title'])
            self.year_input.setText(data['year'])
            heights = ', '.join(f'{h}p' for h in data['heights']) or t('res_undeclared')
            self.res_label.setText(f'{t("res_offered")}: {heights}')
            if data['title'] and self.settings.get('tmdb_key'):
                self.query.setText(data['title'])
                QTimer.singleShot(100, self._search)
        self._task(lambda: analyze(self.exe, url), done, self.analyze_btn)

    def _change_kind(self):
        key = 'movie_dir' if self.kind.currentIndex() == 0 else 'tv_dir'
        d = self.settings.get(key, '')
        if d:
            self.directory.setText(d)

    def _choose_directory(self):
        path = QFileDialog.getExistingDirectory(self, t('destination'), self.directory.text() or str(Path.home()))
        if path:
            self.directory.setText(path)

    def _search(self):
        query = self.query.text().strip()
        if not query:
            return
        key = self.settings['tmdb_key']
        def done(items):
            self.results.clear()
            for data in items:
                name = data.get('title') or data.get('name') or t('untitled')
                year = (data.get('release_date') or data.get('first_air_date') or '')[:4]
                icon = '\U0001f3ac' if data.get('_kind') == 'movie' else '\U0001f4fa'
                item = QListWidgetItem(f'{icon} {name} ({year or "?"})')
                item.setData(Qt.ItemDataRole.UserRole, data)
                if data.get('poster_bytes'):
                    pix = QPixmap()
                    pix.loadFromData(data['poster_bytes'])
                    item.setIcon(QIcon(pix))
                self.results.addItem(item)
            if not items:
                self.synopsis.setText(t('no_results'))
        self._task(lambda: search_tmdb_both(query, key), done, self.search_btn)

    def _select_result(self, item, previous):
        if not item:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        self.title_input.setText(data.get('title') or data.get('name') or '')
        self.year_input.setText((data.get('release_date') or data.get('first_air_date') or '')[:4])
        self.synopsis.setText(data.get('overview') or t('no_synopsis'))
        if data.get('_kind') == 'tv':
            self.kind.setCurrentIndex(1)
        elif data.get('_kind') == 'movie':
            self.kind.setCurrentIndex(0)

    def _add_job(self):
        try:
            validate_url(self.url.text().strip())
            if not self.title_input.text().strip():
                raise ValueError(t('enter_title'))
            yr = self.year_input.text()
            if yr and not (yr.isdigit() and len(yr) == 4):
                raise ValueError(t('year_digits'))
            dest = self.directory.text().strip()
            if not dest:
                raise ValueError(t('choose_folder'))
            directory = Path(dest)
            directory.mkdir(parents=True, exist_ok=True)
            base = unique_base(directory, safe_name(self.title_input.text(), yr), [j['base'] for j in self.jobs])
            frags = int(self.fragments.currentText())
            job = {
                'url': self.url.text().strip(), 'base': str(base), 'quality': self.quality.currentData(),
                'fragments': frags, 'subtitles': self.subs_check.isChecked(),
                'sub_langs': self.sub_langs.currentText().strip() or 'it,en', 'state': t('queued'),
            }
            self.jobs.append(job)
            card = DownloadCard(base.name)
            self.cards.append(card)
            self.queue_layout.insertWidget(self.queue_layout.count() - 1, card)
            self.queue_empty_label.hide()

            key = 'movie_dir' if self.kind.currentIndex() == 0 else 'tv_dir'
            self.settings[key] = str(directory)
            self.settings['fragments'] = frags
            self.settings['subtitles'] = self.subs_check.isChecked()
            self.settings['sub_langs'] = self.sub_langs.currentText().strip() or 'it,en'
            save(self.settings)
            self._save_queue()
            self._switch_page(1)
        except Exception as e:
            self._fail(str(e))

    # ---- Queue management ----
    def _save_queue(self):
        save_queue([j for j in self.jobs if j['state'] in (t('queued'), t('paused'))])

    def _restore_queue(self):
        for job in load_queue():
            job['state'] = t('queued')
            self.jobs.append(job)
            card = DownloadCard(Path(job['base']).name)
            self.cards.append(card)
            self.queue_layout.insertWidget(self.queue_layout.count() - 1, card)
        if self.jobs:
            self.queue_empty_label.hide()

    def _start_queue(self):
        if not self.versions_ok:
            self._fail(t('verify_tools'))
            return
        self.running = True
        self._next_job()

    def _next_job(self):
        if self.current is not None or not self.running:
            return
        idx = next((i for i, j in enumerate(self.jobs) if j['state'] == t('queued')), None)
        if idx is None:
            self.running = False
            if any(j['state'] == t('completed') for j in self.jobs):
                self._notify(t('queue_done_title'), t('queue_done_msg'))
            return
        self.current = idx
        self.buffer = ''
        self.jobs[idx]['state'] = t('downloading')
        self.cards[idx].set_status(t('downloading'))
        self.cards[idx].setObjectName('card_active')
        self.cards[idx].setStyleSheet(self.cards[idx].styleSheet())
        args = command(self.exe, self.jobs[idx], find_ffmpeg(self.settings['ffmpeg']))
        self.logger.info('Start: %s', Path(self.jobs[idx]['base']).name)
        self.process.start(args[0], args[1:])

    def _read_output(self):
        self.buffer += bytes(self.process.readAllStandardOutput()).decode('utf-8', errors='replace')
        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            self.logger.info(line.rstrip())
            data = progress(line)
            if data and self.current is not None:
                card = self.cards[self.current]
                card.update_progress(data['percent'], data['size'], data['speed'] or 0, data['eta'])
                if data['status'] == 'finished':
                    card.set_status(t('processing'))

    def _finished(self, code, status):
        self._read_output()
        if self.current is None:
            return
        idx = self.current
        job = self.jobs[idx]
        card = self.cards[idx]
        card.setObjectName('card')
        card.setStyleSheet(card.styleSheet())
        if job['state'] not in (t('paused'), t('cancelled')):
            ok = code == 0
            st = t('completed') if ok else t('error_log')
            job['state'] = st
            card.set_status(st)
            if ok:
                self._notify(t('download_done'), Path(job['base']).name)
            self._add_history(job, st)
        self._save_queue()
        self.current = None
        QTimer.singleShot(0, self._next_job)

    def _process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart and self.current is not None:
            self.jobs[self.current]['state'] = t('error_start')
            self.cards[self.current].set_status(t('error_start'))
            self.current = None
            self.running = False
            self._fail(t('ytdlp_start_fail'))

    def _pause(self):
        self.running = False
        if self.current is not None:
            self.jobs[self.current]['state'] = t('paused')
            self.cards[self.current].set_status(t('paused'))
            self.process.kill()
        self._save_queue()

    def _resume(self):
        if self.current is not None:
            return
        for i, j in enumerate(self.jobs):
            if j['state'] == t('paused'):
                j['state'] = t('queued')
                self.cards[i].set_status(t('queued'))
        self._start_queue()

    def _clear_completed(self):
        i = len(self.jobs) - 1
        while i >= 0:
            if self.jobs[i]['state'] in (t('completed'), t('cancelled'), t('error_log'), t('error_start')):
                if i == self.current:
                    i -= 1
                    continue
                self.jobs.pop(i)
                card = self.cards.pop(i)
                self.queue_layout.removeWidget(card)
                card.deleteLater()
                if self.current is not None and self.current > i:
                    self.current -= 1
            i -= 1
        if not self.jobs:
            self.queue_empty_label.show()
        self._save_queue()

    def _notify(self, title, message):
        if self.tray.isVisible():
            self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 5000)
        QApplication.beep()

    # ---- History ----
    def _add_history(self, job, status):
        entry = {
            'file': Path(job['base']).name,
            'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
            'quality': job['quality'], 'status': status,
        }
        self.history.append(entry)
        save_history(self.history)
        self._refresh_history_table()

    def _refresh_history_table(self):
        self.history_table.setRowCount(0)
        for entry in reversed(self.history[-100:]):
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)
            for col, key in enumerate(['file', 'date', 'quality', 'status']):
                self.history_table.setItem(row, col, QTableWidgetItem(str(entry.get(key, ''))))

    def _clear_history(self):
        self.history.clear()
        save_history(self.history)
        self._refresh_history_table()

    # ---- Custom Paths ----
    def _apply_custom_path(self, index):
        path = self.path_combo.currentData()
        if path:
            self.directory.setText(path)

    def _browse_custom_path(self):
        path = QFileDialog.getExistingDirectory(self, t('folder'), self.path_dir_input.text() or str(Path.home()))
        if path:
            self.path_dir_input.setText(path)

    def _add_custom_path(self):
        name = self.path_name_input.text().strip()
        path = self.path_dir_input.text().strip()
        if not name or not path:
            self._fail(t('enter_name_path'))
            return
        paths = self.settings.get('custom_paths', [])
        if any(p['name'] == name for p in paths):
            self._fail(t('path_exists').format(name))
            return
        paths.append({'name': name, 'path': path})
        self.settings['custom_paths'] = paths
        save(self.settings)
        self.path_combo.addItem(name, path)
        self._refresh_paths_table()
        self.path_name_input.clear()
        self.path_dir_input.clear()

    def _remove_custom_path(self):
        row = self.paths_table.currentRow()
        if row < 0:
            return
        name = self.paths_table.item(row, 0).text()
        self.settings['custom_paths'] = [p for p in self.settings.get('custom_paths', []) if p['name'] != name]
        save(self.settings)
        self._rebuild_path_combo()
        self._refresh_paths_table()

    def _rebuild_path_combo(self):
        self.path_combo.blockSignals(True)
        self.path_combo.clear()
        self.path_combo.addItem(t('custom'), '')
        for cp in self.settings.get('custom_paths', []):
            self.path_combo.addItem(cp['name'], cp['path'])
        self.path_combo.blockSignals(False)

    def _refresh_paths_table(self):
        self.paths_table.setRowCount(0)
        for cp in self.settings.get('custom_paths', []):
            row = self.paths_table.rowCount()
            self.paths_table.insertRow(row)
            self.paths_table.setItem(row, 0, QTableWidgetItem(cp['name']))
            self.paths_table.setItem(row, 1, QTableWidgetItem(cp['path']))

    # ---- Settings actions ----
    def _save_settings(self):
        old_lang = self.settings.get('language', 'en')
        new_lang = self.s_lang.currentData()
        self.settings.update(
            tmdb_key=self.s_tmdb.text().strip(),
            ffmpeg=self.s_ffmpeg.text().strip(),
            movie_dir=self.s_movie.text().strip(),
            tv_dir=self.s_tv.text().strip(),
            language=new_lang,
            auto_update=self.s_auto_update.isChecked(),
        )
        save(self.settings)
        self._check_tools()
        self.s_tools_label.setText(t('saved'))
        QTimer.singleShot(3000, lambda: self.s_tools_label.setText(''))
        if new_lang != old_lang:
            QMessageBox.information(self, 'Movie Downloader', t('restart_lang'))

    def _update_ytdlp_click(self):
        self.s_tools_label.setText(t('updating'))
        def done(output):
            self.s_tools_label.setText(output[:120])
            self._check_tools()
        self._task(lambda: update_ytdlp(self.exe), done)

    def _check_updates_click(self):
        self.s_tools_label.setText(t('checking_update'))
        def done(result):
            if result is None:
                self.s_tools_label.setText('—')
            elif result.get('up_to_date'):
                self.s_tools_label.setText(t('up_to_date').format(VERSION))
            else:
                self.s_tools_label.setText(t('new_version').format(result['version']))
                QDesktopServices.openUrl(QUrl(result['url']))
        self._task(lambda: check_app_update(VERSION), done)

    def _auto_check_update(self):
        def done(result):
            if result and not result.get('up_to_date') and result.get('url'):
                self._notify(t('new_version').format(result['version']), result['url'])
        self._task(lambda: check_app_update(VERSION), done)

    # ---- Window events ----
    def changeEvent(self, event):
        if event.type() == event.Type.WindowStateChange and self.isMinimized():
            self.hide()
            self.tray.showMessage('Movie Downloader', t('minimized_tray'), QSystemTrayIcon.MessageIcon.Information, 2000)
        super().changeEvent(event)

    def closeEvent(self, event):
        if self.tasks or self.current is not None:
            QMessageBox.information(self, 'Movie Downloader', t('busy_close'))
            event.ignore()
            return
        self._save_queue()
        save(self.settings)
        self.tray.hide()
        event.accept()
