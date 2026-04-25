import json
import math
import queue
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
EXPLOSION_DURATION = 20
SMOKE_DURATION = 36
PROJECTILE_SPEED = 18
GROUND_HEIGHT = 92
CANNON_TURN_SPEED = 0.11
FIRE_PRIORITY_GAP = 0.22

ASSETS_DIR = Path(__file__).with_name("assets")
MUSIC_FILE = ASSETS_DIR / "be_chillin.mp3"
FIRE_SOUND_FILE = ASSETS_DIR / "cannon_fire.wav"
TURN_SOUND_FILE = ASSETS_DIR / "turret_turn.wav"
EXPLOSION_SOUND_FILE = ASSETS_DIR / "shell_explosion.wav"
SAVE_FILE = Path(__file__).with_name("balloon_typing_save.json")

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
            "wrong": [(280, 120)],
            "start": [(700, 70), (920, 90)],
            "win": [(780, 80), (980, 80), (1280, 120)],
            "lose": [(180, 220), (130, 240), (100, 260)],
        }
        self.bgm_alias = "balloon_bgm"
        self.music_loaded = False
        self.effect_queue: queue.Queue[tuple[Path | None, str | None, float]] = queue.Queue()
        self.effect_thread = threading.Thread(target=self._effect_worker, daemon=True)
        self.effect_thread.start()
        self.last_fire_time = 0.0

    def play_pattern(self, name: str) -> None:
        if not self.enabled or name not in self.pattern_sounds:
            return
        threading.Thread(target=self._play_pattern, args=(self.pattern_sounds[name],), daemon=True).start()

    def _play_pattern(self, pattern: list[tuple[int, int]]) -> None:
        for freq, duration in pattern:
            try:
                winsound.Beep(freq, duration)
            except RuntimeError:
                return

    def queue_wav(self, file_path: Path, fallback_name: str | None = None, delay: float = 0.0) -> None:
        self.effect_queue.put((file_path, fallback_name, delay))

    def queue_fire(self, file_path: Path) -> None:
        self.last_fire_time = time.time()
        self.queue_wav(file_path, fallback_name="start")

    def queue_explosion(self, file_path: Path) -> None:
        now = time.time()
        delay = max(0.0, FIRE_PRIORITY_GAP - (now - self.last_fire_time))
        self.queue_wav(file_path, fallback_name="lose", delay=delay)

    def _effect_worker(self) -> None:
        while True:
            file_path, fallback_name, delay = self.effect_queue.get()
            if delay > 0:
                time.sleep(delay)
            if self.enabled and file_path and file_path.exists():
                try:
                    winsound.PlaySound(
                        str(file_path),
                        winsound.SND_FILENAME | winsound.SND_SYNC | winsound.SND_NODEFAULT,
                    )
                    continue
                except RuntimeError:
                    pass
            if fallback_name:
                self.play_pattern(fallback_name)

    def start_bgm(self, music_file: Path) -> None:
        if not music_file.exists():
            return
        self.stop_bgm()
        path = str(music_file.resolve()).replace("\\", "\\\\")
        if windll.winmm.mciSendStringW(
            f'open "{path}" type mpegvideo alias {self.bgm_alias}',
            None,
            0,
            0,
        ) == 0:
            self.music_loaded = True
            windll.winmm.mciSendStringW(f"play {self.bgm_alias} repeat", None, 0, 0)

    def stop_bgm(self) -> None:
        if self.music_loaded:
            windll.winmm.mciSendStringW(f"stop {self.bgm_alias}", None, 0, 0)
            windll.winmm.mciSendStringW(f"close {self.bgm_alias}", None, 0, 0)
            self.music_loaded = False


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
        self.smokes: list[dict] = []
        self.projectiles: list[dict] = []
        self.pending_shots: list[dict] = []
        self.sound = SoundManager()

        self.cannon_x = WINDOW_WIDTH // 2
        self.carriage_y = WINDOW_HEIGHT - GROUND_HEIGHT + 22
        self.pivot_x = self.cannon_x
        self.pivot_y = self.carriage_y - 46
        self.cannon_angle = -math.pi / 2
        self.cannon_target_angle = -math.pi / 2
        self.cannon_recoil = 0.0
        self.muzzle_flash_frames = 0
        self.wheel_spin = 0.0
        self.turn_sound_cooldown = 0.0
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
            text="炮管从上部炮座旋转，带机械音、后坐力、烟雾与强化爆炸",
            fg=TEXT_MUTED,
            bg=BG_TOP,
            font=("Microsoft YaHei UI", 10),
        ).pack(anchor="w", pady=(0, 10))

        top_bar = tk.Frame(outer, bg=BG_TOP)
        top_bar.pack(fill="x", pady=(0, 10))

        stats = tk.Frame(top_bar, bg=PANEL_COLOR, padx=12, pady=10)
        stats.pack(side="left", fill="x", expand=True)

        tk.Label(stats, textvariable=self.score_var, fg=TEXT_MAIN, bg=PANEL_COLOR, font=("Microsoft YaHei UI", 12, "bold")).pack(side="left", padx=(0, 18))
        tk.Label(stats, textvariable=self.lives_var, fg=TEXT_MAIN, bg=PANEL_COLOR, font=("Microsoft YaHei UI", 11)).pack(side="left", padx=(0, 18))
        tk.Label(stats, textvariable=self.status_var, fg=ACCENT, bg=PANEL_COLOR, font=("Microsoft YaHei UI", 11)).pack(side="left")

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

        tk.Label(side, text="排行榜", fg=TEXT_MAIN, bg=PANEL_COLOR, font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w")
        tk.Label(side, textvariable=self.rank_var, justify="left", anchor="nw", fg=TEXT_MAIN, bg=PANEL_COLOR, font=("Consolas", 10)).pack(anchor="w", fill="both", expand=True, pady=(10, 0))

        help_bar = tk.Frame(outer, bg=BG_TOP, pady=10)
        help_bar.pack(fill="x")
        tk.Label(
            help_bar,
            text="操作：直接按字母键开炮，Esc 重开，音效策略：发射优先，爆炸短延迟排队播放",
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
            lines.append(f"{index:>2}. {item['name'][:8]:<8} {item['score']:>3}  {item['difficulty']}")
        self.rank_var.set("\n".join(lines))

    def start_game(self) -> None:
        if self.running:
            self.root.focus_force()
            return
        if self.game_over:
            self.restart_game()
            return
        self.running = True
        self.status_var.set(f"游戏进行中 {self.difficulty_var.get()}")
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
        self.smokes = []
        self.projectiles = []
        self.pending_shots = []
        self.next_balloon_id = 1
        self.cannon_angle = -math.pi / 2
        self.cannon_target_angle = -math.pi / 2
        self.cannon_recoil = 0.0
        self.muzzle_flash_frames = 0
        self.wheel_spin = 0.0
        self.turn_sound_cooldown = 0.0
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
            if any(balloon["letter"] == letter and balloon["targeted"] for balloon in self.balloons):
                self.status_var.set(f"字母 {letter.upper()} 正在被追踪")
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
        self.cannon_target_angle = math.atan2(target["y"] - self.pivot_y, target["x"] - self.pivot_x)
        self.pending_shots.append({"target_id": target["id"], "color": target["color"], "letter": letter})
        self.status_var.set(f"锁定字母 {letter.upper()}，炮管转向中")
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
            self.balloons.append(
                {
                    "id": self.next_balloon_id,
                    "x": x,
                    "y": y,
                    "speed": speed,
                    "letter": random.choice(choices or list(string.ascii_lowercase)),
                    "color": random.choice(BALLOON_COLORS),
                    "targeted": False,
                }
            )
            self.next_balloon_id += 1
        self._schedule_spawn()

    def _tick(self) -> None:
        self.tick_after_id = None
        if not self.running or self.game_over:
            return

        self._update_cannon_motion()

        escaped = 0
        escaped_target_ids: set[int] = set()
        remaining_balloons = []
        for balloon in self.balloons:
            balloon["y"] -= balloon["speed"]
            if balloon["y"] + BALLOON_RADIUS < 0:
                escaped += 1
                escaped_target_ids.add(balloon["id"])
            else:
                remaining_balloons.append(balloon)
        self.balloons = remaining_balloons
        balloon_map = {balloon["id"]: balloon for balloon in self.balloons}

        if self.pending_shots:
            shot = self.pending_shots[0]
            target = balloon_map.get(shot["target_id"])
            if target is None:
                self.pending_shots.pop(0)
            elif self._angle_diff(self.cannon_target_angle, self.cannon_angle) < 0.05:
                muzzle_x, muzzle_y = self._get_cannon_muzzle()
                self.projectiles.append(
                    {
                        "x": muzzle_x,
                        "y": muzzle_y,
                        "target_id": target["id"],
                        "color": shot["color"],
                        "letter": shot["letter"],
                    }
                )
                self.cannon_recoil = 16.0
                self.muzzle_flash_frames = 5
                self.wheel_spin += 0.9
                self.sound.queue_fire(FIRE_SOUND_FILE)
                self.status_var.set(f"炮弹已发射，目标 {shot['letter'].upper()}")
                self.pending_shots.pop(0)

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
                self.explosions.append({"x": target["x"], "y": target["y"], "color": target["color"], "frame": 0})
                self.smokes.append({"x": target["x"], "y": target["y"], "frame": 0})
                self.sound.queue_explosion(EXPLOSION_SOUND_FILE)
                self.score += 1
                self.score_var.set(f"分数 {self.score}")
                self.status_var.set(f"炮弹命中 {projectile['letter'].upper()} 气球")
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
            self.projectiles = [p for p in self.projectiles if p["target_id"] not in escaped_target_ids]
            self.pending_shots = [p for p in self.pending_shots if p["target_id"] not in escaped_target_ids]

        self.explosions = [self._advance_frame(item, EXPLOSION_DURATION) for item in self.explosions if item["frame"] < EXPLOSION_DURATION]
        self.smokes = [self._advance_frame(item, SMOKE_DURATION) for item in self.smokes if item["frame"] < SMOKE_DURATION]

        if escaped:
            self.lives -= escaped
            self.lives_var.set(f"失误余量 {self.lives}")
            self.status_var.set(f"有 {escaped} 个气球飞走了")
            if self.lives <= 0:
                self._end_game("气球飞走太多，游戏结束")
                return

        self._draw_scene()
        self._schedule_tick()

    def _advance_frame(self, item: dict, max_frames: int) -> dict:
        item["frame"] += 1
        return item

    def _update_cannon_motion(self) -> None:
        diff = self._normalize_angle(self.cannon_target_angle - self.cannon_angle)
        moved = False
        if abs(diff) > CANNON_TURN_SPEED:
            self.cannon_angle += CANNON_TURN_SPEED if diff > 0 else -CANNON_TURN_SPEED
            moved = True
        else:
            if abs(diff) > 0.01:
                moved = True
            self.cannon_angle = self.cannon_target_angle
        self.cannon_angle = self._normalize_angle(self.cannon_angle)

        if moved and self.turn_sound_cooldown <= 0:
            self.sound.queue_wav(TURN_SOUND_FILE, fallback_name=None)
            self.turn_sound_cooldown = 0.18
        self.turn_sound_cooldown = max(0.0, self.turn_sound_cooldown - TICK_MS / 1000)

        self.cannon_recoil *= 0.72
        if self.cannon_recoil < 0.25:
            self.cannon_recoil = 0.0
        if self.muzzle_flash_frames > 0:
            self.muzzle_flash_frames -= 1
        self.wheel_spin *= 0.9

    def _normalize_angle(self, angle: float) -> float:
        while angle > math.pi:
            angle -= 2 * math.pi
        while angle < -math.pi:
            angle += 2 * math.pi
        return angle

    def _angle_diff(self, target: float, current: float) -> float:
        return abs(self._normalize_angle(target - current))

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
        self._draw_smokes()
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
            self.canvas.create_rectangle(0, y, WINDOW_WIDTH, y + 8, fill=f"#{r:02x}{g:02x}{b:02x}", outline="")

    def _draw_clouds(self) -> None:
        for x, y in [(120, 80), (350, 140), (640, 90), (780, 170)]:
            self.canvas.create_oval(x, y, x + 70, y + 42, fill="#ffffff", outline="")
            self.canvas.create_oval(x + 25, y - 16, x + 95, y + 34, fill="#ffffff", outline="")
            self.canvas.create_oval(x + 55, y, x + 125, y + 42, fill="#ffffff", outline="")

    def _draw_ground(self) -> None:
        self.canvas.create_rectangle(0, WINDOW_HEIGHT - GROUND_HEIGHT, WINDOW_WIDTH, WINDOW_HEIGHT, fill="#86efac", outline="")
        self.canvas.create_text(120, WINDOW_HEIGHT - 34, text=f"当前难度 {self.difficulty_var.get()}", fill="#166534", font=("Microsoft YaHei UI", 12, "bold"))
        self.canvas.create_text(WINDOW_WIDTH - 120, WINDOW_HEIGHT - 34, text=f"目标 {TARGET_SCORE} 分", fill="#166534", font=("Microsoft YaHei UI", 12, "bold"))

    def _draw_balloons(self) -> None:
        for balloon in self.balloons:
            x = balloon["x"]
            y = balloon["y"]
            outline = "#f8fafc" if not balloon["targeted"] else "#0f172a"
            width = 2 if not balloon["targeted"] else 4
            self.canvas.create_oval(x - BALLOON_RADIUS, y - BALLOON_RADIUS, x + BALLOON_RADIUS, y + BALLOON_RADIUS + 12, fill=balloon["color"], outline=outline, width=width)
            self.canvas.create_line(x, y + BALLOON_RADIUS + 10, x - 8, y + BALLOON_RADIUS + 42, fill="#6b7280", width=2)
            self.canvas.create_text(x, y + 2, text=balloon["letter"].upper(), fill="white", font=("Consolas", 20, "bold"))

    def _draw_cannon(self) -> None:
        pivot_x, pivot_y = self._get_cannon_pivot()
        dir_x = math.cos(self.cannon_angle)
        dir_y = math.sin(self.cannon_angle)
        perp_x = -dir_y
        perp_y = dir_x
        barrel_length = 90
        barrel_half_width = 17

        rear_left = (pivot_x - perp_x * barrel_half_width, pivot_y - perp_y * barrel_half_width)
        rear_right = (pivot_x + perp_x * barrel_half_width, pivot_y + perp_y * barrel_half_width)
        front_center = (pivot_x + dir_x * barrel_length, pivot_y + dir_y * barrel_length)
        front_left = (front_center[0] - perp_x * 13, front_center[1] - perp_y * 13)
        front_right = (front_center[0] + perp_x * 13, front_center[1] + perp_y * 13)

        self.canvas.create_oval(self.cannon_x - 84, self.carriage_y + 26, self.cannon_x + 84, self.carriage_y + 76, fill="#000000", outline="", stipple="gray25")
        self._draw_wheel(self.cannon_x - 54, self.carriage_y + 26, 28)
        self._draw_wheel(self.cannon_x + 54, self.carriage_y + 26, 28)

        self.canvas.create_polygon(
            self.cannon_x - 46, self.carriage_y + 18,
            self.cannon_x + 46, self.carriage_y + 18,
            self.cannon_x + 26, self.carriage_y - 8,
            self.cannon_x - 26, self.carriage_y - 8,
            fill="#475569",
            outline="",
        )
        self.canvas.create_rectangle(self.cannon_x - 26, self.carriage_y - 20, self.cannon_x + 26, self.carriage_y + 10, fill="#64748b", outline="")

        self.canvas.create_polygon(
            rear_left[0] + 7, rear_left[1] + 10,
            rear_right[0] + 7, rear_right[1] + 10,
            front_right[0] + 7, front_right[1] + 10,
            front_left[0] + 7, front_left[1] + 10,
            fill="#0f172a", outline="", stipple="gray50"
        )
        self.canvas.create_polygon(
            rear_left[0], rear_left[1],
            rear_right[0], rear_right[1],
            front_right[0], front_right[1],
            front_left[0], front_left[1],
            fill="#334155", outline=""
        )
        self.canvas.create_polygon(
            rear_left[0] - dir_x * 8 + perp_x * 4, rear_left[1] - dir_y * 8 + perp_y * 4,
            rear_right[0] - dir_x * 8 + perp_x * 4, rear_right[1] - dir_y * 8 + perp_y * 4,
            rear_right[0], rear_right[1],
            rear_left[0], rear_left[1],
            fill="#94a3b8", outline=""
        )
        self.canvas.create_polygon(
            front_left[0], front_left[1],
            front_right[0], front_right[1],
            front_center[0] + dir_x * 14, front_center[1] + dir_y * 14,
            fill="#111827", outline=""
        )

        self.canvas.create_oval(pivot_x - 15, pivot_y - 15, pivot_x + 15, pivot_y + 15, fill="#94a3b8", outline="")
        self.canvas.create_oval(pivot_x - 7, pivot_y - 7, pivot_x + 7, pivot_y + 7, fill="#e2e8f0", outline="")

        if self.muzzle_flash_frames > 0:
            scale = 1 + self.muzzle_flash_frames * 0.16
            tip_x = front_center[0] + dir_x * (28 * scale)
            tip_y = front_center[1] + dir_y * (28 * scale)
            side = 18 * scale
            back = 12 * scale
            self.canvas.create_polygon(
                front_center[0] + perp_x * side, front_center[1] + perp_y * side,
                tip_x, tip_y,
                front_center[0] - perp_x * side, front_center[1] - perp_y * side,
                front_center[0] - dir_x * back, front_center[1] - dir_y * back,
                fill="#f97316", outline=""
            )
            self.canvas.create_polygon(
                front_center[0] + perp_x * (side * 0.55), front_center[1] + perp_y * (side * 0.55),
                front_center[0] + dir_x * (34 * scale), front_center[1] + dir_y * (34 * scale),
                front_center[0] - perp_x * (side * 0.55), front_center[1] - perp_y * (side * 0.55),
                front_center[0] - dir_x * (5 * scale), front_center[1] - dir_y * (5 * scale),
                fill="#fde68a", outline=""
            )

    def _draw_wheel(self, center_x: float, center_y: float, radius: float) -> None:
        self.canvas.create_oval(center_x - radius, center_y - radius, center_x + radius, center_y + radius, fill="#475569", outline="#1e293b", width=3)
        self.canvas.create_oval(center_x - radius * 0.35, center_y - radius * 0.35, center_x + radius * 0.35, center_y + radius * 0.35, fill="#cbd5e1", outline="")
        for index in range(6):
            angle = self.wheel_spin + index * math.pi / 3
            dx = math.cos(angle) * radius * 0.8
            dy = math.sin(angle) * radius * 0.8
            self.canvas.create_line(center_x, center_y, center_x + dx, center_y + dy, fill="#e2e8f0", width=2)

    def _draw_projectiles(self) -> None:
        for projectile in self.projectiles:
            x = projectile["x"]
            y = projectile["y"]
            self.canvas.create_oval(x - 8, y - 8, x + 8, y + 8, fill="#111827", outline="#f8fafc", width=1)

    def _get_cannon_pivot(self) -> tuple[float, float]:
        dir_x = math.cos(self.cannon_angle)
        dir_y = math.sin(self.cannon_angle)
        return self.pivot_x - dir_x * self.cannon_recoil, self.pivot_y - dir_y * self.cannon_recoil

    def _get_cannon_muzzle(self) -> tuple[float, float]:
        pivot_x, pivot_y = self._get_cannon_pivot()
        dir_x = math.cos(self.cannon_angle)
        dir_y = math.sin(self.cannon_angle)
        return pivot_x + dir_x * 104, pivot_y + dir_y * 104

    def _draw_explosions(self) -> None:
        for explosion in self.explosions:
            x = explosion["x"]
            y = explosion["y"]
            frame = explosion["frame"]
            progress = frame / EXPLOSION_DURATION
            radius = 10 + progress * 46
            inner = max(4, radius * 0.32)
            color = explosion["color"]
            self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, outline=color, width=3)
            self.canvas.create_oval(x - inner, y - inner, x + inner, y + inner, fill="#fff7ed", outline="")
            self.canvas.create_oval(x - radius * 0.65, y - radius * 0.65, x + radius * 0.65, y + radius * 0.65, outline="#fde68a", width=2)
            for index in range(12):
                angle = progress * 0.9 + index * (math.pi * 2 / 12)
                spark_len = radius + 6 + (index % 4) * 4
                sx = x + math.cos(angle) * spark_len
                sy = y + math.sin(angle) * spark_len
                self.canvas.create_line(x, y, sx, sy, fill=color, width=2)
                self.canvas.create_oval(sx - 2, sy - 2, sx + 2, sy + 2, fill="#fde68a", outline="")

    def _draw_smokes(self) -> None:
        for smoke in self.smokes:
            progress = smoke["frame"] / SMOKE_DURATION
            alpha_scale = 1.0 - progress
            base = 16 + progress * 26
            color = "#cbd5e1" if progress < 0.45 else "#94a3b8"
            for dx, dy, scale in [(-18, -8, 0.9), (0, -18, 1.1), (16, -6, 0.8), (-6, 10, 0.7)]:
                radius = base * scale
                x = smoke["x"] + dx * progress
                y = smoke["y"] + dy * progress
                self.canvas.create_oval(
                    x - radius,
                    y - radius,
                    x + radius,
                    y + radius,
                    fill=color,
                    outline="",
                    stipple="gray25" if alpha_scale > 0.45 else "gray50",
                )

    def _draw_message(self, title: str, subtitle: str) -> None:
        left = 220
        top = 180
        right = WINDOW_WIDTH - 220
        bottom = WINDOW_HEIGHT - 190
        self.canvas.create_rectangle(left, top, right, bottom, fill="#ffffff", outline="#60a5fa", width=3)
        self.canvas.create_text(WINDOW_WIDTH // 2, top + 52, text=title, fill="#1d4ed8", font=("Microsoft YaHei UI", 24, "bold"), width=right - left - 40)
        self.canvas.create_text(WINDOW_WIDTH // 2, top + 106, text=subtitle, fill=TEXT_MAIN, font=("Microsoft YaHei UI", 12), width=right - left - 40)
        self.canvas.create_text(WINDOW_WIDTH // 2, top + 148, text="音乐：Be Chillin | 转向：Turret Turn | 发射：Cannon Fire | 爆炸：Shell Explosion", fill=TEXT_MUTED, font=("Microsoft YaHei UI", 10), width=right - left - 40)

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
