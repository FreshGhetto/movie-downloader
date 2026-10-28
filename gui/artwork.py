"""Asynchronous TMDb artwork, independent of the download queue."""
import re
from collections import OrderedDict

from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtGui import QImage
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply


class ArtworkLoader(QObject):
    ready = Signal(str, bytes)
    IMAGE_BASE = 'https://image.tmdb.org/t/p/w1280'
    MAX_BYTES = 6 * 1024 * 1024

    def __init__(self, parent=None):
        super().__init__(parent)
        self.network = QNetworkAccessManager(self)
        self.pending = None
        self.cache = OrderedDict()

    def cancel(self):
        reply, self.pending = self.pending, None
        if reply is not None:
            reply.abort()

    def request(self, path):
        self.cancel()
        # Only image filenames from TMDb results, never arbitrary URLs.
        if not isinstance(path, str) or not re.fullmatch(r'/[\w-]+\.(?:jpg|png|webp)', path, re.ASCII):
            return
        if path in self.cache:
            self.cache.move_to_end(path)
            self.ready.emit(path, self.cache[path])
            return
        request = QNetworkRequest(QUrl(self.IMAGE_BASE + path))
        request.setTransferTimeout(8000)
        reply = self.network.get(request)
        self.pending = reply
        reply.downloadProgress.connect(
            lambda received, total: reply.abort() if max(received, total) > self.MAX_BYTES else None)
        reply.finished.connect(lambda: self._finished(reply, path))

    def _finished(self, reply, path):
        try:
            if reply is not self.pending:
                return
            self.pending = None
            if reply.error() != QNetworkReply.NetworkError.NoError:
                return
            data = bytes(reply.readAll())
            if not data or len(data) > self.MAX_BYTES or QImage.fromData(data).isNull():
                return
            self.cache[path] = data
            while len(self.cache) > 8:
                self.cache.popitem(last=False)
            self.ready.emit(path, data)
        finally:
            reply.deleteLater()
