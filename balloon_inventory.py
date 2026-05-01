# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import messagebox

from balloon_shop import CANNON_ITEMS, DECORATION_ITEMS, draw_cannon_preview, draw_decoration_preview, normalize_inventory


class BackpackWindow:
    def __init__(self, parent: tk.Tk, get_state, equip_cannon, equip_decoration, on_close=None) -> None:
        self.get_state = get_state
        self.equip_cannon = equip_cannon
        self.equip_decoration = equip_decoration
        self.on_close = on_close
        self.window = tk.Toplevel(parent)
        self.window.title("背包")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.configure(bg="#f8fafc")
        self.coin_var = tk.StringVar()
        self.status_var = tk.StringVar(value="这里只显示当前玩家已经拥有的道具。")
        self.rows: dict[str, dict[str, tk.Widget]] = {}

        self._build_header()
        self.body = tk.Frame(self.window, bg="#f8fafc", padx=14, pady=14)
        self.body.pack(fill="both")
        self._build_footer()
        self.refresh()
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.grab_set()
        self.window.focus_force()

    def _build_header(self) -> None:
        header = tk.Frame(self.window, bg="#0f172a", padx=16, pady=12)
        header.pack(fill="x")
        tk.Label(header, text="背包", fg="white", bg="#0f172a", font=("Microsoft YaHei UI", 14, "bold")).pack(side="left")
        tk.Label(header, textvariable=self.coin_var, fg="#fde68a", bg="#0f172a", font=("Microsoft YaHei UI", 11, "bold")).pack(side="right")

    def _build_footer(self) -> None:
        footer = tk.Frame(self.window, bg="#f8fafc", padx=14)
        footer.pack(fill="x", pady=(0, 14))
        tk.Label(footer, textvariable=self.status_var, fg="#2563eb", bg="#f8fafc", font=("Microsoft YaHei UI", 10), anchor="w").pack(side="left", fill="x", expand=True)
        tk.Button(footer, text="关闭", command=self.close, width=10, bg="#475569", fg="white", relief="flat", font=("Microsoft YaHei UI", 10, "bold")).pack(side="right")

    def refresh(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()
        self.rows.clear()

        coins, inventory = self.get_state()
        inventory = normalize_inventory(inventory)
        owned_cannons = inventory["cannons_owned"]
        owned_decorations = inventory["decorations_owned"]
        equipped_cannon = inventory["equipped_cannon"]
        equipped_decorations = set(inventory["equipped_decorations"])
        self.coin_var.set(f"金币：{coins}")

        if not owned_cannons and not owned_decorations:
            tk.Label(self.body, text="当前背包为空", fg="#64748b", bg="#f8fafc", font=("Microsoft YaHei UI", 11)).pack(padx=30, pady=30)
            return

        self._build_section_label("大炮")
        for cannon_id in owned_cannons:
            row, state_label, action_button = _build_item_row(self.body, cannon_id, "cannon")
            if cannon_id == equipped_cannon:
                state_label.config(text="已装备", fg="#166534")
                action_button.config(text="已装备", state="disabled", bg="#94a3b8", command=lambda: None)
            else:
                state_label.config(text="已拥有", fg="#2563eb")
                action_button.config(text="装备", state="normal", bg="#2563eb", command=lambda value=cannon_id: self._equip(value))
            self.rows[cannon_id] = {"state": state_label, "button": action_button, "type": "cannon"}

        if owned_decorations:
            self._build_section_label("装饰")
        for item_id in owned_decorations:
            row, state_label, action_button = _build_item_row(self.body, item_id, "decoration")
            if item_id in equipped_decorations:
                state_label.config(text="已装备", fg="#166534")
                action_button.config(text="卸下", state="normal", bg="#475569", command=lambda value=item_id: self._toggle_decoration(value))
            else:
                state_label.config(text="已拥有", fg="#2563eb")
                action_button.config(text="装备", state="normal", bg="#2563eb", command=lambda value=item_id: self._toggle_decoration(value))
            self.rows[item_id] = {"state": state_label, "button": action_button, "type": "decoration"}

    def _build_section_label(self, text: str) -> None:
        tk.Label(self.body, text=text, fg="#0f172a", bg="#f8fafc", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w", pady=(0, 6))

    def _equip(self, cannon_id: str) -> None:
        ok, message = self.equip_cannon(cannon_id)
        self.status_var.set(message)
        if not ok:
            messagebox.showinfo("背包", message, parent=self.window)
        self.refresh()

    def _toggle_decoration(self, item_id: str) -> None:
        ok, message = self.equip_decoration(item_id)
        self.status_var.set(message)
        if not ok:
            messagebox.showinfo("背包", message, parent=self.window)
        self.refresh()

    def close(self) -> None:
        if self.on_close:
            self.on_close()
        self.window.destroy()


def _build_item_row(parent: tk.Frame, item_id: str, item_type: str) -> tuple[tk.Frame, tk.Label, tk.Button]:
    item = CANNON_ITEMS[item_id] if item_type == "cannon" else DECORATION_ITEMS[item_id]
    row = tk.Frame(parent, bg="white", padx=10, pady=10, highlightthickness=1, highlightbackground="#cbd5e1")
    row.pack(fill="x", pady=(0, 10))

    preview = tk.Canvas(row, width=160, height=92, bg="#e0f2fe", highlightthickness=0)
    preview.pack(side="left", padx=(0, 12))
    if item_type == "decoration":
        draw_decoration_preview(preview, 76, 42, item_id, 1.0)
    else:
        draw_cannon_preview(preview, 72, 50, item_id, 0.8)

    text_col = tk.Frame(row, bg="white", width=260)
    text_col.pack(side="left", fill="x", expand=True)
    tk.Label(text_col, text=item.name, fg="#0f172a", bg="white", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
    tk.Label(text_col, text=item.description, fg="#475569", bg="white", font=("Microsoft YaHei UI", 9), wraplength=250, justify="left").pack(anchor="w", pady=(4, 0))

    state_label = tk.Label(row, width=10, fg="#166534", bg="white", font=("Microsoft YaHei UI", 10, "bold"))
    state_label.pack(side="left", padx=(8, 8))
    action_button = tk.Button(row, width=10, bg="#2563eb", fg="white", relief="flat", font=("Microsoft YaHei UI", 10, "bold"), cursor="hand2")
    action_button.pack(side="left")
    return row, state_label, action_button
