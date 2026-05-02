import math
import sys

from PyQt5.QtCore import Qt, QRectF, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QApplication, QWidget


# --- Layout constants ----------------------------------------------------
WIN_WIDTH = 200
WIN_HEIGHT = 38
BAR_COUNT = 9
BAR_WIDTH = 3
BAR_GAP = 5
BAR_RADIUS = 1.5
BAR_MIN_HEIGHT = 4
BAR_MAX_HEIGHT = 24
DOT_RADIUS = 3
DOT_SPACING = 14
DOT_BOUNCE = 5
SCREEN_BOTTOM_OFFSET = 60

# --- Visual style --------------------------------------------------------
BG_COLOR = QColor(20, 20, 22, 235)
BG_BORDER = QColor(255, 255, 255, 28)
ACCENT = QColor(255, 255, 255, 235)


class StatusWindow(QWidget):
    """A slim, pill-shaped overlay that visualises microphone activity.

    Modes:
        recording     -> live waveform driven by ``audioLevelSignal``
        transcribing  -> three bouncing dots
        idle/error/cancel -> hidden
    """

    statusSignal = pyqtSignal(str)
    audioLevelSignal = pyqtSignal(float)  # 0..1
    closeSignal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setFixedSize(WIN_WIDTH, WIN_HEIGHT)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowTitle('AsklaionTyper')

        self._state = 'idle'
        self._bar_targets = [0.0] * BAR_COUNT
        self._bar_currents = [0.0] * BAR_COUNT
        self._dot_phase = 0.0
        self._drag_origin = None

        self.statusSignal.connect(self.updateStatus)
        self.audioLevelSignal.connect(self.setAudioLevel)

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(16)  # ~60 fps
        self._tick_timer.timeout.connect(self._tick)

    # --- Public API ------------------------------------------------------

    def show(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = screen.height() - self.height() - SCREEN_BOTTOM_OFFSET
        self.move(x, y)
        super().show()

    def closeEvent(self, event):
        self.closeSignal.emit()
        super().closeEvent(event)

    @pyqtSlot(str)
    def updateStatus(self, status):
        self._state = status
        if status == 'recording':
            self._bar_targets = [0.0] * BAR_COUNT
            self._bar_currents = [0.0] * BAR_COUNT
            if not self._tick_timer.isActive():
                self._tick_timer.start()
            self.show()
        elif status == 'transcribing':
            self._dot_phase = 0.0
            if not self._tick_timer.isActive():
                self._tick_timer.start()
            if not self.isVisible():
                self.show()
        elif status in ('idle', 'error', 'cancel'):
            self._tick_timer.stop()
            self.hide()

    @pyqtSlot(float)
    def setAudioLevel(self, level):
        """Inject a fresh RMS level (0..1). Pushes a Gaussian-ish wave around
        the centre of the bar strip so the animation looks like a ripple."""
        level = max(0.0, min(1.0, float(level)))
        center = (BAR_COUNT - 1) / 2.0
        for i in range(BAR_COUNT):
            dist = abs(i - center)
            falloff = math.exp(-(dist * dist) / 4.5)
            target = level * falloff
            if target > self._bar_targets[i]:
                self._bar_targets[i] = target

    # --- Animation -------------------------------------------------------

    def _tick(self):
        for i in range(BAR_COUNT):
            self._bar_targets[i] *= 0.90  # decay so bars fall back to rest
            self._bar_currents[i] += (self._bar_targets[i] - self._bar_currents[i]) * 0.35
        self._dot_phase += 0.18
        self.update()

    # --- Painting --------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Pill-shaped background
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        path = QPainterPath()
        path.addRoundedRect(rect, self.height() / 2, self.height() / 2)
        painter.setPen(QPen(BG_BORDER, 1))
        painter.setBrush(QBrush(BG_COLOR))
        painter.drawPath(path)

        cx = self.width() / 2.0
        cy = self.height() / 2.0

        if self._state == 'transcribing':
            self._paint_dots(painter, cx, cy)
        else:
            # recording (default visual when active)
            self._paint_bars(painter, cx, cy)

    def _paint_bars(self, painter, cx, cy):
        total_w = BAR_COUNT * BAR_WIDTH + (BAR_COUNT - 1) * BAR_GAP
        x0 = cx - total_w / 2.0
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(ACCENT))
        for i, val in enumerate(self._bar_currents):
            h = BAR_MIN_HEIGHT + val * (BAR_MAX_HEIGHT - BAR_MIN_HEIGHT)
            x = x0 + i * (BAR_WIDTH + BAR_GAP)
            y = cy - h / 2.0
            painter.drawRoundedRect(QRectF(x, y, BAR_WIDTH, h), BAR_RADIUS, BAR_RADIUS)

    def _paint_dots(self, painter, cx, cy):
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(ACCENT))
        for i in range(3):
            phase = self._dot_phase + i * 0.55
            yoff = math.sin(phase) * DOT_BOUNCE
            x = cx + (i - 1) * DOT_SPACING
            painter.drawEllipse(
                QRectF(x - DOT_RADIUS, cy + yoff - DOT_RADIUS,
                       DOT_RADIUS * 2, DOT_RADIUS * 2)
            )

    # --- Drag to reposition ---------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_origin = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._drag_origin is not None:
            self.move(event.globalPos() - self._drag_origin)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_origin = None
        event.accept()


if __name__ == '__main__':
    import random

    app = QApplication(sys.argv)
    win = StatusWindow()
    win.statusSignal.emit('recording')

    feed = QTimer()
    feed.setInterval(60)
    feed.timeout.connect(lambda: win.audioLevelSignal.emit(
        max(0.0, min(1.0, random.gauss(0.45, 0.25)))
    ))
    feed.start()

    QTimer.singleShot(5000, lambda: win.statusSignal.emit('transcribing'))
    QTimer.singleShot(8000, lambda: win.statusSignal.emit('idle'))
    QTimer.singleShot(8500, app.quit)

    sys.exit(app.exec_())
