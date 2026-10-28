from PySide6.QtWidgets import QApplication
from gui.window import Window

def test_default_fragments_and_catalog_selection(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = Window()
    assert window.fragments.currentText() == '16'
    window.url.setText('https://example.org/authorized.mp4')
    window.query.setText('Film')
    monkeypatch.setattr(window, 'task', lambda fn, callback, button=None: callback([
        {'title':'Titolo italiano','release_date':'2024-04-01','overview':'Sinossi di prova'},
        {'title':'Secondo risultato','release_date':'2023-01-01','overview':'Seconda sinossi'},
    ]))
    window.search()
    assert window.results.count() == 2
    window.results.setCurrentRow(0)
    assert window.title.text() == 'Titolo italiano'
    assert window.year.text() == '2024'
    assert window.synopsis.toPlainText() == 'Sinossi di prova'
    window.results.setCurrentRow(1)
    assert window.title.text() == 'Secondo risultato'
    assert window.url.text() == 'https://example.org/authorized.mp4'
    window.deleteLater()
