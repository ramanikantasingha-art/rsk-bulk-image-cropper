#!/usr/bin/env python3
"""
Bulk Image Cropper 2.0
--------------------------------
A desktop app (PyQt5 + Pillow) that lets you:
  1. Pick an input folder of images
  2. Draw / fine-tune a single crop rectangle on a preview image
  3. Apply that exact rectangle to every image in the folder
  4. Save the results (lossless PNG or quality=100 JPEG) to an output folder

Run:
    pip install -r requirements.txt
    python bulk_image_cropper.py
"""

import sys
import os
import traceback
import datetime
import re

# --------------------------------------------------------------------------
# Crash logging: write any startup/runtime crash to a log file next to the
# script, since double-clicking a .bat/.exe often closes the console before
# an error can be read. Check crash_log.txt after a silent crash.
# --------------------------------------------------------------------------
LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "crash_log.txt"
)


def log_crash(exc_type, exc_value, exc_tb):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n----- {datetime.datetime.now().isoformat()} -----\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except Exception:
        pass
    # Also print to console in case one is attached
    if sys.stderr is not None:
        traceback.print_exception(exc_type, exc_value, exc_tb)
    if os.name == 'nt':
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                None, f"{exc_type.__name__}: {exc_value}\n\nDetails: {LOG_PATH}",
                "Bulk Image Cropper error", 0x10)
        except Exception:
            pass


sys.excepthook = log_crash

try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QPushButton, QLabel, QFileDialog, QSpinBox, QCheckBox, QMessageBox,
        QGraphicsView, QGraphicsScene, QGraphicsRectItem, QProgressBar, QFrame,
        QSizePolicy
    )
    from PyQt5.QtCore import Qt, QRectF, QPointF, QThread, pyqtSignal
    from PyQt5.QtGui import QPixmap, QPen, QColor, QBrush
    from PIL import Image
except Exception:
    # Import failures (missing/mismatched packages) are the #1 cause of a
    # "crashes with no error" launch. Log it, then re-raise so the launcher
    # script's own error handling / pause still kicks in.
    log_crash(*sys.exc_info())
    raise

VALID_EXT = ('.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tiff', '.tif')


class CropView(QGraphicsView):
    """Eight screen-sized handles, bounded movement and image-pixel geometry."""
    selectionChanged = pyqtSignal(QRectF)

    def __init__(self, scene):
        super().__init__(scene)
        self.image_bounds = QRectF()
        self.selection = QRectF()
        self.drag_start = None
        self.drag_rect = QRectF()
        self.mode = None
        self.locked_ratio = None
        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setCursor(Qt.CrossCursor)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def handles(self):
        r = self.selection
        return {'nw': r.topLeft(), 'n': QPointF(r.center().x(), r.top()),
                'ne': r.topRight(), 'e': QPointF(r.right(), r.center().y()),
                'se': r.bottomRight(), 's': QPointF(r.center().x(), r.bottom()),
                'sw': r.bottomLeft(), 'w': QPointF(r.left(), r.center().y())}

    def hit_test(self, point):
        if self.selection.isEmpty():
            return 'draw'
        tolerance = 8 / max(self.transform().m11(), 0.001)
        for name, p in self.handles().items():
            if abs(point.x()-p.x()) <= tolerance and abs(point.y()-p.y()) <= tolerance:
                return name
        r = self.selection
        if r.top() <= point.y() <= r.bottom():
            if abs(point.x()-r.left()) <= tolerance: return 'w'
            if abs(point.x()-r.right()) <= tolerance: return 'e'
        if r.left() <= point.x() <= r.right():
            if abs(point.y()-r.top()) <= tolerance: return 'n'
            if abs(point.y()-r.bottom()) <= tolerance: return 's'
        return 'move' if r.contains(point) else 'draw'

    def set_selection(self, rect):
        self.selection = QRectF(rect)
        self.viewport().update()

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        if self.selection.isEmpty(): return
        painter.save()
        # Paint in viewport coordinates so handles remain easy to grab at any scale.
        painter.resetTransform()
        painter.setPen(QPen(QColor('#167bd5'), 1))
        painter.setBrush(QBrush(QColor('white')))
        for p in self.handles().values():
            q = self.mapFromScene(p)
            painter.drawRect(QRectF(q.x()-4, q.y()-4, 8, 8))
        painter.restore()

    def mousePressEvent(self, event):
        point = self.mapToScene(event.pos())
        mode = self.hit_test(point)
        if event.button() == Qt.LeftButton and (self.image_bounds.contains(point)
                                                or mode not in ('draw', 'move')):
            self.drag_start = point
            self.drag_rect = QRectF(self.selection)
            self.mode = 'draw' if event.modifiers() & Qt.ShiftModifier else mode
            self.setFocus()
            event.accept()
            return
        super().mousePressEvent(event)

    def _select(self, point):
        b, r = self.image_bounds, self.drag_rect
        x = min(max(point.x(), b.left()), b.right())
        y = min(max(point.y(), b.top()), b.bottom())
        mode = self.mode
        if mode == 'move':
            dx, dy = point.x()-self.drag_start.x(), point.y()-self.drag_start.y()
            left = min(max(r.left()+dx, b.left()), b.right()-r.width())
            top = min(max(r.top()+dy, b.top()), b.bottom()-r.height())
            result = QRectF(left, top, r.width(), r.height())
        elif mode == 'draw':
            anchor = QPointF(min(max(self.drag_start.x(), b.left()), b.right()),
                             min(max(self.drag_start.y(), b.top()), b.bottom()))
            dx, dy = x-anchor.x(), y-anchor.y()
            if self.locked_ratio:
                width = min(abs(dx), abs(dy)*self.locked_ratio)
                dx = width if dx >= 0 else -width
                dy = width/self.locked_ratio if dy >= 0 else -width/self.locked_ratio
            result = QRectF(anchor, anchor+QPointF(dx, dy)).normalized()
        elif mode:
            left, top, right, bottom = r.left(), r.top(), r.right(), r.bottom()
            if 'w' in mode: left = min(x, right-1)
            if 'e' in mode: right = max(x, left+1)
            if 'n' in mode: top = min(y, bottom-1)
            if 's' in mode: bottom = max(y, top+1)
            if self.locked_ratio:
                ratio = self.locked_ratio
                if len(mode) == 2:
                    ax = r.right() if 'w' in mode else r.left()
                    ay = r.bottom() if 'n' in mode else r.top()
                    maxw = ax-b.left() if 'w' in mode else b.right()-ax
                    maxh = ay-b.top() if 'n' in mode else b.bottom()-ay
                    width = min(right-left, (bottom-top)*ratio, maxw, maxh*ratio)
                    height = width/ratio
                    left = ax-width if 'w' in mode else ax
                    top = ay-height if 'n' in mode else ay
                elif mode in ('e','w'):
                    width = min(right-left, 2*min(r.center().y()-b.top(),
                                                 b.bottom()-r.center().y())*ratio)
                    height = width/ratio
                    left = r.right()-width if mode=='w' else r.left()
                    top = r.center().y()-height/2
                else:
                    height = min(bottom-top, 2*min(r.center().x()-b.left(),
                                                   b.right()-r.center().x())/ratio)
                    width = height*ratio
                    left = r.center().x()-width/2
                    top = r.bottom()-height if mode=='n' else r.top()
                right, bottom = left+width, top+height
            result = QRectF(left, top, right-left, bottom-top)
        else:
            return
        if result.width() >= 1 and result.height() >= 1:
            self.selectionChanged.emit(result)

    def mouseMoveEvent(self, event):
        point = self.mapToScene(event.pos())
        if self.drag_start is not None:
            self._select(point)
            event.accept()
            return
        mode = self.hit_test(point)
        cursor = {'nw': Qt.SizeFDiagCursor, 'se': Qt.SizeFDiagCursor,
                  'ne': Qt.SizeBDiagCursor, 'sw': Qt.SizeBDiagCursor,
                  'n': Qt.SizeVerCursor, 's': Qt.SizeVerCursor,
                  'e': Qt.SizeHorCursor, 'w': Qt.SizeHorCursor,
                  'move': Qt.SizeAllCursor}.get(mode, Qt.CrossCursor)
        self.setCursor(cursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.drag_start is not None:
            self._select(self.mapToScene(event.pos()))
            self.drag_start = None
            self.mode = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.drag_start is not None:
            if not self.drag_rect.isEmpty(): self.selectionChanged.emit(self.drag_rect)
            self.drag_start = None
            self.mode = None
            event.accept()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'image_bounds') and not self.image_bounds.isEmpty():
            self.fitInView(self.image_bounds, Qt.KeepAspectRatio)


# --------------------------------------------------------------------------
# Background worker so the UI never freezes during bulk processing
# --------------------------------------------------------------------------
class CropWorker(QThread):
    progress = pyqtSignal(int, int)      # (done, total)
    finished_ok = pyqtSignal(int, list)  # (success_count, errors)

    def __init__(self, files, input_folder, output_folder, box, quality):
        super().__init__()
        self.files = files
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.box = box  # (left, top, right, bottom) in pixel coords
        self.quality = quality
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        left, top, right, bottom = self.box
        success = 0
        errors = []

        for i, fname in enumerate(self.files, start=1):
            if self._stop:
                break
            in_path = os.path.join(self.input_folder, fname)
            out_path = os.path.join(self.output_folder, fname)

            try:
                with Image.open(in_path) as img:
                    w, h = img.size
                    crop_box = (
                        max(0, min(left, w)),
                        max(0, min(top, h)),
                        max(0, min(right, w)),
                        max(0, min(bottom, h)),
                    )
                    if crop_box[2] <= crop_box[0] or crop_box[3] <= crop_box[1]:
                        raise ValueError("Crop rectangle falls outside this image")

                    cropped = img.crop(crop_box)

                    ext = os.path.splitext(fname)[1].lower()
                    if ext in ('.jpg', '.jpeg'):
                        if cropped.mode in ('RGBA', 'P'):
                            cropped = cropped.convert('RGB')
                        cropped.save(out_path, 'JPEG', quality=self.quality, subsampling=0)
                    elif ext == '.png':
                        cropped.save(out_path, 'PNG')
                    else:
                        cropped.save(out_path)

                success += 1
            except Exception as e:
                errors.append(f"{fname}: {e}")

            self.progress.emit(i, len(self.files))

        self.finished_ok.emit(success, errors)


# --------------------------------------------------------------------------
# Main window
# --------------------------------------------------------------------------
class ImageCropperApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bulk Image Cropper 2.0")
        self.setGeometry(100, 100, 1150, 720)

        self.input_folder = ""
        self.output_folder = ""
        self.image_files = []
        self.preview_index = 0
        self.current_pixmap = None
        self.aspect_ratio = 1.0
        self.is_updating = False
        self.worker = None
        self.selection_rect = None

        self.initUI()

    # ---------------------------------------------------------------- UI --
    def initUI(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # ---- Left: preview + crop rectangle -------------------------------
        left_col = QVBoxLayout()

        self.scene = QGraphicsScene()
        self.view = CropView(self.scene)
        self.view.selectionChanged.connect(self.update_crop_box)
        self.pixmap_item = self.scene.addPixmap(QPixmap())
        left_col.addWidget(self.view, stretch=1)

        nav_layout = QHBoxLayout()
        self.btn_prev = QPushButton("< Prev image")
        self.btn_prev.clicked.connect(self.show_prev_image)
        self.btn_prev.setEnabled(False)
        self.lbl_preview_info = QLabel("No images loaded")
        self.lbl_preview_info.setAlignment(Qt.AlignCenter)
        self.btn_next = QPushButton("Next image >")
        self.btn_next.clicked.connect(self.show_next_image)
        self.btn_next.setEnabled(False)
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.lbl_preview_info, stretch=1)
        nav_layout.addWidget(self.btn_next)
        left_col.addLayout(nav_layout)

        layout.addLayout(left_col, stretch=3)

        # ---- Right: controls ------------------------------------------------
        control_layout = QVBoxLayout()

        self.btn_input = QPushButton("1. Select Input Folder")
        self.btn_input.clicked.connect(self.select_input_folder)
        control_layout.addWidget(self.btn_input)
        self.lbl_input = QLabel("No folder selected")
        self.lbl_input.setWordWrap(True)
        control_layout.addWidget(self.lbl_input)

        self.btn_output = QPushButton("2. Select Output Folder")
        self.btn_output.clicked.connect(self.select_output_folder)
        control_layout.addWidget(self.btn_output)
        self.lbl_output = QLabel("No folder selected")
        self.lbl_output.setWordWrap(True)
        control_layout.addWidget(self.lbl_output)

        control_layout.addWidget(self._hline())

        control_layout.addWidget(QLabel("Crop position (top-left, pixels):"))
        pos_layout = QGridLayout()
        pos_layout.addWidget(QLabel("X:"), 0, 0)
        self.spin_x = QSpinBox()
        self.spin_x.setMaximum(100000)
        self.spin_x.valueChanged.connect(self.update_from_spinboxes)
        pos_layout.addWidget(self.spin_x, 0, 1)
        pos_layout.addWidget(QLabel("Y:"), 0, 2)
        self.spin_y = QSpinBox()
        self.spin_y.setMaximum(100000)
        self.spin_y.valueChanged.connect(self.update_from_spinboxes)
        pos_layout.addWidget(self.spin_y, 0, 3)
        control_layout.addLayout(pos_layout)

        control_layout.addWidget(QLabel("Crop size (pixels):"))
        dim_layout = QGridLayout()
        dim_layout.addWidget(QLabel("W:"), 0, 0)
        self.spin_width = QSpinBox()
        self.spin_width.setRange(1, 100000)
        self.spin_width.valueChanged.connect(self.update_from_spinboxes)
        dim_layout.addWidget(self.spin_width, 0, 1)
        dim_layout.addWidget(QLabel("H:"), 0, 2)
        self.spin_height = QSpinBox()
        self.spin_height.setRange(1, 100000)
        self.spin_height.valueChanged.connect(self.update_from_spinboxes)
        dim_layout.addWidget(self.spin_height, 0, 3)
        control_layout.addLayout(dim_layout)

        self.chk_ratio = QCheckBox("Lock aspect ratio")
        self.chk_ratio.stateChanged.connect(self.toggle_ratio)
        control_layout.addWidget(self.chk_ratio)
        hint = QLabel("Drag handles or edges to resize. Drag inside to move.\nDrag outside (or Shift-drag anywhere) to draw a new box.")
        hint.setWordWrap(True)
        control_layout.addWidget(hint)
        self.btn_full = QPushButton("Select full image")
        self.btn_full.clicked.connect(lambda: self.update_crop_box(self.view.image_bounds))
        control_layout.addWidget(self.btn_full)
        self.chk_apply_all = QCheckBox("Apply to all images")
        self.chk_apply_all.setChecked(True)
        self.chk_apply_all.setToolTip(
            "Checked: crop every image using the same pixel coordinates. "
            "Unchecked: save only the current image. Smaller images are clipped to their edges."
        )
        self.chk_apply_all.toggled.connect(self.update_process_label)
        control_layout.addWidget(self.chk_apply_all)

        control_layout.addWidget(self._hline())

        control_layout.addWidget(QLabel("JPEG quality (1-100):"))
        self.spin_quality = QSpinBox()
        self.spin_quality.setRange(1, 100)
        self.spin_quality.setValue(100)
        control_layout.addWidget(self.spin_quality)

        control_layout.addWidget(self._hline())

        self.btn_process = QPushButton("3. BULK CROP ALL IMAGES")
        self.btn_process.setMinimumHeight(50)
        self.btn_process.setStyleSheet(
            "background-color: #28a745; color: white; font-weight: bold;"
        )
        self.btn_process.clicked.connect(self.process_bulk_crop)
        control_layout.addWidget(self.btn_process)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        control_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        control_layout.addWidget(self.lbl_status)

        control_layout.addStretch()
        layout.addLayout(control_layout, stretch=1)

        # Crop rectangle overlay
        self.crop_rect = QGraphicsRectItem()
        pen = QPen(QColor(35, 145, 235), 2)
        pen.setCosmetic(True)
        self.crop_rect.setPen(pen)
        self.crop_rect.setBrush(QBrush(QColor(100, 185, 245, 85)))
        self.crop_rect.setZValue(1)
        self.crop_rect.setAcceptedMouseButtons(Qt.NoButton)
        self.scene.addItem(self.crop_rect)

    def update_process_label(self):
        self.btn_process.setText(
            "3. BULK CROP ALL IMAGES" if self.chk_apply_all.isChecked()
            else "3. CROP CURRENT IMAGE"
        )

    @staticmethod
    def _hline():
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    # ------------------------------------------------------------ folders --
    def select_input_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if folder:
            self.input_folder = folder
            self.lbl_input.setText(folder)
            self.load_images()

    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_folder = folder
            self.lbl_output.setText(folder)

    # ------------------------------------------------------------- images --
    def load_images(self):
        self.image_files = sorted(
            (f for f in os.listdir(self.input_folder)
             if f.lower().endswith(VALID_EXT)
             and os.path.isfile(os.path.join(self.input_folder, f))),
            key=lambda name: [int(part) if part.isdigit() else part.casefold()
                              for part in re.split(r"(\d+)", name)]
        )
        self.selection_rect = None
        self.current_pixmap = None
        self.pixmap_item.setPixmap(QPixmap())
        self.crop_rect.setRect(QRectF())
        self.view.image_bounds = QRectF()
        self.view.set_selection(QRectF())

        if not self.image_files:
            QMessageBox.warning(
                self, "No Images",
                "No supported image files (png/jpg/jpeg/bmp/webp/tiff) "
                "were found in that folder."
            )
            self.lbl_preview_info.setText("No images loaded")
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)
            return

        self.preview_index = 0
        self.btn_prev.setEnabled(len(self.image_files) > 1)
        self.btn_next.setEnabled(len(self.image_files) > 1)
        self.show_preview_image()

    def show_prev_image(self):
        if not self.image_files:
            return
        self.preview_index = (self.preview_index - 1) % len(self.image_files)
        self.show_preview_image()

    def show_next_image(self):
        if not self.image_files:
            return
        self.preview_index = (self.preview_index + 1) % len(self.image_files)
        self.show_preview_image()

    def show_preview_image(self):
        name = self.image_files[self.preview_index]
        self.lbl_preview_info.setText(
            f"{self.preview_index + 1} / {len(self.image_files)} — {name}"
        )
        path = os.path.join(self.input_folder, name)
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.current_pixmap = None
            self.pixmap_item.setPixmap(QPixmap())
            self.crop_rect.setRect(QRectF())
            self.view.image_bounds = QRectF()
            self.view.set_selection(QRectF())
            self.lbl_status.setText(f"Could not preview: {name}. Try Previous or Next.")
            return

        self.current_pixmap = pixmap
        # Keep both graphics items alive: scene.clear() would delete the overlay.
        self.pixmap_item.setPixmap(pixmap)
        bounds = QRectF(0, 0, pixmap.width(), pixmap.height())
        self.scene.setSceneRect(bounds)
        self.view.image_bounds = bounds
        self.view.fitInView(bounds, Qt.KeepAspectRatio)
        self.lbl_preview_info.setText(
            f"{self.preview_index + 1} / {len(self.image_files)} — {name} "
            f"({pixmap.width()}x{pixmap.height()})"
        )
        self.lbl_status.setText("")
        if self.selection_rect is None:
            self.update_crop_box(QRectF(0, 0, min(300, pixmap.width()),
                                       min(300, pixmap.height())))
        else:
            self.update_crop_box(self.selection_rect, remember=False)

    # --------------------------------------------------------- crop logic --
    def update_crop_box(self, rect, remember=True):
        if self.current_pixmap is None:
            return
        rect = rect.normalized()
        # Display and export use the same integer pixel coordinates.
        rect = QRectF(int(rect.x()), int(rect.y()),
                      max(1, int(rect.width())), max(1, int(rect.height())))
        if remember:
            rect = rect.intersected(self.view.image_bounds)
            if rect.isEmpty():
                return
            self.selection_rect = QRectF(rect)
        self.is_updating = True
        try:
            self.crop_rect.setRect(rect.intersected(self.view.image_bounds))
            self.view.set_selection(self.crop_rect.rect())
            self.spin_x.setValue(int(rect.x()))
            self.spin_y.setValue(int(rect.y()))
            self.spin_width.setValue(int(rect.width()))
            self.spin_height.setValue(int(rect.height()))
        finally:
            self.is_updating = False

    def toggle_ratio(self):
        if self.chk_ratio.isChecked() and self.spin_height.value() > 0:
            self.aspect_ratio = self.spin_width.value() / self.spin_height.value()
        self.view.locked_ratio = self.aspect_ratio if self.chk_ratio.isChecked() else None

    def update_from_spinboxes(self):
        if self.is_updating:
            return

        x = self.spin_x.value()
        y = self.spin_y.value()
        w = self.spin_width.value()
        h = self.spin_height.value()

        if self.chk_ratio.isChecked() and self.aspect_ratio > 0:
            sender = self.sender()
            if sender is self.spin_width:
                h = int(w / self.aspect_ratio)
                self.is_updating = True
                self.spin_height.setValue(h)
                self.is_updating = False
            elif sender is self.spin_height:
                w = int(h * self.aspect_ratio)
                self.is_updating = True
                self.spin_width.setValue(w)
                self.is_updating = False

        if self.current_pixmap is not None:
            x = min(x, self.current_pixmap.width() - 1)
            y = min(y, self.current_pixmap.height() - 1)
            self.update_crop_box(QRectF(x, y, max(1, w), max(1, h)))

    # ----------------------------------------------------------- process --
    def process_bulk_crop(self):
        if not self.input_folder or not self.output_folder:
            QMessageBox.critical(self, "Error", "Please select both an Input and an Output folder.")
            return

        if not self.image_files:
            QMessageBox.critical(self, "Error", "No images found in the input folder.")
            return

        rect = self.selection_rect or QRectF()
        if rect.width() <= 0 or rect.height() <= 0:
            QMessageBox.critical(self, "Error", "The crop rectangle is empty. Draw a rectangle on the preview first.")
            return

        if os.path.normcase(os.path.abspath(self.input_folder)) == \
                os.path.normcase(os.path.abspath(self.output_folder)):
            reply = QMessageBox.question(
                self, "Same Folder",
                "Input and output folders are the same. Original images will be "
                "overwritten with their cropped versions. Continue?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        try:
            os.makedirs(self.output_folder, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, "Output folder error", str(exc))
            return

        box = (
            int(rect.left()), int(rect.top()),
            int(rect.right()), int(rect.bottom())
        )

        files = (list(self.image_files) if self.chk_apply_all.isChecked()
                 else [self.image_files[self.preview_index]])
        self.processing_count = len(files)
        self.btn_process.setEnabled(False)
        self.btn_input.setEnabled(False)
        self.btn_output.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(files))
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Processing...")

        self.worker = CropWorker(
            files, self.input_folder, self.output_folder,
            box, self.spin_quality.value()
        )
        self.worker.progress.connect(self.on_progress)
        self.worker.finished_ok.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, done, total):
        self.progress_bar.setValue(done)
        self.lbl_status.setText(f"Processing {done}/{total}...")

    def on_finished(self, success_count, errors):
        self.btn_process.setEnabled(True)
        self.btn_input.setEnabled(True)
        self.btn_output.setEnabled(True)
        self.progress_bar.setVisible(False)

        if errors:
            self.lbl_status.setText(f"Done. {success_count} succeeded, {len(errors)} failed.")
            detail = "\n".join(errors[:20])
            if len(errors) > 20:
                detail += f"\n...and {len(errors) - 20} more."
            QMessageBox.warning(
                self, "Finished with errors",
                f"Cropped {success_count} of {self.processing_count} images.\n\n"
                f"Failures:\n{detail}"
            )
        else:
            self.lbl_status.setText(f"Done. {success_count} images cropped successfully.")
            QMessageBox.information(
                self, "Success",
                f"Successfully cropped and saved {success_count} images to:\n{self.output_folder}"
            )

    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
            self.lbl_status.setText("Stopping after the current image; close again when finished.")
            event.ignore()
            return
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet('''
        QMainWindow { background: #f3f6fa; }
        QPushButton { padding: 7px 10px; }
        QSpinBox { padding: 4px; }
        QGraphicsView { background: #dde5ef; border: 1px solid #bbc9d8; }
        QLabel { color: #20334a; }
        QCheckBox { padding: 4px 0; }
    ''')
    window = ImageCropperApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    try:
        main()
    except Exception:
        log_crash(*sys.exc_info())
        print(f"\nA crash log was written to: {LOG_PATH}")
        # Keep a plain console open if one exists, so the message is visible
        # even when double-clicked rather than run from an existing terminal.
        if sys.stdin and sys.stdin.isatty():
            input("Press Enter to close...")
        raise
