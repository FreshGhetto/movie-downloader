"""Smoked-glass surfaces and small, scalable controls for the desktop UI."""
from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QIcon, QRadialGradient, QPainterPath, QLinearGradient
from PySide6.QtWidgets import (
    QWidget, QFrame, QCheckBox, QHBoxLayout, QBoxLayout, QLabel, QComboBox,
    QGraphicsScene, QGraphicsPixmapItem, QGraphicsBlurEffect,
)

BG = '#101b24'
BG_CARD = '#202f3c'
BG_INPUT = '#243542'
BG_NAV = '#16232e'
ACCENT = '#9bc6ef'
ACCENT_H = '#c0ddf8'
GREEN = '#42c9b0'
GREEN_H = '#70ddc7'
RED = '#f19198'
YELLOW = '#e6c48a'
TEXT = '#edf4fc'
TEXT_DIM = '#a4b8cc'
BORDER = '#3b5063'


def icon(name, color=TEXT_DIM, size=24):
    """Draw a consistent set of outlined icons without external font/assets."""
    pix = QPixmap(size * 2, size * 2)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 12, size / 12)
    p.setPen(QPen(QColor(color), 1.6, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    def line(x1, y1, x2, y2):
        p.drawLine(int(x1), int(y1), int(x2), int(y2))
    if name == 'download':
        line(12, 3, 12, 15); line(7, 10, 12, 15); line(17, 10, 12, 15)
        line(4, 16, 4, 21); line(4, 21, 20, 21); line(20, 21, 20, 16)
    elif name == 'queue':
        for y in (6, 12, 18):
            p.drawEllipse(QRectF(3, y - 1, 2, 2)); line(9, y, 21, y)
    elif name == 'history':
        p.drawEllipse(QRectF(3, 3, 18, 18)); line(12, 6, 12, 12); line(12, 12, 16, 14)
    elif name == 'folder':
        path = QPainterPath()
        for i, (x, y) in enumerate([(3, 6), (9, 6), (11, 9), (21, 9), (21, 20), (3, 20), (3, 6)]):
            path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
        p.drawPath(path); line(4, 12, 20, 12)
    elif name == 'settings':
        for y, x in ((6, 8), (12, 16), (18, 10)):
            line(3, y, x - 3, y); line(x + 3, y, 21, y)
            p.drawEllipse(QRectF(x - 2.5, y - 2.5, 5, 5))
    elif name == 'search':
        p.drawEllipse(QRectF(3, 3, 12, 12)); line(14, 14, 21, 21)
    elif name == 'film':
        p.drawRoundedRect(QRectF(3, 3, 18, 18), 2, 2)
        line(7, 3, 7, 21); line(17, 3, 17, 21)
        for y in (8, 16):
            line(3, y, 7, y); line(17, y, 21, y)
    elif name == 'paste':
        p.drawRoundedRect(QRectF(5, 5, 14, 17), 2, 2)
        p.drawRoundedRect(QRectF(9, 2, 6, 5), 1, 1)
    elif name == 'link':
        p.save(); p.translate(12, 12); p.rotate(40)
        p.drawRoundedRect(QRectF(-4, -11, 8, 13), 4, 4)
        p.drawRoundedRect(QRectF(-4, -2, 8, 13), 4, 4); p.restore()
    elif name == 'plus':
        line(12, 4, 12, 20); line(4, 12, 20, 12)
    elif name == 'check':
        line(5, 12, 10, 17); line(10, 17, 20, 6)
    elif name == 'chevron':
        line(7, 9, 12, 14); line(12, 14, 17, 9)
    p.end()
    pix.setDevicePixelRatio(2)
    return QIcon(pix)


class GlassBackdrop(QWidget):
    """Stable internal backdrop; does not depend on OS transparency settings."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._artwork = QPixmap()

    def set_artwork(self, data=None):
        if not data:
            self._artwork = QPixmap()
            self.update()
            return True
        source = QPixmap()
        if not source.loadFromData(data):
            return False
        # Blur once per selection, never on every frame or during resizing.
        source = source.scaled(1280, 800, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        scene = QGraphicsScene()
        item = QGraphicsPixmapItem(source)
        effect = QGraphicsBlurEffect()
        effect.setBlurRadius(14)
        effect.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
        item.setGraphicsEffect(effect)
        scene.addItem(item)
        rendered = QPixmap(source.size())
        rendered.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rendered)
        scene.render(painter, QRectF(rendered.rect()), QRectF(source.rect()))
        painter.end()
        self._artwork = rendered
        self.update()
        return True

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(BG))
        if not self._artwork.isNull():
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            # Cover the full window without stretching either orientation.
            scale = max(self.width() / self._artwork.width(), self.height() / self._artwork.height())
            width, height = self._artwork.width() * scale, self._artwork.height() * scale
            target = QRectF((self.width() - width) / 2, (self.height() - height) / 2, width, height)
            p.drawPixmap(target, self._artwork, QRectF(self._artwork.rect()))
            veil = QLinearGradient(0, 0, 0, self.height())
            veil.setColorAt(0, QColor(9, 17, 26, 115))
            veil.setColorAt(1, QColor(9, 17, 26, 205))
            p.fillRect(self.rect(), veil)
            return
        for x, y, radius, color in ((0.12, 0.02, 0.8, '#192b3b'),
                                     (0.9, 0.8, 0.65, '#142632')):
            gradient = QRadialGradient(self.width() * x, self.height() * y,
                                       max(self.width(), self.height()) * radius)
            gradient.setColorAt(0, QColor(color))
            gradient.setColorAt(1, QColor(16, 27, 36, 0))
            p.fillRect(self.rect(), gradient)


class GlassPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('glass')


class GlassComboBox(QComboBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(TEXT_DIM), 1.5, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        x, y = self.width() - 16, self.height() // 2
        p.drawLine(x - 4, y - 2, x, y + 2)
        p.drawLine(x, y + 2, x + 4, y - 2)


class ResponsiveColumns(QWidget):
    """Stack the inspector below the content on smaller windows."""
    def __init__(self, left, right):
        super().__init__()
        self.columns = QHBoxLayout(self)
        self.columns.setContentsMargins(0, 0, 0, 0)
        self.columns.setSpacing(16)
        self.columns.addWidget(left, 2)
        self.columns.addWidget(right, 1)
        self.columns.setAlignment(Qt.AlignmentFlag.AlignTop)

    def resizeEvent(self, event):
        direction = QBoxLayout.Direction.TopToBottom if self.width() < 930 else QBoxLayout.Direction.LeftToRight
        if direction != self.columns.direction():
            self.columns.setDirection(direction)
        super().resizeEvent(event)


class ElidedLabel(QLabel):
    """Keep long movie titles from widening the whole window."""
    def minimumSizeHint(self):
        return QSize(0, super().minimumSizeHint().height())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setFont(self.font())
        p.setPen(self.palette().windowText().color())
        text = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, self.width())
        p.drawText(self.rect(), self.alignment() | Qt.AlignmentFlag.AlignVCenter, text)


class Toggle(QCheckBox):
    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.setAccessibleName(label)
        self.setToolTip(label)
        self.setFixedSize(44, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(ACCENT if self.hasFocus() else BORDER), 1))
        p.setBrush(QColor('#719bc2' if self.isChecked() else BG_INPUT))
        p.drawRoundedRect(QRectF(1, 2, 42, 22), 11, 11)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(TEXT if self.isEnabled() else TEXT_DIM))
        p.drawEllipse(QRectF(23 if self.isChecked() else 5, 5, 16, 16))


STYLE = f'''
* {{ font-family: "Segoe UI", sans-serif; font-size: 13px; color: {TEXT}; }}
QMainWindow {{ background: {BG}; }}
QWidget#page, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}
QFrame#glass, QWidget#sidebar {{
    background: qlineargradient(x1:0,y1:0,x2:0.8,y2:1,stop:0 rgba(51,70,86,185),stop:1 rgba(23,36,47,218));
    border: 1px solid rgba(147,183,213,34); border-radius: 22px;
}}
QPushButton#nav {{ background: transparent; border: 1px solid transparent; text-align: left;
    padding: 13px 14px; border-radius: 16px; color: {TEXT_DIM}; font-weight: 500; }}
QPushButton#nav:hover {{ background: rgba(126,162,193,18); color: {TEXT}; }}
QPushButton#nav:checked {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #3a536a,stop:1 #293f52);
    color: {TEXT}; border: 1px solid rgba(160,198,230,40); }}
QLabel {{ background: transparent; border: none; }}
QLabel#page_title {{ font-size: 30px; font-weight: 700; }}
QLabel#section {{ font-size: 16px; font-weight: 600; }}
QLabel#hint {{ color: {TEXT_DIM}; font-size: 12px; }}
QLabel#status_bar {{ color: {TEXT_DIM}; font-size: 11px; padding: 7px 22px; }}
QLabel#empty {{ color: {TEXT_DIM}; font-size: 13px; padding: 24px; }}
QLabel#version {{ color: {TEXT_DIM}; font-size: 11px; padding: 8px 12px; }}
QLabel#logo {{ font-size: 15px; font-weight: 700; }}
QLineEdit, QComboBox {{ background: rgba(33,49,63,170); border: 1px solid {BORDER};
    border-radius: 11px; padding: 10px 12px; selection-background-color: #496e90; min-height: 18px; }}
QLineEdit:focus, QComboBox:focus {{ border-color: {ACCENT}; background: #293e50; }}
QLineEdit:disabled, QComboBox:disabled {{ color: #758a9d; background: rgba(22,34,44,150); }}
QComboBox {{ padding-right: 26px; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ image: none; }}
QComboBox QAbstractItemView {{ background: {BG_CARD}; border: 1px solid {BORDER};
    selection-background-color: #3d5b75; color: {TEXT}; padding: 6px; outline: 0; }}
QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:0.7,y2:1,stop:0 #304557,stop:1 #243543);
    border: 1px solid {BORDER}; border-radius: 12px; padding: 10px 16px; font-weight: 500; }}
QPushButton:hover {{ background: #3b5369; border-color: #63839e; }}
QPushButton:pressed {{ background: #23394b; }}
QPushButton:focus {{ border-color: {ACCENT}; }}
QPushButton:disabled {{ color: #768b9d; background: #202f3b; border-color: #344657; }}
QPushButton#primary {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #b0d6f7,stop:1 #83b0d9);
    color: #102337; border: 1px solid #bddaf2; font-weight: 700; border-radius: 14px; }}
QPushButton#primary:hover {{ background: {ACCENT_H}; }}
QPushButton#primary:pressed {{ background: #7aa6ce; }}
QPushButton#accent {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #6386a5,stop:1 #405f7b);
    border: 1px solid #7a9ab6; font-weight: 600; }}
QPushButton#accent:hover {{ background: #6486a5; }}
QPushButton#accent:disabled, QPushButton#primary:disabled {{ background: #304353; color: #91a7bb; border-color: #455d71; }}
QPushButton#danger {{ color: {RED}; }}
QPushButton#danger:hover {{ background: #5a3741; border-color: {RED}; }}
QPushButton#small {{ padding: 6px 12px; font-size: 12px; }}
QPushButton#chip {{ border-radius: 12px; padding: 7px 12px; color: {TEXT_DIM}; }}
QPushButton#chip:checked {{ background: #36536d; border-color: #85b2da; color: {TEXT}; }}
QPushButton#disclosure {{ background: transparent; border: none; text-align: left; padding: 10px 0; color: {TEXT_DIM}; }}
QPushButton#disclosure:focus {{ color: {TEXT}; }}
QFrame#summary {{ background: rgba(17,30,40,85); border: 1px solid rgba(147,183,213,25); border-radius: 16px; }}
QListWidget, QTextEdit, QTableWidget {{ background: rgba(30,45,58,210); border: 1px solid {BORDER};
    border-radius: 14px; padding: 8px; outline: none; }}
QListWidget::item {{ padding: 8px; border-radius: 8px; }}
QListWidget::item:selected, QTableWidget::item:selected {{ background: #3b5c78; }}
QTableWidget {{ gridline-color: {BORDER}; }}
QTableWidget::item {{ padding: 8px; border-bottom: 1px solid {BORDER}; }}
QHeaderView::section {{ background: {BG_INPUT}; border: none; padding: 12px; color: {TEXT_DIM}; font-weight: 600; }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 4px 0; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 0 4px; }}
QScrollBar::handle {{ background: #526d84; border-radius: 4px; min-height: 28px; min-width: 28px; }}
QScrollBar::handle:hover {{ background: #819fb8; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid {BORDER}; border-radius: 5px; background: {BG_INPUT}; }}
QCheckBox::indicator:checked {{ background: #709bc1; border: 3px solid #bad8f3; }}
QProgressBar {{ background: {BG_INPUT}; border: none; border-radius: 4px; text-align: center; }}
QProgressBar::chunk {{ background: #93bde3; border-radius: 4px; }}
QFrame#card {{ background: rgba(39,58,74,190); border: 1px solid {BORDER}; border-radius: 16px; }}
QFrame#card_active {{ background: rgba(47,71,90,210); border: 1px solid {ACCENT}; border-radius: 16px; }}
QFrame#separator {{ background: rgba(145,177,203,40); border: none; max-height: 1px; }}
QToolTip, QMenu {{ color: {TEXT}; background: {BG_CARD}; border: 1px solid {BORDER}; padding: 6px; }}
QMenu::item:selected {{ background: #3a5770; }}
QDialog, QMessageBox {{ background: {BG}; }}
'''
