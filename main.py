import os
import io
import sys
import base64
import cv2
import fitz
import json
import uuid
import time
import shutil
import sqlite3
import zipfile
import tempfile
import traceback
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import numpy as np
from PIL import Image
from cryptography.fernet import Fernet

from PyQt5.QtCore import Qt, QRectF, pyqtSignal, QSize, QPointF
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QMessageBox,
    QListWidget,
    QListWidgetItem,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QInputDialog,
    QLineEdit,
    QComboBox,
    QTabWidget,
    QScrollArea,
    QSplitter,
    QDialog,
    QTextEdit,
    QFrame,
)


APP_NAME = "Smart ID Card Pro (Offline Python Edition)"
APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
FILES_DIR = os.path.join(APP_DIR, "files")
THUMBS_DIR = os.path.join(APP_DIR, "thumbs")
DB_PATH = os.path.join(APP_DIR, "id_cards.db")
KEY_PATH = os.path.join(APP_DIR, "fernet.key")


@dataclass
class RenderedPage:
    page_index: int
    image: np.ndarray  # BGR


class EncryptionManager:
    def __init__(self, key_path: str = KEY_PATH):
        self.key_path = key_path
        os.makedirs(os.path.dirname(self.key_path), exist_ok=True)
        self.fernet = Fernet(self._load_or_create_key())

    def _load_or_create_key(self) -> bytes:
        if os.path.exists(self.key_path):
            with open(self.key_path, "rb") as f:
                return f.read()
        key = Fernet.generate_key()
        with open(self.key_path, "wb") as f:
            f.write(key)
        return key

    def encrypt_bytes(self, data: bytes) -> bytes:
        return self.fernet.encrypt(data)

    def decrypt_bytes(self, encrypted: bytes) -> bytes:
        return self.fernet.decrypt(encrypted)

    def encrypt_file(self, src_path: str, dst_path: str):
        with open(src_path, "rb") as f:
            enc = self.encrypt_bytes(f.read())
        with open(dst_path, "wb") as f:
            f.write(enc)

    def decrypt_file(self, src_path: str, dst_path: str):
        with open(src_path, "rb") as f:
            raw = self.decrypt_bytes(f.read())
        with open(dst_path, "wb") as f:
            f.write(raw)


class DatabaseManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS id_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                type TEXT,
                created_at TEXT,
                pdf_path TEXT,
                output_path TEXT,
                dpi INTEGER,
                format TEXT
            )
            """
        )
        self.conn.commit()

    def add_record(self, name: str, card_type: str, pdf_path: str, output_path: str, dpi: int, out_format: str) -> int:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO id_cards(name, type, created_at, pdf_path, output_path, dpi, format)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, card_type, datetime.utcnow().isoformat(), pdf_path, output_path, dpi, out_format),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_all_records(self) -> List[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM id_cards ORDER BY id DESC")
        return cur.fetchall()

    def get_record(self, record_id: int) -> Optional[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM id_cards WHERE id=?", (record_id,))
        return cur.fetchone()

    def delete_record(self, record_id: int):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM id_cards WHERE id=?", (record_id,))
        self.conn.commit()


class PDFHandler:
    def __init__(self):
        self.doc = None
        self.pdf_path = None

    def open_pdf(self, path: str, password: Optional[str] = None):
        self.doc = fitz.open(path)
        if self.doc.needs_pass:
            if not password:
                raise ValueError("PDF is password protected")
            if not self.doc.authenticate(password):
                raise ValueError("Invalid PDF password")
        self.pdf_path = path

    def is_protected(self, path: str) -> bool:
        doc = fitz.open(path)
        needs = doc.needs_pass
        doc.close()
        return needs

    def render_pages(self, scale: float = 1.3) -> List[RenderedPage]:
        if not self.doc:
            return []
        matrix = fitz.Matrix(scale, scale)
        pages = []
        for i in range(len(self.doc)):
            page = self.doc[i]
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4:
                img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
            else:
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            pages.append(RenderedPage(i, img))
        return pages

    def close(self):
        if self.doc:
            self.doc.close()
            self.doc = None


class ImageProcessor:
    @staticmethod
    def enhance(image_bgr: np.ndarray) -> np.ndarray:
        denoised = cv2.fastNlMeansDenoisingColored(image_bgr, None, 8, 8, 7, 21)
        lab = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
        l2 = clahe.apply(l)
        merged = cv2.merge((l2, a, b))
        contrast = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
        kernel = np.array([[0, -1, 0], [-1, 5.2, -1], [0, -1, 0]], dtype=np.float32)
        sharp = cv2.filter2D(contrast, -1, kernel)

        gray = cv2.cvtColor(sharp, cv2.COLOR_BGR2GRAY)
        bg = cv2.medianBlur(gray, 35)
        diff = cv2.absdiff(gray, bg)
        norm = cv2.normalize(diff, None, 0, 255, cv2.NORM_MINMAX)
        cleaned = cv2.cvtColor(norm, cv2.COLOR_GRAY2BGR)
        blend = cv2.addWeighted(sharp, 0.75, cleaned, 0.25, 0)
        return blend


class CardGenerator:
    CARD_W_MM = 85.6
    CARD_H_MM = 53.98

    def _mm_to_px(self, mm: float, dpi: int) -> int:
        return max(1, int(round(mm / 25.4 * dpi)))

    def _fit_image(self, image: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
        h, w = image.shape[:2]
        scale = min(target_w / w, target_h / h)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        canvas = np.full((target_h, target_w, 3), 255, dtype=np.uint8)
        x = (target_w - new_w) // 2
        y = (target_h - new_h) // 2
        canvas[y : y + new_h, x : x + new_w] = resized
        return canvas

    def generate(self, front: np.ndarray, back: Optional[np.ndarray], layout: str, dpi: int) -> np.ndarray:
        card_w = self._mm_to_px(self.CARD_W_MM, dpi)
        card_h = self._mm_to_px(self.CARD_H_MM, dpi)

        fimg = self._fit_image(front, card_w, card_h)
        bimg = self._fit_image(back, card_w, card_h) if back is not None else None

        if layout == "Single" or bimg is None:
            return fimg
        if layout == "Horizontal":
            return np.hstack([fimg, bimg])
        if layout == "Vertical":
            return np.vstack([fimg, bimg])
        return fimg

    def export(self, image: np.ndarray, out_path: str, fmt: str, dpi: int):
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        f = fmt.upper()
        if f in {"JPG", "JPEG"}:
            pil.save(out_path, format="JPEG", quality=100, subsampling=0, dpi=(dpi, dpi), optimize=False)
        elif f == "PNG":
            pil.save(out_path, format="PNG", compress_level=0, dpi=(dpi, dpi))
        elif f == "PDF":
            pil.save(out_path, format="PDF", resolution=dpi)
        elif f == "SVG":
            h, w = image.shape[:2]
            with open(out_path, "w", encoding="utf-8") as fobj:
                fobj.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">')
                fobj.write("\n")
                buf = io.BytesIO()
                pil.save(buf, format="PNG", compress_level=0)
                b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                fobj.write('  <desc>Embedded PNG image.</desc>\n')
                fobj.write(f'  <image width="{w}" height="{h}" href="data:image/png;base64,{b64}"/>\n')
                fobj.write("</svg>")
        else:
            raise ValueError(f"Unsupported format: {fmt}")


class BackupManager:
    def __init__(self, app_dir: str = APP_DIR):
        self.app_dir = app_dir

    def create_backup(self, zip_path: str):
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(self.app_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, self.app_dir)
                    zf.write(full_path, arcname=arcname)

    def restore_backup(self, zip_path: str):
        if not zipfile.is_zipfile(zip_path):
            raise ValueError("Invalid backup zip")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(self.app_dir)


class CropGraphicsView(QGraphicsView):
    cropChanged = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pixmap_item = None
        self._origin = QPointF()
        self._rubber = None
        self._crop_rect = QRectF()
        self._drawing = False
        self.scale_factor = 1.0
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)

    def set_image(self, pixmap: QPixmap):
        self.scene.clear()
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.pixmap_item)
        self.scene.setSceneRect(self.pixmap_item.boundingRect())
        self._crop_rect = QRectF(0, 0, pixmap.width(), pixmap.height())
        self._rubber = self.scene.addRect(self._crop_rect, QPen(QColor("red"), 2))
        self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
        self.scale_factor = 1.0
        self.cropChanged.emit(self._crop_rect)

    def wheelEvent(self, event):
        zoom_in = 1.15
        zoom_out = 1 / zoom_in
        if event.angleDelta().y() > 0:
            factor = zoom_in
        else:
            factor = zoom_out
        self.scale_factor *= factor
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.pixmap_item is not None:
            self._drawing = True
            self._origin = self.mapToScene(event.pos())
            if self._rubber:
                self.scene.removeItem(self._rubber)
            self._rubber = self.scene.addRect(QRectF(self._origin, self._origin), QPen(QColor("red"), 2))
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drawing and self._rubber:
            current = self.mapToScene(event.pos())
            rect = QRectF(self._origin, current).normalized()
            bounds = self.pixmap_item.boundingRect()
            rect = rect.intersected(bounds)
            self._rubber.setRect(rect)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drawing and self._rubber:
            self._drawing = False
            rect = self._rubber.rect()
            if rect.width() > 5 and rect.height() > 5:
                self._crop_rect = rect
                self.cropChanged.emit(self._crop_rect)
        super().mouseReleaseEvent(event)

    def get_crop_rect(self) -> QRectF:
        return self._crop_rect


class DetailDialog(QDialog):
    editRequested = pyqtSignal(int)

    def __init__(self, record: sqlite3.Row, db: DatabaseManager, enc: EncryptionManager, parent=None):
        super().__init__(parent)
        self.record = record
        self.db = db
        self.enc = enc
        self.setWindowTitle(f"History Detail - #{record['id']}")
        self.resize(960, 600)

        layout = QVBoxLayout(self)
        previews = QHBoxLayout()

        self.pdf_preview = QLabel("Original PDF")
        self.pdf_preview.setFixedSize(420, 250)
        self.pdf_preview.setFrameShape(QFrame.StyledPanel)
        self.pdf_preview.setAlignment(Qt.AlignCenter)
        previews.addWidget(self.pdf_preview)

        self.out_preview = QLabel("Generated ID")
        self.out_preview.setFixedSize(420, 250)
        self.out_preview.setFrameShape(QFrame.StyledPanel)
        self.out_preview.setAlignment(Qt.AlignCenter)
        previews.addWidget(self.out_preview)

        layout.addLayout(previews)

        meta = QTextEdit()
        meta.setReadOnly(True)
        meta.setFixedHeight(160)
        meta.setText(json.dumps({k: record[k] for k in record.keys()}, indent=2))
        layout.addWidget(meta)

        btns = QHBoxLayout()
        edit_btn = QPushButton("Edit")
        del_btn = QPushButton("Delete")
        export_btn = QPushButton("Export Again")
        btns.addWidget(edit_btn)
        btns.addWidget(del_btn)
        btns.addWidget(export_btn)
        layout.addLayout(btns)

        edit_btn.clicked.connect(lambda: self.editRequested.emit(record["id"]))
        del_btn.clicked.connect(self._delete)
        export_btn.clicked.connect(self._export_again)

        self._load_previews()

    def _load_previews(self):
        try:
            tmpdir = tempfile.mkdtemp(prefix="sidp_hist_")
            pdf_tmp = os.path.join(tmpdir, "source.pdf")
            out_tmp = os.path.join(tmpdir, "out.bin")

            if os.path.exists(self.record["pdf_path"]):
                self.enc.decrypt_file(self.record["pdf_path"], pdf_tmp)
                doc = fitz.open(pdf_tmp)
                page = doc[0]
                pix = page.get_pixmap(matrix=fitz.Matrix(0.7, 0.7), alpha=False)
                qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
                self.pdf_preview.setPixmap(QPixmap.fromImage(qimg.copy()).scaled(self.pdf_preview.size(), Qt.KeepAspectRatio))
                doc.close()

            if os.path.exists(self.record["output_path"]):
                self.enc.decrypt_file(self.record["output_path"], out_tmp)
                pix = QPixmap(out_tmp)
                if not pix.isNull():
                    self.out_preview.setPixmap(pix.scaled(self.out_preview.size(), Qt.KeepAspectRatio))
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass

    def _delete(self):
        if QMessageBox.question(self, "Confirm", "Delete this item?") != QMessageBox.Yes:
            return
        for p in [self.record["pdf_path"], self.record["output_path"]]:
            if p and os.path.exists(p):
                os.remove(p)
        self.db.delete_record(self.record["id"])
        QMessageBox.information(self, "Deleted", "Record deleted.")
        self.accept()

    def _export_again(self):
        save_path, _ = QFileDialog.getSaveFileName(self, "Export Again", "", "All Files (*.*)")
        if not save_path:
            return
        try:
            self.enc.decrypt_file(self.record["output_path"], save_path)
            QMessageBox.information(self, "Done", "Export successful.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1440, 900)

        for d in [APP_DIR, FILES_DIR, THUMBS_DIR]:
            os.makedirs(d, exist_ok=True)

        self.enc = EncryptionManager()
        self.db = DatabaseManager()
        self.pdf = PDFHandler()
        self.processor = ImageProcessor()
        self.generator = CardGenerator()
        self.backup = BackupManager()

        self.pages: List[RenderedPage] = []
        self.front_img: Optional[np.ndarray] = None
        self.back_img: Optional[np.ndarray] = None
        self.current_source_page: Optional[np.ndarray] = None

        self._init_ui()
        self.refresh_history()

    def _init_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        h = QHBoxLayout(root)

        sidebar = QVBoxLayout()
        sidebar.setAlignment(Qt.AlignTop)
        self.btn_create = QPushButton("Create ID")
        self.btn_history = QPushButton("History")
        self.btn_backup = QPushButton("Backup")
        for b in [self.btn_create, self.btn_history, self.btn_backup]:
            b.setMinimumHeight(46)
            sidebar.addWidget(b)

        h.addLayout(sidebar, 1)

        self.tabs = QTabWidget()
        h.addWidget(self.tabs, 9)

        self.create_tab = self._build_create_tab()
        self.history_tab = self._build_history_tab()
        self.backup_tab = self._build_backup_tab()

        self.tabs.addTab(self.create_tab, "Create")
        self.tabs.addTab(self.history_tab, "History")
        self.tabs.addTab(self.backup_tab, "Backup")

        self.btn_create.clicked.connect(lambda: self.tabs.setCurrentWidget(self.create_tab))
        self.btn_history.clicked.connect(lambda: self.tabs.setCurrentWidget(self.history_tab))
        self.btn_backup.clicked.connect(lambda: self.tabs.setCurrentWidget(self.backup_tab))

    def _build_create_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        top = QHBoxLayout()
        upload_btn = QPushButton("Upload PDF")
        upload_btn.clicked.connect(self.upload_pdf)
        top.addWidget(upload_btn)

        self.layout_combo = QComboBox()
        self.layout_combo.addItems(["Single", "Horizontal", "Vertical"])
        self.dpi_combo = QComboBox()
        self.dpi_combo.addItems(["300", "600", "1200"])
        self.dpi_combo.setCurrentText("600")
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPEG", "PDF", "SVG"])

        top.addWidget(QLabel("Layout"))
        top.addWidget(self.layout_combo)
        top.addWidget(QLabel("DPI"))
        top.addWidget(self.dpi_combo)
        top.addWidget(QLabel("Format"))
        top.addWidget(self.format_combo)
        top.addStretch()
        layout.addLayout(top)

        split = QSplitter(Qt.Horizontal)

        left = QWidget()
        left_l = QVBoxLayout(left)
        left_l.addWidget(QLabel("PDF Pages"))
        self.thumb_list = QListWidget()
        self.thumb_list.setIconSize(QSize(140, 170))
        self.thumb_list.itemClicked.connect(self.select_page)
        left_l.addWidget(self.thumb_list)
        split.addWidget(left)

        mid = QWidget()
        mid_l = QVBoxLayout(mid)
        mid_l.addWidget(QLabel("Crop / Zoom (mouse wheel + drag)"))
        self.editor_view = CropGraphicsView()
        mid_l.addWidget(self.editor_view)

        selectors = QHBoxLayout()
        btn_set_front = QPushButton("Set as Front")
        btn_set_back = QPushButton("Set as Back")
        btn_set_front.clicked.connect(self.set_front)
        btn_set_back.clicked.connect(self.set_back)
        selectors.addWidget(btn_set_front)
        selectors.addWidget(btn_set_back)
        mid_l.addLayout(selectors)

        split.addWidget(mid)

        right = QWidget()
        right_l = QVBoxLayout(right)
        right_l.addWidget(QLabel("Preview"))
        self.preview = QLabel("No preview")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(400, 300)
        self.preview.setFrameShape(QFrame.StyledPanel)
        right_l.addWidget(self.preview)

        btn_preview = QPushButton("Generate Preview")
        btn_export = QPushButton("Export & Save")
        btn_preview.clicked.connect(self.generate_preview)
        btn_export.clicked.connect(self.export_and_save)
        right_l.addWidget(btn_preview)
        right_l.addWidget(btn_export)
        right_l.addStretch()

        split.addWidget(right)
        split.setSizes([250, 700, 400])

        layout.addWidget(split)
        return w

    def _build_history_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        self.history_grid = QGridLayout()
        container = QWidget()
        container.setLayout(self.history_grid)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        v.addWidget(scroll)
        return w

    def _build_backup_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        create_btn = QPushButton("Create Backup")
        restore_btn = QPushButton("Restore Backup")
        create_btn.clicked.connect(self.create_backup)
        restore_btn.clicked.connect(self.restore_backup)

        layout.addWidget(create_btn)
        layout.addWidget(restore_btn)
        layout.addStretch()
        return w

    def upload_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if not path:
            return
        try:
            password = None
            if self.pdf.is_protected(path):
                password, ok = QInputDialog.getText(self, "Password", "Enter PDF password:", QLineEdit.Password)
                if not ok:
                    return
            self.pdf.open_pdf(path, password=password)
            self.pages = self.pdf.render_pages(scale=1.2)
            self.thumb_list.clear()
            for p in self.pages:
                qimg = self.cv_to_qimage(p.image)
                pix = QPixmap.fromImage(qimg)
                icon = QIcon(pix.scaled(140, 170, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                item = QListWidgetItem(icon, f"Page {p.page_index + 1}")
                item.setData(Qt.UserRole, p.page_index)
                self.thumb_list.addItem(item)

            with open(path, "rb") as f:
                raw = f.read()
            enc_path = os.path.join(FILES_DIR, f"pdf_{uuid.uuid4().hex}.bin")
            with open(enc_path, "wb") as f:
                f.write(self.enc.encrypt_bytes(raw))
            self.current_pdf_encrypted = enc_path
            QMessageBox.information(self, "Loaded", "PDF loaded successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open PDF: {e}")

    def select_page(self, item: QListWidgetItem):
        idx = item.data(Qt.UserRole)
        page = next((p for p in self.pages if p.page_index == idx), None)
        if not page:
            return
        self.current_source_page = page.image.copy()
        pix = QPixmap.fromImage(self.cv_to_qimage(page.image))
        self.editor_view.set_image(pix)

    def set_front(self):
        img = self.get_current_cropped_image()
        if img is None:
            QMessageBox.warning(self, "Warning", "Select and crop a page first")
            return
        self.front_img = self.processor.enhance(img)
        QMessageBox.information(self, "Front", "Front side captured.")

    def set_back(self):
        img = self.get_current_cropped_image()
        if img is None:
            QMessageBox.warning(self, "Warning", "Select and crop a page first")
            return
        self.back_img = self.processor.enhance(img)
        QMessageBox.information(self, "Back", "Back side captured.")

    def get_current_cropped_image(self) -> Optional[np.ndarray]:
        if self.current_source_page is None:
            return None
        rect = self.editor_view.get_crop_rect()
        x = max(0, int(rect.x()))
        y = max(0, int(rect.y()))
        w = max(1, int(rect.width()))
        h = max(1, int(rect.height()))
        img = self.current_source_page
        x2 = min(img.shape[1], x + w)
        y2 = min(img.shape[0], y + h)
        if x2 <= x or y2 <= y:
            return None
        return img[y:y2, x:x2].copy()

    def generate_preview(self):
        if self.front_img is None:
            QMessageBox.warning(self, "Missing", "Please set front side first.")
            return
        layout = self.layout_combo.currentText()
        dpi = int(self.dpi_combo.currentText())
        composed = self.generator.generate(self.front_img, self.back_img, layout, dpi)
        self.current_generated = composed
        pix = QPixmap.fromImage(self.cv_to_qimage(composed))
        self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def export_and_save(self):
        if not hasattr(self, "current_generated"):
            self.generate_preview()
            if not hasattr(self, "current_generated"):
                return

        out_fmt = self.format_combo.currentText().upper()
        ext = "jpg" if out_fmt == "JPEG" else out_fmt.lower()
        out_path, _ = QFileDialog.getSaveFileName(self, "Save Output", f"id_card.{ext}", f"*.{ext}")
        if not out_path:
            return

        try:
            dpi = int(self.dpi_combo.currentText())
            self.generator.export(self.current_generated, out_path, out_fmt, dpi)

            with open(out_path, "rb") as f:
                data = f.read()
            enc_out = os.path.join(FILES_DIR, f"output_{uuid.uuid4().hex}.bin")
            with open(enc_out, "wb") as f:
                f.write(self.enc.encrypt_bytes(data))

            name, ok = QInputDialog.getText(self, "Name", "Card name/customer:")
            if not ok or not name.strip():
                name = f"ID-{int(time.time())}"
            layout = self.layout_combo.currentText()
            rec_id = self.db.add_record(name.strip(), layout, self.current_pdf_encrypted, enc_out, dpi, out_fmt)
            QMessageBox.information(self, "Saved", f"Exported and saved record #{rec_id}")
            self.refresh_history()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def refresh_history(self):
        while self.history_grid.count():
            item = self.history_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        records = self.db.get_all_records()
        cols = 3
        for i, row in enumerate(records):
            card = QFrame()
            card.setFrameShape(QFrame.StyledPanel)
            v = QVBoxLayout(card)

            thumb = QLabel("No Thumbnail")
            thumb.setFixedSize(300, 170)
            thumb.setAlignment(Qt.AlignCenter)
            thumb.setStyleSheet("background:#fafafa;")

            try:
                tmp = tempfile.mktemp(suffix=".img")
                self.enc.decrypt_file(row["output_path"], tmp)
                pix = QPixmap(tmp)
                if not pix.isNull():
                    thumb.setPixmap(pix.scaled(thumb.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass

            title = QLabel(f"<b>{row['name']}</b>")
            date = QLabel(row["created_at"])
            btn = QPushButton("Open")
            btn.clicked.connect(lambda _, rid=row["id"]: self.open_history_detail(rid))

            v.addWidget(thumb)
            v.addWidget(title)
            v.addWidget(date)
            v.addWidget(btn)

            r, c = divmod(i, cols)
            self.history_grid.addWidget(card, r, c)

    def open_history_detail(self, record_id: int):
        rec = self.db.get_record(record_id)
        if not rec:
            return
        dlg = DetailDialog(rec, self.db, self.enc, self)
        dlg.editRequested.connect(self.reload_from_history)
        dlg.exec_()
        self.refresh_history()

    def reload_from_history(self, record_id: int):
        rec = self.db.get_record(record_id)
        if not rec:
            return
        try:
            tmp_pdf = tempfile.mktemp(suffix=".pdf")
            self.enc.decrypt_file(rec["pdf_path"], tmp_pdf)
            self.pdf.close()
            self.pdf.open_pdf(tmp_pdf)
            self.pages = self.pdf.render_pages(scale=1.2)
            self.thumb_list.clear()
            for p in self.pages:
                icon = QIcon(QPixmap.fromImage(self.cv_to_qimage(p.image)).scaled(140, 170, Qt.KeepAspectRatio))
                item = QListWidgetItem(icon, f"Page {p.page_index + 1}")
                item.setData(Qt.UserRole, p.page_index)
                self.thumb_list.addItem(item)
            self.current_pdf_encrypted = rec["pdf_path"]
            self.tabs.setCurrentWidget(self.create_tab)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not reload: {e}")

    def create_backup(self):
        path, _ = QFileDialog.getSaveFileName(self, "Create Backup", "backup.zip", "Zip Files (*.zip)")
        if not path:
            return
        try:
            self.backup.create_backup(path)
            QMessageBox.information(self, "Done", "Backup created.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def restore_backup(self):
        path, _ = QFileDialog.getOpenFileName(self, "Restore Backup", "", "Zip Files (*.zip)")
        if not path:
            return
        if QMessageBox.question(self, "Confirm", "This will overwrite local data. Continue?") != QMessageBox.Yes:
            return
        try:
            self.backup.restore_backup(path)
            QMessageBox.information(self, "Done", "Backup restored. Restart app recommended.")
            self.refresh_history()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    @staticmethod
    def cv_to_qimage(img_bgr: np.ndarray) -> QImage:
        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        return QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        traceback.print_exc()
        QMessageBox.critical(None, APP_NAME, f"Fatal error: {exc}")
