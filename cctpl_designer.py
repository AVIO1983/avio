import json
import math
import os
from dataclasses import dataclass
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageTk
import fitz


APP_TITLE = "CCTPL Template Designer"
HISTORY_FILE = "template_history.json"
DEFAULT_DPI = 300
MAX_PREVIEW_SIZE = (220, 140)


@dataclass
class CropData:
    abs_coords: list
    normalized: list
    xywh: list


class TemplateDesignerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1400x860")
        self.root.minsize(1100, 720)

        self.current_image = None
        self.current_image_path = None
        self.current_image_size = (0, 0)
        self.loaded_dpi = DEFAULT_DPI

        self.zoom = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 12.0
        self.pan_x = 0
        self.pan_y = 0

        self.active_tool = tk.StringVar(value="crop")
        self.template_name_var = tk.StringVar(value="(unsaved)")

        self.front_crop = None
        self.rear_crop = None

        self.tk_canvas_image = None
        self.display_image = None
        self.canvas_image_id = None

        self.drag_start_canvas = None
        self.drag_start_image = None
        self.crop_rect_canvas_id = None
        self.current_crop_data = None
        self.is_dragging = False

        self.preview_photo = None

        self.templates = []

        self._configure_theme()
        self._build_ui()
        self._bind_canvas_events()
        self.load_history()

    def _configure_theme(self):
        bg = "#1E1F24"
        panel = "#252831"
        card = "#2D313C"
        accent = "#5B9BFF"
        fg = "#ECEFF4"
        muted = "#AAB0BE"

        self.colors = {
            "bg": bg,
            "panel": panel,
            "card": card,
            "accent": accent,
            "fg": fg,
            "muted": muted,
            "border": "#3A3F4E",
            "success": "#57C478",
            "warning": "#F0B429",
        }

        style = ttk.Style(self.root)
        style.theme_use("clam")
        self.root.configure(bg=bg)

        style.configure("TFrame", background=bg)
        style.configure("Panel.TFrame", background=panel)
        style.configure("Card.TFrame", background=card)
        style.configure("TLabel", background=bg, foreground=fg, font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=panel, foreground=fg, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=panel, foreground=muted, font=("Segoe UI", 9))
        style.configure("Header.TLabel", background=panel, foreground=fg, font=("Segoe UI Semibold", 13))
        style.configure("Accent.TButton", font=("Segoe UI Semibold", 10), padding=(10, 6))
        style.map(
            "Accent.TButton",
            background=[("!disabled", accent), ("pressed", "#447BD8"), ("active", "#4C89EA")],
            foreground=[("!disabled", "#FFFFFF")],
        )
        style.configure("TButton", padding=(8, 5), font=("Segoe UI", 10), background=card, foreground=fg)
        style.map(
            "TButton",
            background=[("active", "#3B4352"), ("pressed", "#333A47")],
            foreground=[("disabled", "#6F7788")],
        )
        style.configure(
            "TRadiobutton",
            background=panel,
            foreground=fg,
            indicatorcolor=panel,
            focuscolor=panel,
            font=("Segoe UI", 10),
        )
        style.map("TRadiobutton", background=[("active", panel)], foreground=[("active", fg)])

        style.configure(
            "Treeview",
            background=card,
            fieldbackground=card,
            foreground=fg,
            bordercolor=self.colors["border"],
            rowheight=28,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Treeview.Heading",
            background=panel,
            foreground=fg,
            font=("Segoe UI Semibold", 10),
        )
        style.map("Treeview", background=[("selected", "#3B6ACB")], foreground=[("selected", "#FFFFFF")])

    def _build_ui(self):
        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True)

        sidebar = ttk.Frame(main, style="Panel.TFrame", width=380)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        workspace = ttk.Frame(main)
        workspace.pack(side="left", fill="both", expand=True)

        self._build_sidebar(sidebar)
        self._build_workspace(workspace)

    def _build_sidebar(self, sidebar):
        pad = {"padx": 14, "pady": 8}

        ttk.Label(sidebar, text="CCTPL Designer", style="Header.TLabel").pack(anchor="w", padx=14, pady=(16, 4))
        ttk.Label(sidebar, text="Create ID card front/rear crop templates", style="Muted.TLabel").pack(
            anchor="w", padx=14, pady=(0, 12)
        )

        file_card = ttk.Frame(sidebar, style="Card.TFrame")
        file_card.pack(fill="x", padx=14, pady=(0, 10))
        ttk.Button(file_card, text="Open PDF / Image", command=self.open_file, style="Accent.TButton").pack(fill="x", padx=10, pady=10)
        ttk.Label(file_card, text="Template name:", style="Panel.TLabel").pack(anchor="w", padx=10)
        ttk.Label(file_card, textvariable=self.template_name_var, style="Panel.TLabel").pack(
            anchor="w", padx=10, pady=(0, 8)
        )

        tool_card = ttk.Frame(sidebar, style="Card.TFrame")
        tool_card.pack(fill="x", padx=14, pady=(0, 10))
        ttk.Label(tool_card, text="Tools", style="Panel.TLabel").pack(anchor="w", padx=10, pady=(10, 6))

        radios = ttk.Frame(tool_card, style="Card.TFrame")
        radios.pack(fill="x", padx=8)
        ttk.Radiobutton(radios, text="Crop Tool", value="crop", variable=self.active_tool).pack(side="left", padx=(2, 10))
        ttk.Radiobutton(radios, text="Hand Tool", value="hand", variable=self.active_tool).pack(side="left", padx=(0, 10))

        zf = ttk.Frame(tool_card, style="Card.TFrame")
        zf.pack(fill="x", padx=8, pady=8)
        ttk.Button(zf, text="Zoom -", command=lambda: self.change_zoom(0.85)).pack(side="left")
        ttk.Button(zf, text="Zoom +", command=lambda: self.change_zoom(1.15)).pack(side="left", padx=6)
        ttk.Button(zf, text="Reset View", command=self.reset_view).pack(side="left")

        self.zoom_label = ttk.Label(tool_card, text="Zoom: 100%", style="Muted.TLabel")
        self.zoom_label.pack(anchor="w", padx=10, pady=(0, 10))

        crop_card = ttk.Frame(sidebar, style="Card.TFrame")
        crop_card.pack(fill="x", padx=14, pady=(0, 10))
        ttk.Label(crop_card, text="Crop Actions", style="Panel.TLabel").pack(anchor="w", padx=10, pady=(10, 6))

        ttk.Button(crop_card, text="Save FRONT", command=lambda: self.save_side_crop("front"), style="Accent.TButton").pack(
            fill="x", padx=10, pady=(0, 6)
        )
        ttk.Button(crop_card, text="Save REAR", command=lambda: self.save_side_crop("rear")).pack(fill="x", padx=10, pady=(0, 6))
        ttk.Button(crop_card, text="Export CCTPL Template", command=self.export_template).pack(fill="x", padx=10, pady=(0, 10))

        self.front_status = ttk.Label(crop_card, text="FRONT: not set", style="Muted.TLabel")
        self.front_status.pack(anchor="w", padx=10)
        self.rear_status = ttk.Label(crop_card, text="REAR: not set", style="Muted.TLabel")
        self.rear_status.pack(anchor="w", padx=10, pady=(0, 10))

        preview_card = ttk.Frame(sidebar, style="Card.TFrame")
        preview_card.pack(fill="x", padx=14, pady=(0, 10))
        ttk.Label(preview_card, text="Crop Preview", style="Panel.TLabel").pack(anchor="w", padx=10, pady=(10, 6))
        self.preview_label = tk.Label(
            preview_card,
            text="No crop selected",
            bg=self.colors["card"],
            fg=self.colors["muted"],
            width=30,
            height=8,
            bd=1,
            relief="solid",
            highlightthickness=0,
        )
        self.preview_label.pack(fill="both", padx=10, pady=(0, 10))

        history_card = ttk.Frame(sidebar, style="Card.TFrame")
        history_card.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        ttk.Label(history_card, text="Template History", style="Panel.TLabel").pack(
            anchor="w", padx=10, pady=(10, 6)
        )
        self.history_tree = ttk.Treeview(history_card, columns=("name", "time"), show="headings", selectmode="browse", height=12)
        self.history_tree.heading("name", text="Template")
        self.history_tree.heading("time", text="Saved At")
        self.history_tree.column("name", width=180, anchor="w")
        self.history_tree.column("time", width=150, anchor="w")
        self.history_tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.history_tree.bind("<Double-1>", self.open_selected_record)

    def _build_workspace(self, workspace):
        top = ttk.Frame(workspace)
        top.pack(fill="x", padx=10, pady=(10, 4))
        self.info_label = ttk.Label(top, text="Load a PDF or image to begin.", style="Muted.TLabel")
        self.info_label.pack(anchor="w")

        canvas_frame = ttk.Frame(workspace)
        canvas_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.canvas = tk.Canvas(
            canvas_frame,
            bg="#13161C",
            highlightthickness=0,
            cursor="cross",
        )
        self.canvas.pack(fill="both", expand=True)

    def _bind_canvas_events(self):
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-4>", lambda e: self.zoom_at_point(1.1, e.x, e.y))
        self.canvas.bind("<Button-5>", lambda e: self.zoom_at_point(0.9, e.x, e.y))
        self.canvas.bind("<Configure>", lambda _e: self.redraw_canvas())

    def open_file(self):
        path = filedialog.askopenfilename(
            title="Open PDF or Image",
            filetypes=[
                ("Supported Files", "*.pdf *.png *.jpg *.jpeg"),
                ("PDF", "*.pdf"),
                ("Image", "*.png *.jpg *.jpeg"),
                ("All Files", "*.*"),
            ],
        )
        if not path:
            return

        try:
            ext = os.path.splitext(path)[1].lower()
            if ext == ".pdf":
                image = self._render_pdf_to_image(path)
            else:
                image = Image.open(path).convert("RGB")

            self.current_image = image
            self.current_image_path = path
            self.current_image_size = image.size
            self.current_crop_data = None
            self.clear_crop_visual()
            self.update_preview(None)
            self.reset_view(auto_center=True)
            self.info_label.configure(
                text=f"Loaded: {os.path.basename(path)} | Size: {image.size[0]}x{image.size[1]} | DPI: {self.loaded_dpi}"
            )
        except Exception as exc:
            messagebox.showerror("Open failed", f"Unable to open file:\n{exc}")

    def _render_pdf_to_image(self, path: str) -> Image.Image:
        doc = fitz.open(path)
        if doc.needs_pass:
            password = simpledialog.askstring("Password Required", "This PDF is password protected. Enter password:", show="*")
            if password is None:
                doc.close()
                raise ValueError("Password entry cancelled")
            if not doc.authenticate(password):
                doc.close()
                raise ValueError("Invalid PDF password")

        page = doc[0]
        matrix = fitz.Matrix(self.loaded_dpi / 72, self.loaded_dpi / 72)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        mode = "RGB"
        image = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
        doc.close()
        return image

    def reset_view(self, auto_center=False):
        if self.current_image is None:
            return
        self.zoom = 1.0
        if auto_center:
            cw = max(self.canvas.winfo_width(), 1)
            ch = max(self.canvas.winfo_height(), 1)
            iw, ih = self.current_image.size
            self.pan_x = (cw - iw) / 2
            self.pan_y = (ch - ih) / 2
        self.redraw_canvas()

    def change_zoom(self, factor):
        cw = self.canvas.winfo_width() // 2
        ch = self.canvas.winfo_height() // 2
        self.zoom_at_point(factor, cw, ch)

    def on_mouse_wheel(self, event):
        if event.delta > 0:
            self.zoom_at_point(1.1, event.x, event.y)
        else:
            self.zoom_at_point(0.9, event.x, event.y)

    def zoom_at_point(self, factor, canvas_x, canvas_y):
        if self.current_image is None:
            return
        new_zoom = max(self.min_zoom, min(self.max_zoom, self.zoom * factor))
        if math.isclose(new_zoom, self.zoom):
            return

        img_x, img_y = self.canvas_to_image(canvas_x, canvas_y)
        self.zoom = new_zoom
        self.pan_x = canvas_x - img_x * self.zoom
        self.pan_y = canvas_y - img_y * self.zoom
        self.redraw_canvas()

    def redraw_canvas(self):
        self.canvas.delete("all")
        self.canvas_image_id = None
        if self.current_image is None:
            self.zoom_label.configure(text="Zoom: 100%")
            return

        iw, ih = self.current_image.size
        dw = max(1, int(round(iw * self.zoom)))
        dh = max(1, int(round(ih * self.zoom)))

        self.display_image = self.current_image.resize((dw, dh), Image.Resampling.LANCZOS)
        self.tk_canvas_image = ImageTk.PhotoImage(self.display_image)
        self.canvas_image_id = self.canvas.create_image(self.pan_x, self.pan_y, image=self.tk_canvas_image, anchor="nw")

        self.zoom_label.configure(text=f"Zoom: {int(self.zoom * 100)}%")

        if self.current_crop_data:
            self.draw_crop_rect(self.current_crop_data.abs_coords)

    def canvas_to_image(self, x, y):
        if self.zoom == 0:
            return 0, 0
        return (x - self.pan_x) / self.zoom, (y - self.pan_y) / self.zoom

    def clamp_to_image(self, x, y):
        if self.current_image is None:
            return 0, 0
        iw, ih = self.current_image.size
        return max(0, min(iw, x)), max(0, min(ih, y))

    def on_mouse_down(self, event):
        if self.current_image is None:
            return
        self.is_dragging = True
        if self.active_tool.get() == "hand":
            self.canvas.configure(cursor="fleur")
            self.drag_start_canvas = (event.x, event.y)
        else:
            self.canvas.configure(cursor="cross")
            ix, iy = self.canvas_to_image(event.x, event.y)
            ix, iy = self.clamp_to_image(ix, iy)
            self.drag_start_image = (ix, iy)
            self.current_crop_data = None
            self.clear_crop_visual()

    def on_mouse_drag(self, event):
        if not self.is_dragging or self.current_image is None:
            return

        if self.active_tool.get() == "hand":
            if not self.drag_start_canvas:
                return
            sx, sy = self.drag_start_canvas
            dx, dy = event.x - sx, event.y - sy
            self.pan_x += dx
            self.pan_y += dy
            self.drag_start_canvas = (event.x, event.y)
            self.redraw_canvas()
        else:
            if not self.drag_start_image:
                return
            ex, ey = self.canvas_to_image(event.x, event.y)
            ex, ey = self.clamp_to_image(ex, ey)
            abs_coords = self._normalize_abs_coords([self.drag_start_image[0], self.drag_start_image[1], ex, ey])
            if abs_coords:
                self.draw_crop_rect(abs_coords)
                self.current_crop_data = self.build_crop_data(abs_coords)
                self.update_preview(self.current_crop_data)

    def on_mouse_up(self, event):
        if self.current_image is None:
            return
        self.is_dragging = False
        self.canvas.configure(cursor="cross" if self.active_tool.get() == "crop" else "fleur")

        if self.active_tool.get() == "crop" and self.drag_start_image:
            ex, ey = self.canvas_to_image(event.x, event.y)
            ex, ey = self.clamp_to_image(ex, ey)
            abs_coords = self._normalize_abs_coords([self.drag_start_image[0], self.drag_start_image[1], ex, ey])
            self.current_crop_data = self.build_crop_data(abs_coords)
            self.update_preview(self.current_crop_data)
        self.drag_start_canvas = None
        self.drag_start_image = None

    def _normalize_abs_coords(self, coords):
        x1, y1, x2, y2 = coords
        x1, x2 = sorted([int(round(x1)), int(round(x2))])
        y1, y2 = sorted([int(round(y1)), int(round(y2))])
        if x2 <= x1 or y2 <= y1:
            return None
        iw, ih = self.current_image.size
        x1 = max(0, min(iw, x1))
        x2 = max(0, min(iw, x2))
        y1 = max(0, min(ih, y1))
        y2 = max(0, min(ih, y2))
        if x2 <= x1 or y2 <= y1:
            return None
        return [x1, y1, x2, y2]

    def draw_crop_rect(self, abs_coords):
        self.clear_crop_visual()
        if not abs_coords:
            return
        x1, y1, x2, y2 = abs_coords
        cx1 = self.pan_x + x1 * self.zoom
        cy1 = self.pan_y + y1 * self.zoom
        cx2 = self.pan_x + x2 * self.zoom
        cy2 = self.pan_y + y2 * self.zoom

        self.crop_rect_canvas_id = self.canvas.create_rectangle(
            cx1,
            cy1,
            cx2,
            cy2,
            outline="#50A6FF",
            width=2,
            dash=(6, 3),
        )

        self.canvas.create_rectangle(cx1, cy1, cx2, cy2, outline="", fill="#4CA0FF", stipple="gray25")

    def clear_crop_visual(self):
        if self.crop_rect_canvas_id:
            self.canvas.delete(self.crop_rect_canvas_id)
            self.crop_rect_canvas_id = None

    def build_crop_data(self, abs_coords):
        if not abs_coords or self.current_image is None:
            return None
        x1, y1, x2, y2 = abs_coords
        w, h = self.current_image.size
        crop_w = x2 - x1
        crop_h = y2 - y1
        normalized = [
            round(x1 / w, 6),
            round(y1 / h, 6),
            round(x2 / w, 6),
            round(y2 / h, 6),
        ]
        xywh = [x1, y1, crop_w, crop_h]
        return CropData(abs_coords=abs_coords, normalized=normalized, xywh=xywh)

    def save_side_crop(self, side):
        if self.current_image is None:
            messagebox.showwarning("No image", "Load a PDF or image before saving crop areas.")
            return
        if not self.current_crop_data:
            messagebox.showwarning("No crop", "Draw a crop region first.")
            return

        if side == "front":
            self.front_crop = self.current_crop_data
            self.front_status.configure(
                text=f"FRONT: {self.front_crop.xywh[2]}x{self.front_crop.xywh[3]} px",
                foreground=self.colors["success"],
            )
        else:
            self.rear_crop = self.current_crop_data
            self.rear_status.configure(
                text=f"REAR: {self.rear_crop.xywh[2]}x{self.rear_crop.xywh[3]} px",
                foreground=self.colors["success"],
            )

    def ask_template_name(self):
        name = simpledialog.askstring("Template Name", "Enter template name (optional):")
        if name is None:
            return None
        clean = name.strip()
        if not clean:
            clean = f"Template_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        return clean

    def export_template(self):
        if self.current_image is None:
            messagebox.showwarning("No source", "Load a file before exporting a template.")
            return
        if not self.front_crop or not self.rear_crop:
            messagebox.showwarning("Missing data", "Save both FRONT and REAR crop selections first.")
            return

        name = self.ask_template_name()
        if name is None:
            return
        self.template_name_var.set(name)

        payload = {
            "format": "CCTPL",
            "version": 2,
            "template_name": name,
            "dpi": self.loaded_dpi,
            "image_size": [self.current_image_size[0], self.current_image_size[1]],
            "front": self.crop_to_dict(self.front_crop),
            "rear": self.crop_to_dict(self.rear_crop),
            "source_file": os.path.basename(self.current_image_path) if self.current_image_path else "",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

        default_filename = f"{name}.cctpl.json"
        out_path = filedialog.asksaveasfilename(
            title="Export CCTPL template",
            defaultextension=".cctpl.json",
            initialfile=default_filename,
            filetypes=[("CCTPL JSON", "*.cctpl.json"), ("JSON", "*.json")],
        )
        if not out_path:
            return

        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

            self.append_history(payload)
            self.info_label.configure(text=f"Template exported: {out_path}")
            messagebox.showinfo("Exported", "Template exported and added to history.")
        except Exception as exc:
            messagebox.showerror("Export failed", f"Failed to export template:\n{exc}")

    @staticmethod
    def crop_to_dict(crop: CropData):
        return {
            "abs": crop.abs_coords,
            "normalized": crop.normalized,
            "xywh": crop.xywh,
        }

    def update_preview(self, crop):
        if self.current_image is None or not crop:
            self.preview_label.configure(image="", text="No crop selected")
            self.preview_photo = None
            return

        x1, y1, x2, y2 = crop.abs_coords
        piece = self.current_image.crop((x1, y1, x2, y2))
        piece.thumbnail(MAX_PREVIEW_SIZE, Image.Resampling.LANCZOS)
        self.preview_photo = ImageTk.PhotoImage(piece)
        self.preview_label.configure(image=self.preview_photo, text="")

    def append_history(self, template_payload):
        entry = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "template_name": template_payload.get("template_name", "Untitled"),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "template": template_payload,
        }
        self.templates.append(entry)
        self.persist_history()
        self.refresh_history_tree()

    def load_history(self):
        if not os.path.exists(HISTORY_FILE):
            self.templates = []
            self.refresh_history_tree()
            return
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.templates = raw if isinstance(raw, list) else []
        except Exception:
            self.templates = []
        self.refresh_history_tree()

    def persist_history(self):
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.templates, f, indent=2)

    def refresh_history_tree(self):
        for row in self.history_tree.get_children():
            self.history_tree.delete(row)
        for entry in reversed(self.templates):
            ts = entry.get("timestamp", "")
            shown_ts = ts.replace("T", " ") if ts else "-"
            self.history_tree.insert("", "end", iid=entry["id"], values=(entry.get("template_name", "Untitled"), shown_ts))

    def open_selected_record(self, _event=None):
        selected = self.history_tree.selection()
        if not selected:
            return
        rec_id = selected[0]
        record = next((t for t in self.templates if t.get("id") == rec_id), None)
        if not record:
            return
        self.open_record_window(record)

    def open_record_window(self, record):
        win = tk.Toplevel(self.root)
        win.title(f"Template Record - {record.get('template_name', 'Untitled')}")
        win.geometry("760x620")
        win.configure(bg=self.colors["bg"])

        head = ttk.Frame(win, style="Panel.TFrame")
        head.pack(fill="x", padx=10, pady=10)
        ttk.Label(head, text=record.get("template_name", "Untitled"), style="Header.TLabel").pack(side="left", padx=8, pady=8)

        body = tk.Text(
            win,
            bg="#10141B",
            fg="#E6EBF2",
            insertbackground="#E6EBF2",
            bd=0,
            relief="flat",
            wrap="none",
            font=("Consolas", 10),
        )
        body.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        body.insert("1.0", json.dumps(record.get("template", {}), indent=2))

        btns = ttk.Frame(win, style="Panel.TFrame")
        btns.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btns, text="Edit Name", command=lambda: self.edit_record_name(record, win)).pack(side="left", padx=(0, 6), pady=8)
        ttk.Button(btns, text="Delete Template", command=lambda: self.delete_record(record, win)).pack(side="left", padx=(0, 6), pady=8)
        ttk.Button(btns, text="Export Template", command=lambda: self.export_record(record)).pack(side="left", pady=8)

    def edit_record_name(self, record, win):
        new_name = simpledialog.askstring("Edit Name", "Enter new template name:", initialvalue=record.get("template_name", ""), parent=win)
        if new_name is None:
            return
        clean = new_name.strip()
        if not clean:
            messagebox.showwarning("Invalid", "Template name cannot be empty.", parent=win)
            return
        record["template_name"] = clean
        if "template" in record and isinstance(record["template"], dict):
            record["template"]["template_name"] = clean
        self.persist_history()
        self.refresh_history_tree()
        win.title(f"Template Record - {clean}")

    def delete_record(self, record, win):
        if not messagebox.askyesno("Delete", "Delete this template from history?", parent=win):
            return
        self.templates = [x for x in self.templates if x.get("id") != record.get("id")]
        self.persist_history()
        self.refresh_history_tree()
        win.destroy()

    def export_record(self, record):
        template = record.get("template", {})
        name = template.get("template_name", record.get("template_name", "template"))
        out_path = filedialog.asksaveasfilename(
            title="Export Template",
            defaultextension=".cctpl.json",
            initialfile=f"{name}.cctpl.json",
            filetypes=[("CCTPL JSON", "*.cctpl.json"), ("JSON", "*.json")],
        )
        if not out_path:
            return
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(template, f, indent=2)
            messagebox.showinfo("Exported", "Template exported successfully.")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to export:\n{exc}")


if __name__ == "__main__":
    root = tk.Tk()
    app = TemplateDesignerApp(root)
    root.mainloop()
