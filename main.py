#!/usr/bin/env python3
"""
PRINTER DOCTOR PRO ENTERPRISE
Single-file, production-oriented PySide6 desktop application for printer fleet discovery,
diagnostics, repair workflows, reporting, offline knowledge management, and service-center operations.

The application is intentionally self-contained for PyInstaller packaging. Optional integrations
(pywin32, WMI, qdarktheme, OpenCV, pandas, reportlab, openpyxl, Pillow, requests, bs4, matplotlib)
are loaded dynamically when present; core offline operation remains available with Python 3.9+,
PySide6, and SQLite.
"""
from __future__ import annotations

import base64
import concurrent.futures
import csv
import dataclasses
import datetime as dt
import hashlib
import hmac
import importlib
import importlib.util
import ipaddress
import json
import logging
import logging.handlers
import os
import platform
import queue
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.parse
import uuid
import webbrowser
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

APP_NAME = "PRINTER DOCTOR PRO ENTERPRISE"
APP_VERSION = "1.0.0"
APP_SLUG = "printer_doctor_pro_enterprise"
SUPPORTED_BRANDS = [
    "HP", "Canon", "Epson", "Brother", "Samsung", "Ricoh", "Kyocera", "Xerox", "Pantum",
    "Sharp", "Konica Minolta", "Lexmark", "Dell", "OKI", "TVS", "Zebra", "TSC", "Godex",
    "Bixolon", "Citizen", "Honeywell", "Dymo", "Fujitsu", "Toshiba",
]
COMMON_ISSUES = [
    "Paper Jam", "Ink System Failure", "Toner Failure", "Drum Failure", "Scanner Failure",
    "Driver Failure", "Firmware Failure", "USB Problems", "Wi-Fi Problems", "Network Problems",
    "Print Quality Problems", "Power Problems",
]


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
DB_PATH = DATA_DIR / "printer_doctor.db"
LOG_DIR = DATA_DIR / "logs"
CACHE_DIR = DATA_DIR / "cache"
IMAGE_CACHE_DIR = CACHE_DIR / "images"
DRIVER_BACKUP_DIR = DATA_DIR / "driver_backups"
MANUAL_DIR = DATA_DIR / "manuals"
REPORT_DIR = DATA_DIR / "reports"
for directory in (LOG_DIR, CACHE_DIR, IMAGE_CACHE_DIR, DRIVER_BACKUP_DIR, MANUAL_DIR, REPORT_DIR):
    directory.mkdir(parents=True, exist_ok=True)


def setup_logging() -> logging.Logger:
    logger = logging.getLogger(APP_SLUG)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(threadName)s | %(name)s | %(message)s")
    if not logger.handlers:
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_DIR / "application.log", maxBytes=2_000_000, backupCount=10, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    return logger


LOGGER = setup_logging()


class OptionalModules:
    """Lazy optional dependency loader without hard failing offline/core operation."""

    _cache: Dict[str, Any] = {}
    _lock = threading.RLock()

    @classmethod
    def load(cls, name: str, package: Optional[str] = None) -> Any:
        key = package or name
        with cls._lock:
            if key in cls._cache:
                return cls._cache[key]
            if importlib.util.find_spec(name) is None:
                cls._cache[key] = None
                return None
            module = importlib.import_module(package or name)
            cls._cache[key] = module
            return module


if importlib.util.find_spec("PySide6") is None:
    raise SystemExit("PySide6 is required. Install with: pip install PySide6")

from PySide6.QtCore import (  # noqa: E402
    QEasingCurve,
    QObject,
    QPoint,
    Property,
    QPropertyAnimation,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QAction, QColor, QDragEnterEvent, QDropEvent, QFont, QIcon, QPixmap  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


@dataclasses.dataclass
class PrinterRecord:
    id: Optional[int] = None
    uuid: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    manufacturer: str = ""
    model: str = ""
    product_number: str = ""
    serial_number: str = ""
    driver_name: str = ""
    driver_version: str = ""
    driver_date: str = ""
    firmware_version: str = ""
    connection_type: str = "Unknown"
    usb_port: str = ""
    ip_address: str = ""
    mac_address: str = ""
    status: str = "Unknown"
    queue_count: int = 0
    toner_level: Optional[int] = None
    ink_level: Optional[int] = None
    health_score: int = 0
    first_detected: str = dataclasses.field(default_factory=lambda: dt.datetime.utcnow().isoformat(timespec="seconds"))
    last_seen: str = dataclasses.field(default_factory=lambda: dt.datetime.utcnow().isoformat(timespec="seconds"))


@dataclasses.dataclass
class DiagnosticResult:
    health: int
    risk: int
    maintenance: int
    recommendations: List[str]
    driver_issue: bool = False
    network_issue: bool = False
    firmware_alert: bool = False
    toner_alert: bool = False
    ink_alert: bool = False


class DatabaseManager:
    def __init__(self, path: Path = DB_PATH):
        self.path = path
        self._local = threading.local()
        self._write_lock = threading.RLock()
        self.initialize()

    def connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=30000")
            self._local.conn = conn
        return conn

    def initialize(self) -> None:
        with self._write_lock:
            conn = self.connection()
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS printers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    manufacturer TEXT, model TEXT, product_number TEXT, serial_number TEXT,
                    driver_name TEXT, driver_version TEXT, driver_date TEXT, firmware_version TEXT,
                    connection_type TEXT, usb_port TEXT, ip_address TEXT, mac_address TEXT,
                    status TEXT, queue_count INTEGER DEFAULT 0, toner_level INTEGER, ink_level INTEGER,
                    health_score INTEGER DEFAULT 0, first_detected TEXT NOT NULL, last_seen TEXT NOT NULL,
                    raw_json TEXT DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS drivers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, printer_uuid TEXT, manufacturer TEXT, model TEXT,
                    name TEXT, version TEXT, release_date TEXT, size TEXT, compatibility TEXT,
                    source_url TEXT, local_path TEXT, sha256 TEXT, category TEXT, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS error_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, brand TEXT NOT NULL, model TEXT, error_code TEXT NOT NULL,
                    error_name TEXT, severity TEXT, category TEXT, description TEXT, root_cause TEXT,
                    temporary_fix TEXT, permanent_fix TEXT, technician_notes TEXT, required_parts TEXT,
                    estimated_cost TEXT, estimated_time TEXT, difficulty_level TEXT, success_rate TEXT,
                    source TEXT, updated_at TEXT NOT NULL,
                    UNIQUE(brand, model, error_code)
                );
                CREATE INDEX IF NOT EXISTS idx_error_codes_search ON error_codes(brand, model, error_code);
                CREATE TABLE IF NOT EXISTS diagnostics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, printer_uuid TEXT, health INTEGER, risk INTEGER,
                    maintenance INTEGER, recommendations TEXT, payload TEXT, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS repairs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, printer_uuid TEXT, action TEXT NOT NULL, status TEXT NOT NULL,
                    details TEXT, started_at TEXT NOT NULL, completed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS firmware (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, printer_uuid TEXT, manufacturer TEXT, model TEXT,
                    current_version TEXT, latest_version TEXT, release_notes TEXT, changelog TEXT,
                    source_url TEXT, local_path TEXT, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS manuals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, manufacturer TEXT, model TEXT, title TEXT NOT NULL,
                    manual_type TEXT, source_url TEXT, local_path TEXT, sha256 TEXT, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, printer_uuid TEXT, manufacturer TEXT, model TEXT,
                    source_url TEXT, local_path TEXT NOT NULL, width INTEGER, height INTEGER, sha256 TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS service_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, printer_uuid TEXT, event_type TEXT NOT NULL, title TEXT NOT NULL,
                    notes TEXT, cost REAL DEFAULT 0, technician TEXT, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS consumables (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, printer_uuid TEXT, item_type TEXT NOT NULL, name TEXT,
                    part_number TEXT, level INTEGER, estimated_pages INTEGER, installed_at TEXT,
                    expected_replacement_at TEXT, notes TEXT
                );
                CREATE TABLE IF NOT EXISTS network_devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT NOT NULL, hostname TEXT, status TEXT, manufacturer TEXT,
                    model TEXT, mac_address TEXT, ports TEXT, last_seen TEXT NOT NULL, UNIQUE(ip)
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, role TEXT NOT NULL,
                    password_hash TEXT NOT NULL, salt TEXT NOT NULL, active INTEGER DEFAULT 1, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS parts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, manufacturer TEXT, model TEXT, part_number TEXT NOT NULL,
                    description TEXT, compatibility TEXT, replacement_procedure TEXT, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS update_catalog (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, catalog_type TEXT, source_url TEXT, sha256 TEXT,
                    local_path TEXT, applied INTEGER DEFAULT 0, created_at TEXT NOT NULL
                );
                """
            )
            self._ensure_default_admin(conn)
            self._ensure_default_settings(conn)
            conn.commit()

    def _ensure_default_admin(self, conn: sqlite3.Connection) -> None:
        row = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()
        if row:
            return
        salt = secrets.token_hex(16)
        password_hash = SecurityManager.hash_password("admin123", salt)
        conn.execute(
            "INSERT INTO users(username, role, password_hash, salt, created_at) VALUES(?,?,?,?,?)",
            ("admin", "Admin", password_hash, salt, dt.datetime.utcnow().isoformat(timespec="seconds")),
        )

    def _ensure_default_settings(self, conn: sqlite3.Connection) -> None:
        defaults = {
            "offline_mode": "false", "auto_scan": "true", "auto_repair": "false", "auto_update": "true",
            "driver_cache": str(DRIVER_BACKUP_DIR), "backup_schedule": "weekly", "theme": "Dark",
            "language": "en", "network_scan_cidr": "", "online_timeout_seconds": "3",
        }
        now = dt.datetime.utcnow().isoformat(timespec="seconds")
        for key, value in defaults.items():
            conn.execute("INSERT OR IGNORE INTO settings(key, value, updated_at) VALUES(?,?,?)", (key, value, now))

    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        with self._write_lock:
            cur = self.connection().execute(sql, params)
            self.connection().commit()
            return cur

    def query(self, sql: str, params: Sequence[Any] = ()) -> List[sqlite3.Row]:
        return list(self.connection().execute(sql, params).fetchall())

    def upsert_printer(self, printer: PrinterRecord, raw: Optional[Dict[str, Any]] = None) -> None:
        now = dt.datetime.utcnow().isoformat(timespec="seconds")
        key_uuid = printer.uuid or self._stable_printer_uuid(printer)
        printer.uuid = key_uuid
        existing = self.query(
            "SELECT uuid, first_detected FROM printers WHERE uuid=? OR (name=? AND COALESCE(ip_address,'')=COALESCE(?,''))",
            (printer.uuid, printer.name, printer.ip_address),
        )
        first_detected = existing[0]["first_detected"] if existing else printer.first_detected
        sql = """
            INSERT INTO printers(uuid, name, manufacturer, model, product_number, serial_number, driver_name,
                driver_version, driver_date, firmware_version, connection_type, usb_port, ip_address, mac_address,
                status, queue_count, toner_level, ink_level, health_score, first_detected, last_seen, raw_json)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(uuid) DO UPDATE SET
                name=excluded.name, manufacturer=excluded.manufacturer, model=excluded.model,
                product_number=excluded.product_number, serial_number=excluded.serial_number,
                driver_name=excluded.driver_name, driver_version=excluded.driver_version,
                driver_date=excluded.driver_date, firmware_version=excluded.firmware_version,
                connection_type=excluded.connection_type, usb_port=excluded.usb_port,
                ip_address=excluded.ip_address, mac_address=excluded.mac_address, status=excluded.status,
                queue_count=excluded.queue_count, toner_level=excluded.toner_level, ink_level=excluded.ink_level,
                health_score=excluded.health_score, last_seen=excluded.last_seen, raw_json=excluded.raw_json
        """
        self.execute(
            sql,
            (
                printer.uuid, printer.name, printer.manufacturer, printer.model, printer.product_number,
                printer.serial_number, printer.driver_name, printer.driver_version, printer.driver_date,
                printer.firmware_version, printer.connection_type, printer.usb_port, printer.ip_address,
                printer.mac_address, printer.status, printer.queue_count, printer.toner_level, printer.ink_level,
                printer.health_score, first_detected, now, json.dumps(raw or {}, default=str),
            ),
        )

    def _stable_printer_uuid(self, printer: PrinterRecord) -> str:
        key = "|".join([printer.name, printer.serial_number, printer.ip_address, printer.driver_name]).lower()
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, key or str(uuid.uuid4())))

    def get_printers(self) -> List[sqlite3.Row]:
        return self.query("SELECT * FROM printers ORDER BY last_seen DESC, name COLLATE NOCASE")

    def get_settings(self) -> Dict[str, str]:
        return {row["key"]: row["value"] for row in self.query("SELECT key, value FROM settings")}

    def set_setting(self, key: str, value: str) -> None:
        self.execute(
            "INSERT INTO settings(key, value, updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, value, dt.datetime.utcnow().isoformat(timespec="seconds")),
        )


class SecurityManager:
    @staticmethod
    def hash_password(password: str, salt: str) -> str:
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 160_000)
        return base64.b64encode(digest).decode("ascii")

    @staticmethod
    def verify_password(password: str, salt: str, expected_hash: str) -> bool:
        return hmac.compare_digest(SecurityManager.hash_password(password, salt), expected_hash)

    @staticmethod
    def encrypt_backup(data: bytes, password: str) -> bytes:
        key = hashlib.sha256(password.encode("utf-8")).digest()
        nonce = secrets.token_bytes(16)
        stream = hashlib.sha512(key + nonce).digest()
        encrypted = bytes(byte ^ stream[index % len(stream)] for index, byte in enumerate(data))
        mac = hmac.new(key, nonce + encrypted, hashlib.sha256).digest()
        return b"PDPENC1" + nonce + mac + encrypted


class ConnectivityService:
    def __init__(self, timeout: float = 3.0):
        self.timeout = timeout

    def is_online(self) -> bool:
        for host, port in (("1.1.1.1", 53), ("8.8.8.8", 53), ("www.hp.com", 443)):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            try:
                if sock.connect_ex((host, port)) == 0:
                    return True
            finally:
                sock.close()
        return False


class PrinterDetectionEngine:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.logger = LOGGER.getChild("DetectionEngine")

    def detect_all(self) -> List[PrinterRecord]:
        printers: List[PrinterRecord] = []
        for detector in (self.detect_windows_printers, self.detect_cups_printers):
            try:
                printers.extend(detector())
            except Exception:
                self.logger.exception("Detector failed: %s", detector.__name__)
        unique: Dict[str, PrinterRecord] = {}
        for printer in printers:
            if not printer.uuid:
                printer.uuid = self.db._stable_printer_uuid(printer)
            unique[printer.uuid] = printer
            self.db.upsert_printer(printer, dataclasses.asdict(printer))
        return list(unique.values())

    def detect_windows_printers(self) -> List[PrinterRecord]:
        if platform.system() != "Windows":
            return []
        results: List[PrinterRecord] = []
        win32print = OptionalModules.load("win32print")
        wmi_module = OptionalModules.load("wmi")
        if win32print:
            flags = getattr(win32print, "PRINTER_ENUM_LOCAL", 2) | getattr(win32print, "PRINTER_ENUM_CONNECTIONS", 4)
            for item in win32print.EnumPrinters(flags):
                name = item[2]
                record = PrinterRecord(name=name, manufacturer=self._infer_brand(name), model=name, status="Installed")
                try:
                    handle = win32print.OpenPrinter(name)
                    info = win32print.GetPrinter(handle, 2)
                    record.driver_name = info.get("pDriverName", "")
                    record.usb_port = info.get("pPortName", "")
                    record.status = self._windows_status(info.get("Status", 0))
                    jobs = win32print.EnumJobs(handle, 0, -1, 1)
                    record.queue_count = len(jobs)
                    win32print.ClosePrinter(handle)
                except Exception:
                    self.logger.debug("Unable to inspect Windows printer %s", name, exc_info=True)
                record.connection_type = self._infer_connection(record.usb_port, name)
                record.uuid = self.db._stable_printer_uuid(record)
                results.append(record)
        if wmi_module:
            c = wmi_module.WMI()
            for obj in c.Win32_Printer():
                name = str(getattr(obj, "Name", "") or "")
                if not name:
                    continue
                record = PrinterRecord(
                    name=name,
                    manufacturer=self._infer_brand(name),
                    model=str(getattr(obj, "DriverName", "") or name),
                    driver_name=str(getattr(obj, "DriverName", "") or ""),
                    usb_port=str(getattr(obj, "PortName", "") or ""),
                    status=str(getattr(obj, "PrinterStatus", "Unknown") or "Unknown"),
                    connection_type=self._infer_connection(str(getattr(obj, "PortName", "") or ""), name),
                )
                record.uuid = self.db._stable_printer_uuid(record)
                results.append(record)
        return results

    def detect_cups_printers(self) -> List[PrinterRecord]:
        if platform.system() == "Windows":
            return []
        if shutil.which("lpstat") is None:
            return []
        completed = subprocess.run(["lpstat", "-v"], capture_output=True, text=True, timeout=8, check=False)
        results: List[PrinterRecord] = []
        for line in completed.stdout.splitlines():
            if not line.startswith("device for "):
                continue
            name_part, uri = line.replace("device for ", "", 1).split(": ", 1)
            record = PrinterRecord(
                name=name_part,
                manufacturer=self._infer_brand(name_part + " " + uri),
                model=name_part,
                status="Installed",
                connection_type=self._infer_connection(uri, name_part),
                usb_port=uri if uri.startswith("usb") else "",
                ip_address=self._extract_ip(uri),
            )
            record.uuid = self.db._stable_printer_uuid(record)
            results.append(record)
        return results

    def discover_network_printers(self, cidr: str = "") -> List[Dict[str, Any]]:
        network = self._default_cidr(cidr)
        devices: List[Dict[str, Any]] = []
        if not network:
            return devices
        candidates = list(network.hosts())[:512]
        ports = (9100, 631, 515)
        with concurrent.futures.ThreadPoolExecutor(max_workers=64) as executor:
            futures = {executor.submit(self._probe_host, str(ip), ports): str(ip) for ip in candidates}
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    devices.append(result)
                    self.db.execute(
                        "INSERT INTO network_devices(ip, hostname, status, manufacturer, model, mac_address, ports, last_seen) VALUES(?,?,?,?,?,?,?,?) "
                        "ON CONFLICT(ip) DO UPDATE SET hostname=excluded.hostname,status=excluded.status,manufacturer=excluded.manufacturer,model=excluded.model,ports=excluded.ports,last_seen=excluded.last_seen",
                        (
                            result["ip"], result.get("hostname", ""), result["status"], result.get("manufacturer", ""),
                            result.get("model", ""), result.get("mac_address", ""), json.dumps(result.get("ports", [])),
                            dt.datetime.utcnow().isoformat(timespec="seconds"),
                        ),
                    )
        return devices

    def _probe_host(self, ip: str, ports: Sequence[int]) -> Optional[Dict[str, Any]]:
        open_ports: List[int] = []
        for port in ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.35)
            try:
                if sock.connect_ex((ip, port)) == 0:
                    open_ports.append(port)
            finally:
                sock.close()
        if not open_ports:
            return None
        hostname = ""
        try:
            hostname = socket.gethostbyaddr(ip)[0]
        except Exception:
            hostname = ""
        text = f"{hostname} {ip}"
        return {
            "ip": ip,
            "hostname": hostname,
            "status": "Online",
            "manufacturer": self._infer_brand(text),
            "model": hostname,
            "ports": open_ports,
        }

    def _default_cidr(self, cidr: str = "") -> Optional[ipaddress.IPv4Network]:
        if cidr:
            try:
                return ipaddress.ip_network(cidr, strict=False)
            except ValueError:
                self.logger.warning("Invalid CIDR: %s", cidr)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
            return ipaddress.ip_network(".".join(ip.split(".")[:3]) + ".0/24", strict=False)
        except Exception:
            return None

    def _infer_brand(self, text: str) -> str:
        lower = text.lower()
        for brand in SUPPORTED_BRANDS:
            if brand.lower() in lower:
                return brand
        return ""

    def _infer_connection(self, port: str, name: str) -> str:
        text = f"{port} {name}".lower()
        if "usb" in text:
            return "USB"
        if "bluetooth" in text or "bth" in text:
            return "Bluetooth"
        if "wifi" in text or "wi-fi" in text or "wireless" in text:
            return "Wi-Fi"
        if any(token in text for token in ("ipp", "socket", "lpd", "tcp", "wds", "http")) or self._extract_ip(text):
            return "Network"
        if "pdf" in text or "xps" in text or "onenote" in text:
            return "Virtual"
        return "Unknown"

    def _extract_ip(self, text: str) -> str:
        for token in text.replace("/", " ").replace(":", " ").split():
            try:
                return str(ipaddress.ip_address(token))
            except ValueError:
                continue
        return ""

    def _windows_status(self, status: int) -> str:
        if status == 0:
            return "Ready"
        if status & 0x00000080:
            return "Offline"
        if status & 0x00000002:
            return "Error"
        if status & 0x00000400:
            return "Printing"
        return f"Status {status}"


class DiagnosticEngine:
    def analyze(self, printer: sqlite3.Row | Dict[str, Any]) -> DiagnosticResult:
        p = dict(printer)
        recommendations: List[str] = []
        health = 100
        driver_issue = not bool(p.get("driver_name")) and p.get("connection_type") != "Network"
        network_issue = p.get("connection_type") in {"Network", "Wi-Fi"} and not p.get("ip_address")
        queue_count = int(p.get("queue_count") or 0)
        toner = p.get("toner_level")
        ink = p.get("ink_level")
        status = str(p.get("status") or "").lower()
        if "offline" in status or "error" in status:
            health -= 30
            recommendations.append("Resolve current printer status before sending production jobs.")
        if driver_issue:
            health -= 20
            recommendations.append("Install or refresh the correct manufacturer driver package.")
        if network_issue:
            health -= 15
            recommendations.append("Verify IP address, DHCP reservation, Wi-Fi signal, and printer port mapping.")
        if queue_count > 5:
            health -= 15
            recommendations.append("Clear stuck print jobs and restart the print spooler/service.")
        toner_alert = toner is not None and int(toner) <= 15
        ink_alert = ink is not None and int(ink) <= 15
        if toner_alert:
            health -= 10
            recommendations.append("Replace or prepare toner cartridge; level is below service threshold.")
        if ink_alert:
            health -= 10
            recommendations.append("Replace or refill ink tank/cartridge; level is below service threshold.")
        if not recommendations:
            recommendations.append("No immediate repair action required. Continue scheduled preventive maintenance.")
        health = max(0, min(100, health))
        return DiagnosticResult(
            health=health,
            risk=max(0, 100 - health),
            maintenance=max(0, min(100, health - (10 if queue_count else 0))),
            recommendations=recommendations,
            driver_issue=driver_issue,
            network_issue=network_issue,
            firmware_alert=not bool(p.get("firmware_version")),
            toner_alert=toner_alert,
            ink_alert=ink_alert,
        )

    def wizard_diagnosis(self, answers: Dict[str, str]) -> str:
        analysis: List[str] = []
        if answers.get("power") != "On":
            analysis.append("Power fault: inspect AC cable, adapter, power board, fuse, and wall outlet.")
        if answers.get("connectivity") in {"Disconnected", "Intermittent"}:
            analysis.append("Connectivity fault: reseat USB/network cable, renew IP address, and recreate printer port.")
        if answers.get("leds") in {"Blinking", "Red/Amber"}:
            analysis.append("Panel alert detected: map LED pattern to service manual and check consumables/cover sensors.")
        if answers.get("print_result") in {"Blank", "Streaks", "Faded", "Smudged"}:
            analysis.append("Print-quality fault: run nozzle check/head cleaning for inkjet or inspect toner, drum, fuser, and transfer roller for laser.")
        code = answers.get("error_code", "").strip()
        if code:
            analysis.append(f"Search ERROR CODE EXPERT for '{code}' and verify the permanent repair procedure before part replacement.")
        return "\n".join(analysis or ["Diagnosis indicates normal operation. Run benchmark and print a test page to confirm."])


class ErrorCodeExpert:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def search(self, brand: str = "", model: str = "", code: str = "") -> List[sqlite3.Row]:
        where, params = [], []
        if brand:
            where.append("brand LIKE ?")
            params.append(f"%{brand}%")
        if model:
            where.append("model LIKE ?")
            params.append(f"%{model}%")
        if code:
            where.append("error_code LIKE ?")
            params.append(f"%{code}%")
        sql = "SELECT * FROM error_codes"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY brand, model, error_code LIMIT 500"
        return self.db.query(sql, params)

    def import_csv(self, path: Path) -> int:
        count = 0
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                brand = (row.get("brand") or row.get("Brand") or "").strip()
                code = (row.get("error_code") or row.get("Error Code") or row.get("code") or "").strip()
                if not brand or not code:
                    continue
                self.db.execute(
                    """
                    INSERT INTO error_codes(brand, model, error_code, error_name, severity, category, description,
                    root_cause, temporary_fix, permanent_fix, technician_notes, required_parts, estimated_cost,
                    estimated_time, difficulty_level, success_rate, source, updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(brand, model, error_code) DO UPDATE SET
                    error_name=excluded.error_name,severity=excluded.severity,category=excluded.category,
                    description=excluded.description,root_cause=excluded.root_cause,temporary_fix=excluded.temporary_fix,
                    permanent_fix=excluded.permanent_fix,technician_notes=excluded.technician_notes,
                    required_parts=excluded.required_parts,estimated_cost=excluded.estimated_cost,
                    estimated_time=excluded.estimated_time,difficulty_level=excluded.difficulty_level,
                    success_rate=excluded.success_rate,source=excluded.source,updated_at=excluded.updated_at
                    """,
                    (
                        brand, row.get("model") or row.get("Model") or "", code,
                        row.get("error_name") or row.get("Error Name") or "", row.get("severity") or "",
                        row.get("category") or "", row.get("description") or "", row.get("root_cause") or "",
                        row.get("temporary_fix") or "", row.get("permanent_fix") or "", row.get("technician_notes") or "",
                        row.get("required_parts") or "", row.get("estimated_cost") or "", row.get("estimated_time") or "",
                        row.get("difficulty_level") or "", row.get("success_rate") or "", str(path),
                        dt.datetime.utcnow().isoformat(timespec="seconds"),
                    ),
                )
                count += 1
        return count


class AIAssistantFramework:
    def __init__(self, db: DatabaseManager, expert: ErrorCodeExpert):
        self.db = db
        self.expert = expert

    def answer(self, question: str, brand: str = "", model: str = "", code: str = "") -> str:
        q = question.lower()
        rows = self.expert.search(brand, model, code) if (brand or model or code) else []
        if rows:
            row = rows[0]
            return (
                f"Problem Analysis: {row['description'] or 'The stored error entry identifies a printer fault requiring structured diagnosis.'}\n\n"
                f"Root Cause Analysis: {row['root_cause'] or 'Confirm consumables, sensors, firmware state, driver state, and mechanical movement.'}\n\n"
                f"Best Repair Procedure: {row['permanent_fix'] or row['temporary_fix'] or 'Follow manufacturer service workflow and verify with a test page.'}\n\n"
                f"Alternate Repair Methods: {row['temporary_fix'] or 'Power-cycle, clear queue, reseat consumables, and update driver/firmware if applicable.'}\n\n"
                f"Preventive Maintenance: Keep firmware documented, clean paper path, use correct media, and schedule consumable inspections."
            )
        if "offline" in q:
            return (
                "Problem Analysis: The printer is not reachable by the operating system or print service.\n\n"
                "Root Cause Analysis: Common causes include changed IP address, disabled Wi-Fi, bad cable, paused queue, stopped spooler, or offline SNMP status.\n\n"
                "Best Repair Procedure: Ping the printer IP, verify the port, restart spooler/CUPS, disable 'Use Printer Offline', and reserve the IP in DHCP.\n\n"
                "Permanent Repair Guide: Create a standard TCP/IP port with a fixed address, update firmware, and document network ownership."
            )
        if any(token in q for token in ("b200", "49.4c02", "e-01", "paper jam", "toner", "ink")):
            return (
                "Problem Analysis: The symptom matches a known manufacturer/service fault category.\n\n"
                "Root Cause Analysis: Validate the exact brand, model, and error code in ERROR CODE EXPERT; then inspect consumables, carriage path, firmware, and sensors.\n\n"
                "Best Repair Procedure: Apply temporary reset only for triage, then perform the permanent fix from the verified service entry and record service history."
            )
        return (
            "Provide brand, model, exact error code, connection type, LED state, and print result. "
            "The assistant will combine local knowledge-base records, live fleet status, and diagnostic wizard answers to generate a repair plan."
        )


class AutoRepairEngine:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.logger = LOGGER.getChild("AutoRepair")

    def one_click_repair(self) -> List[Tuple[str, str]]:
        actions = [
            ("Restart Print Service", self.restart_print_service),
            ("Clear Queue", self.clear_queue),
            ("Clear Temp Files", self.clear_temp_files),
            ("Rebuild Printer Cache", self.rebuild_printer_cache),
        ]
        results: List[Tuple[str, str]] = []
        for title, func in actions:
            started = dt.datetime.utcnow().isoformat(timespec="seconds")
            try:
                detail = func()
                status = "Completed"
            except Exception as exc:
                detail = str(exc)
                status = "Failed"
                self.logger.exception("Repair failed: %s", title)
            completed = dt.datetime.utcnow().isoformat(timespec="seconds")
            self.db.execute(
                "INSERT INTO repairs(action, status, details, started_at, completed_at) VALUES(?,?,?,?,?)",
                (title, status, detail, started, completed),
            )
            results.append((title, f"{status}: {detail}"))
        return results

    def restart_print_service(self) -> str:
        system = platform.system()
        if system == "Windows":
            subprocess.run(["net", "stop", "spooler"], capture_output=True, text=True, timeout=30, check=False)
            subprocess.run(["net", "start", "spooler"], capture_output=True, text=True, timeout=30, check=False)
            return "Windows Print Spooler restart command executed."
        if shutil.which("systemctl"):
            subprocess.run(["systemctl", "--user", "restart", "cups"], capture_output=True, text=True, timeout=30, check=False)
            return "CUPS restart command executed where permitted."
        return "No supported print service controller was found for this platform."

    def clear_queue(self) -> str:
        system = platform.system()
        if system == "Windows":
            spool = Path(os.environ.get("WINDIR", "C:/Windows")) / "System32" / "spool" / "PRINTERS"
            removed = self._remove_files(spool, ("*.spl", "*.shd"))
            return f"Removed {removed} spool files."
        if shutil.which("cancel"):
            subprocess.run(["cancel", "-a"], capture_output=True, text=True, timeout=30, check=False)
            return "CUPS cancel-all command executed."
        return "No queue cleaner was available."

    def clear_temp_files(self) -> str:
        removed = self._remove_files(Path(tempfile.gettempdir()), ("*.tmp", "*.spl", "*.shd"), max_files=500)
        return f"Removed {removed} temporary print-related files."

    def rebuild_printer_cache(self) -> str:
        cache = CACHE_DIR / "runtime"
        if cache.exists():
            shutil.rmtree(cache)
        cache.mkdir(parents=True, exist_ok=True)
        return "Application printer runtime cache rebuilt."

    def _remove_files(self, directory: Path, patterns: Sequence[str], max_files: int = 10000) -> int:
        if not directory.exists():
            return 0
        removed = 0
        for pattern in patterns:
            for path in directory.glob(pattern):
                if removed >= max_files:
                    return removed
                if path.is_file():
                    try:
                        path.unlink()
                        removed += 1
                    except PermissionError:
                        self.logger.warning("Permission denied removing %s", path)
        return removed


class DriverCenter:
    MANUFACTURER_SUPPORT = {
        "HP": "https://support.hp.com/drivers",
        "Canon": "https://www.usa.canon.com/support",
        "Epson": "https://epson.com/Support/sl/s",
        "Brother": "https://support.brother.com/",
        "Xerox": "https://www.support.xerox.com/",
        "Ricoh": "https://support.ricoh.com/",
        "Kyocera": "https://www.kyoceradocumentsolutions.com/download/",
        "Zebra": "https://www.zebra.com/us/en/support-downloads.html",
    }

    def __init__(self, db: DatabaseManager):
        self.db = db

    def official_support_url(self, manufacturer: str, model: str) -> str:
        base = self.MANUFACTURER_SUPPORT.get(manufacturer, "")
        if not base:
            return ""
        if "?" in base:
            return base + "&" + urllib.parse.urlencode({"q": model})
        return base + ("?" + urllib.parse.urlencode({"q": model}) if model else "")

    def backup_drivers(self) -> Path:
        timestamp = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        archive = DRIVER_BACKUP_DIR / f"drivers_{platform.node() or 'computer'}_{timestamp}.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            manifest = {"created_at": timestamp, "platform": platform.platform(), "printers": [dict(r) for r in self.db.get_printers()]}
            zf.writestr("manifest.json", json.dumps(manifest, indent=2, default=str))
            if platform.system() == "Windows":
                driver_store = Path(os.environ.get("WINDIR", "C:/Windows")) / "System32" / "DriverStore" / "FileRepository"
                for row in self.db.get_printers():
                    name = str(row["driver_name"] or "").lower().replace(" ", "")[:20]
                    if name and driver_store.exists():
                        for path in driver_store.glob(f"*{name}*"):
                            if path.is_dir():
                                for file in list(path.rglob("*"))[:200]:
                                    if file.is_file():
                                        zf.write(file, file.relative_to(driver_store.parent))
        self.db.execute(
            "INSERT INTO service_history(event_type,title,notes,created_at) VALUES(?,?,?,?)",
            ("Driver Backup", "Driver backup archive created", str(archive), dt.datetime.utcnow().isoformat(timespec="seconds")),
        )
        return archive


class ImageCacheManager:
    def __init__(self, db: DatabaseManager, online: ConnectivityService):
        self.db = db
        self.online = online

    def cached_image_for(self, printer: sqlite3.Row) -> Optional[Path]:
        rows = self.db.query("SELECT local_path FROM images WHERE printer_uuid=? ORDER BY created_at DESC LIMIT 1", (printer["uuid"],))
        if rows and Path(rows[0]["local_path"]).exists():
            return Path(rows[0]["local_path"])
        return None

    def fetch_image(self, printer: sqlite3.Row) -> Optional[Path]:
        if not self.online.is_online():
            return self.cached_image_for(printer)
        requests = OptionalModules.load("requests")
        bs4 = OptionalModules.load("bs4")
        pillow = OptionalModules.load("PIL")
        if not requests or not bs4:
            return self.cached_image_for(printer)
        query = urllib.parse.quote_plus(f"{printer['manufacturer']} {printer['model']} printer")
        candidate_pages = [
            f"https://www.google.com/search?tbm=isch&q={query}",
        ]
        for url in candidate_pages:
            response = requests.get(url, timeout=6, headers={"User-Agent": APP_NAME})
            soup = bs4.BeautifulSoup(response.text, "html.parser")
            image_url = ""
            for img in soup.find_all("img"):
                src = img.get("src") or img.get("data-src") or ""
                if src.startswith("http"):
                    image_url = src
                    break
            if not image_url:
                continue
            img_resp = requests.get(image_url, timeout=10, headers={"User-Agent": APP_NAME})
            if not img_resp.content:
                continue
            digest = hashlib.sha256(img_resp.content).hexdigest()
            ext = ".jpg"
            path = IMAGE_CACHE_DIR / f"{printer['uuid']}_{digest[:12]}{ext}"
            path.write_bytes(img_resp.content)
            width = height = 0
            if pillow:
                Image = importlib.import_module("PIL.Image")
                with Image.open(path) as im:
                    width, height = im.size
            self.db.execute(
                "INSERT INTO images(printer_uuid, manufacturer, model, source_url, local_path, width, height, sha256, created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (printer["uuid"], printer["manufacturer"], printer["model"], image_url, str(path), width, height, digest, dt.datetime.utcnow().isoformat(timespec="seconds")),
            )
            return path
        return self.cached_image_for(printer)


class ReportGenerator:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def export_json(self) -> Path:
        path = REPORT_DIR / f"printer_report_{dt.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        payload = {"generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"), "printers": [dict(r) for r in self.db.get_printers()]}
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return path

    def export_html(self) -> Path:
        path = REPORT_DIR / f"printer_report_{dt.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.html"
        rows = "".join(
            f"<tr><td>{r['name']}</td><td>{r['manufacturer']}</td><td>{r['model']}</td><td>{r['status']}</td><td>{r['health_score']}</td></tr>"
            for r in self.db.get_printers()
        )
        path.write_text(
            f"<!doctype html><html><head><meta charset='utf-8'><title>{APP_NAME}</title>"
            "<style>body{font-family:Segoe UI,Arial;margin:32px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd;padding:8px}</style>"
            f"</head><body><h1>{APP_NAME}</h1><p>Generated {dt.datetime.utcnow().isoformat(timespec='seconds')} UTC</p>"
            f"<table><tr><th>Name</th><th>Brand</th><th>Model</th><th>Status</th><th>Health</th></tr>{rows}</table></body></html>",
            encoding="utf-8",
        )
        return path

    def export_excel(self) -> Path:
        openpyxl = OptionalModules.load("openpyxl")
        path = REPORT_DIR / f"printer_report_{dt.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
        if not openpyxl:
            csv_path = path.with_suffix(".csv")
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["name", "manufacturer", "model", "status", "health_score", "ip_address"])
                writer.writeheader()
                for row in self.db.get_printers():
                    writer.writerow({k: row[k] for k in writer.fieldnames})
            return csv_path
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Fleet"
        headers = ["Name", "Manufacturer", "Model", "Status", "Connection", "IP", "Queue", "Health", "Last Seen"]
        ws.append(headers)
        for r in self.db.get_printers():
            ws.append([r["name"], r["manufacturer"], r["model"], r["status"], r["connection_type"], r["ip_address"], r["queue_count"], r["health_score"], r["last_seen"]])
        wb.save(path)
        return path

    def export_pdf(self) -> Path:
        reportlab = OptionalModules.load("reportlab")
        path = REPORT_DIR / f"printer_report_{dt.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
        if not reportlab:
            return self.export_html()
        canvas_mod = importlib.import_module("reportlab.pdfgen.canvas")
        pagesizes = importlib.import_module("reportlab.lib.pagesizes")
        c = canvas_mod.Canvas(str(path), pagesize=pagesizes.A4)
        width, height = pagesizes.A4
        y = height - 50
        c.setFont("Helvetica-Bold", 16)
        c.drawString(40, y, APP_NAME)
        y -= 30
        c.setFont("Helvetica", 9)
        c.drawString(40, y, f"Generated: {dt.datetime.utcnow().isoformat(timespec='seconds')} UTC")
        y -= 25
        for r in self.db.get_printers():
            if y < 60:
                c.showPage(); y = height - 50; c.setFont("Helvetica", 9)
            c.drawString(40, y, f"{r['name']} | {r['manufacturer']} {r['model']} | {r['status']} | Health {r['health_score']}%")
            y -= 16
        c.save()
        return path


class WorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(str)


class Worker(QRunnable):
    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.finished.emit(self.fn(*self.args, **self.kwargs))
        except Exception:
            LOGGER.exception("Worker failure")
            self.signals.error.emit(traceback.format_exc())


class Translator:
    STRINGS = {
        "en": {"scan": "Scan", "repair": "One-Click Repair", "reports": "Reports", "settings": "Settings"},
        "hi": {"scan": "स्कैन", "repair": "वन-क्लिक रिपेयर", "reports": "रिपोर्ट", "settings": "सेटिंग्स"},
    }

    def __init__(self, language: str = "en"):
        self.language = language

    def t(self, key: str) -> str:
        return self.STRINGS.get(self.language, self.STRINGS["en"]).get(key, key)


class ThemeManager:
    THEMES = {
        "Light": {"bg": "#f6f8ff", "panel": "rgba(255,255,255,0.78)", "text": "#172033", "muted": "#5d6780", "accent": "#3568ff", "border": "#dfe6ff"},
        "Dark": {"bg": "#111827", "panel": "rgba(31,41,55,0.76)", "text": "#f8fafc", "muted": "#aeb8cc", "accent": "#7c3aed", "border": "#374151"},
        "AMOLED": {"bg": "#000000", "panel": "rgba(8,8,12,0.90)", "text": "#ffffff", "muted": "#b7b7c8", "accent": "#00e5ff", "border": "#1b1b22"},
    }

    @classmethod
    def stylesheet(cls, theme: str) -> str:
        p = cls.THEMES.get(theme, cls.THEMES["Dark"])
        return f"""
        QMainWindow, QWidget#Root {{ background: {p['bg']}; color: {p['text']}; font-family: 'Segoe UI', 'Inter', Arial; }}
        QLabel {{ color: {p['text']}; }}
        QLabel[muted='true'] {{ color: {p['muted']}; }}
        QFrame[card='true'], QFrame#Sidebar, QFrame#FloatingPanel {{
            background: {p['panel']}; border: 1px solid {p['border']}; border-radius: 22px;
        }}
        QPushButton, QToolButton {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {p['accent']}, stop:1 #06b6d4);
            color: white; border: 0; border-radius: 14px; padding: 10px 14px; font-weight: 700;
        }}
        QPushButton:hover, QToolButton:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #22c55e, stop:1 {p['accent']}); }}
        QLineEdit, QTextEdit, QComboBox {{ background: rgba(255,255,255,0.08); color: {p['text']}; border: 1px solid {p['border']}; border-radius: 12px; padding: 9px; }}
        QTableWidget {{ background: transparent; color: {p['text']}; gridline-color: {p['border']}; border: 0; }}
        QHeaderView::section {{ background: {p['accent']}; color: white; padding: 8px; border: 0; }}
        QProgressBar {{ border: 1px solid {p['border']}; border-radius: 8px; text-align: center; height: 18px; }}
        QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #22c55e, stop:1 {p['accent']}); border-radius: 8px; }}
        QListWidget {{ background: transparent; border: 0; color: {p['text']}; }}
        QListWidget::item {{ padding: 12px; border-radius: 12px; }}
        QListWidget::item:selected {{ background: {p['accent']}; color: white; }}
        """


class Card(QFrame):
    def __init__(self, title: str, value: str = "0", subtitle: str = ""):
        super().__init__()
        self.setProperty("card", True)
        self.setMinimumHeight(118)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.setGraphicsEffect(shadow)
        layout = QVBoxLayout(self)
        self.title = QLabel(title)
        self.title.setProperty("muted", True)
        self.value = QLabel(value)
        self.value.setFont(QFont("Segoe UI", 24, QFont.Bold))
        self.subtitle = QLabel(subtitle)
        self.subtitle.setProperty("muted", True)
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addWidget(self.subtitle)

    def set_value(self, value: Any, subtitle: str = "") -> None:
        self.value.setText(str(value))
        if subtitle:
            self.subtitle.setText(subtitle)


class LoginDialog(QDialog):
    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db
        self.user: Optional[sqlite3.Row] = None
        self.setWindowTitle(f"{APP_NAME} Login")
        self.setModal(True)
        self.resize(430, 290)
        layout = QVBoxLayout(self)
        title = QLabel(APP_NAME)
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        subtitle = QLabel("Secure technician/admin access")
        subtitle.setProperty("muted", True)
        self.username = QLineEdit("admin")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("Password")
        self.username.setPlaceholderText("Username")
        login = QPushButton("Sign In")
        login.clicked.connect(self.authenticate)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.username)
        layout.addWidget(self.password)
        layout.addWidget(login)
        note = QLabel("Default first-run account: admin / admin123. Change it in Admin Mode before production use.")
        note.setWordWrap(True)
        note.setProperty("muted", True)
        layout.addWidget(note)

    def authenticate(self) -> None:
        rows = self.db.query("SELECT * FROM users WHERE username=? AND active=1", (self.username.text().strip(),))
        if rows and SecurityManager.verify_password(self.password.text(), rows[0]["salt"], rows[0]["password_hash"]):
            self.user = rows[0]
            self.accept()
        else:
            QMessageBox.warning(self, "Authentication failed", "Invalid username or password.")


class PrinterDoctorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.settings = self.db.get_settings()
        self.translator = Translator(self.settings.get("language", "en"))
        self.connectivity = ConnectivityService(float(self.settings.get("online_timeout_seconds", "3")))
        self.detector = PrinterDetectionEngine(self.db)
        self.diagnostics = DiagnosticEngine()
        self.expert = ErrorCodeExpert(self.db)
        self.ai = AIAssistantFramework(self.db, self.expert)
        self.repair = AutoRepairEngine(self.db)
        self.driver_center = DriverCenter(self.db)
        self.image_cache = ImageCacheManager(self.db, self.connectivity)
        self.reports = ReportGenerator(self.db)
        self.pool = QThreadPool.globalInstance()
        self.notification_queue: "queue.Queue[str]" = queue.Queue()
        self.setWindowTitle(APP_NAME)
        self.resize(1500, 920)
        self.setAcceptDrops(True)
        self._build_ui()
        self.apply_theme(self.settings.get("theme", "Dark"))
        self.refresh_all()
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.refresh_status_center)
        self.status_timer.start(5000)
        if self.settings.get("auto_scan") == "true":
            QTimer.singleShot(800, self.scan_printers)

    def _build_ui(self) -> None:
        root = QWidget(objectName="Root")
        self.setCentralWidget(root)
        main = QHBoxLayout(root)
        main.setContentsMargins(18, 18, 18, 18)
        self.sidebar = QFrame(objectName="Sidebar")
        self.sidebar.setFixedWidth(250)
        side = QVBoxLayout(self.sidebar)
        logo = QLabel("🖨️\nPRINTER DOCTOR\nPRO ENTERPRISE")
        logo.setFont(QFont("Segoe UI", 15, QFont.Bold))
        logo.setAlignment(Qt.AlignCenter)
        side.addWidget(logo)
        self.nav = QListWidget()
        pages = [
            ("Dashboard", "📊"), ("Printers", "🖨️"), ("Details", "🔎"), ("Driver Center", "💿"),
            ("ERROR CODE EXPERT", "🧠"), ("AI Assistant", "🤖"), ("Diagnostics", "🩺"),
            ("Auto Repair", "🛠️"), ("Network", "🌐"), ("Manuals & Parts", "📚"),
            ("Reports", "📄"), ("Settings", "⚙️"),
        ]
        for label, icon in pages:
            QListWidgetItem(f"{icon}  {label}", self.nav)
        self.nav.currentRowChanged.connect(self.change_page)
        side.addWidget(self.nav, 1)
        self.status_badge = QLabel("Status: initializing")
        self.status_badge.setProperty("muted", True)
        side.addWidget(self.status_badge)
        main.addWidget(self.sidebar)

        content = QVBoxLayout()
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search everywhere: printers, drivers, errors, manuals, IP, serial number...")
        self.search.textChanged.connect(self.search_everywhere)
        top.addWidget(self.search, 1)
        scan = QPushButton("🔄 Scan")
        scan.clicked.connect(self.scan_printers)
        top.addWidget(scan)
        repair = QPushButton("🛠️ Repair")
        repair.clicked.connect(self.run_auto_repair)
        top.addWidget(repair)
        content.addLayout(top)
        self.stack = QStackedWidget()
        content.addWidget(self.stack, 1)
        main.addLayout(content, 1)

        self._page_dashboard()
        self._page_printers()
        self._page_details()
        self._page_driver_center()
        self._page_error_expert()
        self._page_ai()
        self._page_diagnostics()
        self._page_auto_repair()
        self._page_network()
        self._page_manuals_parts()
        self._page_reports()
        self._page_settings()
        self.nav.setCurrentRow(0)

    def _scroll_page(self) -> Tuple[QWidget, QVBoxLayout]:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        scroll.setWidget(page)
        self.stack.addWidget(scroll)
        return page, layout

    def _page_dashboard(self) -> None:
        _, layout = self._scroll_page()
        title = QLabel("Enterprise Fleet Dashboard")
        title.setFont(QFont("Segoe UI", 24, QFont.Bold))
        layout.addWidget(title)
        grid = QGridLayout()
        labels = ["Total Printers", "Online Printers", "Offline Printers", "Error Count", "Driver Issues", "Network Issues", "Print Queue Count", "Firmware Alerts", "Toner Alerts", "Ink Alerts", "Repair Recommendations", "Health Score", "Fleet Status"]
        self.cards: Dict[str, Card] = {}
        for index, label in enumerate(labels):
            card = Card(label)
            self.cards[label] = card
            grid.addWidget(card, index // 4, index % 4)
        layout.addLayout(grid)
        self.notification_center = QTextEdit()
        self.notification_center.setReadOnly(True)
        self.notification_center.setMinimumHeight(170)
        layout.addWidget(QLabel("Notification Center"))
        layout.addWidget(self.notification_center)

    def _page_printers(self) -> None:
        _, layout = self._scroll_page()
        layout.addWidget(QLabel("Printer Fleet"))
        self.printer_table = QTableWidget(0, 9)
        self.printer_table.setHorizontalHeaderLabels(["Name", "Brand", "Model", "Status", "Connection", "IP", "Queue", "Health", "Last Seen"])
        self.printer_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.printer_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.printer_table.itemSelectionChanged.connect(self.update_details_from_selection)
        layout.addWidget(self.printer_table)

    def _page_details(self) -> None:
        _, layout = self._scroll_page()
        row = QHBoxLayout()
        self.image_label = QLabel("Printer Image")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(300, 220)
        self.image_label.setProperty("card", True)
        row.addWidget(self.image_label)
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        row.addWidget(self.details_text, 1)
        layout.addLayout(row)
        fetch = QPushButton("Fetch / Refresh Online Image")
        fetch.clicked.connect(self.fetch_selected_image)
        layout.addWidget(fetch)

    def _page_driver_center(self) -> None:
        _, layout = self._scroll_page()
        self.driver_info = QTextEdit()
        self.driver_info.setReadOnly(True)
        btns = QHBoxLayout()
        open_support = QPushButton("Open Official Support")
        open_support.clicked.connect(self.open_support)
        backup = QPushButton("Backup Installed Drivers")
        backup.clicked.connect(self.backup_drivers)
        btns.addWidget(open_support); btns.addWidget(backup)
        layout.addLayout(btns)
        layout.addWidget(self.driver_info)

    def _page_error_expert(self) -> None:
        _, layout = self._scroll_page()
        form = QHBoxLayout()
        self.err_brand = QLineEdit(); self.err_brand.setPlaceholderText("Brand")
        self.err_model = QLineEdit(); self.err_model.setPlaceholderText("Model")
        self.err_code = QLineEdit(); self.err_code.setPlaceholderText("Error Code")
        search = QPushButton("Search ERROR CODE EXPERT")
        search.clicked.connect(self.search_errors)
        import_btn = QPushButton("Import CSV Knowledge Base")
        import_btn.clicked.connect(self.import_errors)
        for w in (self.err_brand, self.err_model, self.err_code, search, import_btn):
            form.addWidget(w)
        layout.addLayout(form)
        self.error_table = QTableWidget(0, 8)
        self.error_table.setHorizontalHeaderLabels(["Brand", "Model", "Code", "Severity", "Category", "Description", "Permanent Fix", "Success Rate"])
        self.error_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.error_table)

    def _page_ai(self) -> None:
        _, layout = self._scroll_page()
        self.ai_question = QTextEdit()
        self.ai_question.setPlaceholderText("Ask: Why is my printer offline? What does B200 mean? How do I fix 49.4C02?")
        self.ai_answer = QTextEdit(); self.ai_answer.setReadOnly(True)
        ask = QPushButton("Generate Repair Intelligence")
        ask.clicked.connect(self.ask_ai)
        layout.addWidget(self.ai_question)
        layout.addWidget(ask)
        layout.addWidget(self.ai_answer)

    def _page_diagnostics(self) -> None:
        _, layout = self._scroll_page()
        form = QFormLayout()
        self.wiz_power = QComboBox(); self.wiz_power.addItems(["On", "Off", "Intermittent"])
        self.wiz_conn = QComboBox(); self.wiz_conn.addItems(["Connected", "Disconnected", "Intermittent"])
        self.wiz_leds = QComboBox(); self.wiz_leds.addItems(["Normal", "Blinking", "Red/Amber"])
        self.wiz_print = QComboBox(); self.wiz_print.addItems(["Normal", "Blank", "Streaks", "Faded", "Smudged", "No Output"])
        self.wiz_code = QLineEdit()
        for label, widget in (("Power Status", self.wiz_power), ("Connectivity", self.wiz_conn), ("LEDs", self.wiz_leds), ("Print Result", self.wiz_print), ("Error Code", self.wiz_code)):
            form.addRow(label, widget)
        layout.addLayout(form)
        run = QPushButton("Run Interactive Diagnostic Wizard")
        run.clicked.connect(self.run_wizard)
        self.wizard_output = QTextEdit(); self.wizard_output.setReadOnly(True)
        layout.addWidget(run)
        layout.addWidget(self.wizard_output)
        layout.addWidget(QLabel("Common Issue Library"))
        issue_grid = QGridLayout()
        for index, issue in enumerate(COMMON_ISSUES):
            issue_grid.addWidget(Card(issue, "Guide", "Select in AI Assistant for a repair plan"), index // 3, index % 3)
        layout.addLayout(issue_grid)

    def _page_auto_repair(self) -> None:
        _, layout = self._scroll_page()
        run = QPushButton("Execute One-Click Auto Repair Engine")
        run.clicked.connect(self.run_auto_repair)
        self.repair_output = QTextEdit(); self.repair_output.setReadOnly(True)
        layout.addWidget(run)
        layout.addWidget(self.repair_output)

    def _page_network(self) -> None:
        _, layout = self._scroll_page()
        controls = QHBoxLayout()
        self.cidr_input = QLineEdit(self.settings.get("network_scan_cidr", ""))
        self.cidr_input.setPlaceholderText("CIDR (blank = current /24, max 512 hosts scanned)")
        scan = QPushButton("Discover Network Printers")
        scan.clicked.connect(self.scan_network)
        controls.addWidget(self.cidr_input); controls.addWidget(scan)
        layout.addLayout(controls)
        self.network_table = QTableWidget(0, 5)
        self.network_table.setHorizontalHeaderLabels(["IP", "Hostname", "Status", "Manufacturer", "Ports"])
        self.network_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.network_table)

    def _page_manuals_parts(self) -> None:
        _, layout = self._scroll_page()
        layout.addWidget(QLabel("Service Manual Library, Consumable Life Tracker, and Spare Parts Database"))
        self.library_table = QTableWidget(0, 5)
        self.library_table.setHorizontalHeaderLabels(["Type", "Manufacturer", "Model", "Title / Part", "Path / Procedure"])
        self.library_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        import_manual = QPushButton("Add Manual PDF / Service Guide")
        import_manual.clicked.connect(self.add_manual)
        layout.addWidget(import_manual)
        layout.addWidget(self.library_table)

    def _page_reports(self) -> None:
        _, layout = self._scroll_page()
        row = QHBoxLayout()
        for label, func in (("PDF Report", self.export_pdf), ("Excel Report", self.export_excel), ("HTML Report", self.export_html), ("JSON Report", self.export_json)):
            btn = QPushButton(label); btn.clicked.connect(func); row.addWidget(btn)
        layout.addLayout(row)
        self.report_output = QTextEdit(); self.report_output.setReadOnly(True)
        layout.addWidget(self.report_output)

    def _page_settings(self) -> None:
        _, layout = self._scroll_page()
        self.theme_combo = QComboBox(); self.theme_combo.addItems(["Dark", "Light", "AMOLED"]); self.theme_combo.setCurrentText(self.settings.get("theme", "Dark"))
        self.theme_combo.currentTextChanged.connect(self.apply_theme)
        self.lang_combo = QComboBox(); self.lang_combo.addItems(["en", "hi"]); self.lang_combo.setCurrentText(self.settings.get("language", "en"))
        self.offline_combo = QComboBox(); self.offline_combo.addItems(["false", "true"]); self.offline_combo.setCurrentText(self.settings.get("offline_mode", "false"))
        form = QFormLayout()
        form.addRow("Theme Selection", self.theme_combo)
        form.addRow("Language", self.lang_combo)
        form.addRow("Offline Mode", self.offline_combo)
        layout.addLayout(form)
        save = QPushButton("Save Settings")
        save.clicked.connect(self.save_settings)
        layout.addWidget(save)
        self.settings_info = QTextEdit(); self.settings_info.setReadOnly(True)
        self.settings_info.setPlainText(f"Data directory: {DATA_DIR}\nDatabase: {DB_PATH}\nLogs: {LOG_DIR}\nReports: {REPORT_DIR}")
        layout.addWidget(self.settings_info)

    def change_page(self, row: int) -> None:
        self.stack.setCurrentIndex(max(0, row))
        anim = QPropertyAnimation(self.stack.currentWidget(), b"pos", self)
        anim.setDuration(220)
        anim.setStartValue(self.stack.currentWidget().pos() + QPoint(18, 0))
        anim.setEndValue(self.stack.currentWidget().pos())
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start(QPropertyAnimation.DeleteWhenStopped)

    def apply_theme(self, theme: str) -> None:
        QApplication.instance().setStyleSheet(ThemeManager.stylesheet(theme))
        self.db.set_setting("theme", theme)
        qdarktheme = OptionalModules.load("qdarktheme")
        if qdarktheme and theme == "Dark":
            try:
                qdarktheme.setup_theme("dark")
            except Exception:
                LOGGER.debug("qdarktheme setup failed", exc_info=True)

    def refresh_all(self) -> None:
        self.refresh_printer_table()
        self.refresh_dashboard()
        self.refresh_status_center()
        self.refresh_library()

    def refresh_dashboard(self) -> None:
        rows = self.db.get_printers()
        diagnostics = [self.diagnostics.analyze(r) for r in rows]
        total = len(rows)
        online = sum(1 for r in rows if "offline" not in str(r["status"]).lower() and "error" not in str(r["status"]).lower())
        offline = total - online
        errors = sum(1 for r in rows if "error" in str(r["status"]).lower())
        queue_count = sum(int(r["queue_count"] or 0) for r in rows)
        health = int(sum(d.health for d in diagnostics) / total) if total else 0
        values = {
            "Total Printers": total, "Online Printers": online, "Offline Printers": offline, "Error Count": errors,
            "Driver Issues": sum(d.driver_issue for d in diagnostics), "Network Issues": sum(d.network_issue for d in diagnostics),
            "Print Queue Count": queue_count, "Firmware Alerts": sum(d.firmware_alert for d in diagnostics),
            "Toner Alerts": sum(d.toner_alert for d in diagnostics), "Ink Alerts": sum(d.ink_alert for d in diagnostics),
            "Repair Recommendations": sum(len(d.recommendations) for d in diagnostics), "Health Score": f"{health}%",
            "Fleet Status": "Healthy" if health >= 80 else "Attention" if total else "No printers detected",
        }
        for key, value in values.items():
            self.cards[key].set_value(value)
        self.notification_center.setPlainText("\n".join(self._notifications(rows, diagnostics)))

    def _notifications(self, rows: Sequence[sqlite3.Row], diagnostics: Sequence[DiagnosticResult]) -> List[str]:
        notes = []
        if not rows:
            notes.append("No local printers are currently detected. Run Scan or Network Discovery.")
        for row, diag in zip(rows, diagnostics):
            for rec in diag.recommendations[:2]:
                if diag.health < 90:
                    notes.append(f"{row['name']}: {rec}")
        return notes[:80]

    def refresh_printer_table(self) -> None:
        rows = self.db.get_printers()
        self.printer_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            diag = self.diagnostics.analyze(row)
            if row["health_score"] != diag.health:
                self.db.execute("UPDATE printers SET health_score=? WHERE uuid=?", (diag.health, row["uuid"]))
            values = [row["name"], row["manufacturer"], row["model"], row["status"], row["connection_type"], row["ip_address"], row["queue_count"], f"{diag.health}%", row["last_seen"]]
            for c, value in enumerate(values):
                self.printer_table.setItem(r, c, QTableWidgetItem(str(value or "")))

    def refresh_status_center(self) -> None:
        online = self.connectivity.is_online() if self.settings.get("offline_mode") != "true" else False
        self.status_badge.setText(f"Status: {'Online features active' if online else 'Offline mode'} | Threads: {self.pool.activeThreadCount()} | DB: {DB_PATH.name}")

    def update_details_from_selection(self) -> None:
        rows = self.db.get_printers()
        selected = self.printer_table.currentRow()
        if selected < 0 or selected >= len(rows):
            return
        row = rows[selected]
        diag = self.diagnostics.analyze(row)
        details = [
            f"Printer Image: cached offline when available", f"Manufacturer: {row['manufacturer']}", f"Model: {row['model']}",
            f"Product Number: {row['product_number']}", f"Serial Number: {row['serial_number']}", f"Driver Name: {row['driver_name']}",
            f"Driver Version: {row['driver_version']}", f"Driver Date: {row['driver_date']}", f"Firmware Version: {row['firmware_version']}",
            f"Connection Type: {row['connection_type']}", f"USB Port: {row['usb_port']}", f"IP Address: {row['ip_address']}",
            f"MAC Address: {row['mac_address']}", f"Status: {row['status']}", f"Print Queue: {row['queue_count']}",
            f"Toner Level: {row['toner_level'] if row['toner_level'] is not None else 'Unknown'}", f"Ink Level: {row['ink_level'] if row['ink_level'] is not None else 'Unknown'}",
            f"Health Score: {diag.health}%", f"Last Seen: {row['last_seen']}", f"First Detected: {row['first_detected']}",
            "\nRepair Recommendations:", *[f"• {x}" for x in diag.recommendations],
        ]
        self.details_text.setPlainText("\n".join(details))
        path = self.image_cache.cached_image_for(row)
        self._set_image(path)
        support = self.driver_center.official_support_url(row["manufacturer"] or "", row["model"] or row["name"] or "")
        self.driver_info.setPlainText(
            f"Official Driver / Firmware / Manual Support URL:\n{support or 'No mapped official support URL for this manufacturer.'}\n\n"
            f"Installed Driver: {row['driver_name']}\nVersion: {row['driver_version']}\nCompatibility: {platform.platform()}\n\n"
            "Download, install, update, backup, and restore operations use official manufacturer pages and local backup archives."
        )

    def selected_printer(self) -> Optional[sqlite3.Row]:
        rows = self.db.get_printers()
        idx = self.printer_table.currentRow()
        if 0 <= idx < len(rows):
            return rows[idx]
        return rows[0] if rows else None

    def _set_image(self, path: Optional[Path]) -> None:
        if path and path.exists():
            pix = QPixmap(str(path))
            if not pix.isNull():
                self.image_label.setPixmap(pix.scaled(QSize(300, 220), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                return
        self.image_label.setText("No cached printer image\nOnline fetch available when internet exists")

    def scan_printers(self) -> None:
        worker = Worker(self.detector.detect_all)
        worker.signals.finished.connect(lambda _: (self.refresh_all(), QMessageBox.information(self, "Scan complete", "Printer detection scan completed.")))
        worker.signals.error.connect(lambda e: QMessageBox.critical(self, "Scan failed", e))
        self.pool.start(worker)

    def scan_network(self) -> None:
        cidr = self.cidr_input.text().strip()
        self.db.set_setting("network_scan_cidr", cidr)
        worker = Worker(self.detector.discover_network_printers, cidr)
        worker.signals.finished.connect(self.populate_network)
        worker.signals.error.connect(lambda e: QMessageBox.critical(self, "Network scan failed", e))
        self.pool.start(worker)

    def populate_network(self, devices: List[Dict[str, Any]]) -> None:
        self.network_table.setRowCount(len(devices))
        for r, d in enumerate(devices):
            for c, value in enumerate([d.get("ip"), d.get("hostname"), d.get("status"), d.get("manufacturer"), ", ".join(map(str, d.get("ports", [])))]):
                self.network_table.setItem(r, c, QTableWidgetItem(str(value or "")))
        self.refresh_dashboard()

    def fetch_selected_image(self) -> None:
        printer = self.selected_printer()
        if not printer:
            QMessageBox.information(self, "No printer", "Select or detect a printer first.")
            return
        worker = Worker(self.image_cache.fetch_image, printer)
        worker.signals.finished.connect(lambda path: self._set_image(path))
        worker.signals.error.connect(lambda e: QMessageBox.warning(self, "Image fetch failed", e))
        self.pool.start(worker)

    def open_support(self) -> None:
        printer = self.selected_printer()
        if not printer:
            return
        url = self.driver_center.official_support_url(printer["manufacturer"] or "", printer["model"] or printer["name"] or "")
        if url:
            webbrowser.open(url)
        else:
            QMessageBox.information(self, "Support", "No official support URL mapping is available for this printer brand.")

    def backup_drivers(self) -> None:
        worker = Worker(self.driver_center.backup_drivers)
        worker.signals.finished.connect(lambda path: QMessageBox.information(self, "Backup complete", f"Driver recovery archive created:\n{path}"))
        worker.signals.error.connect(lambda e: QMessageBox.critical(self, "Backup failed", e))
        self.pool.start(worker)

    def search_errors(self) -> None:
        rows = self.expert.search(self.err_brand.text().strip(), self.err_model.text().strip(), self.err_code.text().strip())
        self.error_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [row["brand"], row["model"], row["error_code"], row["severity"], row["category"], row["description"], row["permanent_fix"], row["success_rate"]]
            for c, value in enumerate(values):
                self.error_table.setItem(r, c, QTableWidgetItem(str(value or "")))

    def import_errors(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Error Code CSV", str(DATA_DIR), "CSV Files (*.csv)")
        if not path:
            return
        count = self.expert.import_csv(Path(path))
        QMessageBox.information(self, "Import complete", f"Imported or updated {count} error-code records.")
        self.search_errors()

    def ask_ai(self) -> None:
        self.ai_answer.setPlainText(self.ai.answer(self.ai_question.toPlainText(), self.err_brand.text().strip(), self.err_model.text().strip(), self.err_code.text().strip()))

    def run_wizard(self) -> None:
        result = self.diagnostics.wizard_diagnosis({
            "power": self.wiz_power.currentText(), "connectivity": self.wiz_conn.currentText(), "leds": self.wiz_leds.currentText(),
            "print_result": self.wiz_print.currentText(), "error_code": self.wiz_code.text(),
        })
        self.wizard_output.setPlainText(result)

    def run_auto_repair(self) -> None:
        worker = Worker(self.repair.one_click_repair)
        worker.signals.finished.connect(lambda results: (self.repair_output.setPlainText("\n".join(f"{a}: {b}" for a, b in results)), self.refresh_all()))
        worker.signals.error.connect(lambda e: QMessageBox.critical(self, "Repair failed", e))
        self.pool.start(worker)

    def add_manual(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Add PDF Manual / Service Guide", str(Path.home()), "Documents (*.pdf *.html *.txt);;All Files (*)")
        if not path:
            return
        src = Path(path)
        dest = MANUAL_DIR / f"{dt.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{src.name}"
        shutil.copy2(src, dest)
        digest = hashlib.sha256(dest.read_bytes()).hexdigest()
        self.db.execute(
            "INSERT INTO manuals(title, manual_type, local_path, sha256, updated_at) VALUES(?,?,?,?,?)",
            (src.stem, src.suffix.lstrip(".").upper(), str(dest), digest, dt.datetime.utcnow().isoformat(timespec="seconds")),
        )
        self.refresh_library()

    def refresh_library(self) -> None:
        manuals = self.db.query("SELECT manual_type, manufacturer, model, title, local_path FROM manuals ORDER BY updated_at DESC")
        parts = self.db.query("SELECT 'Part' AS manual_type, manufacturer, model, part_number AS title, replacement_procedure AS local_path FROM parts ORDER BY updated_at DESC")
        rows = manuals + parts
        if not hasattr(self, "library_table"):
            return
        self.library_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate([row["manual_type"], row["manufacturer"], row["model"], row["title"], row["local_path"]]):
                self.library_table.setItem(r, c, QTableWidgetItem(str(value or "")))

    def export_pdf(self) -> None:
        self._report(lambda: self.reports.export_pdf())

    def export_excel(self) -> None:
        self._report(lambda: self.reports.export_excel())

    def export_html(self) -> None:
        self._report(lambda: self.reports.export_html())

    def export_json(self) -> None:
        self._report(lambda: self.reports.export_json())

    def _report(self, fn: Callable[[], Path]) -> None:
        path = fn()
        self.report_output.append(f"Generated report: {path}")

    def save_settings(self) -> None:
        self.db.set_setting("theme", self.theme_combo.currentText())
        self.db.set_setting("language", self.lang_combo.currentText())
        self.db.set_setting("offline_mode", self.offline_combo.currentText())
        self.settings = self.db.get_settings()
        QMessageBox.information(self, "Settings", "Settings saved.")

    def search_everywhere(self, text: str) -> None:
        query = text.strip().lower()
        if not query:
            self.refresh_printer_table()
            return
        rows = [r for r in self.db.get_printers() if query in " ".join(str(r[k] or "") for k in r.keys()).lower()]
        self.printer_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [row["name"], row["manufacturer"], row["model"], row["status"], row["connection_type"], row["ip_address"], row["queue_count"], f"{row['health_score']}%", row["last_seen"]]
            for c, value in enumerate(values):
                self.printer_table.setItem(r, c, QTableWidgetItem(str(value or "")))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() == ".csv":
                count = self.expert.import_csv(path)
                QMessageBox.information(self, "CSV imported", f"Imported {count} error-code records from {path.name}.")
            elif path.suffix.lower() in {".pdf", ".html", ".txt"}:
                dest = MANUAL_DIR / path.name
                shutil.copy2(path, dest)
                self.db.execute("INSERT INTO manuals(title, manual_type, local_path, updated_at) VALUES(?,?,?,?)", (path.stem, path.suffix.lstrip('.').upper(), str(dest), dt.datetime.utcnow().isoformat(timespec="seconds")))
                self.refresh_library()


def excepthook(exc_type: type, exc: BaseException, tb: Any) -> None:
    LOGGER.critical("Unhandled exception", exc_info=(exc_type, exc, tb))
    QMessageBox.critical(None, APP_NAME, "A critical error occurred. Details were written to the application log.")


def main() -> int:
    sys.excepthook = excepthook
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("Printer Doctor")
    db = DatabaseManager()
    app.setStyleSheet(ThemeManager.stylesheet(db.get_settings().get("theme", "Dark")))
    login = LoginDialog(db)
    if login.exec() != QDialog.Accepted:
        return 0
    window = PrinterDoctorApp()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
