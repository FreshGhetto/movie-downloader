import logging
import sys
import datetime
from pathlib import Path
from PySide6.QtCore import Qt, QProcess, QTimer, QSize, QUrl, QMimeData
from PySide6.QtGui import QIcon, QPixmap, QDesktopServices, QAction, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QDialog, QFormLayout, QListWidget, QListWidgetItem, QTextEdit, QSplitter,
    QSystemTrayIcon, QMenu, QApplication, QTabWidget)
from config.settings import load, save, load_queue, save_queue, load_history, save_history, ROOT
from config.i18n import t, set_language, LANGUAGES, current as current_lang
from config.version import VERSION
from services.core import safe_name, unique_base, validate_url, find_ffmpeg, version, command, progress
from services.workers import Task, analyze, search_tmdb_both, update_ytdlp, check_app_update

BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = load()
        set_language(self.settings.get('language', 'en'))
        ROOT.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger('movie_downloader')
        if not self.logger.handlers:
            handler = logging.FileHandler(ROOT / 'movie-downloader.log', encoding='utf-8')
            handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        self.exe = str(BASE / 'bin' / 'yt-dlp.exe')
        self.tasks, self.jobs = [], []
        self.history = load_history()
        self.current = None
        self.running = False
        self.buffer = ''
        self.versions_ok = False
        self.setWindowTitle('Movie Downloader')
        self.resize(1120, 870)
        self.setMinimumSize(820, 650)
        self.setAcceptDrops(True)
        self.setStyleSheet('''QWidget{background:#101723;color:#e5edf7;font-size:13px;} QLineEdit,QComboBox,QTextEdit,QListWidget,QTableWidget{background:#1b2636;border:1px solid #35465e;border-radius:6px;padding:7px;} QPushButton{background:#2a3b52;border:0;border-radius:6px;padding:10px 16px;} QPushButton:hover{background:#3b5270;} QPushButton:disabled{color:#778499;} QPushButton#primary{background:#2563eb;} QPushButton#primary:hover{background:#3b82f6;} QPushButton#danger{background:#dc2626;} QPushButton#danger:hover{background:#ef4444;} QHeaderView::section{background:#243249;padding:8px;border:0;} QLabel#heading{font-size:27px;font-weight:700;} QTabWidget::pane{border:1px solid #35465e;border-radius:6px;} QTabBar::tab{background:#1b2636;padding:8px 16px;border:1px solid #35465e;border-bottom:0;border-radius:6px 6px 0 0;} QTabBar::tab:selected{background:#243249;}''')
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        heading = QLabel('Movie Downloader'); heading.setObjectName('heading'); layout.addWidget(heading)
        layout.addWidget(QLabel(t('subtitle')))

        row = QHBoxLayout(); layout.addLayout(row)
        self.url = QLineEdit(); self.url.setPlaceholderText(t('url_placeholder')); row.addWidget(self.url, 1)
        self.button(row, t('paste'), self._paste_url)
        self.analyze_button = self.button(row, t('analyze'), self.analyze_link)

        form = QFormLayout(); layout.addLayout(form)
        self.title = QLineEdit(); form.addRow(t('title'), self.title)
        self.year = QLineEdit(); self.year.setMaxLength(4); form.addRow(t('year'), self.year)
        self.kind = QComboBox(); self.kind.addItems([t('movie'), t('tv_show')]); self.kind.currentIndexChanged.connect(self.change_kind); form.addRow(t('category'), self.kind)
        row = QHBoxLayout()
        self.path_combo = QComboBox(); self.path_combo.setMinimumWidth(140)
        self.path_combo.addItem(t('custom'), '')
        for cp in self.settings.get('custom_paths', []):
            self.path_combo.addItem(cp['name'], cp['path'])
        self.path_combo.currentIndexChanged.connect(self._apply_custom_path)
        row.addWidget(self.path_combo)
        self.directory = QLineEdit(self.settings['movie_dir']); row.addWidget(self.directory, 1)
        self.button(row, t('browse'), self.choose_directory)
        form.addRow(t('destination'), row)

        row = QHBoxLayout()
        self.quality = QComboBox()
        for label, value in [(t('best'),'best'),(t('up_to_1080'),'1080'),(t('up_to_720'),'720'),(t('up_to_480'),'480'),(t('audio_only'),'audio')]:
            self.quality.addItem(label, value)
        row.addWidget(self.quality)
        row.addWidget(QLabel(t('fragments')))
        self.fragments = QComboBox(); self.fragments.addItems(['1','4','8','16']); self.fragments.setCurrentText(str(self.settings.get('fragments', 16))); row.addWidget(self.fragments)
        self.subs_check = QCheckBox(t('subtitles')); self.subs_check.setChecked(self.settings.get('subtitles', True))
        row.addWidget(self.subs_check)
        self.sub_langs = QLineEdit(self.settings.get('sub_langs', 'it,en')); self.sub_langs.setMaximumWidth(80); self.sub_langs.setPlaceholderText('it,en')
        row.addWidget(self.sub_langs)
        form.addRow(t('quality'), row)

        self.resolutions = QLabel(t('res_hint')); layout.addWidget(self.resolutions)

        row = QHBoxLayout(); layout.addLayout(row)
        self.query = QLineEdit(); self.query.setPlaceholderText(t('tmdb_placeholder')); row.addWidget(self.query)
        self.search_button = self.button(row, t('search_tmdb'), self.search)
        self.query.returnPressed.connect(self.search_button.click)

        splitter = QSplitter(); layout.addWidget(splitter, 1)
        self.results = QListWidget(); self.results.setIconSize(QSize(62, 92)); self.results.currentItemChanged.connect(self.select_result); splitter.addWidget(self.results)
        self.synopsis = QTextEdit(); self.synopsis.setReadOnly(True); self.synopsis.setPlaceholderText(t('synopsis_hint')); splitter.addWidget(self.synopsis)

        row = QHBoxLayout(); layout.addLayout(row)
        self.add_button = self.button(row, t('add_to_queue'), self.add_job); self.add_button.setObjectName('primary')
        self.button(row, t('settings'), self.configure)
        self.button(row, t('open_log'), lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(ROOT / 'movie-downloader.log'))))

        tabs = QTabWidget(); layout.addWidget(tabs, 2)

        queue_widget = QWidget(); queue_layout = QVBoxLayout(queue_widget)
        self.table = QTableWidget(0, 5); self.table.setHorizontalHeaderLabels([t('col_file'), t('col_status'), t('col_progress'), t('col_size_speed'), t('col_time_left')])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        queue_layout.addWidget(self.table)
        row = QHBoxLayout(); queue_layout.addLayout(row)
        self.button(row, t('start'), self.start_queue); self.button(row, t('pause'), self.pause); self.button(row, t('resume'), self.resume)
        cancel_btn = self.button(row, t('cancel_selected'), self.cancel); cancel_btn.setObjectName('danger')
        self.button(row, t('clear_completed'), self.clear_completed)
        tabs.addTab(queue_widget, t('queue'))

        history_widget = QWidget(); history_layout = QVBoxLayout(history_widget)
        self.history_table = QTableWidget(0, 4); self.history_table.setHorizontalHeaderLabels([t('col_file'), t('col_date'), t('quality'), t('col_status')])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        history_layout.addWidget(self.history_table)
        row = QHBoxLayout(); history_layout.addLayout(row)
        clear_hist = self.button(row, t('clear_history'), self.clear_history); clear_hist.setObjectName('danger')
        row.addStretch()
        tabs.addTab(history_widget, t('history'))
        self._refresh_history_table()

        paths_widget = QWidget(); paths_layout = QVBoxLayout(paths_widget)
        paths_layout.addWidget(QLabel(t('paths_hint')))
        self.paths_table = QTableWidget(0, 2); self.paths_table.setHorizontalHeaderLabels([t('col_shortcut'), t('col_folder')])
        self.paths_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.paths_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.paths_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        paths_layout.addWidget(self.paths_table)
        add_row = QHBoxLayout(); paths_layout.addLayout(add_row)
        self.path_name_input = QLineEdit(); self.path_name_input.setPlaceholderText(t('path_name_hint')); add_row.addWidget(self.path_name_input)
        self.path_dir_input = QLineEdit(); self.path_dir_input.setPlaceholderText(t('folder')); add_row.addWidget(self.path_dir_input, 1)
        self.button(add_row, t('browse'), self._browse_custom_path)
        add_path_btn = self.button(add_row, t('add'), self._add_custom_path); add_path_btn.setObjectName('primary')
        row = QHBoxLayout(); paths_layout.addLayout(row)
        rm_path_btn = self.button(row, t('remove_selected'), self._remove_custom_path); rm_path_btn.setObjectName('danger')
        row.addStretch()
        tabs.addTab(paths_widget, t('paths'))
        self._refresh_paths_table()

        self.status = QLabel(t('checking_tools')); self.status.setWordWrap(True); layout.addWidget(self.status)

        self.process = QProcess(self); self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_output); self.process.finished.connect(self.finished); self.process.errorOccurred.connect(self.process_error)

        self._setup_tray()
        self._restore_queue()
        QTimer.singleShot(0, self.check_tools)
        if self.settings.get('auto_update', True):
            QTimer.singleShot(3000, self._auto_check_update)

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setToolTip('Movie Downloader')
        menu = QMenu()
        show_action = QAction(t('show'), self); show_action.triggered.connect(self.showNormal); menu.addAction(show_action)
        quit_action = QAction(t('quit'), self); quit_action.triggered.connect(self._quit_app); menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.showNormal() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()

    def _quit_app(self):
        self._save_queue()
        self.tray.hide()
        QApplication.quit()

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
            self.analyze_link()

    def button(self, row, label, callback):
        b = QPushButton(label); b.clicked.connect(callback); row.addWidget(b); return b

    def fail(self, message):
        self.logger.error(message); QMessageBox.warning(self, 'Movie Downloader', message)

    def task(self, fn, callback, button=None):
        t = Task(fn); self.tasks.append(t)
        if button: button.setEnabled(False)
        t.result.connect(callback); t.error.connect(self.fail)
        def cleanup():
            if button: button.setEnabled(True)
            self.tasks.remove(t); t.deleteLater()
        t.finished.connect(cleanup); t.start()

    def check_tools(self):
        self.versions_ok = False
        ff = find_ffmpeg(self.settings['ffmpeg'])
        def check():
            return version(self.exe), version(ff)
        def done(data):
            self.versions_ok = True; self.status.setText(f'yt-dlp {data[0]} • {data[1]}'); self.logger.info(self.status.text())
        self.task(check, done)

    def analyze_link(self):
        url = self.url.text().strip()
        def done(data):
            if self.url.text().strip() != url: return
            self.title.setText(data['title']); self.year.setText(data['year'])
            heights_str = ', '.join(f'{h}p' for h in data['heights']) or t('res_undeclared')
            self.resolutions.setText(f'{t("res_offered")}: {heights_str}')
            if data['title'] and self.settings.get('tmdb_key'):
                self.query.setText(data['title'])
                QTimer.singleShot(100, self.search)
        self.task(lambda: analyze(self.exe, url), done, self.analyze_button)

    def change_kind(self):
        self.directory.setText(self.settings['movie_dir' if self.kind.currentIndex() == 0 else 'tv_dir'])

    def choose_directory(self):
        path = QFileDialog.getExistingDirectory(self, t('destination'), self.directory.text())
        if path: self.directory.setText(path)

    def search(self):
        query = self.query.text().strip()
        if not query: return
        key = self.settings['tmdb_key']
        def done(items):
            self.results.clear()
            for data in items:
                title = data.get('title') or data.get('name') or t('untitled')
                year = (data.get('release_date') or data.get('first_air_date') or '')[:4]
                kind_label = '\U0001f3ac' if data.get('_kind') == 'movie' else '\U0001f4fa'
                item = QListWidgetItem(f'{kind_label} {title} ({year or "?"})')
                item.setData(Qt.ItemDataRole.UserRole, data)
                if data.get('poster_bytes'):
                    pix = QPixmap(); pix.loadFromData(data['poster_bytes']); item.setIcon(QIcon(pix))
                self.results.addItem(item)
            if not items: self.synopsis.setText(t('no_results'))
        self.task(lambda: search_tmdb_both(query, key), done, self.search_button)

    def select_result(self, item, previous):
        if not item: return
        data = item.data(Qt.ItemDataRole.UserRole)
        self.title.setText(data.get('title') or data.get('name') or '')
        self.year.setText((data.get('release_date') or data.get('first_air_date') or '')[:4])
        self.synopsis.setText(data.get('overview') or t('no_synopsis'))
        if data.get('_kind') == 'tv':
            self.kind.setCurrentIndex(1)
        elif data.get('_kind') == 'movie':
            self.kind.setCurrentIndex(0)

    def add_job(self):
        try:
            validate_url(self.url.text().strip())
            if not self.title.text().strip(): raise ValueError(t('enter_title'))
            if self.year.text() and not (self.year.text().isdigit() and len(self.year.text()) == 4): raise ValueError(t('year_digits'))
            directory = Path(self.directory.text()); directory.mkdir(parents=True, exist_ok=True)
            base = unique_base(directory, safe_name(self.title.text(), self.year.text()), [j['base'] for j in self.jobs])
            frags = int(self.fragments.currentText())
            job = {
                'url': self.url.text().strip(), 'base': str(base), 'quality': self.quality.currentData(),
                'fragments': frags, 'subtitles': self.subs_check.isChecked(),
                'sub_langs': self.sub_langs.text().strip() or 'it,en', 'state': t('queued')
            }
            self.jobs.append(job)
            row = self.table.rowCount(); self.table.insertRow(row)
            for col, text in enumerate([base.name, t('queued'), '—', '—', '—']):
                self.table.setItem(row, col, QTableWidgetItem(text))
            self.settings['movie_dir' if self.kind.currentIndex() == 0 else 'tv_dir'] = str(directory)
            self.settings['fragments'] = frags
            self.settings['subtitles'] = self.subs_check.isChecked()
            self.settings['sub_langs'] = self.sub_langs.text().strip() or 'it,en'
            save(self.settings)
            self._save_queue()
        except Exception as e:
            self.fail(str(e))

    def _save_queue(self):
        pending = [j for j in self.jobs if j['state'] in (t('queued'), t('paused'))]
        save_queue(pending)

    def _restore_queue(self):
        saved = load_queue()
        for job in saved:
            job['state'] = t('queued')
            self.jobs.append(job)
            row = self.table.rowCount(); self.table.insertRow(row)
            name = Path(job['base']).name
            for col, text in enumerate([name, t('queued'), '—', '—', '—']):
                self.table.setItem(row, col, QTableWidgetItem(text))

    def set_state(self, index, state):
        self.jobs[index]['state'] = state; self.table.item(index, 1).setText(state)

    def start_queue(self):
        if not self.versions_ok: self.fail(t('verify_tools')); return
        self.running = True; self.next_job()

    def next_job(self):
        if self.current is not None or not self.running: return
        index = next((i for i, j in enumerate(self.jobs) if j['state'] == t('queued')), None)
        if index is None:
            self.running = False
            if any(j['state'] == t('completed') for j in self.jobs):
                self._notify(t('queue_done_title'), t('queue_done_msg'))
            return
        self.current = index; self.buffer = ''; self.set_state(index, t('downloading'))
        args = command(self.exe, self.jobs[index], find_ffmpeg(self.settings['ffmpeg']))
        self.logger.info('Start: %s', Path(self.jobs[index]['base']).name)
        self.process.start(args[0], args[1:])

    def read_output(self):
        self.buffer += bytes(self.process.readAllStandardOutput()).decode('utf-8', errors='replace')
        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1); self.logger.info(line.rstrip())
            data = progress(line)
            if data and self.current is not None:
                r = self.current
                self.table.item(r, 2).setText(f'{data["percent"]:.1f}%')
                self.table.item(r, 3).setText(f'{data["size"]/1048576:.1f} MiB / {data["speed"]/1048576:.2f} MiB/s')
                self.table.item(r, 4).setText(f'{data["eta"]} s' if data['eta'] is not None else '—')
                if data['status'] == 'finished': self.table.item(r, 1).setText(t('processing'))

    def finished(self, code, status):
        self.read_output()
        if self.current is None: return
        r = self.current
        job = self.jobs[r]
        if job['state'] not in (t('paused'), t('cancelled')):
            ok = code == 0
            self.set_state(r, t('completed') if ok else t('error_log'))
            if ok:
                self.table.item(r, 2).setText('100%')
                self._notify(t('download_done'), Path(job['base']).name)
            self._add_history(job, t('completed') if ok else t('error_log'))
        self._save_queue()
        self.current = None; QTimer.singleShot(0, self.next_job)

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart and self.current is not None:
            self.set_state(self.current, t('error_start')); self.current = None; self.running = False
            self.fail(t('ytdlp_start_fail'))

    def pause(self):
        self.running = False
        if self.current is not None:
            self.set_state(self.current, t('paused')); self.process.kill()
        self._save_queue()

    def resume(self):
        if self.current is not None: return
        for i, j in enumerate(self.jobs):
            if j['state'] == t('paused'): self.set_state(i, t('queued'))
        self.start_queue()

    def cancel(self):
        row = self.table.currentRow()
        if row < 0: row = self.current if self.current is not None else -1
        if row < 0 or self.jobs[row]['state'] == t('completed'): return
        self.set_state(row, t('cancelled'))
        if row == self.current: self.process.kill()
        self._save_queue()

    def clear_completed(self):
        i = len(self.jobs) - 1
        while i >= 0:
            if self.jobs[i]['state'] in (t('completed'), t('cancelled'), t('error_log'), t('error_start')):
                if i == self.current: i -= 1; continue
                self.jobs.pop(i); self.table.removeRow(i)
                if self.current is not None and self.current > i: self.current -= 1
            i -= 1
        self._save_queue()

    def _notify(self, title, message):
        if self.tray.isVisible():
            self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 5000)
        QApplication.beep()

    def _add_history(self, job, status):
        entry = {
            'file': Path(job['base']).name, 'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
            'quality': job['quality'], 'status': status
        }
        self.history.append(entry)
        save_history(self.history)
        self._refresh_history_table()

    def _refresh_history_table(self):
        self.history_table.setRowCount(0)
        for entry in reversed(self.history[-100:]):
            row = self.history_table.rowCount(); self.history_table.insertRow(row)
            for col, key in enumerate(['file', 'date', 'quality', 'status']):
                self.history_table.setItem(row, col, QTableWidgetItem(str(entry.get(key, ''))))

    def clear_history(self):
        self.history.clear(); save_history(self.history); self._refresh_history_table()

    def _apply_custom_path(self, index):
        path = self.path_combo.currentData()
        if path:
            self.directory.setText(path)

    def _browse_custom_path(self):
        path = QFileDialog.getExistingDirectory(self, t('folder'), self.path_dir_input.text() or str(Path.home()))
        if path: self.path_dir_input.setText(path)

    def _add_custom_path(self):
        name = self.path_name_input.text().strip()
        path = self.path_dir_input.text().strip()
        if not name or not path:
            self.fail(t('enter_name_path')); return
        paths = self.settings.get('custom_paths', [])
        if any(p['name'] == name for p in paths):
            self.fail(t('path_exists').format(name)); return
        paths.append({'name': name, 'path': path})
        self.settings['custom_paths'] = paths
        save(self.settings)
        self.path_combo.addItem(name, path)
        self._refresh_paths_table()
        self.path_name_input.clear(); self.path_dir_input.clear()

    def _remove_custom_path(self):
        row = self.paths_table.currentRow()
        if row < 0: return
        name = self.paths_table.item(row, 0).text()
        paths = [p for p in self.settings.get('custom_paths', []) if p['name'] != name]
        self.settings['custom_paths'] = paths
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
            row = self.paths_table.rowCount(); self.paths_table.insertRow(row)
            self.paths_table.setItem(row, 0, QTableWidgetItem(cp['name']))
            self.paths_table.setItem(row, 1, QTableWidgetItem(cp['path']))

    def _auto_check_update(self):
        def done(result):
            if result and not result.get('up_to_date') and result.get('url'):
                self._notify(t('new_version').format(result['version']), result['url'])
        self.task(lambda: check_app_update(VERSION), done)

    def configure(self):
        dialog = QDialog(self); dialog.setWindowTitle(t('settings_title')); form = QFormLayout(dialog)
        key = QLineEdit(self.settings['tmdb_key']); key.setEchoMode(QLineEdit.EchoMode.Password); form.addRow(t('tmdb_key_label'), key)
        ff = QLineEdit(self.settings['ffmpeg']); ff.setPlaceholderText(t('ffmpeg_hint')); form.addRow(t('ffmpeg_label'), ff)
        movie = QLineEdit(self.settings['movie_dir']); tv = QLineEdit(self.settings['tv_dir'])
        form.addRow(t('movie_folder'), movie); form.addRow(t('tv_folder'), tv)

        lang_combo = QComboBox()
        for code, name in LANGUAGES.items():
            lang_combo.addItem(name, code)
        lang_combo.setCurrentIndex(list(LANGUAGES.keys()).index(current_lang()))
        form.addRow(t('language_label'), lang_combo)

        auto_update_check = QCheckBox(t('auto_update_label'))
        auto_update_check.setChecked(self.settings.get('auto_update', True))
        form.addRow('', auto_update_check)

        form.addRow(QLabel(''))
        check_btn = QPushButton(t('check_updates')); form.addRow(check_btn)
        check_label = QLabel(''); form.addRow(check_label)
        def do_check():
            check_btn.setEnabled(False); check_label.setText(t('checking_update'))
            def done(result):
                if result is None:
                    check_label.setText('—')
                elif result.get('up_to_date'):
                    check_label.setText(t('up_to_date').format(VERSION))
                else:
                    check_label.setText(t('new_version').format(result['version']))
                    QDesktopServices.openUrl(QUrl(result['url']))
            def err(msg):
                check_label.setText(msg[:200])
            t_task = Task(lambda: check_app_update(VERSION)); self.tasks.append(t_task)
            t_task.result.connect(done); t_task.error.connect(err)
            t_task.finished.connect(lambda: (check_btn.setEnabled(True), self.tasks.remove(t_task), t_task.deleteLater()))
            t_task.start()
        check_btn.clicked.connect(do_check)

        form.addRow(QLabel(''))
        update_btn = QPushButton(t('update_ytdlp')); form.addRow(update_btn)
        update_label = QLabel(''); form.addRow(update_label)
        def do_update():
            update_btn.setEnabled(False); update_label.setText(t('updating'))
            def done(output):
                update_label.setText(output[:200]); self.check_tools()
            def err(msg):
                update_label.setText(msg[:200])
            t_task = Task(lambda: update_ytdlp(self.exe)); self.tasks.append(t_task)
            t_task.result.connect(done); t_task.error.connect(err)
            t_task.finished.connect(lambda: (update_btn.setEnabled(True), self.tasks.remove(t_task), t_task.deleteLater()))
            t_task.start()
        update_btn.clicked.connect(do_update)

        b = QPushButton(t('save_verify')); form.addRow(b); b.clicked.connect(dialog.accept)
        if dialog.exec():
            old_lang = self.settings.get('language', 'en')
            new_lang = lang_combo.currentData()
            self.settings.update(
                tmdb_key=key.text().strip(), ffmpeg=ff.text().strip(),
                movie_dir=movie.text(), tv_dir=tv.text(),
                language=new_lang, auto_update=auto_update_check.isChecked()
            )
            save(self.settings); self.change_kind(); self.check_tools()
            if new_lang != old_lang:
                QMessageBox.information(self, 'Movie Downloader', t('restart_lang'))

    def changeEvent(self, event):
        if event.type() == event.Type.WindowStateChange and self.isMinimized():
            self.hide()
            self.tray.showMessage('Movie Downloader', t('minimized_tray'), QSystemTrayIcon.MessageIcon.Information, 2000)
        super().changeEvent(event)

    def closeEvent(self, event):
        if self.tasks or self.current is not None:
            QMessageBox.information(self, 'Movie Downloader', t('busy_close'))
            event.ignore(); return
        self._save_queue()
        save(self.settings)
        self.tray.hide()
        event.accept()
