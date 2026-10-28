"""Exercise the real download page with isolated persistence and no network."""
import copy
from unittest.mock import Mock
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QBoxLayout
from PySide6.QtTest import QTest
from config.settings import DEFAULTS
from config.i18n import t
import gui.window as gui


@pytest.fixture
def window(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    # The offscreen Windows plugin has no system font discovery.
    from pathlib import Path
    for filename in ('segoeui.ttf', 'segoeuib.ttf', 'seguisb.ttf'):
        font = Path('C:/Windows/Fonts') / filename
        if font.exists():
            QFontDatabase.addApplicationFont(str(font))
    settings = copy.deepcopy(DEFAULTS) | {'language': 'it', 'auto_update': False}
    monkeypatch.setattr(gui, 'ROOT', tmp_path)
    monkeypatch.setattr(gui, 'load', lambda: settings)
    monkeypatch.setattr(gui, 'load_queue', lambda: [])
    monkeypatch.setattr(gui, 'load_history', lambda: [])
    monkeypatch.setattr(gui, 'save', Mock())
    monkeypatch.setattr(gui, 'save_queue', Mock())
    monkeypatch.setattr(gui.Window, '_check_tools', lambda self: None)
    monkeypatch.setattr(gui.Window, '_setup_tray', lambda self: setattr(self, 'tray', Mock()))
    w = gui.Window()
    w.resize(1440, 900)
    w.show()
    app.processEvents()
    yield w
    w.close()
    w.deleteLater()
    app.processEvents()


def results(window):
    window.query.setText('Film')
    items = [
        {'title': 'Titolo italiano', 'release_date': '2024-04-01', '_kind': 'movie'},
        {'name': 'Secondo risultato', 'first_air_date': '2023-01-01', '_kind': 'tv'},
    ]
    window._task = lambda fn, callback, button=None: callback(items)
    window.search_btn.click()
    QApplication.processEvents()


def test_catalog_selection_preserves_url_and_updates_summary(window):
    window.url.setText('https://example.org/authorized.mp4')
    results(window)
    assert len(window.poster_cards) == 2
    QTest.mouseClick(window.poster_cards[0], Qt.MouseButton.LeftButton)
    assert window.title_input.text() == 'Titolo italiano'
    assert window.year_input.text() == '2024'
    assert window.summary_title.text() == 'Titolo italiano (2024)'
    assert window.kind.currentIndex() == 0
    window.poster_cards[1].click()
    assert window.title_input.text() == 'Secondo risultato'
    assert window.kind.currentIndex() == 1
    assert not window.poster_cards[0].isChecked()
    assert window.poster_cards[1].isChecked()
    window.poster_cards[1].click()
    assert window.poster_cards[1].isChecked()
    assert window.url.text() == 'https://example.org/authorized.mp4'
    assert window.results_scroll.viewport().height() >= window.poster_cards[0].height()


def test_empty_search_clears_results(window):
    results(window)
    window._task = lambda fn, callback, button=None: callback([])
    window.search_btn.click()
    assert not window.poster_cards
    assert window.results_scroll.isHidden()
    assert window.no_results_label.text() == t('no_results')


def test_languages_and_advanced_controls(window):
    assert window.fragments.currentText() == '16'
    assert window.advanced_options.isHidden()
    window.advanced_button.click()
    assert not window.advanced_options.isHidden()
    window.sub_langs.setCurrentText('it,en,fr')
    window.language_chips['it'].click()
    assert window.sub_langs.currentText() == 'en,fr'
    window.language_chips['it'].click()
    assert set(window.sub_langs.currentText().split(',')) == {'it', 'en', 'fr'}
    QTest.mouseClick(window.subs_check, Qt.MouseButton.LeftButton)
    assert not window.sub_langs.isEnabled()
    assert not window.language_chips['en'].isEnabled()
    QTest.mouseClick(window.subs_check, Qt.MouseButton.LeftButton)
    assert window.sub_langs.isEnabled()
    window.sub_langs.setCurrentText('it')
    window.language_chips['it'].click()
    assert not window.subs_check.isChecked()
    window.subs_check.setChecked(True)
    assert window.sub_langs.currentText() == 'it,en'


def test_add_to_queue_preserves_options_and_badge(window, tmp_path):
    window.url.setText('https://example.org/authorized.mp4')
    window.title_input.setText('Test locale')
    window.year_input.setText('2024')
    window.directory.setText(str(tmp_path / 'downloads'))
    window.quality.setCurrentIndex(2)
    window.fragments.setCurrentText('8')
    window.sub_langs.setCurrentText('it,fr')
    window.add_button.click()
    assert len(window.jobs) == 1
    job = window.jobs[0]
    assert job['quality'] == '720'
    assert job['fragments'] == 8
    assert job['sub_langs'] == 'it,fr'
    assert job['subtitles'] is True
    assert window.stack.currentIndex() == 1
    assert window.queue_badge.text() == '1 in coda'
    window.jobs[0]['state'] = t('completed')
    window._clear_completed()
    assert window.queue_badge.text() == '0 in coda'


@pytest.mark.parametrize('size', [(1440, 900), (1060, 740), (860, 600)])
def test_responsive_layout_does_not_clip(window, size):
    results(window)
    window.resize(*size)
    for _ in range(5):
        QApplication.processEvents()
    scroll = window.stack.widget(0)
    assert scroll.horizontalScrollBar().maximum() == 0
    assert window.results_scroll.viewport().height() >= window.poster_cards[0].height()
    expected = QBoxLayout.Direction.LeftToRight if size[0] == 1440 else QBoxLayout.Direction.TopToBottom
    assert window.download_columns.columns.direction() == expected
    window.advanced_button.click()
    for _ in range(5):
        QApplication.processEvents()
    assert scroll.horizontalScrollBar().maximum() == 0
    for index in range(5):
        window.nav_buttons[index].click()
        assert window.stack.currentIndex() == index


def artwork_bytes(color):
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QImage, QColor
    image = QImage(320, 180, QImage.Format.Format_RGB32)
    image.fill(QColor(color))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, 'PNG')
    return bytes(buffer.data())


def test_default_dark_and_selected_poster_fallback(window):
    assert window.backdrop._artwork.isNull()
    window._select_backdrop({'poster_bytes': artwork_bytes('#ffdd00')})
    assert not window.backdrop._artwork.isNull()
    window._select_backdrop({})
    assert window.backdrop._artwork.isNull()
    window._select_backdrop({'poster_bytes': b'invalid'})
    assert window.backdrop._artwork.isNull()


def test_late_artwork_cannot_replace_current_selection(window, monkeypatch):
    monkeypatch.setattr(window.artwork_loader, 'request', Mock())
    first = {'title': 'Primo', '_kind': 'movie', 'backdrop_path': '/first.jpg',
             'poster_bytes': artwork_bytes('red')}
    second = {'title': 'Secondo', '_kind': 'movie', 'backdrop_path': '/second.jpg',
              'poster_bytes': artwork_bytes('blue')}
    window._task = lambda fn, callback, button=None: callback([first, second])
    window.query.setText('Film')
    window.search_btn.click()
    window.poster_cards[0].click()
    window.poster_cards[1].click()
    window.artwork_loader.ready.emit('/second.jpg', artwork_bytes('green'))
    current = window.backdrop._artwork.cacheKey()
    window.artwork_loader.ready.emit('/first.jpg', artwork_bytes('red'))
    assert window.backdrop._artwork.cacheKey() == current
    assert window.title_input.text() == 'Secondo'
    window.artwork_loader.ready.emit('/second.jpg', b'not an image')
    assert window.backdrop._artwork.cacheKey() == current
    window._select_backdrop({})
    window.artwork_loader.ready.emit('/second.jpg', artwork_bytes('blue'))
    assert window.backdrop._artwork.isNull()


def test_bright_artwork_stays_dark_and_resizes(window):
    from gui.design import GlassBackdrop
    surface = GlassBackdrop()
    surface.resize(800, 450)
    surface.set_artwork(artwork_bytes('white'))
    rendered = surface.grab().toImage()
    assert rendered.pixelColor(400, 10).lightness() < 160
    assert rendered.pixelColor(400, 430).lightness() < 80
    surface.resize(400, 700)
    assert surface.grab().size().height() == 700
    surface.set_artwork()
    assert surface.grab().toImage().pixelColor(200, 350).lightness() < 60
    surface.deleteLater()
