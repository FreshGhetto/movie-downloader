"""Smoked-glass surfaces and small, scalable controls for the desktop UI."""
from PySide6.QtCore import Qt, QRectF, QSize, QPoint, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QIcon, QRadialGradient, QPainterPath, QLinearGradient
from PySide6.QtWidgets import (
    QWidget, QFrame, QCheckBox, QHBoxLayout, QBoxLayout, QLabel, QComboBox,
    QGraphicsScene, QGraphicsPixmapItem, QGraphicsBlurEffect,
)

BG = '#151515'
BG_CARD = '#292929'
BG_INPUT = '#303030'
BG_NAV = '#202020'
ACCENT = '#dedede'
ACCENT_H = '#f1f1f1'
GREEN = '#42c9b0'
GREEN_H = '#70ddc7'
RED = '#f19198'
YELLOW = '#e6c48a'
TEXT = '#f3f3f3'
TEXT_DIM = '#bcbcbc'
BORDER = 'rgba(255,255,255,40)'


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
    """Cached clear/blurred background pairs with an interruptible crossfade."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._artwork = QPixmap()
        self._blurred = QPixmap()
        self._artwork_key = None
        self._previous = None
        self._target = None
        self._scene = None
        self._progress = 1.0
        self.transition = QVariantAnimation(self)
        self.transition.setDuration(800)
        self.transition.setStartValue(0.0)
        self.transition.setEndValue(1.0)
        self.transition.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.transition.valueChanged.connect(self._advance)
        self.transition.finished.connect(self._finish_transition)

    @staticmethod
    def _blur(source):
        scene = QGraphicsScene()
        item = QGraphicsPixmapItem(source)
        effect = QGraphicsBlurEffect()
        effect.setBlurRadius(32)
        effect.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
        item.setGraphicsEffect(effect)
        scene.addItem(item)
        rendered = QPixmap(source.size())
        rendered.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rendered)
        scene.render(painter, QRectF(rendered.rect()), QRectF(source.rect()))
        painter.end()
        return rendered

    def set_artwork(self, data=None, *, animate=True):
        key = hash(data) if data else None
        if key == self._artwork_key:
            return True
        source = QPixmap()
        if data and not source.loadFromData(data):
            return False
        if not source.isNull():
            source = source.scaled(1280, 800, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
        previous = self._snapshot()
        self.transition.stop()
        self._artwork_key = key
        self._artwork = source
        self._blurred = self._blur(source) if not source.isNull() else QPixmap()
        self._target = self._render_pair()
        if previous is None or not animate or self.width() == 0:
            self._previous = None
            self._scene = self._target
            self._progress = 1.0
            self.update()
            for panel in self.findChildren(GlassPanel):
                panel.update()
        else:
            self._previous = self._ensure_size(previous)
            self._progress = 0.0
            self._scene = self._previous
            self.transition.start()
        return True

    def _render_layer(self, image):
        result = QPixmap(self.size())
        result.fill(QColor(BG))
        p = QPainter(result)
        if image.isNull():
            gradient = QRadialGradient(self.width() * .18, 0, max(self.width(), self.height()))
            gradient.setColorAt(0, QColor('#292929'))
            gradient.setColorAt(1, QColor(BG))
            p.fillRect(self.rect(), gradient)
        else:
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            scale = max(self.width() / image.width(), self.height() / image.height())
            width, height = image.width() * scale, image.height() * scale
            target = QRectF((self.width() - width) / 2, (self.height() - height) / 2, width, height)
            p.drawPixmap(target, image, QRectF(image.rect()))
            veil = QLinearGradient(0, 0, 0, self.height())
            veil.setColorAt(0, QColor(0, 0, 0, 120))
            veil.setColorAt(1, QColor(0, 0, 0, 200))
            p.fillRect(self.rect(), veil)
        p.end()
        return result

    def _render_pair(self):
        return self._render_layer(self._artwork), self._render_layer(self._blurred)

    def _snapshot(self):
        if self._scene is not None and self._scene[0].width() > 0:
            return self._scene
        if self.width() > 0:
            return self._render_pair()
        return None

    def _ensure_size(self, pair):
        w, h = self.width(), self.height()
        if pair[0].size() == QSize(w, h):
            return pair
        return tuple(
            f.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                     Qt.TransformationMode.SmoothTransformation)
            for f in pair
        )

    def frame_pair(self):
        if self._scene is None:
            self._scene = self._render_pair()
        return self._scene

    def _advance(self, value):
        self._progress = float(value)
        if self._target is None:
            return
        if value >= 1 or self._previous is None:
            self._scene = self._target
        elif value <= 0:
            self._scene = self._previous
        else:
            frames = []
            for old, new in zip(self._previous, self._target):
                frame = QPixmap(new.size())
                frame.fill(QColor(BG))
                painter = QPainter(frame)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                painter.setOpacity(1.0 - value)
                painter.drawPixmap(QRectF(frame.rect()), old, QRectF(old.rect()))
                painter.setOpacity(value)
                painter.drawPixmap(0, 0, new)
                painter.end()
                frames.append(frame)
            self._scene = tuple(frames)
        self.update()
        for panel in self.findChildren(GlassPanel):
            panel.update()

    def _finish_transition(self):
        self._scene = self._target
        self._previous = None
        self._progress = 1.0
        self.update()
        for panel in self.findChildren(GlassPanel):
            panel.update()

    def resizeEvent(self, event):
        if self._previous:
            self._previous = self._ensure_size(self._previous)
        self._target = self._render_pair()
        if self._scene is not None:
            self._advance(self._progress)
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.frame_pair()[0])


class GlassPanel(QFrame):
    """Frost the matching background region; never blur foreground controls."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('glass')

    def paintEvent(self, event):
        backdrop = self.parentWidget()
        while backdrop is not None and not isinstance(backdrop, GlassBackdrop):
            backdrop = backdrop.parentWidget()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        outline = QPainterPath()
        outline.addRoundedRect(rect, 22, 22)
        painter.setClipPath(outline)
        if backdrop is not None:
            offset = self.mapTo(backdrop, QPoint(0, 0))
            source = QRectF(offset.x(), offset.y(), self.width(), self.height())
            painter.drawPixmap(QRectF(self.rect()), backdrop.frame_pair()[1], source)
        else:
            painter.fillRect(self.rect(), QColor(BG_CARD))
        painter.setClipping(False)


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
        p.setPen(QPen(QColor(ACCENT) if self.hasFocus() else QColor(255, 255, 255, 40), 1))
        p.setBrush(QColor('#808080' if self.isChecked() else BG_INPUT))
        p.drawRoundedRect(QRectF(1, 2, 42, 22), 11, 11)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(TEXT if self.isEnabled() else TEXT_DIM))
        p.drawEllipse(QRectF(23 if self.isChecked() else 5, 5, 16, 16))


STYLE = f'''
* {{ font-family: "Segoe UI", sans-serif; font-size: 13px; color: {TEXT}; }}
QMainWindow {{ background: {BG}; }}
QWidget#page, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}
QFrame#glass, QWidget#sidebar {{
    background: transparent; border: none; border-radius: 22px;
}}
QPushButton#nav {{ background: transparent; border: none; text-align: left;
    padding: 13px 14px; border-radius: 16px; color: {TEXT_DIM}; font-weight: 500; }}
QPushButton#nav:hover {{ background: rgba(255,255,255,15); color: {TEXT}; }}
QPushButton#nav:checked {{ background: rgba(255,255,255,25); color: {TEXT}; }}
QLabel {{ background: transparent; border: none; }}
QLabel#page_title {{ font-size: 30px; font-weight: 700; }}
QLabel#section {{ font-size: 16px; font-weight: 600; }}
QLabel#hint {{ color: {TEXT_DIM}; font-size: 12px; }}
QLabel#status_bar {{ color: {TEXT_DIM}; font-size: 11px; padding: 7px 22px; }}
QLabel#empty {{ color: {TEXT_DIM}; font-size: 13px; padding: 24px; }}
QLabel#version {{ color: {TEXT_DIM}; font-size: 11px; padding: 8px 12px; }}
QLabel#logo {{ font-size: 15px; font-weight: 700; }}
QLineEdit, QComboBox {{ background: rgba(0,0,0,38); border: 1px solid transparent;
    border-radius: 11px; padding: 10px 12px; selection-background-color: #666666; min-height: 18px; }}
QLineEdit:focus, QComboBox:focus {{ border-color: rgba(255,255,255,40); background: rgba(255,255,255,16); }}
QLineEdit:disabled, QComboBox:disabled {{ color: #858585; background: rgba(0,0,0,28); }}
QComboBox {{ padding-right: 26px; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ image: none; }}
QComboBox QAbstractItemView {{ background: {BG_CARD}; border: 1px solid {BORDER};
    selection-background-color: #555555; color: {TEXT}; padding: 6px; outline: 0; }}
QPushButton {{ background: rgba(255,255,255,20);
    border: none; border-radius: 12px; padding: 10px 16px; font-weight: 500; }}
QPushButton:hover {{ background: rgba(255,255,255,36); }}
QPushButton:pressed {{ background: rgba(0,0,0,48); }}
QPushButton:disabled {{ color: #888888; background: rgba(255,255,255,8); }}
QPushButton#primary {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #e3e3e3,stop:1 #c7c7c7);
    color: #171717; border: none; font-weight: 700; border-radius: 14px; }}
QPushButton#primary:hover {{ background: {ACCENT_H}; }}
QPushButton#primary:pressed {{ background: #bbbbbb; }}
QPushButton#accent {{ background: rgba(255,255,255,30); border: none; font-weight: 600; }}
QPushButton#accent:hover {{ background: rgba(255,255,255,46); }}
QPushButton#accent:disabled, QPushButton#primary:disabled {{ background: rgba(255,255,255,10); color: #999999; }}
QPushButton#danger {{ color: {RED}; }}
QPushButton#danger:hover {{ background: #5a3741; }}
QPushButton#small {{ padding: 6px 12px; font-size: 12px; }}
QPushButton#chip {{ border-radius: 12px; padding: 7px 12px; color: {TEXT_DIM}; }}
QPushButton#chip:checked {{ background: rgba(255,255,255,25); color: {TEXT}; }}
QPushButton#disclosure {{ background: transparent; border: none; text-align: left; padding: 10px 0; color: {TEXT_DIM}; }}
QPushButton#disclosure:focus {{ color: {TEXT}; }}
QFrame#summary {{ background: rgba(0,0,0,24); border: none; border-radius: 16px; }}
QListWidget, QTextEdit, QTableWidget {{ background: rgba(0,0,0,45); border: none;
    border-radius: 14px; padding: 8px; outline: none; }}
QListWidget::item {{ padding: 8px; border-radius: 8px; }}
QListWidget::item:selected, QTableWidget::item:selected {{ background: #555555; }}
QTableWidget {{ gridline-color: {BORDER}; }}
QTableWidget::item {{ padding: 8px; border-bottom: 1px solid {BORDER}; }}
QHeaderView::section {{ background: {BG_INPUT}; border: none; padding: 12px; color: {TEXT_DIM}; font-weight: 600; }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 4px 0; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 0 4px; }}
QScrollBar::handle {{ background: #666666; border-radius: 4px; min-height: 28px; min-width: 28px; }}
QScrollBar::handle:hover {{ background: #999999; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid {BORDER}; border-radius: 5px; background: {BG_INPUT}; }}
QCheckBox::indicator:checked {{ background: #777777; border: 3px solid #dddddd; }}
QProgressBar {{ background: {BG_INPUT}; border: none; border-radius: 4px; text-align: center; }}
QProgressBar::chunk {{ background: #cccccc; border-radius: 4px; }}
QFrame#card {{ background: rgba(255,255,255,15); border: none; border-radius: 16px; }}
QFrame#card_active {{ background: rgba(255,255,255,25); border: none; border-radius: 16px; }}
QFrame#separator {{ background: rgba(255,255,255,30); border: none; max-height: 1px; }}
QToolTip, QMenu {{ color: {TEXT}; background: {BG_CARD}; border: 1px solid {BORDER}; padding: 6px; }}
QMenu::item:selected {{ background: #505050; }}
QDialog, QMessageBox {{ background: {BG}; }}
'''
