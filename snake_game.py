# -*- coding: utf-8 -*-

import random
import threading
import tkinter as tk

try:
    import winsound
except ImportError:  # pragma: no cover
    winsound = None


CELL_SIZE = 20
GRID_WIDTH = 30
GRID_HEIGHT = 20
FOOD_COUNT = 4
BOMB_COUNT = 1
BOMB_REFRESH_MS = 5000

DIFFICULTY_SETTINGS = {
    "简单": {"delay": 160},
    "普通": {"delay": 120},
    "困难": {"delay": 90},
}

FOOD_TYPES = [
    {"name": "苹果", "color": "#ff5a5f", "points": 10},
    {"name": "芒果", "color": "#ffd166", "points": 20},
    {"name": "葡萄", "color": "#7ddc6d", "points": 30},
    {"name": "桃子", "color": "#ff9ec4", "points": 40},
]

SCENE_SETTINGS = {
    "土地": {
        "bg": "#e6c86a",
        "panel": "#f5e3a7",
        "grid": "#c6aa57",
        "text_main": "#5c4312",
        "text_muted": "#8a6a24",
        "snake_head": "#f97316",
        "snake_body": "#22c55e",
        "snake_body_alt": "#16a34a",
        "bomb": "#ef4444",
        "border": "#b8943d",
    },
    "草地": {
        "bg": "#bde59b",
        "panel": "#f4f9ea",
        "grid": "#8bb96f",
        "text_main": "#274c2b",
        "text_muted": "#567a55",
        "snake_head": "#ff7f50",
        "snake_body": "#2f9e44",
        "snake_body_alt": "#248232",
        "bomb": "#d94841",
        "border": "#7aa660",
    },
}

ACCENT = "#f97316"


class SoundManager:
    def __init__(self) -> None:
        self.enabled = winsound is not None
        self._sounds = {
            "start": [(700, 80), (860, 90), (1040, 120)],
            "eat": [(880, 60), (1180, 80)],
            "pause": [(520, 80)],
            "resume": [(720, 80)],
            "restart": [(620, 70), (780, 70)],
            "dead": [(180, 260), (140, 260), (110, 320)],
            "bomb": [(1200, 70), (700, 90), (260, 320)],
            "win": [(700, 90), (900, 90), (1200, 110), (1500, 150)],
        }

    def play(self, name: str) -> None:
        if not self.enabled:
            return
        pattern = self._sounds.get(name)
        if not pattern:
            return
        threading.Thread(target=self._play_pattern, args=(pattern,), daemon=True).start()

    def _play_pattern(self, pattern: list[tuple[int, int]]) -> None:
        for freq, duration in pattern:
            try:
                winsound.Beep(freq, duration)
            except RuntimeError:
                return


class SnakeGame:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("贪吃蛇")
        self.root.resizable(False, False)

        self.canvas_width = CELL_SIZE * GRID_WIDTH
        self.canvas_height = CELL_SIZE * GRID_HEIGHT

        self.score_var = tk.StringVar(value="分数 0")
        self.best_var = tk.StringVar(value="最高分 0")
        self.status_var = tk.StringVar(value="选择难度和场景后开始游戏")
        self.difficulty_var = tk.StringVar(value="普通")
        self.scene_var = tk.StringVar(value="土地")

        self.best_score = 0
        self.running = False
        self.paused = False
        self.game_over = False
        self.after_id = None
        self.bomb_after_id = None
        self.sound = SoundManager()

        self._apply_scene()
        self._build_ui()
        self._bind_keys()
        self._show_menu()

    def _apply_scene(self) -> None:
        scene = SCENE_SETTINGS[self.scene_var.get()]
        self.bg_color = scene["bg"]
        self.panel_color = scene["panel"]
        self.grid_color = scene["grid"]
        self.text_main = scene["text_main"]
        self.text_muted = scene["text_muted"]
        self.snake_head = scene["snake_head"]
        self.snake_body = scene["snake_body"]
        self.snake_body_alt = scene["snake_body_alt"]
        self.bomb_color = scene["bomb"]
        self.border_color = scene["border"]
        self.root.configure(bg=self.bg_color)

    def _build_ui(self) -> None:
        self.outer = tk.Frame(self.root, bg=self.bg_color, padx=16, pady=16)
        self.outer.pack()

        self.title_label = tk.Label(
            self.outer,
            text="NEON SNAKE",
            fg="#f8fafc",
            bg=self.bg_color,
            font=("Consolas", 24, "bold"),
        )
        self.title_label.pack(anchor="w")

        self.subtitle_label = tk.Label(
            self.outer,
            text="方向键移动，空格暂停，R 重新开始",
            fg=self.text_muted,
            bg=self.bg_color,
            font=("Microsoft YaHei UI", 10),
        )
        self.subtitle_label.pack(anchor="w", pady=(0, 10))

        top_bar = tk.Frame(self.outer, bg=self.bg_color)
        top_bar.pack(fill="x", pady=(0, 10))

        self.stats_card = tk.Frame(top_bar, bg=self.panel_color, padx=12, pady=10)
        self.stats_card.pack(side="left", fill="x", expand=True)

        self.score_label = tk.Label(self.stats_card, textvariable=self.score_var, fg=self.text_main, bg=self.panel_color, font=("Microsoft YaHei UI", 12, "bold"))
        self.score_label.pack(side="left", padx=(0, 14))
        self.best_label = tk.Label(self.stats_card, textvariable=self.best_var, fg=self.text_muted, bg=self.panel_color, font=("Microsoft YaHei UI", 11))
        self.best_label.pack(side="left", padx=(0, 14))
        self.status_label = tk.Label(self.stats_card, textvariable=self.status_var, fg="#38bdf8", bg=self.panel_color, font=("Microsoft YaHei UI", 11))
        self.status_label.pack(side="left")

        self.control_card = tk.Frame(top_bar, bg=self.panel_color, padx=12, pady=10)
        self.control_card.pack(side="left", padx=(10, 0))

        self.diff_label = tk.Label(self.control_card, text="难度", fg=self.text_muted, bg=self.panel_color, font=("Microsoft YaHei UI", 10))
        self.diff_label.pack(side="left", padx=(0, 6))
        self.diff_option = tk.OptionMenu(self.control_card, self.difficulty_var, *DIFFICULTY_SETTINGS.keys())
        self._style_option_menu(self.diff_option)
        self.diff_option.pack(side="left", padx=(0, 10))

        self.scene_label = tk.Label(self.control_card, text="场景", fg=self.text_muted, bg=self.panel_color, font=("Microsoft YaHei UI", 10))
        self.scene_label.pack(side="left", padx=(0, 6))
        self.scene_option = tk.OptionMenu(self.control_card, self.scene_var, *SCENE_SETTINGS.keys(), command=lambda _value: self.change_scene())
        self._style_option_menu(self.scene_option)
        self.scene_option.pack(side="left")

        self.board = tk.Frame(self.outer, bg=self.panel_color, padx=10, pady=10)
        self.board.pack()

        self.canvas = tk.Canvas(
            self.board,
            width=self.canvas_width,
            height=self.canvas_height,
            bg=self.bg_color,
            highlightthickness=1,
            highlightbackground=self.border_color,
        )
        self.canvas.pack()

        action_bar = tk.Frame(self.outer, bg=self.bg_color, pady=10)
        action_bar.pack(fill="x")

        self.start_button = self._create_button(action_bar, "开始", self.start_from_menu)
        self.start_button.pack(side="left")
        self.pause_button = self._create_button(action_bar, "暂停", self.toggle_pause)
        self.pause_button.pack(side="left", padx=8)
        self.restart_button = self._create_button(action_bar, "重开", self.restart_game)
        self.restart_button.pack(side="left")

        self.legend = tk.Frame(self.outer, bg=self.bg_color)
        self.legend.pack(fill="x", pady=(6, 0))

        self.legend_pills: list[tk.Frame] = []
        for item in FOOD_TYPES:
            self.legend_pills.append(self._create_legend_pill(self.legend, item["color"], f'{item["name"]} +{item["points"]}'))
        self.legend_pills.append(self._create_legend_pill(self.legend, self.bomb_color, "炸弹 碰到即死"))

    def _style_option_menu(self, option: tk.OptionMenu) -> None:
        option.config(
            width=6,
            bg="#1f2937",
            fg="white",
            activebackground="#334155",
            activeforeground="white",
            relief="flat",
            highlightthickness=0,
            font=("Microsoft YaHei UI", 10),
        )
        option["menu"].config(
            bg="#1f2937",
            fg="white",
            activebackground="#334155",
            activeforeground="white",
            font=("Microsoft YaHei UI", 10),
        )

    def _create_button(self, parent: tk.Widget, text: str, command) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            width=11,
            bg=ACCENT,
            fg="#fff7ed",
            activebackground="#ea580c",
            activeforeground="#fff7ed",
            relief="flat",
            bd=0,
            font=("Microsoft YaHei UI", 10, "bold"),
            cursor="hand2",
        )

    def _create_legend_pill(self, parent: tk.Widget, color: str, text: str) -> tk.Frame:
        pill = tk.Frame(parent, bg=self.panel_color, padx=8, pady=6)
        pill.pack(side="left", padx=(0, 8))
        marker = tk.Canvas(pill, width=12, height=12, bg=self.panel_color, highlightthickness=0)
        marker.pack(side="left")
        marker.create_oval(1, 1, 11, 11, fill=color, outline="")
        tk.Label(pill, text=text, fg=self.text_main, bg=self.panel_color, font=("Microsoft YaHei UI", 9)).pack(side="left", padx=(6, 0))
        return pill

    def _bind_keys(self) -> None:
        self.root.bind("<Up>", lambda _event: self.change_direction("Up"))
        self.root.bind("<Down>", lambda _event: self.change_direction("Down"))
        self.root.bind("<Left>", lambda _event: self.change_direction("Left"))
        self.root.bind("<Right>", lambda _event: self.change_direction("Right"))
        self.root.bind("<space>", lambda _event: self.toggle_pause())
        self.root.bind("r", lambda _event: self.restart_game())
        self.root.focus_force()

    def change_scene(self) -> None:
        self._apply_scene()
        self._refresh_theme()
        if self.running or self.game_over or hasattr(self, "snake"):
            self._draw()
        else:
            self._draw_menu_overlay()

    def _refresh_theme(self) -> None:
        title_text = "EARTH SNAKE" if self.scene_var.get() == "土地" else "MEADOW SNAKE"
        self.title_label.config(text=title_text, bg=self.bg_color)
        self.subtitle_label.config(bg=self.bg_color, fg=self.text_muted)
        self.outer.config(bg=self.bg_color)
        self.stats_card.config(bg=self.panel_color)
        self.control_card.config(bg=self.panel_color)
        self.board.config(bg=self.panel_color)
        self.legend.config(bg=self.bg_color)
        self.canvas.config(bg=self.bg_color, highlightbackground=self.border_color)
        self.score_label.config(bg=self.panel_color, fg=self.text_main)
        self.best_label.config(bg=self.panel_color, fg=self.text_muted)
        self.status_label.config(bg=self.panel_color)
        self.diff_label.config(bg=self.panel_color, fg=self.text_muted)
        self.scene_label.config(bg=self.panel_color, fg=self.text_muted)
        self.legend.destroy()
        self.legend = tk.Frame(self.outer, bg=self.bg_color)
        self.legend.pack(fill="x", pady=(6, 0))
        self.legend_pills = []
        for item in FOOD_TYPES:
            self.legend_pills.append(self._create_legend_pill(self.legend, item["color"], f'{item["name"]} +{item["points"]}'))
        self.legend_pills.append(self._create_legend_pill(self.legend, self.bomb_color, "炸弹 碰到即死"))

    def _show_menu(self) -> None:
        self.running = False
        self.paused = False
        self.game_over = False
        self._cancel_tick()
        self._cancel_bomb_refresh()
        self.score_var.set("分数 0")
        self.status_var.set("选择难度和场景后开始游戏")
        self._draw_menu_overlay()

    def start_from_menu(self) -> None:
        self._reset_game()
        self.start_game()

    def _reset_game(self) -> None:
        center_x = GRID_WIDTH // 2
        center_y = GRID_HEIGHT // 2
        self.snake = [(center_x, center_y), (center_x - 1, center_y), (center_x - 2, center_y)]
        self.direction = "Right"
        self.next_direction = "Right"
        self.score = 0
        self.running = False
        self.paused = False
        self.game_over = False
        setting = DIFFICULTY_SETTINGS[self.difficulty_var.get()]
        self.update_delay_ms = setting["delay"]
        self.foods = self._spawn_foods()
        self.bombs = self._spawn_bombs()
        self.score_var.set("分数 0")
        self.status_var.set(f"当前难度 {self.difficulty_var.get()} | 场景 {self.scene_var.get()}")
        self._draw()

    def _free_positions(self) -> list[tuple[int, int]]:
        occupied = set(getattr(self, "snake", []))
        occupied.update(food["position"] for food in getattr(self, "foods", []))
        occupied.update(getattr(self, "bombs", set()))
        return [(x, y) for x in range(GRID_WIDTH) for y in range(GRID_HEIGHT) if (x, y) not in occupied]

    def _spawn_foods(self) -> list[dict]:
        available = self._free_positions()
        count = min(FOOD_COUNT, len(available), len(FOOD_TYPES))
        foods: list[dict] = []
        for position, food_type in zip(random.sample(available, count), FOOD_TYPES[:count]):
            foods.append({"position": position, **food_type})
        return foods

    def _spawn_single_food(self) -> None:
        occupied_food_names = {food["name"] for food in self.foods}
        remaining_types = [item for item in FOOD_TYPES if item["name"] not in occupied_food_names]
        available = self._free_positions()
        if available and remaining_types:
            self.foods.append({"position": random.choice(available), **random.choice(remaining_types)})

    def _spawn_bombs(self) -> set[tuple[int, int]]:
        available = self._free_positions()
        return set(random.sample(available, min(BOMB_COUNT, len(available))))

    def _schedule_bomb_refresh(self) -> None:
        if self.bomb_after_id is None and self.running and not self.paused and not self.game_over:
            self.bomb_after_id = self.root.after(BOMB_REFRESH_MS, self._refresh_bombs)

    def _cancel_bomb_refresh(self) -> None:
        if self.bomb_after_id is not None:
            self.root.after_cancel(self.bomb_after_id)
            self.bomb_after_id = None

    def _refresh_bombs(self) -> None:
        self.bomb_after_id = None
        if not self.running or self.paused or self.game_over:
            return
        self.bombs = self._spawn_bombs()
        self.status_var.set("炸弹位置已刷新")
        self._draw()
        self._schedule_bomb_refresh()

    def start_game(self) -> None:
        if self.game_over:
            self.restart_game()
            return
        if not hasattr(self, "snake"):
            self._reset_game()
        if not self.running:
            self.running = True
            self.paused = False
            self.status_var.set(f"游戏进行中 {self.difficulty_var.get()} | {self.scene_var.get()}")
            self.sound.play("start")
            self._schedule_tick()
            self._schedule_bomb_refresh()

    def toggle_pause(self) -> None:
        if not hasattr(self, "snake") or self.game_over:
            return
        if not self.running:
            self.start_game()
            return
        self.paused = not self.paused
        self.status_var.set("已暂停" if self.paused else f"游戏进行中 {self.difficulty_var.get()} | {self.scene_var.get()}")
        self.sound.play("pause" if self.paused else "resume")
        if self.paused:
            self._cancel_bomb_refresh()
        else:
            self._schedule_tick()
            self._schedule_bomb_refresh()

    def restart_game(self) -> None:
        self._cancel_tick()
        self._cancel_bomb_refresh()
        self._reset_game()
        self.sound.play("restart")
        self.start_game()

    def change_direction(self, new_direction: str) -> None:
        if not hasattr(self, "snake"):
            return
        opposite = {"Up": "Down", "Down": "Up", "Left": "Right", "Right": "Left"}
        if new_direction == opposite[self.direction]:
            return
        self.next_direction = new_direction
        if not self.running and not self.game_over:
            self.start_game()

    def _cancel_tick(self) -> None:
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

    def _schedule_tick(self) -> None:
        if self.after_id is None and self.running and not self.paused:
            self.after_id = self.root.after(self.update_delay_ms, self._tick)

    def _tick(self) -> None:
        self.after_id = None
        if not self.running or self.paused or self.game_over:
            return

        self.direction = self.next_direction
        head_x, head_y = self.snake[0]
        move_map = {"Up": (0, -1), "Down": (0, 1), "Left": (-1, 0), "Right": (1, 0)}
        dx, dy = move_map[self.direction]
        new_head = (head_x + dx, head_y + dy)

        hit_wall = not (0 <= new_head[0] < GRID_WIDTH and 0 <= new_head[1] < GRID_HEIGHT)
        hit_self = new_head in self.snake[:-1]
        if hit_wall or hit_self:
            self._end_game("撞到了边界或自己")
            return

        if new_head in self.bombs:
            self.snake.insert(0, new_head)
            self._end_game("你碰到了炸弹", bomb_hit=True)
            return

        self.snake.insert(0, new_head)
        eaten_food = next((food for food in self.foods if food["position"] == new_head), None)
        if eaten_food is not None:
            self.score += eaten_food["points"]
            self.foods.remove(eaten_food)
            self._spawn_single_food()
            self.score_var.set(f"分数 {self.score}")
            self.status_var.set(f'{eaten_food["name"]} +{eaten_food["points"]}')
            self.sound.play("eat")
        else:
            self.snake.pop()

        free_cells = GRID_WIDTH * GRID_HEIGHT - len(self.bombs)
        if len(self.snake) >= free_cells:
            self._win_game()
            return

        self._draw()
        self._schedule_tick()

    def _end_game(self, reason: str, bomb_hit: bool = False) -> None:
        self.running = False
        self.game_over = True
        self._cancel_bomb_refresh()
        self.best_score = max(self.best_score, self.score)
        self.best_var.set(f"最高分 {self.best_score}")
        if bomb_hit:
            self.status_var.set("碰到炸弹，游戏结束")
            self.sound.play("bomb")
            subtitle = reason
        else:
            self.status_var.set("游戏结束，按 R 重开")
            self.sound.play("dead")
            subtitle = reason
        self._draw()
        self._draw_center_message("游戏结束", "#fb7185", subtitle)

    def _win_game(self) -> None:
        self.running = False
        self.game_over = True
        self._cancel_bomb_refresh()
        self.best_score = max(self.best_score, self.score)
        self.best_var.set(f"最高分 {self.best_score}")
        self.status_var.set("你赢了")
        self.sound.play("win")
        self._draw()
        self._draw_center_message("你赢了", "#4ade80", "所有安全格子都被占满了")

    def _draw(self) -> None:
        self.canvas.delete("all")
        self._draw_background()
        self._draw_grid()
        self._draw_foods()
        self._draw_bombs()
        self._draw_snake()

    def _draw_background(self) -> None:
        if self.scene_var.get() == "土地":
            self.canvas.create_rectangle(0, 0, self.canvas_width, self.canvas_height, fill=self.bg_color, outline="")
            for y in range(0, self.canvas_height, 28):
                band = "#ddbf5e" if (y // 28) % 2 == 0 else "#d3b352"
                self.canvas.create_rectangle(0, y, self.canvas_width, y + 14, fill=band, outline="")
            self._draw_earth_decorations()
        else:
            self.canvas.create_rectangle(0, 0, self.canvas_width, self.canvas_height, fill="#bde59b", outline="")
            for y in range(0, self.canvas_height, 24):
                self.canvas.create_rectangle(0, y, self.canvas_width, y + 12, fill="#b4dc91", outline="")
            self._draw_meadow_decorations()

    def _draw_earth_decorations(self) -> None:
        stones = [
            (70, 80, 11, 7),
            (150, 220, 14, 8),
            (260, 130, 10, 6),
            (360, 310, 13, 8),
            (470, 170, 15, 9),
            (560, 260, 12, 7),
            (120, 340, 9, 6),
            (520, 90, 11, 7),
        ]
        for x, y, rx, ry in stones:
            self.canvas.create_oval(x - rx, y - ry, x + rx, y + ry, fill="#8b7a58", outline="")
            self.canvas.create_oval(x - rx + 2, y - ry + 2, x + rx - 3, y + ry - 3, fill="#a3926b", outline="")

    def _draw_meadow_decorations(self) -> None:
        flowers = [(60, 70), (160, 120), (520, 80), (430, 250), (280, 330), (560, 310)]
        for x, y in flowers:
            self.canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill="#facc15", outline="")
            for dx, dy, color in [(-7, 0, "#ef4444"), (7, 0, "#ec4899"), (0, -7, "#a855f7"), (0, 7, "#f97316")]:
                self.canvas.create_oval(x + dx - 4, y + dy - 4, x + dx + 4, y + dy + 4, fill=color, outline="")
        grass = [(80, 360), (200, 300), (340, 340), (470, 260), (580, 360)]
        for x, y in grass:
            for offset in (-6, 0, 6):
                self.canvas.create_line(x + offset, y, x + offset - 4, y - 16, fill="#3f7d20", width=2)
                self.canvas.create_line(x + offset, y, x + offset + 4, y - 14, fill="#4a8b2f", width=2)

    def _draw_grid(self) -> None:
        for x in range(0, self.canvas_width, CELL_SIZE):
            self.canvas.create_line(x, 0, x, self.canvas_height, fill=self.grid_color)
        for y in range(0, self.canvas_height, CELL_SIZE):
            self.canvas.create_line(0, y, self.canvas_width, y, fill=self.grid_color)

    def _draw_foods(self) -> None:
        for food in self.foods:
            x, y = food["position"]
            x1 = x * CELL_SIZE + 3
            y1 = y * CELL_SIZE + 3
            x2 = x1 + CELL_SIZE - 6
            y2 = y1 + CELL_SIZE - 6
            self.canvas.create_oval(x1, y1, x2, y2, fill=food["color"], outline="")
            self.canvas.create_text(x1 + (CELL_SIZE - 6) / 2, y1 + (CELL_SIZE - 6) / 2, text=str(food["points"]), fill="#0f172a", font=("Consolas", 8, "bold"))

    def _draw_bombs(self) -> None:
        for x, y in self.bombs:
            x1 = x * CELL_SIZE + 3
            y1 = y * CELL_SIZE + 3
            x2 = x1 + CELL_SIZE - 6
            y2 = y1 + CELL_SIZE - 6
            self.canvas.create_oval(x1, y1, x2, y2, fill=self.bomb_color, outline="#fecaca", width=1)
            self.canvas.create_line(x1 + 3, y1 + 3, x2 - 3, y2 - 3, fill="#fff1f2", width=2)
            self.canvas.create_line(x2 - 3, y1 + 3, x1 + 3, y2 - 3, fill="#fff1f2", width=2)

    def _draw_snake(self) -> None:
        for index, (x, y) in enumerate(self.snake):
            x1 = x * CELL_SIZE + 2
            y1 = y * CELL_SIZE + 2
            x2 = x1 + CELL_SIZE - 4
            y2 = y1 + CELL_SIZE - 4
            if index == 0:
                self.canvas.create_oval(x1, y1, x2, y2, fill=self.snake_head, outline="#fdba74")
                eye_y = y1 + 6
                self.canvas.create_oval(x1 + 5, eye_y, x1 + 7, eye_y + 2, fill="#fff7ed", outline="")
                self.canvas.create_oval(x1 + 11, eye_y, x1 + 13, eye_y + 2, fill="#fff7ed", outline="")
            else:
                fill = self.snake_body if index % 2 else self.snake_body_alt
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline="#14532d")

    def _draw_menu_overlay(self) -> None:
        self.canvas.delete("all")
        self._draw_background()
        self.canvas.create_rectangle(70, 80, self.canvas_width - 70, self.canvas_height - 80, fill=self.panel_color, outline=self.border_color, width=2)
        self.canvas.create_text(self.canvas_width // 2, 140, text="贪吃蛇", fill="#f8fafc" if self.scene_var.get() == "土地" else "#274c2b", font=("Microsoft YaHei UI", 28, "bold"))
        scene_text = "土地棋盘" if self.scene_var.get() == "土地" else "草地花园"
        self.canvas.create_text(self.canvas_width // 2, 190, text=f"四种食物，不同分值，炸弹会定时随机刷新\n当前场景：{scene_text}", fill="#cbd5e1" if self.scene_var.get() == "土地" else "#44624a", font=("Microsoft YaHei UI", 13))
        diff = self.difficulty_var.get()
        setting = DIFFICULTY_SETTINGS[diff]
        self.canvas.create_text(self.canvas_width // 2, 255, text=f"当前难度 {diff}  |  速度 {setting['delay']} 毫秒  |  炸弹每 {BOMB_REFRESH_MS // 1000} 秒刷新", fill="#7dd3fc" if self.scene_var.get() == "土地" else "#356859", font=("Consolas", 12, "bold"))
        self.canvas.create_text(self.canvas_width // 2, 320, text="点击开始，或直接按方向键开始", fill=ACCENT, font=("Microsoft YaHei UI", 12))
        self.canvas.create_text(self.canvas_width // 2, 360, text="空格暂停 / R 重开 / 炸弹 = 直接死亡", fill="#94a3b8" if self.scene_var.get() == "土地" else "#567a55", font=("Consolas", 11))

    def _draw_center_message(self, title: str, color: str, subtitle: str) -> None:
        left = 80
        top = 160
        right = self.canvas_width - 80
        bottom = self.canvas_height - 160
        self.canvas.create_rectangle(left, top, right, bottom, fill="#020617" if self.scene_var.get() == "土地" else "#f4f9ea", outline=color, width=2)
        self.canvas.create_text(self.canvas_width // 2, top + 52, text=title, fill=color, font=("Microsoft YaHei UI", 24, "bold"), width=right - left - 40)
        self.canvas.create_text(self.canvas_width // 2, top + 108, text=subtitle, fill="#cbd5e1" if self.scene_var.get() == "土地" else "#456048", font=("Microsoft YaHei UI", 12), width=right - left - 40)
        self.canvas.create_text(self.canvas_width // 2, top + 150, text="按 R 重新开始", fill="#94a3b8" if self.scene_var.get() == "土地" else "#6e8b69", font=("Microsoft YaHei UI", 10), width=right - left - 40)


def main() -> None:
    root = tk.Tk()
    SnakeGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
