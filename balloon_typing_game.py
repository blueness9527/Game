import json
import math
import random
import string
import threading
import time
import tkinter as tk
from ctypes import windll
from pathlib import Path

try:
    import winsound
except ImportError:  # pragma: no cover
    winsound = None


WINDOW_WIDTH = 900
WINDOW_HEIGHT = 620
BALLOON_RADIUS = 28
TARGET_SCORE = 100
INITIAL_LIVES = 5
TICK_MS = 35
EXPLOSION_DURATION = 14
PROJECTILE_SPEED = 18
GROUND_HEIGHT = 92

ASSETS_DIR = Path(__file__).with_name("assets")
MUSIC_FILE = ASSETS_DIR / "be_chillin.mp3"
SHOT_SOUND_FILE = ASSETS_DIR / "cannon_shot.ogg"
SAVE_FILE = Path(__file__).with_name("balloon_typing_save.json")

MUSIC_SOURCE_URL = (
    "https://github.com/SoundSafari/CC0-1.0-Music/raw/refs/heads/main/freepd.com/Be%20Chillin.mp3"
)
SHOT_SOURCE_URL = (
    "https://raw.githubusercontent.com/lavenderdotpet/CC0-Public-Domain-Sounds/main/100-CC0-SFX/shot_01.ogg"
)

BG_TOP = "#d7f0ff"
PANEL_COLOR = "#ffffff"
TEXT_MAIN = "#1f2937"
TEXT_MUTED = "#64748b"
ACCENT = "#2563eb"

DIFFICULTY_SETTINGS = {
    "简单": {"spawn_ms": 1500, "max_balloons": 4, "speed_min": 0.9, "speed_max": 1.6},
    "普通": {"spawn_ms": 1100, "max_balloons": 6, "speed_min": 1.3, "speed_max": 2.2},
    "困难": {"spawn_ms": 800, "max_balloons": 9, "speed_min": 2.2, "speed_max": 3.4},
}

BALLOON_COLORS = [
    "#ff6b6b",
    "#ff9f43",
    "#feca57",
    "#1dd1a1",
    "#54a0ff",
    "#a78bfa",
    "#f472b6",
]


class SoundManager:
    def __init__(self) -> None:
        self.enabled = winsound is not None
        self.pattern_sounds = {
            "pop": [(1200, 40), (900, 30)],
            "wrong": [(280, 120)],
            "start": [(700, 70), (920, 90)],
            "win": [(780, 80), (980, 80), (1280, 120)],
            "lose": [(180, 220), (130, 240), (100, 260)],
        }
        self.bgm_alias = "balloon_bgm"
        self.music_loaded = False
        self.effect_index = 0

    def play_pattern(self, name: str) -> None:
        if not self.enabled or name not in self.pattern_sounds:
            return
        threading.Thread(
            target=self._play_pattern,
            args=(self.pattern_sounds[name],),
            daemon=True,
        ).start()

    def _play_pattern(self, pattern: list[tuple[int, int]]) -> None:
        for freq, duration in pattern:
            try:
                winsound.Beep(freq, duration)
            except RuntimeError:
                return

    def start_bgm(self, music_file: Path) -> None:
        if not music_file.exists():
            return
        self.stop_bgm()
        path = str(music_file.resolve()).replace("\\", "\\\\")
        if windll.winmm.mciSendStringW(
            f'open "{path}" type mpegvideo alias {self.bgm_alias}', None, 0, 0
        ) == 0:
            self.music_loaded = True
            windll.winmm.mciSendStringW(f"play {self.bgm_alias} repeat", None, 0, 0)

    def stop_bgm(self) -> None:
        if self.music_loaded:
            windll.winmm.mciSendStringW(f"stop {self.bgm_alias}", None, 0, 0)
            windll.winmm.mciSendStringW(f"close {self.bgm_alias}", None, 0, 0)
            self.music_loaded = False

    def play_effect_file(self, file_path: Path, fallback_name: str | None = None) -> None:
        if not file_path.exists():
            if fallback_name:
                self.play_pattern(fallback_name)
            return
        threading.Thread(
            target=self._play_effect_file_inner,
            args=(file_path, fallback_name),
            daemon=True,
        ).start()

    def _play_effect_file_inner(self, file_path: Path, fallback_name: str | None) -> None:
        alias = f"balloon_sfx_{self.effect_index}"
        self.effect_index += 1
        path = str(file_path.resolve()).replace("\\", "\\\\")
        result = windll.winmm.mciSendStringW(
            f'open "{path}" type mpegvideo alias {alias}',
            None,
            0,
            0,
        )
        if result != 0:
            if fallback_name:
                self.play_pattern(fallback_name)
            return
        windll.winmm.mciSendStringW(f"play {alias}", None, 0, 0)
        time.sleep(2)
        windll.winmm.mciSendStringW(f"stop {alias}", None, 0, 0)
        windll.winmm.mciSendStringW(f"close {alias}", None, 0, 0)


class BalloonTypingGame:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("打字打气球")
        self.root.resizable(False, False)
        self.root.configure(bg=BG_TOP)

        self.score_var = tk.StringVar(value="分数 0")
        self.status_var = tk.StringVar(value="选择难度和名字后开始，直接按字母键发射炮弹")
        self.lives_var = tk.StringVar(value=f"失误余量 {INITIAL_LIVES}")
        self.difficulty_var = tk.StringVar(value="普通")
        self.player_name_var = tk.StringVar(value="玩家1")
        self.rank_var = tk.StringVar(value="排行榜载入中")

        self.score = 0
        self.lives = INITIAL_LIVES
        self.running = False
        self.game_over = False
        self.result_saved = False
        self.tick_after_id = None
        self.spawn_after_id = None
        self.balloons: list[dict] = []
        self.explosions: list[dict] = []
        self.projectiles: list[dict] = []
        self.sound = SoundManager()
        self.cannon_x = WINDOW_WIDTH // 2
        self.cannon_y = WINDOW_HEIGHT - GROUND_HEIGHT + 8
        self.next_balloon_id = 1

        self.save_data = self._load_save_data()
        self.player_name_var.set(self.save_data.get("player_name", "玩家1"))
        self.difficulty_var.set(self.save_data.get("last_difficulty", "普通"))

        self._build_ui()
        self._bind_keys()
        self._refresh_leaderboard()
        self._draw_scene()
        self._draw_message("打字打气球", "点击开始后直接按字母键开炮")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, bg=BG_TOP, padx=16, pady=16)
        outer.pack()

        tk.Label(
            outer,
            text="BALLOON TYPE",
            fg="#0f172a",
            bg=BG_TOP,
            font=("Consolas", 24, "bold"),
        ).pack(anchor="w")

        tk.Label(
            outer,
            text="已修正为炮弹真实命中后才击碎气球，并加入本地存档与排行榜",
            fg=TEXT_MUTED,
            bg=BG_TOP,
            font=("Microsoft YaHei UI", 10),
        ).pack(anchor="w", pady=(0, 10))

        top_bar = tk.Frame(outer, bg=BG_TOP)
        top_bar.pack(fill="x", pady=(0, 10))

        stats = tk.Frame(top_bar, bg=PANEL_COLOR, padx=12, pady=10)
        stats.pack(side="left", fill="x", expand=True)

        tk.Label(
            stats,
            textvariable=self.score_var,
            fg=TEXT_MAIN,
            bg=PANEL_COLOR,
            font=("Microsoft YaHei UI", 12, "bold"),
        ).pack(side="left", padx=(0, 18))
        tk.Label(
            stats,
            textvariable=self.lives_var,
            fg=TEXT_MAIN,
            bg=PANEL_COLOR,
            font=("Microsoft YaHei UI", 11),
        ).pack(side="left", padx=(0, 18))
        tk.Label(
            stats,
            textvariable=self.status_var,
            fg=ACCENT,
            bg=PANEL_COLOR,
            font=("Microsoft YaHei UI", 11),
        ).pack(side="left")

        control = tk.Frame(top_bar, bg=BG_TOP)
        control.pack(side="left", padx=(10, 0))

        tk.Entry(
            control,
            width=10,
            textvariable=self.player_name_var,
            justify="center",
            font=("Microsoft YaHei UI", 10),
            relief="flat",
        ).pack(side="left", padx=(0, 8))

        option = tk.OptionMenu(control, self.difficulty_var, *DIFFICULTY_SETTINGS.keys())
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
        option.pack(side="left", padx=(0, 8))

        self._create_button(control, "开始", self.start_game).pack(side="left")
        self._create_button(control, "重开", self.restart_game).pack(side="left", padx=8)

        middle = tk.Frame(outer, bg=BG_TOP)
        middle.pack()

        board = tk.Frame(middle, bg=PANEL_COLOR, padx=10, pady=10)
        board.pack(side="left")

        self.canvas = tk.Canvas(
            board,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            bg="#d7f0ff",
            highlightthickness=1,
            highlightbackground="#93c5fd",
        )
        self.canvas.pack()

        side = tk.Frame(middle, bg=PANEL_COLOR, padx=12, pady=12, width=220)
        side.pack(side="left", padx=(12, 0), fill="y")
        side.pack_propagate(False)

        tk.Label(
            side,
            text="排行榜",
            fg=TEXT_MAIN,
            bg=PANEL_COLOR,
            font=("Microsoft YaHei UI", 14, "bold"),
        ).pack(anchor="w")

        tk.Label(
            side,
            textvariable=self.rank_var,
            justify="left",
            anchor="nw",
            fg=TEXT_MAIN,
            bg=PANEL_COLOR,
            font=("Consolas", 10),
        ).pack(anchor="w", fill="both", expand=True, pady=(10, 0))

        help_bar = tk.Frame(outer, bg=BG_TOP, pady=10)
        help_bar.pack(fill="x")

        music_text = "背景音乐：Be Chillin（CC0）" if MUSIC_FILE.exists() else "背景音乐文件缺失"
        shot_text = "发射音效：shot_01.ogg（CC0）" if SHOT_SOUND_FILE.exists() else "发射音效文件缺失"
        tk.Label(
            help_bar,
            text=f"操作：直接按字母键开炮，Esc 重开，{music_text}，{shot_text}",
            fg=TEXT_MAIN,
            bg=BG_TOP,
            font=("Microsoft YaHei UI", 10, "bold"),
        ).pack(side="left")

    def _create_button(self, parent: tk.Widget, text: str, command) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            width=10,
            bg=ACCENT,
            fg="white",
            activebackground="#1d4ed8",
            activeforeground="white",
            relief="flat",
            bd=0,
            font=("Microsoft YaHei UI", 10, "bold"),
            cursor="hand2",
        )

    def _bind_keys(self) -> None:
        self.root.bind("<Key>", self._handle_keypress)
        self.root.bind("<Escape>", lambda _event: self.restart_game())
        self.root.focus_force()

    def _handle_keypress(self, event: tk.Event) -> None:
        if event.widget is not self.root and isinstance(event.widget, tk.Entry):
            return
        char = event.char.lower()
        if char in string.ascii_lowercase:
            self.hit_letter(char)

    def _current_config(self) -> dict:
        return DIFFICULTY_SETTINGS[self.difficulty_var.get()]

    def _load_save_data(self) -> dict:
        if not SAVE_FILE.exists():
            return {"player_name": "玩家1", "last_difficulty": "普通", "leaderboard": []}
        try:
            return json.loads(SAVE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"player_name": "玩家1", "last_difficulty": "普通", "leaderboard": []}

    def _write_save_data(self) -> None:
        SAVE_FILE.write_text(json.dumps(self.save_data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _record_result(self) -> None:
        if self.result_saved:
            return
        name = self.player_name_var.get().strip() or "玩家1"
        entry = {
            "name": name,
            "score": self.score,
            "difficulty": self.difficulty_var.get(),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        leaderboard = self.save_data.get("leaderboard", [])
        leaderboard.append(entry)
        leaderboard.sort(key=lambda item: item["score"], reverse=True)
        self.save_data["leaderboard"] = leaderboard[:10]
        self.save_data["player_name"] = name
        self.save_data["last_difficulty"] = self.difficulty_var.get()
        self._write_save_data()
        self._refresh_leaderboard()
        self.result_saved = True

    def _refresh_leaderboard(self) -> None:
        leaderboard = self.save_data.get("leaderboard", [])
        if not leaderboard:
            self.rank_var.set("暂无记录")
            return
        lines = []
        for index, item in enumerate(leaderboard[:8], start=1):
            lines.append(
                f"{index:>2}. {item['name'][:8]:<8} {item['score']:>3}  {item['difficulty']}"
            )
        self.rank_var.set("\n".join(lines))

    def start_game(self) -> None:
        if self.running:
            self.root.focus_force()
            return
        if self.game_over:
            self.restart_game()
            return
        self.running = True
        self.status_var.set(f'游戏进行中 {self.difficulty_var.get()}')
        self.sound.play_pattern("start")
        self.sound.start_bgm(MUSIC_FILE)
        self.root.focus_force()
        self._schedule_tick()
        self._schedule_spawn()

    def restart_game(self) -> None:
        self._cancel_timers()
        self.sound.stop_bgm()
        self.score = 0
        self.lives = INITIAL_LIVES
        self.running = False
        self.game_over = False
        self.result_saved = False
        self.balloons = []
        self.explosions = []
        self.projectiles = []
        self.next_balloon_id = 1
        self.score_var.set("分数 0")
        self.lives_var.set(f"失误余量 {self.lives}")
        self.status_var.set("选择难度和名字后开始，直接按字母键发射炮弹")
        self.save_data["player_name"] = self.player_name_var.get().strip() or "玩家1"
        self.save_data["last_difficulty"] = self.difficulty_var.get()
        self._write_save_data()
        self._draw_scene()
        self._draw_message("打字打气球", "点击开始后直接按字母键开炮")
        self.root.focus_force()

    def hit_letter(self, letter: str) -> None:
        if not self.running or self.game_over:
            return

        target = next(
            (balloon for balloon in self.balloons if balloon["letter"] == letter and not balloon["targeted"]),
            None,
        )
        if target is None:
            already_targeted = any(
                balloon["letter"] == letter and balloon["targeted"] for balloon in self.balloons
            )
            if already_targeted:
                self.status_var.set(f"字母 {letter.upper()} 正在被炮弹追踪")
                return
            self.score -= 1
            self.lives -= 1
            self.score_var.set(f"分数 {self.score}")
            self.lives_var.set(f"失误余量 {self.lives}")
            self.status_var.set(f"按错了字母 {letter.upper()}")
            self.sound.play_pattern("wrong")
            if self.lives <= 0:
                self._end_game("失误次数用完了")
                return
            self._draw_scene()
            return

        target["targeted"] = True
        self.projectiles.append(
            {
                "x": self.cannon_x,
                "y": self.cannon_y - 30,
                "target_id": target["id"],
                "color": target["color"],
                "letter": letter,
            }
        )
        self.status_var.set(f"已向字母 {letter.upper()} 发射炮弹")
        self.sound.play_effect_file(SHOT_SOUND_FILE, fallback_name="start")
        self._draw_scene()

    def _schedule_tick(self) -> None:
        if self.tick_after_id is None and self.running and not self.game_over:
            self.tick_after_id = self.root.after(TICK_MS, self._tick)

    def _schedule_spawn(self) -> None:
        config = self._current_config()
        if self.spawn_after_id is None and self.running and not self.game_over:
            self.spawn_after_id = self.root.after(config["spawn_ms"], self._spawn_balloon)

    def _cancel_timers(self) -> None:
        if self.tick_after_id is not None:
            self.root.after_cancel(self.tick_after_id)
            self.tick_after_id = None
        if self.spawn_after_id is not None:
            self.root.after_cancel(self.spawn_after_id)
            self.spawn_after_id = None

    def _spawn_balloon(self) -> None:
        self.spawn_after_id = None
        if not self.running or self.game_over:
            return

        config = self._current_config()
        if len(self.balloons) < config["max_balloons"]:
            x = random.randint(BALLOON_RADIUS + 10, WINDOW_WIDTH - BALLOON_RADIUS - 10)
            y = WINDOW_HEIGHT + BALLOON_RADIUS
            speed = random.uniform(config["speed_min"], config["speed_max"])
            existing_letters = {balloon["letter"] for balloon in self.balloons}
            choices = [ch for ch in string.ascii_lowercase if ch not in existing_letters]
            letter = random.choice(choices or list(string.ascii_lowercase))
            color = random.choice(BALLOON_COLORS)
            self.balloons.append(
                {
                    "id": self.next_balloon_id,
                    "x": x,
                    "y": y,
                    "speed": speed,
                    "letter": letter,
                    "color": color,
                    "targeted": False,
                }
            )
            self.next_balloon_id += 1
        self._schedule_spawn()

    def _tick(self) -> None:
        self.tick_after_id = None
        if not self.running or self.game_over:
            return

        escaped = 0
        remaining_balloons = []
        escaped_target_ids: set[int] = set()
        for balloon in self.balloons:
            balloon["y"] -= balloon["speed"]
            if balloon["y"] + BALLOON_RADIUS < 0:
                escaped += 1
                escaped_target_ids.add(balloon["id"])
            else:
                remaining_balloons.append(balloon)
        self.balloons = remaining_balloons

        balloon_map = {balloon["id"]: balloon for balloon in self.balloons}
        hit_ids: set[int] = set()
        remaining_projectiles = []

        for projectile in self.projectiles:
            target = balloon_map.get(projectile["target_id"])
            if target is None:
                continue
            dx = target["x"] - projectile["x"]
            dy = target["y"] - projectile["y"]
            distance = math.hypot(dx, dy)
            if distance <= PROJECTILE_SPEED + BALLOON_RADIUS * 0.35:
                hit_ids.add(target["id"])
                self.explosions.append(
                    {
                        "x": target["x"],
                        "y": target["y"],
                        "color": target["color"],
                        "frame": 0,
                    }
                )
                self.sound.play_pattern("pop")
                self.score += 1
                self.score_var.set(f"分数 {self.score}")
                self.status_var.set(f'炮弹命中 {projectile["letter"].upper()} 气球')
                if self.score >= TARGET_SCORE:
                    self._win_game()
                    return
            else:
                projectile["x"] += dx / distance * PROJECTILE_SPEED
                projectile["y"] += dy / distance * PROJECTILE_SPEED
                remaining_projectiles.append(projectile)
        self.projectiles = remaining_projectiles

        if hit_ids:
            self.balloons = [balloon for balloon in self.balloons if balloon["id"] not in hit_ids]

        if escaped_target_ids:
            self.projectiles = [
                projectile
                for projectile in self.projectiles
                if projectile["target_id"] not in escaped_target_ids
            ]

        next_explosions = []
        for explosion in self.explosions:
            explosion["frame"] += 1
            if explosion["frame"] <= EXPLOSION_DURATION:
                next_explosions.append(explosion)
        self.explosions = next_explosions

        if escaped:
            self.lives -= escaped
            self.lives_var.set(f"失误余量 {self.lives}")
            self.status_var.set(f"有 {escaped} 个气球飞走了")
            if self.lives <= 0:
                self._end_game("气球飞走太多，游戏结束")
                return

        self._draw_scene()
        self._schedule_tick()

    def _win_game(self) -> None:
        self.running = False
        self.game_over = True
        self._cancel_timers()
        self.sound.stop_bgm()
        self.status_var.set("你已通关")
        self.sound.play_pattern("win")
        self._record_result()
        self._draw_scene()
        self._draw_message("挑战成功", "你已经达到 100 分")

    def _end_game(self, reason: str) -> None:
        self.running = False
        self.game_over = True
        self._cancel_timers()
        self.sound.stop_bgm()
        self.status_var.set(reason)
        self.sound.play_pattern("lose")
        self._record_result()
        self._draw_scene()
        self._draw_message("游戏结束", reason)

    def _draw_scene(self) -> None:
        self.canvas.delete("all")
        self._draw_background()
        self._draw_clouds()
        self._draw_ground()
        self._draw_balloons()
        self._draw_projectiles()
        self._draw_explosions()
        self._draw_cannon()

    def _draw_background(self) -> None:
        self.canvas.create_rectangle(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, fill=BG_TOP, outline="")
        for y in range(0, WINDOW_HEIGHT, 8):
            ratio = y / WINDOW_HEIGHT
            r = int(215 * (1 - ratio) + 254 * ratio)
            g = int(240 * (1 - ratio) + 243 * ratio)
            b = int(255 * (1 - ratio) + 199 * ratio)
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.canvas.create_rectangle(0, y, WINDOW_WIDTH, y + 8, fill=color, outline="")

    def _draw_clouds(self) -> None:
        clouds = [(120, 80), (350, 140), (640, 90), (780, 170)]
        for x, y in clouds:
            self.canvas.create_oval(x, y, x + 70, y + 42, fill="#ffffff", outline="")
            self.canvas.create_oval(x + 25, y - 16, x + 95, y + 34, fill="#ffffff", outline="")
            self.canvas.create_oval(x + 55, y, x + 125, y + 42, fill="#ffffff", outline="")

    def _draw_ground(self) -> None:
        self.canvas.create_rectangle(
            0,
            WINDOW_HEIGHT - GROUND_HEIGHT,
            WINDOW_WIDTH,
            WINDOW_HEIGHT,
            fill="#86efac",
            outline="",
        )
        self.canvas.create_text(
            120,
            WINDOW_HEIGHT - 34,
            text=f"当前难度 {self.difficulty_var.get()}",
            fill="#166534",
            font=("Microsoft YaHei UI", 12, "bold"),
        )
        self.canvas.create_text(
            WINDOW_WIDTH - 120,
            WINDOW_HEIGHT - 34,
            text=f"目标 {TARGET_SCORE} 分",
            fill="#166534",
            font=("Microsoft YaHei UI", 12, "bold"),
        )

    def _draw_balloons(self) -> None:
        for balloon in self.balloons:
            x = balloon["x"]
            y = balloon["y"]
            color = balloon["color"]
            outline = "#f8fafc" if not balloon["targeted"] else "#0f172a"
            width = 2 if not balloon["targeted"] else 4
            self.canvas.create_oval(
                x - BALLOON_RADIUS,
                y - BALLOON_RADIUS,
                x + BALLOON_RADIUS,
                y + BALLOON_RADIUS + 12,
                fill=color,
                outline=outline,
                width=width,
            )
            self.canvas.create_line(
                x,
                y + BALLOON_RADIUS + 10,
                x - 8,
                y + BALLOON_RADIUS + 42,
                fill="#6b7280",
                width=2,
            )
            self.canvas.create_text(
                x,
                y + 2,
                text=balloon["letter"].upper(),
                fill="white",
                font=("Consolas", 20, "bold"),
            )

    def _draw_cannon(self) -> None:
        base_y = WINDOW_HEIGHT - GROUND_HEIGHT + 16
        self.canvas.create_oval(
            self.cannon_x - 42,
            base_y + 18,
            self.cannon_x + 42,
            base_y + 72,
            fill="#334155",
            outline="",
        )
        self.canvas.create_rectangle(
            self.cannon_x - 18,
            base_y - 8,
            self.cannon_x + 18,
            base_y + 40,
            fill="#475569",
            outline="",
        )
        self.canvas.create_polygon(
            self.cannon_x - 16,
            base_y - 4,
            self.cannon_x + 16,
            base_y - 4,
            self.cannon_x + 26,
            base_y - 60,
            self.cannon_x - 26,
            base_y - 60,
            fill="#1e293b",
            outline="",
        )
        self.canvas.create_oval(
            self.cannon_x - 8,
            base_y - 54,
            self.cannon_x + 8,
            base_y - 38,
            fill="#94a3b8",
            outline="",
        )

    def _draw_projectiles(self) -> None:
        for projectile in self.projectiles:
            x = projectile["x"]
            y = projectile["y"]
            self.canvas.create_oval(
                x - 7,
                y - 7,
                x + 7,
                y + 7,
                fill="#111827",
                outline="#f8fafc",
                width=1,
            )
            self.canvas.create_line(x - 14, y + 6, x - 24, y + 16, fill="#cbd5e1", width=2)

    def _draw_explosions(self) -> None:
        for explosion in self.explosions:
            x = explosion["x"]
            y = explosion["y"]
            frame = explosion["frame"]
            radius = 8 + frame * 3
            inner = max(2, radius - 10)
            color = explosion["color"]
            self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, outline=color, width=3)
            self.canvas.create_oval(x - inner, y - inner, x + inner, y + inner, fill="#fff7ed", outline="")
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
                length = radius + 8
                self.canvas.create_line(x, y, x + dx * length, y + dy * length, fill=color, width=2)

    def _draw_message(self, title: str, subtitle: str) -> None:
        left = 220
        top = 180
        right = WINDOW_WIDTH - 220
        bottom = WINDOW_HEIGHT - 190
        self.canvas.create_rectangle(left, top, right, bottom, fill="#ffffff", outline="#60a5fa", width=3)
        self.canvas.create_text(
            WINDOW_WIDTH // 2,
            top + 52,
            text=title,
            fill="#1d4ed8",
            font=("Microsoft YaHei UI", 24, "bold"),
            width=right - left - 40,
        )
        self.canvas.create_text(
            WINDOW_WIDTH // 2,
            top + 106,
            text=subtitle,
            fill=TEXT_MAIN,
            font=("Microsoft YaHei UI", 12),
            width=right - left - 40,
        )
        self.canvas.create_text(
            WINDOW_WIDTH // 2,
            top + 148,
            text="音乐：Be Chillin（CC0） | 发射音效：shot_01.ogg（CC0）",
            fill=TEXT_MUTED,
            font=("Microsoft YaHei UI", 10),
            width=right - left - 40,
        )

    def _on_close(self) -> None:
        self._cancel_timers()
        self.sound.stop_bgm()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    BalloonTypingGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
