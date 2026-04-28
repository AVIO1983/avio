#!/usr/bin/env python3
"""
Ultimate License Injector X
Single-file injector GUI that generates internal multi-module licensing runtime.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import platform
import queue
import shutil
import socket
import subprocess
import sys
import textwrap
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Tuple
from urllib import error, parse, request


@dataclass
class InjectConfig:
    target_path: Path
    app_id: str
    api_url: str
    kill_switch: bool
    offline_mode: bool
    encryption: bool
    anti_debug: bool
    silent_mode: bool
    heartbeat: bool
    auto_updater: bool
    offline_grace_days: int
    check_interval_seconds: int


class ULIX:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Ultimate License Injector X")
        self.root.geometry("1000x760")
        self.root.minsize(940, 700)
        self.q: "queue.Queue[str]" = queue.Queue()
        self.target_var = tk.StringVar()
        self.app_id_var = tk.StringVar()
        self.api_url_var = tk.StringVar()
        self.kill_switch_var = tk.BooleanVar(value=True)
        self.offline_mode_var = tk.BooleanVar(value=True)
        self.encryption_var = tk.BooleanVar(value=True)
        self.anti_debug_var = tk.BooleanVar(value=True)
        self.silent_mode_var = tk.BooleanVar(value=True)
        self.heartbeat_var = tk.BooleanVar(value=True)
        self.auto_updater_var = tk.BooleanVar(value=False)
        self.offline_grace_var = tk.StringVar(value="7")
        self.check_interval_var = tk.StringVar(value="120")
        self._build_ui()
        self.root.after(140, self._flush_logs)

    def _build_ui(self) -> None:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TFrame", background="#141820")
        style.configure("TLabel", background="#141820", foreground="#e8ebef")
        style.configure("Header.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Small.TLabel", font=("Segoe UI", 9), foreground="#a8b3c4")

        self.root.configure(bg="#141820")
        root_frame = ttk.Frame(self.root, padding=18)
        root_frame.pack(fill="both", expand=True)

        ttk.Label(root_frame, text="Ultimate License Injector X", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            root_frame,
            text="Single-file injector that generates secure runtime modules during injection.",
            style="Small.TLabel",
        ).pack(anchor="w", pady=(0, 14))

        card = tk.Frame(root_frame, bg="#1b2230", highlightthickness=1, highlightbackground="#30394a")
        card.pack(fill="x", padx=1, pady=(0, 14))

        self._path_row(card)
        self._config_rows(card)
        self._toggle_rows(card)
        self._button_row(card)

        log_card = tk.Frame(root_frame, bg="#11151e", highlightthickness=1, highlightbackground="#2a3241")
        log_card.pack(fill="both", expand=True)
        ttk.Label(log_card, text="Logs", background="#11151e").pack(anchor="w", padx=10, pady=(8, 4))
        self.log_widget = tk.Text(
            log_card,
            height=20,
            bg="#090d14",
            fg="#d7e2f5",
            insertbackground="#d7e2f5",
            relief="flat",
            font=("Consolas", 10),
            wrap="word",
        )
        self.log_widget.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _path_row(self, parent: tk.Widget) -> None:
        frame = ttk.Frame(parent, padding=(12, 12, 12, 2))
        frame.pack(fill="x")
        ttk.Label(frame, text="Select App (file/folder):").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.target_var, width=92).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        ttk.Button(frame, text="Select File", command=self.select_file).grid(row=1, column=3, padx=(8, 4))
        ttk.Button(frame, text="Select Folder", command=self.select_folder).grid(row=1, column=4)
        frame.columnconfigure(0, weight=1)

    def _config_rows(self, parent: tk.Widget) -> None:
        frame = ttk.Frame(parent, padding=(12, 8, 12, 2))
        frame.pack(fill="x")

        ttk.Label(frame, text="App ID").grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text="API URL").grid(row=0, column=1, sticky="w", padx=(12, 0))
        ttk.Entry(frame, textvariable=self.app_id_var).grid(row=1, column=0, sticky="ew", pady=(4, 8))
        ttk.Entry(frame, textvariable=self.api_url_var).grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=(4, 8))

        ttk.Label(frame, text="Offline Grace Days").grid(row=2, column=0, sticky="w")
        ttk.Label(frame, text="Check Interval (seconds)").grid(row=2, column=1, sticky="w", padx=(12, 0))
        ttk.Entry(frame, textvariable=self.offline_grace_var).grid(row=3, column=0, sticky="ew", pady=(4, 8))
        ttk.Entry(frame, textvariable=self.check_interval_var).grid(row=3, column=1, sticky="ew", padx=(12, 0), pady=(4, 8))

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

    def _toggle_rows(self, parent: tk.Widget) -> None:
        frame = ttk.Frame(parent, padding=(12, 2, 12, 6))
        frame.pack(fill="x")
        toggles = [
            ("Kill Switch", self.kill_switch_var),
            ("Offline Mode", self.offline_mode_var),
            ("Encryption", self.encryption_var),
            ("Anti-Debug", self.anti_debug_var),
            ("Silent Mode", self.silent_mode_var),
            ("Heartbeat", self.heartbeat_var),
            ("Auto-Updater", self.auto_updater_var),
        ]
        for i, (label, var) in enumerate(toggles):
            ttk.Checkbutton(frame, text=label, variable=var).grid(row=i // 4, column=i % 4, sticky="w", padx=(0, 10), pady=3)

    def _button_row(self, parent: tk.Widget) -> None:
        frame = ttk.Frame(parent, padding=(12, 4, 12, 12))
        frame.pack(fill="x")
        ttk.Button(frame, text="Inject License", command=self.inject_license).pack(side="left", padx=(0, 8))
        ttk.Button(frame, text="Wrapper Mode", command=self.wrapper_mode).pack(side="left", padx=(0, 8))
        ttk.Button(frame, text="Build EXE", command=self.build_exe).pack(side="left")

    def select_file(self) -> None:
        p = filedialog.askopenfilename(title="Select Python entry file", filetypes=[("Python", "*.py"), ("All", "*.*")])
        if p:
            self.target_var.set(p)
            self._log(f"Selected file: {p}")

    def select_folder(self) -> None:
        p = filedialog.askdirectory(title="Select application folder")
        if p:
            self.target_var.set(p)
            self._log(f"Selected folder: {p}")

    def inject_license(self) -> None:
        cfg = self._validate_config()
        if not cfg:
            return
        threading.Thread(target=self._inject_worker, args=(cfg,), daemon=True).start()

    def wrapper_mode(self) -> None:
        cfg = self._validate_config()
        if not cfg:
            return
        threading.Thread(target=self._wrapper_worker, args=(cfg,), daemon=True).start()

    def build_exe(self) -> None:
        cfg = self._validate_config(allow_missing_target=False)
        if not cfg:
            return
        threading.Thread(target=self._build_worker, args=(cfg,), daemon=True).start()

    def _validate_config(self, allow_missing_target: bool = False) -> Optional[InjectConfig]:
        target_raw = self.target_var.get().strip()
        if not target_raw and not allow_missing_target:
            messagebox.showerror("Missing target", "Select a Python file or folder.")
            return None
        target_path = Path(target_raw).expanduser().resolve() if target_raw else Path.cwd()
        if not allow_missing_target and not target_path.exists():
            messagebox.showerror("Invalid target", "Selected path does not exist.")
            return None

        app_id = self.app_id_var.get().strip()
        api_url = self.api_url_var.get().strip().rstrip("/")
        if not app_id or not api_url:
            messagebox.showerror("Invalid settings", "App ID and API URL are required.")
            return None

        try:
            grace = int(self.offline_grace_var.get().strip())
            interval = int(self.check_interval_var.get().strip())
            if grace < 0 or interval < 5:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid numeric values", "Grace days must be >= 0 and check interval >= 5.")
            return None

        return InjectConfig(
            target_path=target_path,
            app_id=app_id,
            api_url=api_url,
            kill_switch=self.kill_switch_var.get(),
            offline_mode=self.offline_mode_var.get(),
            encryption=self.encryption_var.get(),
            anti_debug=self.anti_debug_var.get(),
            silent_mode=self.silent_mode_var.get(),
            heartbeat=self.heartbeat_var.get(),
            auto_updater=self.auto_updater_var.get(),
            offline_grace_days=grace,
            check_interval_seconds=interval,
        )

    def _inject_worker(self, cfg: InjectConfig) -> None:
        try:
            self._log("Starting injection...")
            target_file, base_dir = self._resolve_entry(cfg.target_path)
            self._generate_modules(base_dir, cfg)
            self._inject_snippet(target_file, cfg)
            self._log(f"Injection complete: {target_file}")
        except Exception as exc:
            self._log(f"Injection failed: {exc}")

    def _wrapper_worker(self, cfg: InjectConfig) -> None:
        try:
            self._log("Running wrapper mode...")
            entry, base_dir = self._resolve_entry(cfg.target_path)
            self._generate_modules(base_dir, cfg)
            wrapper = base_dir / "lx_wrapper.py"
            wrapper_text = textwrap.dedent(
                f'''\
                from core.engine import LXManager
                LXManager("{cfg.app_id}", "{cfg.api_url}").boot()

                import runpy
                runpy.run_path(r"{entry}", run_name="__main__")
                '''
            )
            wrapper.write_text(wrapper_text, encoding="utf-8")
            self._log(f"Wrapper created: {wrapper}")
        except Exception as exc:
            self._log(f"Wrapper mode failed: {exc}")

    def _build_worker(self, cfg: InjectConfig) -> None:
        try:
            entry, base_dir = self._resolve_entry(cfg.target_path)
            self._log("Checking PyInstaller availability...")
            check = subprocess.run([sys.executable, "-m", "PyInstaller", "--version"], capture_output=True, text=True)
            if check.returncode != 0:
                raise RuntimeError("PyInstaller is not installed in this environment.")
            self._log("Building single-file executable...")
            cmd = [
                sys.executable,
                "-m",
                "PyInstaller",
                "--noconfirm",
                "--onefile",
                "--name",
                "app",
                str(entry),
            ]
            run = subprocess.run(cmd, cwd=str(base_dir), capture_output=True, text=True)
            if run.returncode != 0:
                raise RuntimeError(run.stderr.strip() or "PyInstaller failed.")
            self._log(f"Build complete: {base_dir / 'dist' / 'app.exe'}")
        except Exception as exc:
            self._log(f"Build failed: {exc}")

    def _resolve_entry(self, target_path: Path) -> Tuple[Path, Path]:
        if target_path.is_file():
            return target_path, target_path.parent
        candidates = [target_path / "main.py", target_path / "app.py", target_path / "__main__.py"]
        for c in candidates:
            if c.exists():
                return c, target_path
        py_files = list(target_path.glob("*.py"))
        if py_files:
            return py_files[0], target_path
        raise FileNotFoundError("No Python entry file found in selected folder.")

    def _inject_snippet(self, file_path: Path, cfg: InjectConfig) -> None:
        snippet = f'from core.engine import LXManager\nLXManager("{cfg.app_id}", "{cfg.api_url}").boot()\n'
        source = file_path.read_text(encoding="utf-8")
        if "from core.engine import LXManager" in source:
            self._log("Injection snippet already exists; skipping source rewrite.")
            return
        file_path.write_text(f"{snippet}\n{source}", encoding="utf-8")

    def _generate_modules(self, base_dir: Path, cfg: InjectConfig) -> None:
        core_dir = base_dir / "core"
        core_dir.mkdir(exist_ok=True)
        (core_dir / "__init__.py").write_text("", encoding="utf-8")
        for rel, content in self._module_map(cfg).items():
            (core_dir / rel).write_text(content, encoding="utf-8")
            self._log(f"Generated module: core/{rel}")

    def _module_map(self, cfg: InjectConfig) -> Dict[str, str]:
        flags = {
            "kill_switch": cfg.kill_switch,
            "offline_mode": cfg.offline_mode,
            "encryption": cfg.encryption,
            "anti_debug": cfg.anti_debug,
            "silent_mode": cfg.silent_mode,
            "heartbeat": cfg.heartbeat,
            "auto_updater": cfg.auto_updater,
            "offline_grace_days": cfg.offline_grace_days,
            "check_interval_seconds": cfg.check_interval_seconds,
        }
        jflags = json.dumps(flags)
        return {
            "engine.py": _engine_py(cfg.app_id, cfg.api_url, jflags),
            "guard.py": _guard_py(),
            "sysid.py": _sysid_py(),
            "secure_store.py": _secure_store_py(),
            "ui_activation.py": _ui_activation_py(),
            "anti_debug.py": _anti_debug_py(),
            "integrity.py": _integrity_py(),
            "heartbeat.py": _heartbeat_py(),
            "updater.py": _updater_py(),
            "feature_lock.py": _feature_lock_py(),
        }

    def _log(self, msg: str) -> None:
        self.q.put(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def _flush_logs(self) -> None:
        while True:
            try:
                line = self.q.get_nowait()
            except queue.Empty:
                break
            self.log_widget.insert("end", line + "\n")
            self.log_widget.see("end")
        self.root.after(140, self._flush_logs)

    def run(self) -> None:
        self.root.mainloop()


def _engine_py(app_id: str, api_url: str, jflags: str) -> str:
    return textwrap.dedent(
        f'''\
        import json
        import os
        import threading
        import time
        from urllib import error, parse, request

        from .anti_debug import d0
        from .feature_lock import F0
        from .guard import G0
        from .heartbeat import H0
        from .integrity import I0
        from .secure_store import S0
        from .sysid import Y0
        from .ui_activation import U0
        from .updater import P0

        _CFG = json.loads(r"""{jflags}""")


        class LXManager:
            def __init__(self, a, u):
                self._a = a
                self._u = u
                self._s = S0(a)
                self._g = G0(_CFG.get("offline_grace_days", 7))
                self._l = F0()
                self._stop = threading.Event()

            def _net(self, path, body):
                url = self._u + path
                payload = json.dumps(body).encode("utf-8")
                req = request.Request(url, data=payload, method="POST", headers={{"Content-Type": "application/json"}})
                with request.urlopen(req, timeout=8) as r:
                    return json.loads(r.read().decode("utf-8"))

            def _online(self, lic):
                try:
                    return self._net("/validate", {{
                        "app_id": self._a,
                        "license": lic,
                        "device": Y0(),
                    }})
                except Exception:
                    return None

            def _kill(self):
                os._exit(0)

            def boot(self):
                if _CFG.get("anti_debug", True) and d0():
                    self._kill()

                i = I0()
                i.baseline()

                c = self._s.read()
                lic = c.get("license")
                resp = self._online(lic) if lic else None

                if resp and resp.get("status") == "valid":
                    self._s.write({{
                        "license": lic,
                        "last_valid": int(time.time()),
                        "features": resp.get("features", {{}}),
                        "kill": bool(resp.get("kill", False)),
                    }})
                    self._l.apply(resp.get("features", {{}}))
                elif resp and resp.get("status") == "revoked":
                    self._s.clear()
                    if _CFG.get("kill_switch", True):
                        self._kill()
                else:
                    if not _CFG.get("offline_mode", True) or not self._g.allow(c):
                        d = U0().prompt()
                        if not d:
                            self._kill()
                        lic = d.get("license")
                        check = self._online(lic)
                        if not check or check.get("status") != "valid":
                            self._kill()
                        self._s.write({{
                            "license": lic,
                            "last_valid": int(time.time()),
                            "features": check.get("features", {{}}),
                            "kill": bool(check.get("kill", False)),
                        }})
                        self._l.apply(check.get("features", {{}}))

                c2 = self._s.read()
                if c2.get("kill") and _CFG.get("kill_switch", True):
                    self._kill()

                if _CFG.get("heartbeat", True):
                    H0(self._u, self._a, self._s, self._l, self._stop, _CFG.get("check_interval_seconds", 120)).start()
                if _CFG.get("auto_updater", False):
                    P0(self._u, self._a, self._s).start()

                if not i.verify():
                    self._kill()
        '''
    )


def _guard_py() -> str:
    return textwrap.dedent(
        '''\
        import time


        class G0:
            def __init__(self, days):
                self._s = int(days) * 86400

            def allow(self, cache):
                if not isinstance(cache, dict):
                    return False
                t = int(cache.get("last_valid", 0))
                if not t:
                    return False
                return (int(time.time()) - t) <= self._s
        '''
    )


def _sysid_py() -> str:
    return textwrap.dedent(
        '''\
        import hashlib
        import os
        import platform
        import socket


        def Y0():
            parts = [
                platform.system(),
                platform.release(),
                platform.machine(),
                socket.gethostname(),
                os.environ.get("PROCESSOR_IDENTIFIER", ""),
            ]
            raw = "|".join(parts).encode("utf-8")
            return hashlib.sha256(raw).hexdigest()
        '''
    )


def _secure_store_py() -> str:
    return textwrap.dedent(
        '''\
        import base64
        import hashlib
        import hmac
        import json
        from pathlib import Path


        class S0:
            def __init__(self, app_id):
                self._p = Path(".sys_cache")
                self._k = hashlib.sha256(("K@" + app_id).encode("utf-8")).digest()

            def _x(self, b):
                return bytes(b[i] ^ self._k[i % len(self._k)] for i in range(len(b)))

            def write(self, obj):
                raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
                enc = base64.b64encode(self._x(raw))
                sig = hmac.new(self._k, enc, hashlib.sha256).hexdigest().encode("utf-8")
                self._p.write_bytes(sig + b"\n" + enc)

            def read(self):
                if not self._p.exists():
                    return {}
                blob = self._p.read_bytes().split(b"\n", 1)
                if len(blob) != 2:
                    return {}
                sig, enc = blob
                chk = hmac.new(self._k, enc, hashlib.sha256).hexdigest().encode("utf-8")
                if not hmac.compare_digest(sig, chk):
                    return {}
                try:
                    return json.loads(self._x(base64.b64decode(enc)).decode("utf-8"))
                except Exception:
                    return {}

            def clear(self):
                if self._p.exists():
                    self._p.unlink(missing_ok=True)
        '''
    )


def _ui_activation_py() -> str:
    return textwrap.dedent(
        '''\
        import tkinter as tk


        class U0:
            def prompt(self):
                out = {}
                root = tk.Tk()
                root.title("Activation Required")
                root.geometry("420x300")
                root.resizable(False, False)

                fields = ["license", "name", "email", "mobile"]
                vars_ = {f: tk.StringVar() for f in fields}

                for i, f in enumerate(fields):
                    tk.Label(root, text=f.title()).grid(row=i, column=0, padx=12, pady=10, sticky="w")
                    tk.Entry(root, textvariable=vars_[f], width=36).grid(row=i, column=1, padx=12, pady=10)

                def done():
                    out.update({k: v.get().strip() for k, v in vars_.items()})
                    root.destroy()

                def stop():
                    out.clear()
                    root.destroy()

                tk.Button(root, text="Activate", command=done).grid(row=5, column=1, sticky="e", padx=12, pady=12)
                tk.Button(root, text="Cancel", command=stop).grid(row=5, column=0, sticky="w", padx=12, pady=12)
                root.protocol("WM_DELETE_WINDOW", stop)
                root.mainloop()
                return out
        '''
    )


def _anti_debug_py() -> str:
    return textwrap.dedent(
        '''\
        import os
        import sys


        def d0():
            if sys.gettrace() is not None:
                return True
            if os.environ.get("PYTHONINSPECT"):
                return True
            return False
        '''
    )


def _integrity_py() -> str:
    return textwrap.dedent(
        '''\
        import hashlib
        from pathlib import Path


        class I0:
            def __init__(self):
                self._h = {}

            def _m(self):
                root = Path(__file__).resolve().parent
                names = ["engine.py", "guard.py", "sysid.py", "secure_store.py", "anti_debug.py", "heartbeat.py", "updater.py", "feature_lock.py"]
                return [root / n for n in names if (root / n).exists()]

            def baseline(self):
                for p in self._m():
                    self._h[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()

            def verify(self):
                for p in self._m():
                    if hashlib.sha256(p.read_bytes()).hexdigest() != self._h.get(str(p), ""):
                        return False
                return True
        '''
    )


def _heartbeat_py() -> str:
    return textwrap.dedent(
        '''\
        import json
        import threading
        from urllib import request


        class H0(threading.Thread):
            def __init__(self, api, app_id, store, lock, stop, iv):
                super().__init__(daemon=True)
                self._u = api
                self._a = app_id
                self._s = store
                self._l = lock
                self._x = stop
                self._iv = max(5, int(iv))
                self._miss = 0

            def run(self):
                while not self._x.wait(self._iv):
                    cache = self._s.read()
                    lic = cache.get("license")
                    if not lic:
                        self._l.restrict_all()
                        continue
                    ok = self._ping(lic)
                    if ok is None:
                        self._miss += 1
                        if self._miss >= 3:
                            self._l.restrict_partial()
                    else:
                        self._miss = 0
                        self._l.apply(ok.get("features", {}))

            def _ping(self, license_key):
                try:
                    payload = json.dumps({"app_id": self._a, "license": license_key}).encode("utf-8")
                    req = request.Request(self._u + "/heartbeat", data=payload, method="POST", headers={"Content-Type": "application/json"})
                    with request.urlopen(req, timeout=7) as r:
                        return json.loads(r.read().decode("utf-8"))
                except Exception:
                    return None
        '''
    )


def _updater_py() -> str:
    return textwrap.dedent(
        '''\
        import json
        import os
        import shutil
        import tempfile
        import threading
        from pathlib import Path
        from urllib import request


        class P0(threading.Thread):
            def __init__(self, api, app_id, store):
                super().__init__(daemon=True)
                self._u = api
                self._a = app_id
                self._s = store

            def run(self):
                cache = self._s.read()
                if not cache.get("license"):
                    return
                meta = self._check(cache.get("license"))
                if not meta or not meta.get("update"):
                    return
                url = meta.get("url")
                if not url:
                    return
                self._download(url)

            def _check(self, lic):
                try:
                    b = json.dumps({"app_id": self._a, "license": lic}).encode("utf-8")
                    req = request.Request(self._u + "/update", data=b, method="POST", headers={"Content-Type": "application/json"})
                    with request.urlopen(req, timeout=8) as r:
                        return json.loads(r.read().decode("utf-8"))
                except Exception:
                    return None

            def _download(self, url):
                try:
                    fd, p = tempfile.mkstemp(prefix="ulix_", suffix=".bin")
                    os.close(fd)
                    with request.urlopen(url, timeout=12) as r, open(p, "wb") as f:
                        f.write(r.read())
                    target = Path(sys.argv[0]).resolve()
                    bak = target.with_suffix(target.suffix + ".bak")
                    shutil.copy2(target, bak)
                    shutil.copy2(p, target)
                except Exception:
                    return
        '''
    )


def _feature_lock_py() -> str:
    return textwrap.dedent(
        '''\
        class F0:
            def __init__(self):
                self._state = {}

            def apply(self, features):
                self._state = dict(features or {})

            def restrict_partial(self):
                self._state["network"] = False
                self._state["reports"] = False

            def restrict_all(self):
                for k in list(self._state.keys()):
                    self._state[k] = False
                self._state["locked"] = True

            def enabled(self, name):
                return bool(self._state.get(name, True))
        '''
    )


def main() -> None:
    ULIX().run()


if __name__ == "__main__":
    main()
