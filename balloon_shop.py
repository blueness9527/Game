# -*- coding: utf-8 -*-

import math
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox


DEFAULT_CANNON_ID = "normal"


@dataclass(frozen=True)
class CannonItem:
    cannon_id: str
    name: str
    price: int
    description: str
    reusable: bool
    style: dict[str, object]


@dataclass(frozen=True)
class DecorationItem:
    item_id: str
    name: str
    price: int
    description: str
    reusable: bool
    asset_file: str


CANNON_ITEMS: dict[str, CannonItem] = {
    "normal": CannonItem(
        cannon_id="normal",
        name="普通大炮",
        price=0,
        description="默认装备，稳定可靠。",
        reusable=False,
        style={
            "shadow": "#000000",
            "carriage": "#475569",
            "carriage_top": "#64748b",
            "body": "#475569",
            "body_light": "#94a3b8",
            "barrel": "#334155",
            "barrel_shadow": "#0f172a",
            "rear": "#94a3b8",
            "muzzle": "#111827",
            "pivot": "#334155",
            "pivot_light": "#e2e8f0",
            "wheel": "#475569",
            "wheel_outline": "#1e293b",
            "wheel_hub": "#cbd5e1",
            "spoke": "#e2e8f0",
            "trim": "#94a3b8",
            "effects": (),
        },
    ),
    "rainbow": CannonItem(
        cannon_id="rainbow",
        name="彩虹大炮",
        price=70,
        description="绚丽的彩虹炮身，购买后可永久装备。",
        reusable=False,
        style={
            "shadow": "#312e81",
            "carriage": "#7c3aed",
            "carriage_top": "#c084fc",
            "body": "#ec4899",
            "body_light": "#f9a8d4",
            "barrel": "#38bdf8",
            "barrel_shadow": "#0c4a6e",
            "rear": "#fde047",
            "muzzle": "#f97316",
            "pivot": "#22c55e",
            "pivot_light": "#fef08a",
            "wheel": "#7c3aed",
            "wheel_outline": "#312e81",
            "wheel_hub": "#fef08a",
            "spoke": "#ffffff",
            "trim": "#fef08a",
            "effects": ("rainbow_bands", "sparkles"),
        },
    ),
    "diamond": CannonItem(
        cannon_id="diamond",
        name="钻石大炮",
        price=100,
        description="高亮钻石质感，炮身和轮毂都有切面光泽。",
        reusable=False,
        style={
            "shadow": "#0f172a",
            "carriage": "#0369a1",
            "carriage_top": "#7dd3fc",
            "body": "#67e8f9",
            "body_light": "#ecfeff",
            "barrel": "#a5f3fc",
            "barrel_shadow": "#155e75",
            "rear": "#e0f2fe",
            "muzzle": "#0e7490",
            "pivot": "#22d3ee",
            "pivot_light": "#ffffff",
            "wheel": "#0891b2",
            "wheel_outline": "#164e63",
            "wheel_hub": "#ecfeff",
            "spoke": "#ffffff",
            "trim": "#bae6fd",
            "effects": ("diamond_facets",),
        },
    ),
}

DECORATION_ITEMS: dict[str, DecorationItem] = {
    "flower": DecorationItem(
        item_id="flower",
        name="花朵",
        price=15,
        description="装饰在炮管上的小花。",
        reusable=False,
        asset_file="flower_4.png",
    ),
    "leaf": DecorationItem(
        item_id="leaf",
        name="叶子",
        price=10,
        description="装饰在炮管上的绿色叶子。",
        reusable=False,
        asset_file="plant_tilemap.png",
    ),
}

ART_SOURCE = {
    "cannon": {
        "name": "Free Pirates Game Assets by Unlucky Studio",
        "url": "https://opengameart.org/content/free-pirates-game-assets-by-unlucky-studio",
        "license": "CC0",
    },
    "flower": {
        "name": "flowers",
        "url": "https://opengameart.org/content/flowers-0",
        "license": "CC0",
    },
    "leaf": {
        "name": "Plant Tileset",
        "url": "https://opengameart.org/content/plant-tileset",
        "license": "CC0",
    },
}


def create_default_inventory() -> dict:
    return {
        "cannons_owned": [DEFAULT_CANNON_ID],
        "equipped_cannon": DEFAULT_CANNON_ID,
        "decorations_owned": [],
        "equipped_decorations": [],
        "consumables": {},
    }


def normalize_inventory(inventory: dict | None) -> dict:
    result = create_default_inventory()
    if isinstance(inventory, dict):
        owned = inventory.get("cannons_owned", inventory.get("owned_cannons", []))
        if isinstance(owned, list):
            result["cannons_owned"] = [item for item in owned if item in CANNON_ITEMS]

        equipped = inventory.get("equipped_cannon", inventory.get("cannon", DEFAULT_CANNON_ID))
        if equipped in CANNON_ITEMS:
            result["equipped_cannon"] = equipped

        decorations_owned = inventory.get("decorations_owned", inventory.get("owned_decorations", []))
        if isinstance(decorations_owned, list):
            result["decorations_owned"] = [item for item in decorations_owned if item in DECORATION_ITEMS]

        equipped_decorations = inventory.get("equipped_decorations", inventory.get("decorations", []))
        if isinstance(equipped_decorations, list):
            result["equipped_decorations"] = [item for item in equipped_decorations if item in DECORATION_ITEMS]

        consumables = inventory.get("consumables", {})
        if isinstance(consumables, dict):
            normalized_consumables = {}
            for key, value in consumables.items():
                item_id = str(key)
                if item_id not in CANNON_ITEMS and item_id not in DECORATION_ITEMS:
                    continue
                try:
                    count = int(value)
                except (TypeError, ValueError):
                    continue
                if count > 0:
                    normalized_consumables[item_id] = count
            result["consumables"] = normalized_consumables

    if DEFAULT_CANNON_ID not in result["cannons_owned"]:
        result["cannons_owned"].insert(0, DEFAULT_CANNON_ID)
    result["cannons_owned"] = list(dict.fromkeys(result["cannons_owned"]))
    if result["equipped_cannon"] not in result["cannons_owned"]:
        result["equipped_cannon"] = DEFAULT_CANNON_ID
    result["decorations_owned"] = list(dict.fromkeys(result["decorations_owned"]))
    result["equipped_decorations"] = [
        item for item in dict.fromkeys(result["equipped_decorations"]) if item in result["decorations_owned"]
    ]
    return result


def get_shop_item(item_id: str):
    return CANNON_ITEMS.get(item_id) or DECORATION_ITEMS.get(item_id)


def get_cannon_style(cannon_id: str) -> dict[str, object]:
    item = CANNON_ITEMS.get(cannon_id, CANNON_ITEMS[DEFAULT_CANNON_ID])
    return dict(item.style)


def draw_cannon_preview(canvas: tk.Canvas, x: float, y: float, cannon_id: str, scale: float = 1.0) -> None:
    style = get_cannon_style(cannon_id)
    effects = set(style.get("effects", ()))
    wheel_r = 12 * scale
    body_w = 62 * scale
    barrel_len = 64 * scale
    barrel_h = 13 * scale

    canvas.create_oval(x - 54 * scale, y + 20 * scale, x + 54 * scale, y + 43 * scale, fill=style["shadow"], outline="", stipple="gray25")
    _draw_preview_wheel(canvas, x - 32 * scale, y + 23 * scale, wheel_r, style)
    _draw_preview_wheel(canvas, x + 32 * scale, y + 23 * scale, wheel_r, style)
    canvas.create_polygon(x - body_w / 2, y + 18 * scale, x + body_w / 2, y + 18 * scale, x + 22 * scale, y - 6 * scale, x - 22 * scale, y - 6 * scale, fill=style["carriage"], outline="")
    canvas.create_oval(x - 34 * scale, y - 33 * scale, x + 34 * scale, y + 8 * scale, fill=style["body"], outline="")
    canvas.create_oval(x - 23 * scale, y - 27 * scale, x + 23 * scale, y - 4 * scale, fill=style["body_light"], outline="")

    left = x - barrel_h
    top = y - 34 * scale - barrel_h / 2
    right = x + barrel_len
    bottom = y - 34 * scale + barrel_h / 2
    canvas.create_rectangle(left + 5 * scale, top + 7 * scale, right + 5 * scale, bottom + 7 * scale, fill=style["barrel_shadow"], outline="")
    canvas.create_rectangle(left, top, right, bottom, fill=style["barrel"], outline="")
    canvas.create_rectangle(right - 5 * scale, top - 3 * scale, right + 12 * scale, bottom + 3 * scale, fill=style["muzzle"], outline="")
    canvas.create_oval(x - 11 * scale, y - 45 * scale, x + 11 * scale, y - 23 * scale, fill=style["pivot"], outline="")
    canvas.create_oval(x - 5 * scale, y - 39 * scale, x + 5 * scale, y - 29 * scale, fill=style["pivot_light"], outline="")

    if "rainbow_bands" in effects:
        colors = ["#ef4444", "#f97316", "#facc15", "#22c55e", "#38bdf8", "#8b5cf6"]
        band_w = barrel_len / len(colors)
        for index, color in enumerate(colors):
            bx = x + index * band_w
            canvas.create_rectangle(bx, top, bx + band_w + 1, bottom, fill=color, outline="")
    if "diamond_facets" in effects:
        for offset in (-24, 0, 24):
            cx = x + offset * scale
            canvas.create_polygon(cx, y - 53 * scale, cx + 12 * scale, y - 41 * scale, cx, y - 29 * scale, cx - 12 * scale, y - 41 * scale, fill="#ffffff", outline="#67e8f9")


def draw_decoration_preview(canvas: tk.Canvas, x: float, y: float, item_id: str, scale: float = 1.0) -> None:
    if item_id == "flower":
        radius = 8 * scale
        for angle in [0, math.pi * 0.4, math.pi * 0.8, math.pi * 1.2, math.pi * 1.6]:
            px = x + math.cos(angle) * radius
            py = y + math.sin(angle) * radius
            canvas.create_oval(px - radius, py - radius, px + radius, py + radius, fill="#f472b6", outline="#be185d")
        canvas.create_oval(x - 6 * scale, y - 6 * scale, x + 6 * scale, y + 6 * scale, fill="#facc15", outline="#a16207")
        canvas.create_line(x, y + 10 * scale, x, y + 34 * scale, fill="#16a34a", width=max(1, int(3 * scale)))
        return
    if item_id == "leaf":
        canvas.create_polygon(
            x,
            y - 24 * scale,
            x + 18 * scale,
            y - 8 * scale,
            x + 10 * scale,
            y + 18 * scale,
            x - 16 * scale,
            y + 22 * scale,
            x - 22 * scale,
            y - 2 * scale,
            fill="#22c55e",
            outline="#166534",
        )
        canvas.create_line(x - 18 * scale, y + 14 * scale, x + 12 * scale, y - 12 * scale, fill="#dcfce7", width=max(1, int(2 * scale)))


def _draw_preview_wheel(canvas: tk.Canvas, center_x: float, center_y: float, radius: float, style: dict[str, object]) -> None:
    canvas.create_oval(center_x - radius, center_y - radius, center_x + radius, center_y + radius, fill=style["wheel"], outline=style["wheel_outline"], width=2)
    for index in range(6):
        angle = index * math.pi / 3
        dx = math.cos(angle) * radius * 0.75
        dy = math.sin(angle) * radius * 0.75
        canvas.create_line(center_x, center_y, center_x + dx, center_y + dy, fill=style["spoke"], width=1)
    canvas.create_oval(center_x - radius * 0.35, center_y - radius * 0.35, center_x + radius * 0.35, center_y + radius * 0.35, fill=style["wheel_hub"], outline="")


class ShopWindow:
    def __init__(self, parent: tk.Tk, get_state, buy_item, on_close=None) -> None:
        self.get_state = get_state
        self.buy_item = buy_item
        self.on_close = on_close
        self.window = tk.Toplevel(parent)
        self.window.title("商店")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.configure(bg="#f8fafc")
        self.coin_var = tk.StringVar()
        self.status_var = tk.StringVar(value="商店商品对所有玩家一致，已拥有的永久道具不能重复购买。")
        self.rows: dict[str, dict[str, tk.Widget]] = {}

        self._build_header("商店")
        body = tk.Frame(self.window, bg="#f8fafc", padx=14, pady=14)
        body.pack(fill="both")
        for cannon_id, item in CANNON_ITEMS.items():
            if item.price > 0:
                self._build_shop_row(body, cannon_id, "cannon")
        for item_id in DECORATION_ITEMS:
            self._build_shop_row(body, item_id, "decoration")
        self._build_footer()
        self.refresh()
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.grab_set()
        self.window.focus_force()

    def _build_header(self, title: str) -> None:
        header = tk.Frame(self.window, bg="#0f172a", padx=16, pady=12)
        header.pack(fill="x")
        tk.Label(header, text=title, fg="white", bg="#0f172a", font=("Microsoft YaHei UI", 14, "bold")).pack(side="left")
        tk.Label(header, textvariable=self.coin_var, fg="#fde68a", bg="#0f172a", font=("Microsoft YaHei UI", 11, "bold")).pack(side="right")

    def _build_footer(self) -> None:
        footer = tk.Frame(self.window, bg="#f8fafc", padx=14)
        footer.pack(fill="x", pady=(0, 14))
        tk.Label(footer, textvariable=self.status_var, fg="#2563eb", bg="#f8fafc", font=("Microsoft YaHei UI", 10), anchor="w").pack(side="left", fill="x", expand=True)
        tk.Button(footer, text="关闭", command=self.close, width=10, bg="#475569", fg="white", relief="flat", font=("Microsoft YaHei UI", 10, "bold")).pack(side="right")

    def _build_shop_row(self, parent: tk.Frame, item_id: str, item_type: str) -> None:
        item = get_shop_item(item_id)
        row, state_label, action_button = _build_item_row(parent, item_id, item_type)
        tk.Label(row, text=f"售价 {item.price} 金币", fg="#b45309", bg="white", font=("Microsoft YaHei UI", 10, "bold")).pack(side="left", padx=(8, 8))
        self.rows[item_id] = {"state": state_label, "button": action_button, "type": item_type}

    def refresh(self) -> None:
        coins, inventory = self.get_state()
        inventory = normalize_inventory(inventory)
        owned = set(inventory["cannons_owned"]) | set(inventory["decorations_owned"])
        self.coin_var.set(f"金币：{coins}")
        for item_id, row in self.rows.items():
            item = get_shop_item(item_id)
            button = row["button"]
            state = row["state"]
            if item_id in owned and not item.reusable:
                state.config(text="已拥有", fg="#166534")
                button.config(text="不可重复", state="disabled", bg="#94a3b8", command=lambda: None)
            elif coins < item.price:
                state.config(text="金币不足", fg="#b45309")
                button.config(text="购买", state="disabled", bg="#94a3b8", command=lambda: None)
            else:
                state.config(text="可购买", fg="#2563eb")
                button.config(text="购买", state="normal", bg="#dc2626", command=lambda value=item_id: self._buy(value))

    def _buy(self, item_id: str) -> None:
        ok, message = self.buy_item(item_id)
        self.status_var.set(message)
        if not ok:
            messagebox.showinfo("商店", message, parent=self.window)
        self.refresh()

    def close(self) -> None:
        if self.on_close:
            self.on_close()
        self.window.destroy()


def _build_item_row(parent: tk.Frame, item_id: str, item_type: str = "cannon") -> tuple[tk.Frame, tk.Label, tk.Button]:
    item = get_shop_item(item_id)
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
