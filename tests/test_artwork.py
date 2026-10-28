from PySide6.QtCore import QObject, Signal, QByteArray
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtGui import QImage, QColor
from PySide6.QtCore import QBuffer, QIODevice
from gui.artwork import ArtworkLoader


class Reply(QObject):
    finished = Signal()
    downloadProgress = Signal(int, int)

    def __init__(self):
        super().__init__()
        self.content = b''
        self.failure = QNetworkReply.NetworkError.NoError

    def abort(self):
        self.failure = QNetworkReply.NetworkError.OperationCanceledError
        self.finished.emit()

    def error(self):
        return self.failure

    def readAll(self):
        return QByteArray(self.content)


class Network:
    def __init__(self):
        self.requests = []

    def get(self, request):
        reply = Reply()
        self.requests.append((request, reply))
        return reply


def png():
    image = QImage(16, 9, QImage.Format.Format_RGB32)
    image.fill(QColor('blue'))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, 'PNG')
    return bytes(buffer.data())


def test_cancel_previous_download_and_reuse_cached_artwork():
    # QApplication is needed later by the GUI tests in this same process.
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    loader = ArtworkLoader()
    loader.network = Network()
    ready = []
    loader.ready.connect(lambda path, data: ready.append((path, data)))
    loader.request('/first.jpg')
    first = loader.network.requests[0][1]
    loader.request('/second.jpg')
    assert first.failure == QNetworkReply.NetworkError.OperationCanceledError
    assert ready == []
    request, second = loader.network.requests[1]
    assert request.url().toString() == 'https://image.tmdb.org/t/p/w1280/second.jpg'
    assert request.transferTimeout() == 8000
    second.content = png()
    second.finished.emit()
    assert ready == [('/second.jpg', second.content)]
    loader.request('/second.jpg')
    assert len(loader.network.requests) == 2
    assert ready[-1] == ('/second.jpg', second.content)
    loader.deleteLater()


def test_unavailable_invalid_and_oversized_artwork_fail_quietly():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    loader = ArtworkLoader()
    loader.network = Network()
    ready = []
    loader.ready.connect(lambda *args: ready.append(args))
    for path in (None, '', 'https://example.org/image.jpg', '/../image.jpg'):
        loader.request(path)
    assert loader.network.requests == []
    loader.request('/invalid.jpg')
    reply = loader.network.requests[-1][1]
    reply.content = b'<html>Error</html>'
    reply.finished.emit()
    loader.request('/missing.jpg')
    reply = loader.network.requests[-1][1]
    reply.failure = QNetworkReply.NetworkError.ContentNotFoundError
    reply.finished.emit()
    loader.request('/huge.jpg')
    reply = loader.network.requests[-1][1]
    reply.downloadProgress.emit(loader.MAX_BYTES + 1, loader.MAX_BYTES + 1)
    assert reply.failure == QNetworkReply.NetworkError.OperationCanceledError
    assert ready == []
    assert not loader.cache
    loader.deleteLater()
