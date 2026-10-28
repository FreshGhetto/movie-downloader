import logging, sys, datetime
from pathlib import Path
from PySide6.QtCore import Qt, QProcess, QTimer, QSize, QUrl, QRectF
from PySide6.QtGui import (
    QIcon, QPixmap, QDesktopServices, QAction, QDragEnterEvent, QDropEvent,
    QPainter, QColor, QPen, QBrush, QLinearGradient, QPainterPath,
)
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QSystemTrayIcon, QMenu, QApplication, QStackedWidget,
    QScrollArea, QFrame, QProgressBar, QFormLayout, QSizePolicy,
)
from config.settings import load, save, load_queue, save_queue, load_history, save_history, ROOT
from config.i18n import t, set_language, LANGUAGES, current as current_lang
from config.version import VERSION
from services.core import safe_name, unique_base, validate_url, find_ffmpeg, version, command, progress
from services.workers import Task, analyze, search_tmdb_both, update_ytdlp, check_app_update

BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))

from gui.design import (
    BG_INPUT, ACCENT, GREEN,
    RED, YELLOW, TEXT, TEXT_DIM, BORDER, STYLE, GlassBackdrop, GlassPanel,
    ResponsiveColumns, Toggle, ElidedLabel, icon, GlassComboBox as QComboBox,
)


class PosterCard(QPushButton):
    def __init__(self, name, year, kind, poster_bytes, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.setFixedSize(144, 252)
        self.setToolTip(f"{name} ({year}) — {kind}")
        self.setAccessibleName(f"{name} ({year})")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f'''
            QPushButton {{
                background: transparent; border: 1px solid transparent; border-radius: 14px;
                padding: 0; text-align: center;
            }}
            QPushButton:hover {{ border-color: {ACCENT}; background: {BG_INPUT}; }}
            QPushButton:checked {{ border-color: {ACCENT}; border-width: 2px; }}
        ''')
        self.setCheckable(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.poster_label = QLabel()
        self.poster_label.setFixedSize(130, 192)
        self.poster_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.poster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.poster_label.setStyleSheet(f'background: {BG_INPUT}; border-radius: 8px; border: none;')
        if poster_bytes:
            pix = QPixmap()
            pix.loadFromData(poster_bytes)
            self.poster_label.setPixmap(self._rounded_poster(pix))
        else:
            self.poster_label.setPixmap(icon('film', TEXT_DIM, 40).pixmap(40, 40))
        layout.addWidget(self.poster_label)
        title_text = self.fontMetrics().elidedText(name, Qt.TextElideMode.ElideRight, 130)
        label_text = f'{title_text}\n{year or "?"}  {kind}'
        title_label = QLabel(label_text)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setWordWrap(True)
        title_label.setStyleSheet(f'color: {TEXT}; font-size: 11px; font-weight: 500; border: none; background: transparent;')
        title_label.setFixedHeight(36)
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(title_label)

    @staticmethod
    def _rounded_poster(pix):
        result = QPixmap(260, 384)
        result.fill(Qt.GlobalColor.transparent)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, 260, 384), 18, 18)
        painter.setClipPath(path)
        scaled = pix.scaled(260, 384, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation)
        painter.drawPixmap((260 - scaled.width()) // 2, (384 - scaled.height()) // 2, scaled)
        painter.end()
        result.setDevicePixelRatio(2)
        return result


class DownloadCard(QFrame):
    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.setObjectName('card')
        self.setFixedHeight(82)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.name_label = QLabel(name)
        self.name_label.setStyleSheet(f'font-weight:600; font-size:13px; color:{TEXT};')
        top.addWidget(self.name_label, 1)
        self.status_label = QLabel(t('queued'))
        self.status_label.setStyleSheet(f'color:{TEXT_DIM}; font-size:12px; font-weight:500;')
        top.addWidget(self.status_label)
        self.info_label = QLabel('')
        self.info_label.setStyleSheet(f'color:{TEXT_DIM}; font-size:11px;')
        top.addWidget(self.info_label)
        layout.addLayout(top)

        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        layout.addWidget(self.bar)

    def update_progress(self, percent, size, speed, eta):
        self.bar.setValue(int(percent * 10))
        parts = []
        if size > 0:
            parts.append(f'{size / 1048576:.1f} MB')
        if speed > 0:
            parts.append(f'{speed / 1048576:.1f} MB/s')
        if eta is not None:
            m, s = divmod(int(eta), 60)
            parts.append(f'{m}:{s:02d}')
        self.info_label.setText('  '.join(parts))
        self.status_label.setText(f'{percent:.0f}%')

    def set_status(self, status):
        self.status_label.setText(status)
        self.info_label.setText('')
        colors = {
            t('completed'): GREEN, t('error_log'): RED,
            t('error_start'): RED, t('cancelled'): YELLOW,
            t('paused'): YELLOW, t('downloading'): ACCENT,
            t('processing'): ACCENT,
        }
        color = colors.get(status, TEXT_DIM)
        self.status_label.setStyleSheet(f'color:{color}; font-size:12px; font-weight:600;')
        if status == t('completed'):
            self.bar.setValue(1000)
            self.bar.setStyleSheet(f'QProgressBar::chunk{{background:{GREEN};border-radius:6px;}}')
        elif status in (t('error_log'), t('error_start')):
            self.bar.setStyleSheet(f'QProgressBar::chunk{{background:{RED};border-radius:6px;}}')


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
        self.setWindowIcon(self._app_icon)
        self.resize(1440, 900)
        available = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1440, available.width() - 60), min(900, available.height() - 60))
        self.setMinimumSize(860, 600)
        self.setAcceptDrops(True)
        self.setStyleSheet(STYLE)

        root = GlassBackdrop()
        root.setObjectName('root')
        self.setCentralWidget(root)
        main_layout = QHBoxLayout(root)
        main_layout.setContentsMargins(12, 12, 12, 8)
        main_layout.setSpacing(6)

        # Sidebar
        sidebar = GlassPanel()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(194)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(10, 18, 10, 10)
        sb_layout.setSpacing(6)

        logo = QLabel('Movie\nDownloader')
        logo.setObjectName('logo')
        brand = QHBoxLayout()
        brand.setContentsMargins(6, 8, 2, 24)
        brand.setSpacing(10)
        brand_icon = QLabel()
        brand_icon.setPixmap(self._app_icon.pixmap(40, 40))
        brand.addWidget(brand_icon)
        brand.addWidget(logo, 1)
        sb_layout.addLayout(brand)

        self.nav_buttons = []
        nav_items = [
            ('nav_download', 'download'),
            ('nav_queue', 'queue'),
            ('nav_history', 'history'),
            ('nav_paths', 'folder'),
            ('nav_settings', 'settings'),
        ]
        for key, icon_name in nav_items:
            if key == "nav_settings":
                sb_layout.addStretch()
            btn = QPushButton(t(key))
            btn.setObjectName('nav')
            btn.setIcon(icon(icon_name))
            btn.setIconSize(QSize(21, 21))
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            idx = len(self.nav_buttons)
            btn.clicked.connect(lambda checked, i=idx: self._switch_page(i))
            sb_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        self.version_label = QLabel(f'v{VERSION}')
        self.version_label.setObjectName('version')
        sb_layout.addWidget(self.version_label)
        main_layout.addWidget(sidebar)

        # Content area
        self.stack = QStackedWidget()

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
        wrapper.addWidget(self.status_bar)
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
        grad = QLinearGradient(0, 0, 64, 64)
        grad.setColorAt(0, QColor('#526f87'))
        grad.setColorAt(1, QColor('#263c4f'))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(2, 2, 60, 60, 18, 18)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#ffffff'))
        path = QPainterPath()
        path.moveTo(32, 14)
        path.lineTo(32, 40)
        path.moveTo(32, 40)
        p.setPen(QPen(QColor('#ffffff'), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(32, 14, 32, 40)
        p.drawLine(22, 32, 32, 42)
        p.drawLine(42, 32, 32, 42)
        p.setPen(QPen(QColor('#ffffff'), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(18, 50, 46, 50)
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
        layout.setContentsMargins(20, 14, 14, 10)
        layout.setSpacing(18)

        def heading(text, name='section'):
            label = QLabel(text)
            label.setObjectName(name)
            if name == 'hint':
                label.setWordWrap(True)
            return label

        def panel():
            widget = GlassPanel()
            box = QVBoxLayout(widget)
            box.setContentsMargins(18, 18, 18, 18)
            box.setSpacing(12)
            return widget, box

        def section(box, text, symbol):
            row = QHBoxLayout()
            row.setSpacing(10)
            image = QLabel()
            image.setPixmap(icon(symbol, TEXT, 22).pixmap(22, 22))
            row.addWidget(image)
            row.addWidget(heading(text), 1)
            box.addLayout(row)

        def field(box, text, widget):
            label = QLabel(text)
            label.setBuddy(widget)
            box.addWidget(label)
            widget.setAccessibleName(text)
            box.addWidget(widget)

        def separator(box):
            line = QFrame()
            line.setObjectName('separator')
            line.setFixedHeight(1)
            box.addWidget(line)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(5)
        titles.addWidget(heading(t('new_download'), 'page_title'))
        titles.addWidget(heading(t('download_intro'), 'hint'))
        header.addLayout(titles, 1)
        self.queue_badge = QPushButton()
        self.queue_badge.setIcon(icon('queue'))
        self.queue_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self.queue_badge.clicked.connect(lambda: self._switch_page(1))
        header.addWidget(self.queue_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(header)

        source, source_box = panel()
        section(source_box, t('video_link'), 'link')
        url_row = QHBoxLayout()
        url_row.setSpacing(10)
        self.url = QLineEdit()
        self.url.setPlaceholderText(t('url_placeholder'))
        self.url.setAccessibleName(t('video_link'))
        self.url.setClearButtonEnabled(True)
        self.url.setMinimumHeight(22)
        url_row.addWidget(self.url, 1)
        paste_btn = QPushButton(t('paste'))
        paste_btn.setIcon(icon('paste'))
        paste_btn.clicked.connect(self._paste_url)
        url_row.addWidget(paste_btn)
        self.analyze_btn = QPushButton(t('analyze_link'))
        self.analyze_btn.setIcon(icon('search', TEXT))
        self.analyze_btn.setObjectName('accent')
        self.analyze_btn.clicked.connect(self._analyze_link)
        self.url.returnPressed.connect(self.analyze_btn.click)
        url_row.addWidget(self.analyze_btn)
        source_box.addLayout(url_row)
        self.res_label = heading(t('res_hint'), 'hint')
        self.res_label.setWordWrap(True)
        source_box.addWidget(self.res_label)
        layout.addWidget(source)

        movie, movie_box = panel()
        movie.setMinimumWidth(360)
        section(movie_box, t('movie_info'), 'film')
        movie_box.addWidget(heading(t('movie_info_hint'), 'hint'))
        search_row = QHBoxLayout()
        search_row.setSpacing(10)
        self.query = QLineEdit()
        self.query.setPlaceholderText(t('tmdb_placeholder'))
        self.query.setAccessibleName(t('search_tmdb'))
        self.query.addAction(icon('search'), QLineEdit.ActionPosition.LeadingPosition)
        self.query.setClearButtonEnabled(True)
        search_row.addWidget(self.query, 1)
        self.search_btn = QPushButton(t('search_tmdb'))
        self.search_btn.setObjectName('accent')
        self.search_btn.clicked.connect(self._search)
        self.query.returnPressed.connect(self.search_btn.click)
        search_row.addWidget(self.search_btn)
        movie_box.addLayout(search_row)

        # A fixed viewport height prevents poster clipping when the form grows.
        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setFixedHeight(272)
        self.results_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results_scroll.setVisible(False)
        self.results_container = QWidget()
        self.results_layout = QHBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(0, 2, 0, 8)
        self.results_layout.setSpacing(10)
        self.results_layout.addStretch()
        self.results_scroll.setWidget(self.results_container)
        self.poster_cards = []
        self.no_results_label = heading(t('catalog_empty'), 'empty')
        self.no_results_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_results_label.setWordWrap(True)
        self.no_results_label.setMinimumHeight(272)
        movie_box.addWidget(self.no_results_label)
        movie_box.addWidget(self.results_scroll)
        separator(movie_box)

        metadata = QHBoxLayout()
        metadata.setSpacing(12)
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText(t('title'))
        self.year_input = QLineEdit()
        self.year_input.setPlaceholderText('2026')
        self.year_input.setMaxLength(4)
        self.year_input.setFixedWidth(78)
        self.kind = QComboBox()
        self.kind.addItems([t('movie'), t('tv_show')])
        self.kind.setFixedWidth(120)
        self.kind.currentIndexChanged.connect(self._change_kind)
        for label, widget, stretch in [(t('title'), self.title_input, 1),
                                        (t('year'), self.year_input, 0),
                                        (t('category'), self.kind, 0)]:
            col = QVBoxLayout()
            col.setSpacing(7)
            field(col, label, widget)
            metadata.addLayout(col, stretch)
        movie_box.addLayout(metadata)
        movie_box.addStretch()

        options, opts = panel()
        options.setMinimumWidth(330)
        section(opts, t('download_options'), 'settings')
        self.quality = QComboBox()
        for label, value in [(t('best'), 'best'), (t('up_to_1080'), '1080'),
                             (t('up_to_720'), '720'), (t('up_to_480'), '480'), (t('audio_only'), 'audio')]:
            self.quality.addItem(label, value)
        field(opts, t('quality'), self.quality)

        self.path_combo = QComboBox()
        self.path_combo.addItem(t('custom'), '')
        for cp in self.settings.get('custom_paths', []):
            self.path_combo.addItem(cp['name'], cp['path'])
        self.path_combo.currentIndexChanged.connect(self._apply_custom_path)
        field(opts, t('destination'), self.path_combo)
        destination = QHBoxLayout()
        destination.setSpacing(8)
        self.directory = QLineEdit(self.settings.get('movie_dir', ''))
        self.directory.setPlaceholderText(t('choose_folder'))
        self.directory.setAccessibleName(t('folder'))
        self.directory.setMinimumWidth(0)
        self.directory.textChanged.connect(self.directory.setToolTip)
        self.directory.setToolTip(self.directory.text())
        destination.addWidget(self.directory, 1)
        browse = QPushButton()
        browse.setIcon(icon('folder'))
        browse.setFixedWidth(44)
        browse.setAccessibleName(t('browse'))
        browse.setToolTip(t('browse'))
        browse.clicked.connect(self._choose_directory)
        destination.addWidget(browse)
        opts.addLayout(destination)

        subs_row = QHBoxLayout()
        subs_row.addWidget(QLabel(t('subtitles')), 1)
        self.subs_check = Toggle(t('subtitles'))
        self.subs_check.setChecked(self.settings.get('subtitles', True))
        subs_row.addWidget(self.subs_check)
        opts.addLayout(subs_row)
        languages = QHBoxLayout()
        self.language_chips = {}
        for code, name in [('it', 'Italiano'), ('en', 'English')]:
            chip = QPushButton(name)
            chip.setObjectName('chip')
            chip.setCheckable(True)
            chip.clicked.connect(lambda checked, c=code: self._toggle_language(c, checked))
            self.language_chips[code] = chip
            languages.addWidget(chip)
        languages.addStretch()
        opts.addLayout(languages)
        separator(opts)

        self.advanced_button = QPushButton(t('advanced_options'))
        self.advanced_button.setIcon(icon('chevron'))
        self.advanced_button.setObjectName('disclosure')
        self.advanced_button.setCheckable(True)
        opts.addWidget(self.advanced_button)
        self.advanced_options = QWidget()
        advanced = QVBoxLayout(self.advanced_options)
        advanced.setContentsMargins(0, 0, 0, 8)
        self.sub_langs = QComboBox()
        self.sub_langs.setEditable(True)
        self.sub_langs.addItems(['en', 'it', 'it,en', 'en,es', 'en,fr', 'en,de'])
        self.sub_langs.setCurrentText(self.settings.get('sub_langs', 'it,en'))
        self.sub_langs.currentTextChanged.connect(self._sync_language_chips)
        field(advanced, t('sub_langs_label'), self.sub_langs)
        self.fragments = QComboBox()
        self.fragments.addItems(['1', '4', '8', '16'])
        self.fragments.setCurrentText(str(self.settings.get('fragments', 16)))
        field(advanced, t('fragments'), self.fragments)
        opts.addWidget(self.advanced_options)
        self.advanced_options.hide()
        self.advanced_button.toggled.connect(self.advanced_options.setVisible)
        self.subs_check.toggled.connect(self._sync_language_chips)
        self._sync_language_chips()
        opts.addStretch()

        summary = QFrame()
        summary.setObjectName('summary')
        summary_box = QVBoxLayout(summary)
        summary_box.setContentsMargins(12, 12, 12, 12)
        summary_box.setSpacing(12)
        summary_row = QHBoxLayout()
        summary_row.setSpacing(12)
        self.summary_poster = QLabel()
        self.summary_poster.setFixedSize(44, 64)
        self.summary_poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.summary_poster.setPixmap(icon('film', TEXT_DIM, 28).pixmap(28, 28))
        summary_row.addWidget(self.summary_poster)
        summary_text = QVBoxLayout()
        self.summary_title = ElidedLabel()
        self.summary_title.setStyleSheet('font-weight: 600;')
        self.summary_title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.summary_meta = ElidedLabel()
        self.summary_meta.setObjectName('hint')
        self.summary_meta.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        summary_text.addWidget(self.summary_title)
        summary_text.addWidget(self.summary_meta)
        summary_row.addLayout(summary_text, 1)
        summary_box.addLayout(summary_row)
        self.add_button = QPushButton(t('add_to_queue'))
        self.add_button.setObjectName('primary')
        self.add_button.setIcon(icon('plus', '#102337'))
        self.add_button.setMinimumHeight(24)
        self.add_button.clicked.connect(self._add_job)
        summary_box.addWidget(self.add_button)
        opts.addWidget(summary)
        for signal in (self.title_input.textChanged, self.year_input.textChanged,
                       self.kind.currentIndexChanged, self.quality.currentIndexChanged):
            signal.connect(self._update_summary)
        self._update_summary()
        self.download_columns = ResponsiveColumns(movie, options)
        layout.addWidget(self.download_columns)
        layout.addStretch()
        for button in page.findChildren(QPushButton):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stack.addWidget(scroll)

    def _update_summary(self, *_):
        title = self.title_input.text().strip()
        year = self.year_input.text().strip()
        display = f'{title} ({year})' if title and year else title or t('selection_empty')
        self.summary_title.setText(display)
        self.summary_title.setToolTip(display)
        self.summary_meta.setText(f'{self.kind.currentText()} · {self.quality.currentText()}')
        self.summary_meta.setToolTip(self.summary_meta.text())

    def _sync_language_chips(self, *_):
        selected = self.sub_langs.currentText().split(',')
        enabled = self.subs_check.isChecked()
        if enabled and not any(s.strip() for s in selected):
            self.sub_langs.setCurrentText('it,en')
            return
        self.sub_langs.setEnabled(enabled)
        for code, chip in self.language_chips.items():
            chip.setChecked(code in [s.strip() for s in selected])
            chip.setEnabled(enabled)
            chip.setIcon(icon('check') if chip.isChecked() else QIcon())

    def _toggle_language(self, code, checked):
        selected = [s.strip() for s in self.sub_langs.currentText().split(',') if s.strip()]
        if checked and code not in selected:
            selected.append(code)
        if not checked:
            selected = [s for s in selected if s != code]
        if not selected:
            self.subs_check.setChecked(False)
        self.sub_langs.setCurrentText(','.join(selected))

    def _update_queue_badge(self):
        count = sum(j['state'] in (t('queued'), t('paused'), t('downloading')) for j in self.jobs)
        self.queue_badge.setText(t('queue_count').format(count))
        self.nav_buttons[1].setText(f"{t('nav_queue')}  {count}" if count else t('nav_queue'))

    # ---- Queue Page ----
    def _build_queue_page(self):
        page = QWidget()
        page.setObjectName('page')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(14)

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
        self.queue_layout.setSpacing(8)
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
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(14)

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
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(14)

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
        add_row.setSpacing(10)
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
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(12)

        title = QLabel(t('nav_settings'))
        title.setObjectName('page_title')
        layout.addWidget(title)

        section = QLabel(t('section_general'))
        section.setObjectName('section')
        layout.addWidget(section)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
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
        form2.setHorizontalSpacing(18)
        form2.setVerticalSpacing(12)
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
        form3.setHorizontalSpacing(18)
        form3.setVerticalSpacing(12)
        self.s_ffmpeg = QLineEdit(self.settings.get('ffmpeg', ''))
        self.s_ffmpeg.setPlaceholderText(t('ffmpeg_hint'))
        form3.addRow(t('ffmpeg_label'), self.s_ffmpeg)
        layout.addLayout(form3)

        tools_row = QHBoxLayout()
        tools_row.setSpacing(10)
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

        layout.addSpacing(18)
        save_btn = QPushButton(t('save_settings'))
        save_btn.setObjectName('primary')
        save_btn.setMinimumHeight(44)
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
            details = f'yt-dlp {data[0]}   {data[1]}'
            self.status_bar.setText('●  ' + t('ready'))
            self.status_bar.setToolTip(details)
            self.s_tools_label.setText(details[:160])
            self.s_tools_label.setToolTip(details)
            self.logger.info(details)
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
            for card in self.poster_cards:
                self.results_layout.removeWidget(card)
                card.deleteLater()
            self.poster_cards.clear()

            if not items:
                self.results_scroll.setVisible(False)
                self.no_results_label.setText(t('no_results'))
                self.no_results_label.setVisible(True)
                return

            self.no_results_label.setVisible(False)
            self.results_scroll.setVisible(True)
            for data in items:
                name = data.get('title') or data.get('name') or t('untitled')
                year = (data.get('release_date') or data.get('first_air_date') or '')[:4]
                kind_tag = t('movie') if data.get('_kind') == 'movie' else t('tv_show')
                card = PosterCard(name, year, kind_tag, data.get('poster_bytes'), data)
                card.clicked.connect(lambda checked, c=card: self._select_poster(c))
                self.results_layout.insertWidget(self.results_layout.count() - 1, card)
                self.poster_cards.append(card)
        self._task(lambda: search_tmdb_both(query, key), done, self.search_btn)

    def _select_poster(self, card):
        for c in self.poster_cards:
            if c is not card:
                c.setChecked(False)
        card.setChecked(True)
        data = card.data
        thumbnail = card.poster_label.pixmap().scaled(44, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        thumbnail.setDevicePixelRatio(1)
        self.summary_poster.setPixmap(thumbnail)
        self.title_input.setText(data.get('title') or data.get('name') or '')
        self.year_input.setText((data.get('release_date') or data.get('first_air_date') or '')[:4])
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
        self._update_queue_badge()
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
        self._update_queue_badge()

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
        self._update_queue_badge()
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
            self._update_queue_badge()
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
