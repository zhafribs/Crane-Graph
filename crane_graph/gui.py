"""PyQt5 GUI for Crane Graph - dynamic working range diagram.

Left panel: all inputs (boom length, boom + jib, boom + extended jib,
crane XY location, angles). Right: interactive graph where the boom tip
and the crane marker can be dragged; every change flows both ways.
"""

import math
import os
import sys

from PyQt5.QtCore import Qt, QPointF, QRectF, QTimer, pyqtSignal
from PyQt5.QtGui import (
    QColor, QFont, QFontMetricsF, QIcon, QPainter, QPainterPath,
    QPen, QPolygonF,
)
from PyQt5.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QDoubleSpinBox,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QRadioButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from . import geometry as geo
from .theme import STYLE


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _label(text="", bold=False, color=None, size=None, align=None):
    lbl = QLabel(text)
    f = lbl.font()
    f.setBold(bold)
    if size:
        f.setPointSize(size)
    lbl.setFont(f)
    if color:
        lbl.setStyleSheet(f"color: {color}; background: transparent;")
    if align is not None:
        lbl.setAlignment(align)
    return lbl


def _dspin(value=0.0, lo=0.0, hi=1.0e9, dec=1, suffix="", step=1.0, w=None):
    box = QDoubleSpinBox()
    box.setRange(lo, hi)
    box.setDecimals(dec)
    box.setValue(value)
    box.setSingleStep(step)
    box.setKeyboardTracking(False)
    if suffix:
        box.setSuffix(" " + suffix)
    if w:
        box.setFixedWidth(w)
    return box


class KeyValuePanel(QGroupBox):
    """Label/value grid used for the readout panel."""

    def __init__(self, title):
        super().__init__(title)
        self._grid = QGridLayout(self)
        self._grid.setHorizontalSpacing(16)
        self._grid.setVerticalSpacing(6)
        self._labels = []
        self._values = []

    def set_rows(self, rows):
        for i, row in enumerate(rows):
            desc = row[0]
            value = str(row[1])
            color = row[2] if len(row) > 2 else None
            if i >= len(self._labels):
                d = _label(desc)
                v = _label(value, bold=True, align=Qt.AlignRight)
                self._grid.addWidget(d, i, 0)
                self._grid.addWidget(v, i, 1)
                self._labels.append(d)
                self._values.append(v)
                self._grid.setColumnStretch(1, 1)
            else:
                self._labels[i].setText(desc)
                self._values[i].setText(value)
            self._values[i].setStyleSheet(
                f"color: {color}; background: transparent;" if color
                else "background: transparent;")
        for j in range(len(self._labels) - 1, len(rows) - 1, -1):
            self._labels[j].hide()
            self._values[j].hide()
        for j in range(len(rows)):
            self._labels[j].show()
            self._values[j].show()


# ---------------------------------------------------------------------------
# Colour palette for the graph
# ---------------------------------------------------------------------------

COL_BG = "#141922"
COL_GRID = "#1f2735"
COL_AXIS = "#5f7191"
COL_AXIS_TEXT = "#7d8ba3"
COL_ENVELOPE_FILL = QColor(92, 179, 255, 26)
COL_ENVELOPE_STROKE = QColor(92, 179, 255, 175)
COL_ENVELOPE_EDGE = QColor(92, 179, 255, 90)
COL_BOOM_ARC = QColor(143, 183, 255, 85)
COL_BOOM = "#ffb703"
COL_JIB = "#5cb3ff"
COL_JOINT = "#e8eaf0"
COL_DIM_R = QColor(255, 183, 3, 170)
COL_DIM_H = QColor(143, 183, 255, 170)
COL_ANGLE = QColor(223, 230, 240, 150)
COL_HANDLE_HOVER = "#ffffff"
COL_PILL_BG = QColor(16, 21, 30, 225)
COL_TEXT = "#dfe6f0"


class GraphCanvas(QWidget):
    """Interactive working-range diagram.

    Mouse model:
      * drag the boom tip handle  -> sets the boom angle
      * drag the crane marker     -> sets the crane (X, Y) location
      * drag empty space          -> pans the view
      * mouse wheel               -> zooms about the cursor
      * double-click              -> fits the view
    """

    angleChanged = pyqtSignal(float)
    craneMoved = pyqtSignal(float, float)
    interactionEnded = pyqtSignal()

    TIP_HIT_R = 14
    CRANE_HIT_R = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = dict(geo.DEFAULT_STATE)
        self._scale = 12.0          # pixels per metre
        self._view_cx = 0.0         # world X shown at widget centre
        self._view_cy = 15.0        # world Y shown at widget centre
        self._drag = None           # None | "tip" | "crane" | "pan"
        self._last_mouse = None
        self._hover = None          # None | "tip" | "crane"
        self._show_dims = True
        self.setMinimumSize(480, 380)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)

    # -- state -------------------------------------------------------------

    def set_state(self, state):
        self._state = dict(state)
        self.update()

    def state(self):
        return dict(self._state)

    def set_show_dims(self, on):
        self._show_dims = bool(on)
        self.update()

    def is_dragging(self):
        return self._drag is not None

    # -- view transform ----------------------------------------------------

    def world_to_screen(self, x, y):
        return ((x - self._view_cx) * self._scale + self.width() / 2.0,
                self.height() / 2.0 - (y - self._view_cy) * self._scale)

    def screen_to_world(self, sx, sy):
        return ((sx - self.width() / 2.0) / self._scale + self._view_cx,
                (self.height() / 2.0 - sy) / self._scale + self._view_cy)

    def fit_view(self):
        if self.width() <= 0 or self.height() <= 0:
            return
        st = self._state
        pivot = (st["crane_x"], st["crane_y"])
        jib = geo.effective_jib_length(st["config"], st["jib_length"],
                                       st["ext_jib_length"])
        radius = geo.envelope_radius(st["boom_length"], jib, st["jib_offset"])
        pts = list(geo.envelope_points(pivot, radius,
                                       st["env_min"], st["env_max"]))
        pts.append(pivot)
        pts.append((pivot[0], 0.0))                     # ground under crane
        pts.append((pivot[0] + radius, pivot[1]))       # farthest reach
        pts.append(geo.tip_for_state(st))               # current tip
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        pad = 0.10 * max(x1 - x0, y1 - y0, 1.0) + 1.5
        x0, x1 = x0 - pad, x1 + pad
        y0, y1 = y0 - pad, y1 + pad
        scale = min(self.width() / (x1 - x0), self.height() / (y1 - y0))
        self._scale = geo.clamp(scale, 0.02, 2000.0)
        self._view_cx = (x0 + x1) / 2.0
        self._view_cy = (y0 + y1) / 2.0
        self.update()

    # -- geometry helpers ---------------------------------------------------

    def _pivot_screen(self):
        st = self._state
        return self.world_to_screen(st["crane_x"], st["crane_y"])

    def _tip_screen(self):
        return self.world_to_screen(*geo.tip_for_state(self._state))

    def _hit(self, kind, pos):
        sx, sy = self._tip_screen() if kind == "tip" else self._pivot_screen()
        r = self.TIP_HIT_R if kind == "tip" else self.CRANE_HIT_R
        dx, dy = pos.x() - sx, pos.y() - sy
        return dx * dx + dy * dy <= r * r

    # -- mouse interaction --------------------------------------------------

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        pos = e.pos()
        if self._hit("tip", pos):
            self._drag = "tip"
            self._emit_tip(pos)
        elif self._hit("crane", pos):
            self._drag = "crane"
            self._emit_crane(pos)
        else:
            self._drag = "pan"
            self._last_mouse = pos
        self.setCursor(Qt.ClosedHandCursor if self._drag != "pan"
                       else Qt.OpenHandCursor)

    def mouseMoveEvent(self, e):
        pos = e.pos()
        if self._drag == "tip":
            self._emit_tip(pos)
        elif self._drag == "crane":
            self._emit_crane(pos)
        elif self._drag == "pan":
            dx = pos.x() - self._last_mouse.x()
            dy = pos.y() - self._last_mouse.y()
            self._view_cx -= dx / self._scale
            self._view_cy += dy / self._scale
            self._last_mouse = pos
            self.update()
        else:
            self._update_hover(pos)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        if self._drag in ("tip", "crane"):
            self.interactionEnded.emit()
        self._drag = None
        self._update_hover(e.pos())

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton and self._drag is None:
            self.fit_view()
            e.accept()

    def mouseLeaveEvent(self, e):
        if self._hover is not None:
            self._hover = None
            if self._drag is None:
                self.unsetCursor()
            self.update()

    def wheelEvent(self, e):
        steps = e.angleDelta().y() / 120.0
        if steps == 0:
            return
        factor = 1.25 ** steps
        new_scale = geo.clamp(self._scale * factor, 0.02, 2000.0)
        wx, wy = self.screen_to_world(e.pos().x(), e.pos().y())
        self._scale = new_scale
        self._view_cx = wx - (e.pos().x() - self.width() / 2.0) / new_scale
        self._view_cy = wy - (self.height() / 2.0 - e.pos().y()) / new_scale
        self.update()
        e.accept()

    def _update_hover(self, pos):
        hover = None
        if self._hit("tip", pos):
            hover = "tip"
        elif self._hit("crane", pos):
            hover = "crane"
        if hover != self._hover:
            self._hover = hover
            self.setCursor(Qt.ClosedHandCursor if hover else Qt.ArrowCursor)
            self.update()

    def _emit_tip(self, pos):
        st = self._state
        wx, wy = self.screen_to_world(pos.x(), pos.y())
        jib = geo.effective_jib_length(st["config"], st["jib_length"],
                                       st["ext_jib_length"])
        try:
            angle = geo.angle_for_tip(
                (st["crane_x"], st["crane_y"]), st["boom_length"], jib,
                st["jib_offset"], (wx, wy))
        except geo.GeometryError:
            return
        angle = round(geo.clamp(angle, geo.ANGLE_MIN, geo.ANGLE_MAX), 1)
        if angle != st["angle"]:
            self.angleChanged.emit(angle)

    def _emit_crane(self, pos):
        st = self._state
        wx, wy = self.screen_to_world(pos.x(), pos.y())
        x = round(geo.clamp(wx, -100.0, 100.0), 1)
        y = round(geo.clamp(wy, -50.0, 100.0), 1)
        if (x, y) != (st["crane_x"], st["crane_y"]):
            self.craneMoved.emit(x, y)

    # -- painting -----------------------------------------------------------

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(COL_BG))
        self._draw_grid(p)
        self._draw_axes_ground(p)
        self._draw_envelope(p)
        if self._show_dims:
            self._draw_dimensions(p)
        self._draw_angle_arc(p)
        self._draw_crane(p)
        self._draw_boom(p)
        self._draw_handles(p)
        p.end()

    # grid + axes

    def _grid_step(self):
        for step in (0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000):
            if step * self._scale >= 45.0:
                return step
        return 1000.0

    def _visible_world(self):
        x0, _ = self.screen_to_world(0, 0)
        x1, _ = self.screen_to_world(self.width(), 0)
        _, y0 = self.screen_to_world(0, 0)
        _, y1 = self.screen_to_world(0, self.height())
        return min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)

    def _draw_grid(self, p):
        step = self._grid_step()
        x0, x1, y0, y1 = self._visible_world()
        p.setPen(QPen(QColor(COL_GRID), 1))
        xs = int(x0 / step) * step
        while xs <= x1:
            if abs(xs) > step * 1e-6:
                sx, _ = self.world_to_screen(xs, 0)
                p.drawLine(QPointF(sx, 0), QPointF(sx, self.height()))
            xs += step
        ys = int(y0 / step) * step
        while ys <= y1:
            if abs(ys) > step * 1e-6:
                _, sy = self.world_to_screen(0, ys)
                p.drawLine(QPointF(0, sy), QPointF(self.width(), sy))
            ys += step

    def _draw_axes_ground(self, p):
        step = self._grid_step()
        x0, x1, y0, y1 = self._visible_world()
        font = QFont("DejaVu Sans", 9)
        p.setFont(font)

        # ground line (y = 0) with engineering hatch below it
        _, gy = self.world_to_screen(0, 0)
        if -2 <= gy <= self.height() + 2:
            p.setPen(QPen(QColor(COL_AXIS), 2))
            p.drawLine(QPointF(0, gy), QPointF(self.width(), gy))
            p.setPen(QPen(QColor(COL_AXIS), 1))
            xs = 0
            while xs <= self.width():
                p.drawLine(QPointF(xs, gy + 1),
                           QPointF(xs - 7, gy + 8))
                xs += 11
            p.setPen(QColor(COL_AXIS_TEXT))
            xs = int(x0 / step) * step
            while xs <= x1:
                sx, _ = self.world_to_screen(xs, 0)
                if 14 <= sx <= self.width() - 14:
                    p.drawText(QPointF(sx + 3, gy + 20),
                               _fmt_tick(xs))
                xs += step

        # y axis (x = 0) with labels
        ax_x, _ = self.world_to_screen(0, 0)
        if -2 <= ax_x <= self.width() + 2:
            p.setPen(QPen(QColor(COL_AXIS), 1))
            p.drawLine(QPointF(ax_x, 0), QPointF(ax_x, self.height()))
            label_x = ax_x - 6
        else:
            label_x = 8.0
        p.setPen(QColor(COL_AXIS_TEXT))
        ys = int(y0 / step) * step
        while ys <= y1:
            _, sy = self.world_to_screen(0, ys)
            if 10 <= sy <= self.height() - 10:
                rect = QRectF(label_x - 60, sy - 8, 56, 16)
                p.drawText(rect, Qt.AlignRight | Qt.AlignVCenter,
                           _fmt_tick(ys))
            ys += step

        # axis captions
        p.setPen(QColor(COL_AXIS_TEXT))
        p.drawText(QRectF(self.width() - 120, self.height() - 24,
                          112, 18),
                   Qt.AlignRight | Qt.AlignVCenter, "X / radius (m)")
        p.drawText(QRectF(8, 6, 110, 18),
                   Qt.AlignLeft | Qt.AlignVCenter, "Y / height (m)")

    # envelope

    def _draw_envelope(self, p):
        st = self._state
        pivot = (st["crane_x"], st["crane_y"])
        jib = geo.effective_jib_length(st["config"], st["jib_length"],
                                       st["ext_jib_length"])
        radius = geo.envelope_radius(st["boom_length"], jib, st["jib_offset"])
        pts = geo.envelope_points(pivot, radius,
                                  st["env_min"], st["env_max"], steps=72)
        scr = [self.world_to_screen(x, y) for x, y in pts]
        px, py = self.world_to_screen(*pivot)

        if len(scr) >= 2:
            sector = QPainterPath()
            sector.moveTo(px, py)
            for sx, sy in scr:
                sector.lineTo(sx, sy)
            sector.closeSubpath()
            p.fillPath(sector, COL_ENVELOPE_FILL)

            p.setPen(QPen(COL_ENVELOPE_STROKE, 2))
            p.drawPolyline(QPolygonF([QPointF(sx, sy) for sx, sy in scr]))

            edge_pen = QPen(COL_ENVELOPE_EDGE, 1, Qt.DashLine)
            p.setPen(edge_pen)
            p.drawLine(QPointF(px, py), QPointF(*scr[0]))
            p.drawLine(QPointF(px, py), QPointF(*scr[-1]))

        # inner arc traced by the boom tip when a jib is fitted
        if jib > 0:
            boom_arc = geo.envelope_points(pivot, st["boom_length"],
                                           st["env_min"], st["env_max"],
                                           steps=48)
            bscr = [self.world_to_screen(x, y) for x, y in boom_arc]
            p.setPen(QPen(COL_BOOM_ARC, 1, Qt.DashLine))
            p.drawPolyline(QPolygonF([QPointF(sx, sy) for sx, sy in bscr]))

        # envelope angle labels at the arc ends
        p.setFont(QFont("DejaVu Sans", 9))
        p.setPen(QColor(COL_JIB))
        for point, angle in ((scr[0], st["env_min"]), (scr[-1], st["env_max"])):
            vx, vy = point[0] - px, point[1] - py
            norm = (vx * vx + vy * vy) ** 0.5 or 1.0
            lx = point[0] + vx / norm * 14
            ly = point[1] + vy / norm * 14
            p.drawText(QPointF(lx - 14, ly + 4), f"{angle:g}\N{DEGREE SIGN}")

    # dimensions (radius + height)

    def _draw_dimensions(self, p):
        st = self._state
        tip = geo.tip_for_state(st)
        px, py = self.world_to_screen(st["crane_x"], st["crane_y"])
        tx, ty = self.world_to_screen(*tip)
        _, gy = self.world_to_screen(0, 0)

        p.setFont(QFont("DejaVu Sans", 10, QFont.Bold))

        # working radius: horizontal dashed line from pivot to tip X
        p.setPen(QPen(COL_DIM_R, 1, Qt.DashLine))
        p.drawLine(QPointF(px, py), QPointF(tx, py))
        p.setPen(QPen(COL_DIM_R, 1.5))
        p.drawLine(QPointF(tx, py - 5), QPointF(tx, py + 5))
        radius = geo.working_radius((st["crane_x"], st["crane_y"]), tip)
        self._pill(p, (px + tx) / 2.0, py - 12,
                   f"R = {radius:.2f} m", COL_BOOM)

        # tip height: dashed line from ground up to the tip
        if -50 <= gy <= self.height() + 50:
            p.setPen(QPen(COL_DIM_H, 1, Qt.DashLine))
            p.drawLine(QPointF(tx, ty), QPointF(tx, gy))
            p.setPen(QPen(COL_DIM_H, 1.5))
            p.drawLine(QPointF(tx - 5, gy), QPointF(tx + 5, gy))
            height = geo.tip_height(tip)
            colour = "#ff6b6b" if height < 0 else COL_JIB
            self._pill(p, tx + 8, (ty + gy) / 2.0,
                       f"H = {height:.2f} m", colour)

    def _draw_angle_arc(self, p):
        st = self._state
        px, py = self._pivot_screen()
        radius = 30.0
        angle = st["angle"]
        pts = []
        steps = max(2, int(abs(angle) / 2) + 1)
        for i in range(steps + 1):
            a = math.radians(angle * i / steps)
            pts.append(QPointF(px + radius * math.cos(a),
                               py - radius * math.sin(a)))
        p.setPen(QPen(COL_ANGLE, 1))
        p.drawPolyline(QPolygonF(pts))
        p.setFont(QFont("DejaVu Sans", 9, QFont.Bold))
        p.setPen(QColor(COL_TEXT))
        a = math.radians(angle / 2.0)
        p.drawText(QPointF(px + (radius + 14) * math.cos(a) - 12,
                           py - (radius + 14) * math.sin(a) + 4),
                   f"{angle:g}\N{DEGREE SIGN}")

    # crane marker

    def _draw_crane(self, p):
        st = self._state
        px, py = self._pivot_screen()
        hot = self._hover == "crane" or self._drag == "crane"
        border = QColor(COL_HANDLE_HOVER) if hot else QColor(COL_JIB)

        # outrigger base bar + feet
        p.setPen(QPen(QColor(COL_AXIS), 1))
        p.setBrush(QColor("#34405a"))
        p.drawRoundedRect(QRectF(px - 22, py + 4, 44, 8), 3, 3)
        p.setBrush(QColor("#5f7191"))
        p.drawRoundedRect(QRectF(px - 24, py + 11, 9, 6), 2, 2)
        p.drawRoundedRect(QRectF(px + 15, py + 11, 9, 6), 2, 2)

        # superstructure (behind the boom = -X side) + counterweight
        p.setPen(QPen(border, 2 if hot else 1))
        p.setBrush(QColor("#2f6fbf"))
        p.drawRoundedRect(QRectF(px - 16, py - 16, 15, 16), 3, 3)
        p.setBrush(QColor("#233047"))
        p.drawRoundedRect(QRectF(px - 23, py - 11, 7, 11), 2, 2)

        # slew / pivot
        p.setBrush(QColor(COL_JOINT))
        p.setPen(QPen(QColor("#141922"), 1))
        p.drawEllipse(QPointF(px, py), 4, 4)

        # location label
        p.setFont(QFont("DejaVu Sans", 9, QFont.Bold))
        text = f"({st['crane_x']:g}, {st['crane_y']:g})"
        self._pill(p, px, py + 30, text, COL_TEXT, size=9)

    # boom + jib

    def _draw_boom(self, p):
        st = self._state
        pivot = (st["crane_x"], st["crane_y"])
        jib = geo.effective_jib_length(st["config"], st["jib_length"],
                                       st["ext_jib_length"])
        boom_end = geo.boom_tip(pivot, st["boom_length"], st["angle"])
        tip = geo.assembly_tip(pivot, st["boom_length"], jib,
                               st["jib_offset"], st["angle"])
        bx, by = self.world_to_screen(*boom_end)
        tx, ty = self.world_to_screen(*tip)
        px, py = self._pivot_screen()

        p.setPen(QPen(QColor(COL_BOOM), 5, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(px, py), QPointF(bx, by))
        if jib > 0:
            p.setPen(QPen(QColor(COL_JIB), 3, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(bx, by), QPointF(tx, ty))
            p.setBrush(QColor(COL_JOINT))
            p.setPen(QPen(QColor("#141922"), 1))
            p.drawEllipse(QPointF(bx, by), 4, 4)

    def _draw_handles(self, p):
        tx, ty = self._tip_screen()
        hot = self._hover == "tip" or self._drag == "tip"
        radius = 9 if hot else 7
        p.setBrush(QColor(COL_BOOM))
        p.setPen(QPen(QColor(COL_HANDLE_HOVER) if hot else QColor("#141922"),
                      2))
        p.drawEllipse(QPointF(tx, ty), radius, radius)
        if hot:
            p.setFont(QFont("DejaVu Sans", 9, QFont.Bold))
            p.setPen(QColor(COL_TEXT))
            tip = geo.tip_for_state(self._state)
            p.drawText(QPointF(tx + 14, ty + 4),
                       f"({tip[0]:.1f}, {tip[1]:.1f})")

    # text pill helper (draws a label on a rounded dark background)

    def _pill(self, p, cx, cy, text, colour, size=10):
        font = QFont("DejaVu Sans", size, QFont.Bold)
        p.setFont(font)
        metrics = QFontMetricsF(font)
        tw = metrics.horizontalAdvance(text)
        th = metrics.height()
        rect = QRectF(cx - tw / 2.0 - 6, cy - th / 2.0 - 3,
                      tw + 12, th + 6)
        rect.moveLeft(geo.clamp(rect.left(), 2, max(2, self.width() - rect.width() - 2)))
        rect.moveTop(geo.clamp(rect.top(), 2,
                               max(2, self.height() - rect.height() - 2)))
        path = QPainterPath()
        path.addRoundedRect(rect, 4, 4)
        p.fillPath(path, COL_PILL_BG)
        p.setPen(QColor(colour))
        p.drawText(rect, Qt.AlignCenter, text)


def _fmt_tick(value):
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Crane Graph")
        self.resize(1360, 840)
        self.setMinimumSize(980, 620)
        self._state = dict(geo.DEFAULT_STATE)
        self._env_guard = False

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # ---- left input panel ----
        panel = QWidget()
        panel.setFixedWidth(370)
        form = QVBoxLayout(panel)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        form.addWidget(self._build_config_group())
        form.addWidget(self._build_angle_group())
        form.addWidget(self._build_crane_group())
        self.readout = KeyValuePanel("Readout")
        form.addWidget(self.readout)
        form.addWidget(_label(
            "Graph: drag the boom tip to set the angle, drag the crane "
            "marker to set (X, Y); wheel zooms, double-click fits.",
            color="#8fa3c0", size=9))
        form.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(panel)
        scroll.setFixedWidth(390)
        scroll.setMinimumWidth(390)
        root.addWidget(scroll)

        # ---- graph ----
        self.canvas = GraphCanvas()
        root.addWidget(self.canvas, 1)
        self.setCentralWidget(central)

        self.statusBar().showMessage(
            "Drag the boom tip to change the angle  |  Drag the crane "
            "marker to move it on the XY axis  |  Wheel zooms  |  "
            "Double-click fits the view")

        self._wire()
        self._apply(fit=False)
        QTimer.singleShot(0, self.canvas.fit_view)

    # -- input panel construction ------------------------------------------

    def _build_config_group(self):
        group = QGroupBox("Boom configuration")
        lay = QVBoxLayout(group)
        lay.setSpacing(6)

        self.radios = []
        self.config_group = QButtonGroup(self)
        for i, key in enumerate(geo.CONFIGS):
            radio = QRadioButton(geo.CONFIG_LABELS[key])
            self.config_group.addButton(radio, i)
            lay.addWidget(radio)
            self.radios.append(radio)
        self.radios[0].setChecked(True)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        self.boom_lbl = _label("Boom length (m):")
        self.boom = _dspin(geo.DEFAULT_STATE["boom_length"], 1, 150, 1, "m",
                           1.0, 110)
        self.jib_lbl = _label("Jib length (m):")
        self.jib = _dspin(geo.DEFAULT_STATE["jib_length"], 0, 60, 1, "m",
                          1.0, 110)
        self.ext_lbl = _label("Extended jib length (m):")
        self.ext = _dspin(geo.DEFAULT_STATE["ext_jib_length"], 0, 80, 1, "m",
                          1.0, 110)
        self.jib_offset_lbl = _label("Jib offset angle (deg):")
        self.jib_offset = _dspin(geo.DEFAULT_STATE["jib_offset"], -30, 60, 1,
                                 "deg", 1.0, 110)
        grid.addWidget(self.boom_lbl, 0, 0)
        grid.addWidget(self.boom, 0, 1)
        grid.addWidget(self.jib_lbl, 1, 0)
        grid.addWidget(self.jib, 1, 1)
        grid.addWidget(self.ext_lbl, 2, 0)
        grid.addWidget(self.ext, 2, 1)
        grid.addWidget(self.jib_offset_lbl, 3, 0)
        grid.addWidget(self.jib_offset, 3, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)
        return group

    def _build_angle_group(self):
        group = QGroupBox("Boom angle & envelope")
        lay = QVBoxLayout(group)
        lay.setSpacing(6)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        self.angle_lbl = _label("Boom angle (deg):")
        self.angle = _dspin(geo.DEFAULT_STATE["angle"],
                            geo.ANGLE_MIN, geo.ANGLE_MAX, 1, "deg", 1.0, 110)
        self.env_min_lbl = _label("Envelope from (deg):")
        self.env_min = _dspin(geo.DEFAULT_STATE["env_min"], 0, 85, 1, "deg",
                              1.0, 110)
        self.env_max_lbl = _label("Envelope to (deg):")
        self.env_max = _dspin(geo.DEFAULT_STATE["env_max"], 0, 85, 1, "deg",
                              1.0, 110)
        grid.addWidget(self.angle_lbl, 0, 0)
        grid.addWidget(self.angle, 0, 1)
        grid.addWidget(self.env_min_lbl, 1, 0)
        grid.addWidget(self.env_min, 1, 1)
        grid.addWidget(self.env_max_lbl, 2, 0)
        grid.addWidget(self.env_max, 2, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)

        opts = QHBoxLayout()
        self.show_dims = QCheckBox("Show dimensions")
        self.show_dims.setChecked(True)
        self.auto_fit = QCheckBox("Auto-fit view")
        self.auto_fit.setChecked(True)
        fit_btn = QPushButton("Fit view")
        fit_btn.setFixedWidth(90)
        opts.addWidget(self.show_dims)
        opts.addWidget(self.auto_fit)
        opts.addStretch(1)
        opts.addWidget(fit_btn)
        lay.addLayout(opts)
        self._fit_btn = fit_btn
        return group

    def _build_crane_group(self):
        group = QGroupBox("Crane location on axis (X, Y)")
        lay = QVBoxLayout(group)
        lay.setSpacing(6)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        self.cx_lbl = _label("Position X (m):")
        self.cx = _dspin(geo.DEFAULT_STATE["crane_x"], -100, 100, 1, "m",
                         0.5, 110)
        self.cy_lbl = _label("Position Y (m):")
        self.cy = _dspin(geo.DEFAULT_STATE["crane_y"], -50, 100, 1, "m",
                         0.5, 110)
        grid.addWidget(self.cx_lbl, 0, 0)
        grid.addWidget(self.cx, 0, 1)
        grid.addWidget(self.cy_lbl, 1, 0)
        grid.addWidget(self.cy, 1, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)

        presets = QHBoxLayout()
        presets.setSpacing(6)
        presets.addWidget(_label("Quick:", color="#8fa3c0", size=10))
        for x, y in ((-3, 0), (0, 0), (0, 3), (3, 0)):
            btn = QPushButton(f"({x:g}, {y:g})")
            btn.setObjectName("preset")
            btn.clicked.connect(
                lambda _=False, x=x, y=y: self._set_crane(x, y))
            presets.addWidget(btn)
        presets.addStretch(1)
        lay.addLayout(presets)
        lay.addWidget(_label("Or drag the crane marker on the graph.",
                             color="#8fa3c0", size=9))
        return group

    # -- wiring -------------------------------------------------------------

    def _wire(self):
        for radio in self.radios:
            radio.toggled.connect(lambda *_: self._apply(fit=True))
        self.boom.valueChanged.connect(lambda *_: self._apply(fit=True))
        self.jib.valueChanged.connect(lambda *_: self._apply(fit=True))
        self.ext.valueChanged.connect(lambda *_: self._apply(fit=True))
        self.jib_offset.valueChanged.connect(lambda *_: self._apply(fit=True))
        self.angle.valueChanged.connect(lambda *_: self._apply(fit=False))
        self.env_min.valueChanged.connect(self._env_changed)
        self.env_max.valueChanged.connect(self._env_changed)
        self.cx.valueChanged.connect(lambda *_: self._apply(fit=True))
        self.cy.valueChanged.connect(lambda *_: self._apply(fit=True))
        self.show_dims.toggled.connect(self.canvas.set_show_dims)
        self._fit_btn.clicked.connect(self.canvas.fit_view)

        self.canvas.angleChanged.connect(self.angle.setValue)
        self.canvas.craneMoved.connect(self._crane_from_graph)
        self.canvas.interactionEnded.connect(self._after_interaction)

    def _env_changed(self, *args):
        if self._env_guard:
            return
        mn, mx = self.env_min.value(), self.env_max.value()
        if mn > mx:
            self._env_guard = True
            if self.sender() is self.env_min:
                self.env_max.setValue(mn)
            else:
                self.env_min.setValue(mx)
            self._env_guard = False
        self._apply(fit=True)

    def _crane_from_graph(self, x, y):
        self.cx.setValue(x)
        self.cy.setValue(y)

    def _set_crane(self, x, y):
        self.cx.setValue(x)
        self.cy.setValue(y)

    def _after_interaction(self):
        if self.auto_fit.isChecked():
            self.canvas.fit_view()

    # -- state flow ---------------------------------------------------------

    def _apply(self, fit=True):
        st = self._state
        st["config"] = geo.CONFIGS[max(0, self.config_group.checkedId())]
        st["boom_length"] = self.boom.value()
        st["jib_length"] = self.jib.value()
        st["ext_jib_length"] = self.ext.value()
        st["jib_offset"] = self.jib_offset.value()
        st["angle"] = self.angle.value()
        st["env_min"] = self.env_min.value()
        st["env_max"] = self.env_max.value()
        st["crane_x"] = self.cx.value()
        st["crane_y"] = self.cy.value()
        self._update_enabled()
        self.canvas.set_state(st)
        self._update_readouts(st)
        if fit and self.auto_fit.isChecked() and not self.canvas.is_dragging():
            self.canvas.fit_view()

    def _update_enabled(self):
        cfg = geo.CONFIGS[max(0, self.config_group.checkedId())]
        jib_on = cfg != geo.CONFIG_BOOM
        ext_on = cfg == geo.CONFIG_BOOM_EXT_JIB
        self.jib.setEnabled(jib_on)
        self.jib_lbl.setEnabled(jib_on)
        self.jib_offset.setEnabled(jib_on)
        self.jib_offset_lbl.setEnabled(jib_on)
        self.ext.setEnabled(ext_on)
        self.ext_lbl.setEnabled(ext_on)

    def _update_readouts(self, st):
        rd = geo.readouts(st)
        jib_active = rd["jib_active"]
        if st["config"] == geo.CONFIG_BOOM_EXT_JIB:
            jib_row = ("Extended jib length",
                       f"{rd['jib_length']:.1f} m" if jib_active else "not fitted")
        else:
            jib_row = ("Jib length",
                       f"{rd['jib_length']:.1f} m" if jib_active else "not fitted")
        tip = rd["tip"]
        if rd["below_ground"]:
            clearance = ("Ground clearance", "BELOW GROUND", "#ff6b6b")
        else:
            clearance = ("Ground clearance", "OK", "#2e7d52")
        self.readout.set_rows([
            ("Configuration", geo.CONFIG_LABELS[st["config"]]),
            ("Boom length", f"{st['boom_length']:.1f} m"),
            jib_row,
            ("Jib offset angle",
             f"{st['jib_offset']:.1f} deg" if jib_active else "—"),
            ("Working radius", f"{rd['working_radius']:.2f} m"),
            ("Tip height above ground", f"{rd['tip_height']:.2f} m"),
            ("Tip height above crane", f"{rd['height_above_crane']:.2f} m"),
            ("Envelope radius", f"{rd['envelope_radius']:.2f} m"),
            ("Envelope sweep",
             f"{st['env_min']:g} - {st['env_max']:g} deg"),
            ("Boom angle", f"{st['angle']:g} deg"),
            ("Crane location (X, Y)",
             f"({st['crane_x']:g}, {st['crane_y']:g})"),
            ("Tip location (X, Y)", f"({tip[0]:.2f}, {tip[1]:.2f})"),
            clearance,
        ])


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    for candidate in (
        os.path.join(os.environ.get("APPDIR", ""),
                     "crane-graph-app.png"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "packaging", "appdir", "crane-graph-app",
                     "crane-graph-app.png"),
    ):
        if candidate and os.path.exists(candidate):
            app.setWindowIcon(QIcon(candidate))
            break
    win = MainWindow()
    win.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
