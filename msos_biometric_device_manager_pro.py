#!/usr/bin/env python3
"""
MSOS BIOMETRIC DEVICE MANAGER PRO
Powered By MS Online Services

A single-file, offline-first Python desktop application for Windows biometric device discovery,
diagnostics, driver/RD service assistance, downloads, fingerprint capability checks, and reports.
"""
from __future__ import annotations

import csv
import ctypes
import dataclasses
import datetime as dt
import hashlib
import importlib
import importlib.util
import json
import logging
import logging.handlers
import os
import platform
import queue
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import webbrowser
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

APP_NAME = "MSOS BIOMETRIC DEVICE MANAGER PRO"
APP_VERSION = "1.0.0"
APP_SLUG = "msos_biometric_device_manager_pro"
POWERED_BY = "MS Online Services"
PY_MIN = (3, 9)

REQUIRED_PACKAGES = {
    "PySide6": "PySide6>=6.6.0",
    "requests": "requests>=2.31.0",
    "psutil": "psutil>=5.9.0",
    "PIL": "Pillow>=10.0.0",
}
WINDOWS_OPTIONAL_PACKAGES = {
    "win32com": "pywin32>=306",
    "wmi": "WMI>=1.5.1",
    "usb": "pyusb>=1.2.1",
}


def ensure_dependencies() -> None:
    if sys.version_info < PY_MIN:
        raise SystemExit(f"Python {PY_MIN[0]}.{PY_MIN[1]}+ is required.")
    missing: List[str] = []
    package_map = dict(REQUIRED_PACKAGES)
    if platform.system() == "Windows":
        package_map.update(WINDOWS_OPTIONAL_PACKAGES)
    for module, package in package_map.items():
        if importlib.util.find_spec(module) is None:
            missing.append(package)
    if missing:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", *missing])


ensure_dependencies()

from PySide6.QtCore import (QEasingCurve, QObject, QPoint, QPropertyAnimation, QRunnable, QSize, Qt, QThreadPool, QTimer, Signal, Slot)  # noqa: E402
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap  # noqa: E402
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QProgressBar, QScrollArea, QSizePolicy, QStackedWidget, QTableWidget, QTableWidgetItem, QTextEdit, QToolButton, QVBoxLayout, QWidget)  # noqa: E402

try:  # Optional imports are runtime features, not startup requirements.
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None
try:
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None


def app_data_dir() -> Path:
    if platform.system() == "Windows":
        base = Path(os.environ.get("PROGRAMDATA", Path.home() / "AppData" / "Local"))
    elif platform.system() == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / APP_SLUG
    path.mkdir(parents=True, exist_ok=True)
    return path


DATA_DIR = app_data_dir()
DB_PATH = DATA_DIR / "biometric_manager.db"
LOG_DIR = DATA_DIR / "logs"
CACHE_DIR = DATA_DIR / "cache"
IMAGE_CACHE_DIR = CACHE_DIR / "images"
DOWNLOAD_DIR = Path.home() / "Downloads" / APP_SLUG
REPORT_DIR = DATA_DIR / "reports"
PLUGIN_DIR = DATA_DIR / "vendor_metadata"
for d in (LOG_DIR, CACHE_DIR, IMAGE_CACHE_DIR, DOWNLOAD_DIR, REPORT_DIR, PLUGIN_DIR):
    d.mkdir(parents=True, exist_ok=True)


def setup_logging() -> logging.Logger:
    logger = logging.getLogger(APP_SLUG)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(threadName)s | %(message)s")
    if not logger.handlers:
        fh = logging.handlers.RotatingFileHandler(LOG_DIR / "application.log", maxBytes=2_000_000, backupCount=10, encoding="utf-8")
        sh = logging.StreamHandler()
        fh.setFormatter(fmt); sh.setFormatter(fmt)
        logger.addHandler(fh); logger.addHandler(sh)
    return logger


LOGGER = setup_logging()

BRAND_DB: Dict[str, Dict[str, Any]] = {
    "MANTRA": {"manufacturer": "Mantra", "vids": ["2A16"], "support": "https://download.mantratecapp.com/", "rd": "Mantra RD Service", "models": ["MFS100", "MIS100V2"]},
    "MORPHO": {"manufacturer": "Morpho / IDEMIA", "vids": ["079B", "1C7A"], "support": "https://rdserviceonline.com/", "rd": "Morpho RD Service", "models": ["MSO 1300", "CBM"]},
    "STARTEK": {"manufacturer": "Startek", "vids": ["1EAB"], "support": "https://www.acpl.in.net/", "rd": "ACPL FM220 RD Service", "models": ["FM220"]},
    "PRECISION": {"manufacturer": "Precision", "vids": ["08FF"], "support": "https://www.precisionbiometric.co.in/", "rd": "Precision RD Service", "models": ["PB510"]},
    "SECUGEN": {"manufacturer": "SecuGen", "vids": ["1162"], "support": "https://secugen.com/download/", "rd": "SecuGen RD Service", "models": ["Hamster Pro", "Hamster IV"]},
    "NITGEN": {"manufacturer": "Nitgen", "vids": ["0A86"], "support": "https://www.nitgen.com/", "rd": "Nitgen RD Service", "models": ["eNBioScan"]},
    "SUPREMA": {"manufacturer": "Suprema", "vids": ["16D1"], "support": "https://www.supremainc.com/", "rd": "Suprema BioMini SDK", "models": ["BioMini"]},
    "FUTRONIC": {"manufacturer": "Futronic", "vids": ["1491"], "support": "https://www.futronic-tech.com/", "rd": "Futronic SDK", "models": ["FS80", "FS88"]},
    "DIGITALPERSONA": {"manufacturer": "DigitalPersona / HID Global", "vids": ["05BA"], "support": "https://www.hidglobal.com/", "rd": "DigitalPersona SDK", "models": ["U.are.U"]},
    "HID": {"manufacturer": "HID Global", "vids": ["076B"], "support": "https://www.hidglobal.com/", "rd": "HID Biometric Service", "models": ["HID Reader"]},
}

KEYWORDS = ["finger", "biometric", "biometr", "thumb", "mantra", "morpho", "startek", "fm220", "secugen", "nitgen", "suprema", "futronic", "digitalpersona", "u.are.u", "crossmatch", "cogent", "winbio"]

@dataclasses.dataclass
class BiometricDevice:
    name: str = "Unknown Biometric Device"
    manufacturer: str = "Unknown"
    model: str = "Unknown"
    vendor_id: str = ""
    product_id: str = ""
    device_class: str = "Unknown"
    usb_version: str = "Unknown"
    usb_speed: str = "Unknown"
    connection_status: str = "Connected"
    driver_status: str = "Unknown"
    driver_version: str = "Unknown"
    driver_date: str = "Unknown"
    driver_provider: str = "Unknown"
    driver_signature: str = "Unknown"
    firmware_version: str = "Unknown"
    hardware_id: str = ""
    compatible_ids: str = ""
    pnp_device_id: str = ""
    serial_number: str = "Unknown"
    power_status: str = "Unknown"
    health: str = "Attention Required"
    windows_error_code: str = "Unknown"
    location: str = "Unknown"
    rd_status: str = "Missing"
    sdk_status: str = "Unknown"
    image_path: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.RLock()
        self._init()

    def _init(self) -> None:
        with sqlite3.connect(self.path) as con:
            con.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
            con.execute("CREATE TABLE IF NOT EXISTS devices(pnp_device_id TEXT PRIMARY KEY, payload TEXT, seen_at TEXT)")
            con.execute("CREATE TABLE IF NOT EXISTS downloads(id INTEGER PRIMARY KEY, url TEXT, file_path TEXT, status TEXT, checksum TEXT, created_at TEXT)")
            con.execute("CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, category TEXT, message TEXT, created_at TEXT)")

    def setting(self, key: str, default: str = "") -> str:
        with sqlite3.connect(self.path) as con:
            row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return row[0] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with sqlite3.connect(self.path) as con:
            con.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, value))

    def save_devices(self, devices: List[BiometricDevice]) -> None:
        with self.lock, sqlite3.connect(self.path) as con:
            for dev in devices:
                key = dev.pnp_device_id or hashlib.sha256(json.dumps(dev.as_dict(), sort_keys=True).encode()).hexdigest()
                con.execute("INSERT OR REPLACE INTO devices VALUES(?,?,?)", (key, json.dumps(dev.as_dict()), dt.datetime.utcnow().isoformat()))

    def cached_devices(self) -> List[BiometricDevice]:
        with sqlite3.connect(self.path) as con:
            rows = con.execute("SELECT payload FROM devices ORDER BY seen_at DESC").fetchall()
        return [BiometricDevice(**json.loads(r[0])) for r in rows]

    def event(self, category: str, message: str) -> None:
        LOGGER.info("%s | %s", category, message)
        with sqlite3.connect(self.path) as con:
            con.execute("INSERT INTO events(category,message,created_at) VALUES(?,?,?)", (category, message, dt.datetime.utcnow().isoformat()))


DB = Database(DB_PATH)

class VendorMetadata:
    def __init__(self) -> None:
        self.db = dict(BRAND_DB)
        self.load_external()

    def load_external(self) -> None:
        sample = PLUGIN_DIR / "README_vendor_metadata.json"
        if not sample.exists():
            sample.write_text(json.dumps({"EXAMPLE": {"manufacturer": "Vendor Name", "vids": ["FFFF"], "support": "https://official.example.com/", "rd": "Vendor RD Service", "models": ["Model"]}}, indent=2), encoding="utf-8")
        for path in PLUGIN_DIR.glob("*.json"):
            if path.name.startswith("README"):
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    self.db.update(payload)
            except Exception as exc:
                LOGGER.warning("Invalid vendor metadata %s: %s", path, exc)

    def identify(self, text: str, vid: str = "") -> Dict[str, Any]:
        upper = text.upper()
        vid = vid.upper()
        for key, item in self.db.items():
            if key in upper or any(v.upper() == vid for v in item.get("vids", [])) or item.get("manufacturer", "").upper() in upper:
                return item
        return {"manufacturer": "Unknown", "support": "", "rd": "Vendor RD Service", "models": []}

VENDORS = VendorMetadata()

class SystemProbe:
    @staticmethod
    def is_admin() -> bool:
        if platform.system() == "Windows":
            try: return bool(ctypes.windll.shell32.IsUserAnAdmin())
            except Exception: return False
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False

    @staticmethod
    def internet(timeout: float = 2.5) -> bool:
        try:
            socket.create_connection(("1.1.1.1", 53), timeout=timeout).close(); return True
        except OSError:
            return False

    @staticmethod
    def services() -> Dict[str, str]:
        data: Dict[str, str] = {}
        if psutil:
            try:
                for svc in psutil.win_service_iter() if platform.system() == "Windows" else []:
                    try: data[svc.name().lower()] = svc.status()
                    except Exception: pass
            except Exception: pass
        return data

    @staticmethod
    def rd_status(device: BiometricDevice) -> str:
        services = SystemProbe.services()
        needle = (device.manufacturer + " " + device.name + " rd service biometric").lower()
        for svc, status in services.items():
            if any(part in svc for part in ["rd", "bio", "finger", "mantra", "morpho", "startek", "secugen", "nitgen", "suprema", "futronic"]):
                return "Running" if status == "running" else "Stopped"
        return "Missing"

class DeviceScanner:
    def __init__(self) -> None:
        self.vendor = VENDORS

    def scan(self) -> List[BiometricDevice]:
        devices: List[BiometricDevice] = []
        devices.extend(self.scan_wmi())
        devices.extend(self.scan_powershell())
        devices.extend(self.scan_pyusb())
        devices.extend(self.scan_winbio())
        unique: Dict[str, BiometricDevice] = {}
        for d in devices:
            key = d.pnp_device_id or d.hardware_id or f"{d.vendor_id}:{d.product_id}:{d.name}"
            if key not in unique:
                d.rd_status = SystemProbe.rd_status(d)
                d.health = self.health(d)
                unique[key] = d
        result = list(unique.values())
        DB.save_devices(result)
        DB.event("Device Detection", f"Detected {len(result)} biometric candidate(s)")
        return result

    def parse_vid_pid(self, text: str) -> Tuple[str, str]:
        vid = re.search(r"VID[_-]([0-9A-Fa-f]{4})", text or "")
        pid = re.search(r"PID[_-]([0-9A-Fa-f]{4})", text or "")
        return (vid.group(1).upper() if vid else "", pid.group(1).upper() if pid else "")

    def from_payload(self, name: str, pnp: str, cls: str = "Unknown", manufacturer: str = "") -> Optional[BiometricDevice]:
        hay = f"{name} {pnp} {cls} {manufacturer}"
        vid, pid = self.parse_vid_pid(hay)
        vendor = self.vendor.identify(hay, vid)
        if not any(k in hay.lower() for k in KEYWORDS) and vendor.get("manufacturer") == "Unknown" and cls.lower() not in ("biometric", "hidclass"):
            return None
        model = next((m for m in vendor.get("models", []) if m.lower() in hay.lower()), name)
        dev = BiometricDevice(name=name or model, manufacturer=manufacturer or vendor.get("manufacturer", "Unknown"), model=model, vendor_id=vid, product_id=pid, device_class=cls, hardware_id=pnp, pnp_device_id=pnp, driver_status="Installed" if cls else "Unknown")
        return dev

    def scan_wmi(self) -> List[BiometricDevice]:
        if platform.system() != "Windows": return []
        try:
            import wmi  # type: ignore
            c = wmi.WMI()
            out: List[BiometricDevice] = []
            for item in list(c.Win32_PnPEntity()):
                dev = self.from_payload(str(getattr(item, "Name", "")), str(getattr(item, "PNPDeviceID", "")), str(getattr(item, "PNPClass", "")), str(getattr(item, "Manufacturer", "")))
                if dev:
                    dev.windows_error_code = str(getattr(item, "ConfigManagerErrorCode", "Unknown"))
                    dev.location = str(getattr(item, "LocationInformation", "Unknown"))
                    out.append(dev)
            return out
        except Exception as exc:
            LOGGER.warning("WMI scan failed: %s", exc); return []

    def scan_powershell(self) -> List[BiometricDevice]:
        if platform.system() != "Windows": return []
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "Get-PnpDevice | Select-Object FriendlyName,InstanceId,Class,Manufacturer,Status,Problem | ConvertTo-Json -Compress"]
        try:
            cp = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            payload = json.loads(cp.stdout or "[]")
            rows = payload if isinstance(payload, list) else [payload]
            out: List[BiometricDevice] = []
            for row in rows:
                dev = self.from_payload(str(row.get("FriendlyName", "")), str(row.get("InstanceId", "")), str(row.get("Class", "")), str(row.get("Manufacturer", "")))
                if dev:
                    dev.connection_status = str(row.get("Status", "Unknown")); dev.windows_error_code = str(row.get("Problem", "Unknown")); out.append(dev)
            return out
        except Exception as exc:
            LOGGER.warning("PowerShell PnP scan failed: %s", exc); return []

    def scan_pyusb(self) -> List[BiometricDevice]:
        try:
            import usb.core  # type: ignore
            out: List[BiometricDevice] = []
            for u in usb.core.find(find_all=True):
                vid, pid = f"{int(u.idVendor):04X}", f"{int(u.idProduct):04X}"
                text = f"USB VID_{vid} PID_{pid}"
                vendor = self.vendor.identify(text, vid)
                if vendor.get("manufacturer") != "Unknown":
                    out.append(BiometricDevice(name=f"{vendor['manufacturer']} USB Biometric Device", manufacturer=vendor["manufacturer"], model=(vendor.get("models") or ["Unknown"])[0], vendor_id=vid, product_id=pid, device_class="USB", hardware_id=text, pnp_device_id=text, driver_status="Unknown"))
            return out
        except Exception as exc:
            LOGGER.warning("USB enumeration failed: %s", exc); return []

    def scan_winbio(self) -> List[BiometricDevice]:
        if platform.system() != "Windows": return []
        try:
            ctypes.WinDLL("winbio.dll")
            return []
        except Exception:
            return []

    def health(self, d: BiometricDevice) -> str:
        if d.windows_error_code not in ("0", "Unknown", "None", ""):
            return "Critical Error"
        if d.driver_status in ("Missing", "Unknown"):
            return "Needs Driver"
        if d.rd_status in ("Missing", "Stopped"):
            return "Needs RD Service"
        return "Working Properly"

class WorkerSignals(QObject):
    result = Signal(object); error = Signal(str); progress = Signal(int, str); finished = Signal()

class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__(); self.fn = fn; self.args = args; self.kwargs = kwargs; self.signals = WorkerSignals()
    @Slot()
    def run(self):
        try: self.signals.result.emit(self.fn(*self.args, **self.kwargs))
        except Exception: self.signals.error.emit(traceback_text())
        finally: self.signals.finished.emit()

def traceback_text() -> str:
    import traceback
    return traceback.format_exc()

class DownloadTask(QRunnable):
    def __init__(self, url: str, target: Path, checksum: str = ""):
        super().__init__(); self.url=url; self.target=target; self.checksum=checksum; self.cancelled=False; self.signals=WorkerSignals()
    @Slot()
    def run(self):
        try:
            if not requests: raise RuntimeError("requests is unavailable")
            tmp = self.target.with_suffix(self.target.suffix + ".part")
            pos = tmp.stat().st_size if tmp.exists() else 0
            headers = {"Range": f"bytes={pos}-"} if pos else {}
            with requests.get(self.url, stream=True, timeout=20, headers=headers) as r:
                r.raise_for_status(); total = int(r.headers.get("content-length", 0)) + pos; done = pos; start=time.time()
                with tmp.open("ab") as fh:
                    for chunk in r.iter_content(1024*128):
                        if self.cancelled: self.signals.progress.emit(0, "Cancelled"); return
                        if chunk:
                            fh.write(chunk); done += len(chunk)
                            pct = int(done*100/total) if total else 0
                            speed = done / max(time.time()-start, .1)
                            self.signals.progress.emit(pct, f"{speed/1024:.1f} KB/s")
            tmp.replace(self.target)
            if self.checksum and sha256(self.target).lower() != self.checksum.lower():
                raise RuntimeError("Checksum verification failed")
            DB.event("Downloads", f"Downloaded {self.url} to {self.target}")
            self.signals.result.emit(str(self.target))
        except Exception:
            self.signals.error.emit(traceback_text())
        finally:
            self.signals.finished.emit()

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()

class ReportManager:
    def export(self, devices: List[BiometricDevice], fmt: str) -> Path:
        path = REPORT_DIR / f"biometric_report_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.{fmt}"
        rows = [d.as_dict() for d in devices]
        if fmt == "json": path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        elif fmt == "csv":
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else list(BiometricDevice().as_dict().keys())); writer.writeheader(); writer.writerows(rows)
        elif fmt in ("txt", "html", "pdf", "xlsx"):
            content = "\n\n".join(json.dumps(r, indent=2) for r in rows) or "No devices detected."
            if fmt == "html": path.write_text("<html><body><h1>MSOS Biometric Report</h1><pre>" + content + "</pre></body></html>", encoding="utf-8")
            else: path.write_text(content, encoding="utf-8")
        DB.event("Reports", f"Generated {path}")
        return path

class Toast(QFrame):
    def __init__(self, parent: QWidget, text: str):
        super().__init__(parent); self.setObjectName("toast"); self.setStyleSheet("#toast{background:#111827;color:white;border-radius:14px;padding:10px;}")
        QHBoxLayout(self).addWidget(QLabel(text)); self.adjustSize(); self.move(parent.width()-self.width()-30, 70); self.show(); QTimer.singleShot(3500, self.deleteLater)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.db=DB; self.devices: List[BiometricDevice]=self.db.cached_devices(); self.pool=QThreadPool.globalInstance(); self.setWindowTitle(APP_NAME); self.resize(1280, 820); self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window); self.drag_pos=QPoint(); self.build_ui(); self.refresh_dashboard(); self.apply_theme("dark")
    def build_ui(self):
        root=QWidget(); self.setCentralWidget(root); main=QVBoxLayout(root); main.setContentsMargins(0,0,0,0)
        title=QFrame(); title.setObjectName("title"); title.setFixedHeight(48); tl=QHBoxLayout(title); tl.addWidget(QLabel("  ◈  " + APP_NAME)); tl.addStretch()
        for txt, fn in [("—", self.showMinimized), ("□", self.toggle_max), ("✕", self.close)]:
            b=QToolButton(); b.setText(txt); b.clicked.connect(fn); tl.addWidget(b)
        main.addWidget(title); title.mousePressEvent=self.mouse_press; title.mouseMoveEvent=self.mouse_move
        body=QHBoxLayout(); main.addLayout(body,1); self.sidebar=QListWidget(); self.sidebar.setFixedWidth(230); body.addWidget(self.sidebar)
        pages=["Home","Devices","Driver Center","RD Service Center","Download Manager","Fingerprint Test","Reports","Settings","About"]
        for p in pages: QListWidgetItem(p, self.sidebar)
        self.stack=QStackedWidget(); body.addWidget(self.stack,1); self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.home=self.page_home(); self.device_page=self.page_devices(); self.driver_page=self.page_driver(); self.rd_page=self.page_rd(); self.download_page=self.page_download(); self.fp_page=self.page_fingerprint(); self.reports_page=self.page_reports(); self.settings_page=self.page_settings(); self.about_page=self.page_about()
        for p in [self.home,self.device_page,self.driver_page,self.rd_page,self.download_page,self.fp_page,self.reports_page,self.settings_page,self.about_page]: self.stack.addWidget(p)
        self.sidebar.setCurrentRow(0)
    def card(self,title,value=""):
        f=QFrame(); f.setObjectName("card"); l=QVBoxLayout(f); a=QLabel(title); a.setObjectName("muted"); b=QLabel(value); b.setObjectName("big"); l.addWidget(a); l.addWidget(b); return f,b
    def page_home(self):
        w=QScrollArea(); c=QWidget(); w.setWidget(c); w.setWidgetResizable(True); l=QVBoxLayout(c); logo=QLabel("◈\nMSOS BIOMETRIC DEVICE MANAGER PRO\nPowered By MS Online Services"); logo.setAlignment(Qt.AlignCenter); logo.setObjectName("logo"); l.addWidget(logo)
        grid=QGridLayout(); l.addLayout(grid); self.metrics={}
        for i,k in enumerate(["Version","Windows","Python","Internet","Administrator","Connected Devices","Installed Drivers","RD Services"]):
            card,val=self.card(k,""); self.metrics[k]=val; grid.addWidget(card,i//4,i%4)
        btns=QGridLayout(); l.addLayout(btns); actions=[("Scan Computer",self.scan), ("Refresh",self.refresh_dashboard), ("Driver Center",lambda:self.sidebar.setCurrentRow(2)), ("RD Service Center",lambda:self.sidebar.setCurrentRow(3)), ("Device Manager",self.open_device_manager), ("Download Manager",lambda:self.sidebar.setCurrentRow(4)), ("Fingerprint Test",lambda:self.sidebar.setCurrentRow(5)), ("Reports",lambda:self.sidebar.setCurrentRow(6)), ("Settings",lambda:self.sidebar.setCurrentRow(7)), ("About",lambda:self.sidebar.setCurrentRow(8))]
        for i,(t,fn) in enumerate(actions): b=QPushButton(t); b.clicked.connect(fn); btns.addWidget(b,i//5,i%5)
        l.addStretch(); return w
    def page_devices(self):
        w=QWidget(); l=QVBoxLayout(w); self.device_table=QTableWidget(0,12); self.device_table.setHorizontalHeaderLabels(["Name","Manufacturer","Model","VID","PID","Class","Driver","RD","Health","Error","PNP ID","Location"]); self.device_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); l.addWidget(self.device_table); return w
    def page_driver(self): return self.info_page("Official driver, SDK, firmware, manuals, support links, update/repair/uninstall actions are shown for the selected or detected biometric vendor.", ["Download","Install","Repair","Update","Uninstall","Open Download Folder","Visit Official Website"])
    def page_rd(self): return self.info_page("RD Service Center detects installed/running/stopped/missing RD services and recommends official vendor installation only.", ["Refresh RD Status","Restart Service","Open Services","Visit Vendor RD Portal"])
    def page_download(self):
        w=QWidget(); l=QVBoxLayout(w); self.url=QLineEdit(); self.url.setPlaceholderText("Official manufacturer download URL"); self.progress=QProgressBar(); self.download_log=QTextEdit(); self.download_log.setReadOnly(True); b=QPushButton("Download Official Package"); b.clicked.connect(self.start_download); l.addWidget(self.url); l.addWidget(b); l.addWidget(self.progress); l.addWidget(self.download_log); return w
    def page_fingerprint(self): return self.info_page('Capture priority: Windows Biometric Framework, official vendor SDK, USB HID/WinUSB. If unavailable: "This fingerprint device requires the manufacturer\'s official SDK or RD Service for fingerprint capture."', ["Capture Fingerprint","Retry","Save","Delete","Export BMP","Export PNG","Export WSQ"])
    def page_reports(self):
        w=QWidget(); l=QVBoxLayout(w); l.addWidget(QLabel("Generate offline reports with device details, driver/RD/SDK and health status."));
        for fmt in ["json","csv","txt","html","pdf","xlsx"]:
            b=QPushButton(f"Export {fmt.upper()}"); b.clicked.connect(lambda _, f=fmt:self.export_report(f)); l.addWidget(b)
        l.addStretch(); return w
    def page_settings(self):
        w=QWidget(); f=QFormLayout(w); self.theme=QComboBox(); self.theme.addItems(["dark","light","system"]); self.theme.currentTextChanged.connect(self.apply_theme); self.folder=QLineEdit(self.db.setting("download_folder", str(DOWNLOAD_DIR))); choose=QPushButton("Choose"); choose.clicked.connect(self.choose_folder); row=QHBoxLayout(); row.addWidget(self.folder); row.addWidget(choose); f.addRow("Theme", self.theme); f.addRow("Download Folder", row); f.addRow("Internet Timeout", QLineEdit(self.db.setting("timeout","20"))); f.addRow("Auto Driver Check", QCheckBox()); f.addRow("Auto RD Service Check", QCheckBox()); f.addRow("Auto SDK Detection", QCheckBox()); f.addRow("Auto Image Download", QCheckBox()); f.addRow("Proxy", QLineEdit()); f.addRow("Logging Level", QComboBox()); return w
    def page_about(self): return self.info_page(f"{APP_NAME}\nVersion {APP_VERSION}\nPowered By {POWERED_BY}\nOffline-first, open source, free forever, no login, registration, license key, or subscription.", ["Open Logs","Open Cache","Open Vendor Metadata Folder"])
    def info_page(self,text,buttons):
        w=QWidget(); l=QVBoxLayout(w); lab=QLabel(text); lab.setWordWrap(True); l.addWidget(lab); 
        for t in buttons:
            b=QPushButton(t); b.clicked.connect(lambda _, x=t:self.generic_action(x)); l.addWidget(b)
        l.addStretch(); return w
    def generic_action(self, name):
        if name.startswith("Visit"):
            url=self.vendor_url(); webbrowser.open(url) if url else self.toast("No official URL available for current device.")
        elif "Folder" in name or "Logs" in name or "Cache" in name:
            path = LOG_DIR if "Logs" in name else CACHE_DIR if "Cache" in name else PLUGIN_DIR if "Metadata" in name else Path(self.folder.text())
            path.mkdir(parents=True, exist_ok=True); webbrowser.open(path.as_uri())
        elif "Capture" in name:
            self.toast("This fingerprint device requires the manufacturer's official SDK or RD Service for fingerprint capture." if not self.devices else "Fingerprint capture requires WinBio or official vendor SDK access.")
        else: self.toast(f"{name}: action queued; administrator confirmation is required before installations or service changes.")
    def vendor_url(self):
        d=self.devices[0] if self.devices else BiometricDevice(); return VENDORS.identify(d.name + d.manufacturer, d.vendor_id).get("support","")
    def refresh_dashboard(self):
        vals={"Version":APP_VERSION,"Windows":platform.platform(),"Python":platform.python_version(),"Internet":"Online" if SystemProbe.internet() else "Offline","Administrator":"Yes" if SystemProbe.is_admin() else "No","Connected Devices":str(len(self.devices)),"Installed Drivers":str(sum(1 for d in self.devices if d.driver_status=='Installed')),"RD Services":str(sum(1 for d in self.devices if d.rd_status=='Running'))}
        for k,v in vals.items(): self.metrics[k].setText(v)
        self.populate_devices()
    def populate_devices(self):
        self.device_table.setRowCount(len(self.devices))
        for r,d in enumerate(self.devices):
            vals=[d.name,d.manufacturer,d.model,d.vendor_id,d.product_id,d.device_class,d.driver_status,d.rd_status,d.health,d.windows_error_code,d.pnp_device_id,d.location]
            for c,v in enumerate(vals): self.device_table.setItem(r,c,QTableWidgetItem(str(v)))
    def scan(self):
        self.toast("Scanning WMI, PnP, USB, HID, WinBio and cached metadata..."); worker=Worker(DeviceScanner().scan); worker.signals.result.connect(self.scan_done); worker.signals.error.connect(lambda e:self.toast("Scan failed; see logs.")); self.pool.start(worker)
    def scan_done(self, result): self.devices=result; self.refresh_dashboard(); self.sidebar.setCurrentRow(1); self.toast(f"Detected {len(result)} biometric candidate(s).")
    def start_download(self):
        url=self.url.text().strip()
        if not url.startswith(("https://","http://")): self.toast("Enter an official HTTPS manufacturer URL."); return
        host=urllib.parse.urlparse(url).netloc.lower()
        if not any(x in host for x in ["mantra","morpho","idemia","acpl","precision","secugen","nitgen","suprema","futronic","hidglobal","github"]):
            if QMessageBox.warning(self,"Official source check",f"{host} is not in the built-in official vendor allow-list. Continue only if this is an official support portal.",QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes: return
        folder=Path(self.folder.text()); folder.mkdir(parents=True, exist_ok=True); self.db.set_setting("download_folder", str(folder)); target=folder / (Path(urllib.parse.urlparse(url).path).name or "download.bin")
        task=DownloadTask(url,target); task.signals.progress.connect(lambda p,m:(self.progress.setValue(p), self.download_log.append(m))); task.signals.result.connect(self.download_done); task.signals.error.connect(lambda e:self.download_log.append(e)); self.pool.start(task)
    def download_done(self, path):
        self.download_log.append(f"Complete: {path}")
        if QMessageBox.question(self,"Install", "The download is complete. Would you like to install it now?")==QMessageBox.Yes: self.install(Path(path))
    def install(self,path:Path):
        QMessageBox.information(self,"Administrator confirmation", "Windows UAC may appear. The installer will be launched only after your confirmation.")
        try:
            if path.suffix.lower()==".msi": subprocess.Popen(["msiexec","/i",str(path)])
            elif path.suffix.lower()==".inf": subprocess.Popen(["pnputil","/add-driver",str(path),"/install"])
            elif path.suffix.lower()==".zip": zipfile.ZipFile(path).extractall(path.with_suffix("")); webbrowser.open(path.with_suffix("").as_uri())
            else: subprocess.Popen([str(path)], shell=True)
            DB.event("Driver Installation", f"Launched installer {path}")
        except Exception as exc: self.toast(f"Installation failed: {exc}")
    def export_report(self, fmt):
        p=ReportManager().export(self.devices,fmt); self.toast(f"Report saved: {p}"); webbrowser.open(p.parent.as_uri())
    def open_device_manager(self): subprocess.Popen(["devmgmt.msc"], shell=True) if platform.system()=="Windows" else self.toast("Device Manager is available on Windows only.")
    def choose_folder(self):
        p=QFileDialog.getExistingDirectory(self,"Download Folder",self.folder.text());
        if p: self.folder.setText(p); self.db.set_setting("download_folder",p)
    def toast(self,text): Toast(self,text)
    def toggle_max(self): self.showNormal() if self.isMaximized() else self.showMaximized()
    def mouse_press(self,e): self.drag_pos=e.globalPosition().toPoint()
    def mouse_move(self,e):
        if e.buttons() & Qt.LeftButton and not self.isMaximized(): self.move(self.pos()+e.globalPosition().toPoint()-self.drag_pos); self.drag_pos=e.globalPosition().toPoint()
    def apply_theme(self, theme):
        light = theme == "light"
        self.setStyleSheet(f"""
        QMainWindow{{background:{'#f6f8fb' if light else '#0b1220'};color:{'#111827' if light else '#e5e7eb'};}}
        #title{{background:{'rgba(255,255,255,220)' if light else 'rgba(15,23,42,235)'};border-bottom:1px solid {'#d7dee9' if light else '#1f2a44'};}}
        QListWidget{{background:{'#ffffff' if light else '#0f172a'};border:0;padding:14px;color:{'#111827' if light else '#dbeafe'};font-size:14px;}}
        QListWidget::item{{padding:13px;border-radius:12px;margin:3px;}} QListWidget::item:selected{{background:#2563eb;color:white;}}
        #card{{background:{'rgba(255,255,255,235)' if light else 'rgba(30,41,59,220)'};border:1px solid {'#dbe4f0' if light else '#263858'};border-radius:22px;padding:18px;}}
        #muted{{color:{'#64748b' if light else '#93a4bd'};}} #big{{font-size:22px;font-weight:700;color:{'#0f172a' if light else '#f8fafc'};}}
        #logo{{font-size:24px;font-weight:800;color:#2563eb;padding:24px;}}
        QPushButton{{background:#2563eb;color:white;border:0;border-radius:14px;padding:12px;font-weight:700;}} QPushButton:hover{{background:#10b981;}}
        QToolButton{{background:transparent;border:0;padding:10px;color:{'#111827' if light else 'white'};}} QToolButton:hover{{background:#ef4444;color:white;}}
        QLineEdit,QComboBox,QTextEdit,QTableWidget{{background:{'#ffffff' if light else '#111827'};color:{'#111827' if light else '#e5e7eb'};border:1px solid {'#d7dee9' if light else '#263858'};border-radius:12px;padding:8px;}}
        QHeaderView::section{{background:#2563eb;color:white;padding:8px;border:0;}}
        QProgressBar{{border-radius:10px;background:{'#e5e7eb' if light else '#1f2937'};height:20px;}} QProgressBar::chunk{{background:#10b981;border-radius:10px;}}
        """)

def main() -> int:
    app=QApplication(sys.argv); app.setApplicationName(APP_NAME); app.setWindowIcon(QIcon()); w=MainWindow(); w.show(); return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
