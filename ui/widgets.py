from __future__ import annotations

import customtkinter as ctk


class MarqueeLabel(ctk.CTkLabel):
    def __init__(self, master, text: str, width: int = 180, **kwargs):
        super().__init__(master, text=text, width=width, anchor="center", **kwargs)
        self.original_text = text
        self.display_text = text
        self.max_chars = max(6, int(width / 8))
        self.offset = 0
        self.after_id = None
        if len(text) > self.max_chars:
            self.after_id = self.after(200, self._scroll)

    def _scroll(self):
        if len(self.original_text) <= self.max_chars:
            return
        loop_text = self.original_text + "   " + self.original_text
        self.offset = (self.offset + 1) % len(self.original_text)
        snippet = loop_text[self.offset : self.offset + self.max_chars]
        self.configure(text=snippet)
        self.after_id = self.after(220, self._scroll)


class CenteredTable(ctk.CTkScrollableFrame):
    def __init__(self, master, columns: list[str], **kwargs):
        super().__init__(master, **kwargs)
        self.columns = columns
        self.rows: list[ctk.CTkFrame] = []
        self._build_header()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 8))
        for i, col in enumerate(self.columns):
            lbl = ctk.CTkLabel(header, text=col, font=ctk.CTkFont(size=12, weight="bold"), anchor="center")
            lbl.grid(row=0, column=i, padx=6, pady=4, sticky="ew")
            header.grid_columnconfigure(i, weight=1)

    def set_rows(self, rows: list[dict]):
        for row in self.rows:
            row.destroy()
        self.rows.clear()

        for rowdata in rows:
            row = ctk.CTkFrame(self, corner_radius=8)
            row.pack(fill="x", pady=3)
            for i, col in enumerate(self.columns):
                val = str(rowdata.get(col, ""))
                cell = MarqueeLabel(row, text=val, width=165)
                cell.grid(row=0, column=i, padx=5, pady=6, sticky="ew")
                row.grid_columnconfigure(i, weight=1)
            self.rows.append(row)
