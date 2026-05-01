# -*- coding: utf-8 -*-

import json
import math
import random
import string
import sys
import threading
import time
import tkinter as tk
import wave
from ctypes import windll
from pathlib import Path
from tkinter import messagebox, simpledialog

try:
    import winsound
except ImportError:  # pragma: no cover
    winsound = None


WINDOW_WIDTH = 900
WINDOW_HEIGHT = 620
BALLOON_RADIUS = 28
INITIAL_LIVES = 5
MAX_MISTAKES = 20
MAX_LEVEL = 100
LEVEL_TARGET = 50
MAX_BURST_SHOTS = 5

TICK_MS = 35
EXPLOSION_DURATION = 20
SMOKE_DURATION = 36
PROJECTILE_SPEED = 18
GROUND_HEIGHT = 92
CANNON_TURN_SPEED = 0.18
BURST_TURN_SPEED = 0.38

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
else:
    APP_DIR = Path(__file__).resolve().parent
    RESOURCE_DIR = APP_DIR

ASSETS_DIR = RESOURCE_DIR / "assets"
MUSIC_FILE = ASSETS_DIR / "be_chillin.mp3"
FIRE_SOUND_FILE = ASSETS_DIR / "cannon_fire.wav"
EXPLOSION_SOUND_FILE = ASSETS_DIR / "shell_explosion.wav"
SAVE_FILE = APP_DIR / "balloon_typing_save.json"

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

MOJIBAKE_MAP = {
    "鐜╁1": "玩家1",
    "鏅€?": "普通",
    "鍥伴毦": "困难",
    "绠€鍗?": "简单",
    "鎱㈡參": "慢慢",
}


def clean_text(value: str, fallback: str = "") -> str:
    if not isinstance(value, str):
        return fallback
    return MOJIBAKE_MAP.get(value, value.strip() or fallback)


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
        self.effect_index = 0

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

    def play_effect_now(self, file_path: Path, fallback_name: str | None = None) -> None:
        if not self.enabled:
            return
        if file_path.exists():
            threading.Thread(target=self._play_effect_file, args=(file_path, fallback_name), daemon=True).start()
            return
        if fallback_name:
            self.play_pattern(fallback_name)

    def _play_effect_file(self, file_path: Path, fallback_name: str | None) -> None:
        try:
            alias = f"balloon_sfx_{self.effect_index}"
            self.effect_index += 1
            path = str(file_path.resolve()).replace("\\", "\\\\")
            result = windll.winmm.mciSendStringW(
                f'open "{path}" type waveaudio alias {alias}',
                None,
                0,
                0,
            )
            if result == 0:
                windll.winmm.mciSendStringW(f"play {alias}", None, 0, 0)
                time.sleep(self._get_wav_duration(file_path) + 0.05)
                windll.winmm.mciSendStringW(f"stop {alias}", None, 0, 0)
                windll.winmm.mciSendStringW(f"close {alias}", None, 0, 0)
                return
            winsound.PlaySound(str(file_path), winsound.SND_FILENAME | winsound.SND_NODEFAULT)
        except Exception:
            if fallback_name:
                self.play_pattern(fallback_name)

    def _get_wav_duration(self, file_path: Path) -> float:
        try:
            with wave.open(str(file_path), "rb") as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                if rate > 0:
                    return frames / float(rate)
        except Exception:
            pass
        return 0.6

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
        self.level_var = tk.StringVar(value="关卡 1")
        self.coin_var = tk.StringVar(value="金币 0")
        self.player_display_var = tk.StringVar(value="玩家：未创建")
        self.save_name_var = tk.StringVar(value="存档：未创建")
        self.status_var = tk.StringVar(value="先创建玩家，再开始游戏")
        self.lives_var = tk.StringVar(value=f"失误余量 {INITIAL_LIVES}")
        self.difficulty_var = tk.StringVar(value="普通")
        self.player_var = tk.StringVar(value="")
        self.rank_var = tk.StringVar(value="排行榜载入中")

        self.score = 0
        self.level = 1
        self.level_score = 0
        self.level_target = LEVEL_TARGET
        self.lives = INITIAL_LIVES
        self.coins = 0
        self.inventory: dict[str, int] = {}

        self.running = False
        self.game_over = False
        self.awaiting_continue = False
        self.result_saved = False
        self.paused = False
        self.session_player: str | None = None
        self.session_best_entry: dict | None = None
        self.exit_dialog: tk.Toplevel | None = None
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
        self.pivot_y = self.carriage_y - 40
        self.cannon_angle = -math.pi / 2
        self.cannon_target_angle = -math.pi / 2
        self.cannon_recoil = 0.0
        self.muzzle_flash_frames = 0
        self.wheel_spin = 0.0
        self.next_balloon_id = 1

        self.save_data = self._load_save_data()
        self.active_player = self.save_data.get("active_player", "")
        if self.active_player and self.active_player not in self.save_data["players"]:
            self.active_player = ""
        if not self.active_player and self.save_data["players"]:
            self.active_player = sorted(self.save_data["players"].keys())[0]
        self.player_var.set(self.active_player)

        self._build_ui()
        self._bind_keys()
        self._refresh_player_menu()
        if self.active_player:
            self._switch_player(self.active_player)
            self._draw_scene()
            self._draw_message("打字打气球", "点击开始或读档继续")
        else:
            self._refresh_leaderboard()
            self._draw_scene()
            self._draw_message("打字打气球", "点击“新建玩家”创建专属存档")

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _load_save_data(self) -> dict:
        default = {"active_player": "", "players": {}, "leaderboard": []}
        if not SAVE_FILE.exists():
            return default
        try:
            raw = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return default

        if "players" in raw and isinstance(raw["players"], dict):
            raw.setdefault("active_player", "")
            raw["leaderboard"] = self._normalize_leaderboard(raw.get("leaderboard", []))
            return raw

        players: dict[str, dict] = {}
        save_slots = raw.get("save_slots", {}) if isinstance(raw.get("save_slots"), dict) else {}
        slot_profiles = raw.get("slot_profiles", {}) if isinstance(raw.get("slot_profiles"), dict) else {}

        for _, slot_data in save_slots.items():
            if not isinstance(slot_data, dict):
                continue
            player_name = clean_text(slot_data.get("player_name", ""), "")
            if not player_name:
                continue
            player = players.setdefault(
                player_name,
                {
                    "save_name": f"{player_name}的存档",
                    "difficulty": clean_text(slot_data.get("difficulty", ""), "普通"),
                    "coins": int(slot_data.get("coins", raw.get("coins", 0))),
                    "inventory": dict(slot_data.get("inventory", raw.get("inventory", {}))),
                    "progress": None,
                    "best_result": None,
                },
            )
            candidate = {
                "score": int(slot_data.get("score", 0)),
                "level": int(slot_data.get("level", 1)),
                "level_score": int(slot_data.get("level_score", 0)),
                "level_target": int(slot_data.get("level_target", LEVEL_TARGET)),
                "lives": int(slot_data.get("lives", INITIAL_LIVES)),
            }
            current = player.get("progress")
            if current is None or (candidate["level"], candidate["score"]) > (current["level"], current["score"]):
                player["progress"] = candidate

        for _, profile in slot_profiles.items():
            if not isinstance(profile, dict):
                continue
            player_name = clean_text(profile.get("player_name", ""), "")
            if not player_name:
                continue
            player = players.setdefault(
                player_name,
                {
                    "save_name": f"{player_name}的存档",
                    "difficulty": clean_text(profile.get("difficulty", ""), "普通"),
                    "coins": int(raw.get("coins", 0)),
                    "inventory": dict(raw.get("inventory", {})),
                    "progress": None,
                    "best_result": None,
                },
            )
            player["save_name"] = f"{player_name}的存档"
            player["difficulty"] = clean_text(profile.get("difficulty", ""), player["difficulty"])

        for item in raw.get("leaderboard", []):
            if not isinstance(item, dict):
                continue
            player_name = clean_text(item.get("name", ""), "")
            if not player_name:
                continue
            entry = {
                "score": int(item.get("score", 0)),
                "level": int(item.get("level", 1)),
                "difficulty": clean_text(item.get("difficulty", ""), "普通"),
                "timestamp": item.get("timestamp", ""),
            }
            player = players.setdefault(
                player_name,
                {
                    "save_name": f"{player_name}的存档",
                    "difficulty": entry["difficulty"],
                    "coins": 0,
                    "inventory": {},
                    "progress": None,
                    "best_result": None,
                },
            )
            best = player.get("best_result")
            if best is None or (entry["level"], entry["score"]) > (best["level"], best["score"]):
                player["best_result"] = entry

        leaderboard = self._normalize_leaderboard(raw.get("leaderboard", []))

        active_player = clean_text(raw.get("player_name", ""), "")
        if active_player not in players:
            active_player = next(iter(players.keys()), "")

        return {"active_player": active_player, "players": players, "leaderboard": leaderboard[:10]}

    def _entry_key(self, item: dict | None) -> tuple[int, int]:
        if not item:
            return (-1, -1)
        return (int(item.get("level", 0)), int(item.get("score", 0)))

    def _normalize_leaderboard(self, entries: list[dict]) -> list[dict]:
        best_by_player: dict[str, dict] = {}
        for item in entries:
            if not isinstance(item, dict):
                continue
            player_name = clean_text(item.get("name", ""), "")
            if not player_name:
                continue
            entry = {
                "name": player_name,
                "score": int(item.get("score", 0)),
                "level": int(item.get("level", 1)),
                "difficulty": clean_text(item.get("difficulty", ""), "普通"),
                "timestamp": str(item.get("timestamp", "")),
            }
            current = best_by_player.get(player_name)
            if current is None or self._entry_key(entry) >= self._entry_key(current):
                best_by_player[player_name] = entry
        result = list(best_by_player.values())
        result.sort(key=self._entry_key, reverse=True)
        return result[:10]

    def _merge_leaderboard_record(self, player_name: str, entry: dict) -> None:
        record = {"name": player_name, **entry}
        entries = [item for item in self.save_data.get("leaderboard", []) if item.get("name") != player_name]
        entries.append(record)
        self.save_data["leaderboard"] = self._normalize_leaderboard(entries)

    def _write_save_data(self) -> None:
        self.save_data["active_player"] = self.active_player
        self.save_data["leaderboard"] = self._normalize_leaderboard(self.save_data.get("leaderboard", []))
        SAVE_FILE.write_text(json.dumps(self.save_data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, bg=BG_TOP, padx=16, pady=16)
        outer.pack()

        tk.Label(outer, text="BALLOON TYPE", fg="#0f172a", bg=BG_TOP, font=("Consolas", 24, "bold")).pack(anchor="w")
        tk.Label(outer, text="玩家和存档完全绑定，排行榜只看真实结算，但会实时预览当前新高", fg=TEXT_MUTED, bg=BG_TOP, font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(0, 10))

        row1 = tk.Frame(outer, bg=BG_TOP)
        row1.pack(fill="x", pady=(0, 8))
        stats = tk.Frame(row1, bg=PANEL_COLOR, padx=12, pady=10, width=1120, height=54)
        stats.pack(side="left")
        stats.pack_propagate(False)
        tk.Label(stats, textvariable=self.score_var, fg=TEXT_MAIN, bg=PANEL_COLOR, font=("Microsoft YaHei UI", 12, "bold")).pack(side="left", padx=(0, 18))
        tk.Label(stats, textvariable=self.level_var, fg=TEXT_MAIN, bg=PANEL_COLOR, font=("Microsoft YaHei UI", 11, "bold")).pack(side="left", padx=(0, 18))
        tk.Label(stats, textvariable=self.coin_var, fg=TEXT_MAIN, bg=PANEL_COLOR, font=("Microsoft YaHei UI", 11, "bold")).pack(side="left", padx=(0, 18))
        tk.Label(stats, textvariable=self.lives_var, fg=TEXT_MAIN, bg=PANEL_COLOR, font=("Microsoft YaHei UI", 11)).pack(side="left", padx=(0, 18))
        tk.Label(stats, textvariable=self.player_display_var, fg=TEXT_MAIN, bg=PANEL_COLOR, font=("Microsoft YaHei UI", 11, "bold")).pack(side="left", padx=(0, 18))
        tk.Label(stats, textvariable=self.status_var, fg=ACCENT, bg=PANEL_COLOR, font=("Microsoft YaHei UI", 11), anchor="w", justify="left", width=28).pack(side="left")

        row2 = tk.Frame(outer, bg=BG_TOP)
        row2.pack(fill="x", pady=(0, 10))
        controls = tk.Frame(row2, bg=PANEL_COLOR, padx=12, pady=10, width=1120, height=56)
        controls.pack(side="left")
        controls.pack_propagate(False)

        self.player_menu = tk.OptionMenu(controls, self.player_var, "")
        self.player_menu.config(width=10, bg="#1f2937", fg="white", activebackground="#334155", activeforeground="white", relief="flat", highlightthickness=0, font=("Microsoft YaHei UI", 10))
        self.player_menu["menu"].config(bg="#1f2937", fg="white", activebackground="#334155", activeforeground="white", font=("Microsoft YaHei UI", 10))
        self.player_menu.pack(side="left", padx=(0, 8))

        diff_option = tk.OptionMenu(controls, self.difficulty_var, *DIFFICULTY_SETTINGS.keys())
        diff_option.config(width=6, bg="#1f2937", fg="white", activebackground="#334155", activeforeground="white", relief="flat", highlightthickness=0, font=("Microsoft YaHei UI", 10))
        diff_option["menu"].config(bg="#1f2937", fg="white", activebackground="#334155", activeforeground="white", font=("Microsoft YaHei UI", 10))
        diff_option.pack(side="left", padx=(0, 8))

        self._create_button(controls, "新建玩家", self.create_player_save).pack(side="left", padx=(0, 8))
        self._create_button(controls, "开始", self.start_game).pack(side="left", padx=(0, 8))
        self._create_button(controls, "读档", self.load_progress).pack(side="left", padx=(0, 8))
        self.continue_button = self._create_button(controls, "继续", self.continue_level)
        self.continue_button.pack(side="left", padx=(0, 8))
        self.continue_button.config(state="disabled")
        self._create_button(controls, "删除玩家", self.delete_player).pack(side="left", padx=(0, 8))
        self._create_button(controls, "重开", self.restart_game).pack(side="left", padx=(0, 8))

        middle = tk.Frame(outer, bg=BG_TOP)
        middle.pack()
        board = tk.Frame(middle, bg=PANEL_COLOR, padx=10, pady=10)
        board.pack(side="left")
        self.canvas = tk.Canvas(board, width=WINDOW_WIDTH, height=WINDOW_HEIGHT, bg="#d7f0ff", highlightthickness=1, highlightbackground="#93c5fd")
        self.canvas.pack()

        side = tk.Frame(middle, bg=PANEL_COLOR, padx=12, pady=12, width=240)
        side.pack(side="left", padx=(12, 0), fill="y")
        side.pack_propagate(False)
        tk.Label(side, textvariable=self.save_name_var, justify="left", anchor="nw", fg=ACCENT, bg=PANEL_COLOR, font=("Microsoft YaHei UI", 10, "bold"), wraplength=210).pack(anchor="w", pady=(0, 10))
        tk.Label(side, text="排行榜", fg=TEXT_MAIN, bg=PANEL_COLOR, font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w")
        tk.Label(side, textvariable=self.rank_var, justify="left", anchor="nw", fg=TEXT_MAIN, bg=PANEL_COLOR, font=("Consolas", 10)).pack(anchor="w", fill="both", expand=True, pady=(10, 0))

        self.root.update_idletasks()
        fixed_width = self.root.winfo_width()
        fixed_height = self.root.winfo_height()
        self.root.geometry(f"{fixed_width}x{fixed_height}")
        self.root.minsize(fixed_width, fixed_height)
        self.root.maxsize(fixed_width, fixed_height)

    def _create_button(self, parent: tk.Widget, text: str, command) -> tk.Button:
        return tk.Button(parent, text=text, command=command, width=10, bg=ACCENT, fg="white", activebackground="#1d4ed8", activeforeground="white", relief="flat", bd=0, font=("Microsoft YaHei UI", 10, "bold"), cursor="hand2")

    def _bind_keys(self) -> None:
        self.root.bind("<Key>", self._handle_keypress)
        self.root.bind("<Escape>", lambda _event: self.request_exit())
        self.player_var.trace_add("write", self._on_player_changed)
        self.root.focus_force()

    def _handle_keypress(self, event: tk.Event) -> None:
        if event.widget is not self.root and isinstance(event.widget, tk.Entry):
            return
        char = event.char.lower()
        if char in string.ascii_lowercase:
            self.hit_letter(char)

    def _refresh_player_menu(self) -> None:
        menu = self.player_menu["menu"]
        menu.delete(0, "end")
        players = sorted(self.save_data["players"].keys())
        for player in players:
            menu.add_command(label=player, command=lambda value=player: self.player_var.set(value))
        if players and self.player_var.get() not in players:
            self.player_var.set(players[0])

    def _current_config(self) -> dict:
        base = DIFFICULTY_SETTINGS[self.difficulty_var.get()]
        level_boost = self.level - 1
        return {
            "spawn_ms": max(260, base["spawn_ms"] - level_boost * 8),
            "max_balloons": min(14, base["max_balloons"] + level_boost // 4),
            "speed_min": base["speed_min"] + level_boost * 0.03,
            "speed_max": base["speed_max"] + level_boost * 0.035,
        }

    def _sync_player_display(self) -> None:
        if not self.active_player:
            self.player_display_var.set("玩家：未创建")
            self.save_name_var.set("存档：未创建")
            return
        player = self.save_data["players"][self.active_player]
        self.player_display_var.set(f"玩家：{self.active_player}")
        self.save_name_var.set(f"存档：{player['save_name']}")

    def _switch_player(self, player_name: str) -> None:
        if player_name not in self.save_data["players"]:
            return
        self.active_player = player_name
        self.player_var.set(player_name)
        player = self.save_data["players"][player_name]
        self.difficulty_var.set(player.get("difficulty", "普通"))
        self.coins = int(player.get("coins", 0))
        self.inventory = dict(player.get("inventory", {}))
        self.coin_var.set(f"金币 {self.coins}")
        if not self.running and not self.awaiting_continue and not self.game_over:
            self.session_player = None
            self.session_best_entry = None
        self._sync_player_display()
        self._refresh_leaderboard()

    def _on_player_changed(self, *_args) -> None:
        player_name = self.player_var.get()
        if player_name and player_name != self.active_player:
            self._switch_player(player_name)

    def _save_player_profile(self) -> None:
        if not self.active_player:
            return
        player = self.save_data["players"].setdefault(
            self.active_player,
            {
                "save_name": f"{self.active_player}的存档",
                "difficulty": "普通",
                "coins": 0,
                "inventory": {},
                "progress": None,
                "best_result": None,
            },
        )
        player["save_name"] = f"{self.active_player}的存档"
        player["difficulty"] = self.difficulty_var.get()
        player["coins"] = self.coins
        player["inventory"] = dict(self.inventory)

    def _snapshot_progress(self) -> dict:
        return {
            "score": self.score,
            "level": self.level,
            "level_score": self.level_score,
            "level_target": self.level_target,
            "lives": self.lives,
        }

    def _default_progress(self) -> dict:
        return {
            "score": 0,
            "level": 1,
            "level_score": 0,
            "level_target": LEVEL_TARGET,
            "lives": INITIAL_LIVES,
        }

    def _save_progress(self) -> None:
        if not self.active_player:
            return
        self._save_player_profile()
        self.save_data["players"][self.active_player]["progress"] = self._snapshot_progress()
        self._write_save_data()

    def _clear_progress(self) -> None:
        if not self.active_player:
            return
        self.save_data["players"][self.active_player]["progress"] = None
        self._write_save_data()

    def _record_result(self) -> None:
        if self.result_saved or not self.active_player:
            return
        entry = {
            "score": self.score,
            "level": self.level,
            "difficulty": self.difficulty_var.get(),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        player = self.save_data["players"][self.active_player]
        best = player.get("best_result")
        if best is None or (entry["level"], entry["score"]) >= (best["level"], best["score"]):
            player["best_result"] = entry
        self._merge_leaderboard_record(self.active_player, entry)
        self._write_save_data()
        self._refresh_leaderboard()
        self.result_saved = True

    def _refresh_leaderboard(self) -> None:
        entries = self._normalize_leaderboard(self.save_data.get("leaderboard", []))
        preview_player = self.session_player
        if preview_player and preview_player in self.save_data["players"] and (self.running or self.awaiting_continue or self.game_over):
            current_entry = {
                "name": preview_player,
                "score": self.score,
                "level": self.level,
                "difficulty": self.difficulty_var.get(),
                "timestamp": "当前",
            }
            if (
                self.session_best_entry is None
                or self.session_best_entry.get("name") != preview_player
                or self._entry_key(current_entry) >= self._entry_key(self.session_best_entry)
            ):
                self.session_best_entry = current_entry
            preview_entry = self.session_best_entry
            global_best = next((item for item in entries if item.get("name") == preview_player), None)
            if self._entry_key(preview_entry) >= self._entry_key(global_best):
                entries = [item for item in entries if item.get("name") != preview_player]
                entries.append(preview_entry)
        entries.sort(key=self._entry_key, reverse=True)
        if not entries:
            self.rank_var.set("暂无记录")
            return
        lines = []
        for index, item in enumerate(entries[:8], start=1):
            lines.append(f"{index:>2}. {item['name'][:6]:<6} L{item['level']:>3}  {item['score']:>3}")
        self.rank_var.set("\n".join(lines))

    def create_player_save(self) -> None:
        player_name = simpledialog.askstring("新建玩家", "输入玩家名字：", parent=self.root)
        if player_name is None:
            return
        player_name = player_name.strip()
        if not player_name:
            messagebox.showwarning("名字为空", "请输入有效的玩家名字。", parent=self.root)
            return
        if player_name in self.save_data["players"]:
            messagebox.showerror("名字重复", f"玩家“{player_name}”已存在。", parent=self.root)
            return

        self.save_data["players"][player_name] = {
            "save_name": f"{player_name}的存档",
            "difficulty": self.difficulty_var.get(),
            "coins": self.coins,
            "inventory": {},
            "progress": None,
            "best_result": None,
        }
        self.active_player = player_name
        self.player_var.set(player_name)

        self.score = 0
        self.level = 1
        self.level_score = 0
        self.level_target = LEVEL_TARGET
        self.lives = INITIAL_LIVES
        self.running = False
        self.game_over = False
        self.awaiting_continue = False
        self.result_saved = False
        self.session_player = None
        self.session_best_entry = None
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

        self._refresh_player_menu()
        self._switch_player(player_name)
        self.session_player = player_name
        self.session_best_entry = None
        self._save_progress()

        self.score_var.set("分数 0")
        self.level_var.set("关卡 1")
        self.coin_var.set(f"金币 {self.coins}")
        self.lives_var.set(f"失误余量 {self.lives}")
        self.status_var.set(f"已创建玩家：{player_name}")
        self.continue_button.config(state="disabled")
        self._draw_scene()
        self._draw_message("玩家已创建", f"{player_name} 的存档已建立，点击开始或读档继续")

    def delete_player(self) -> None:
        if not self.active_player:
            self.status_var.set("当前没有可删除的玩家")
            return
        if not messagebox.askyesno("删除玩家", f"确定删除玩家“{self.active_player}”及其存档吗？", parent=self.root):
            return

        deleted = self.active_player
        self.save_data["players"].pop(deleted, None)
        if self.active_player == deleted:
            self.active_player = ""
        if self.save_data["players"]:
            self.active_player = sorted(self.save_data["players"].keys())[0]
        self._write_save_data()
        self._refresh_player_menu()
        if self.active_player:
            self._switch_player(self.active_player)
        else:
            self.player_display_var.set("玩家：未创建")
            self.save_name_var.set("存档：未创建")
            self.rank_var.set("暂无记录")
        self.restart_game()
        self.status_var.set(f"已删除玩家：{deleted}")

    def start_game(self) -> None:
        if not self.active_player:
            self.status_var.set("请先新建玩家")
            return
        if self.awaiting_continue and not self.game_over:
            self.continue_level()
            return
        if self.running:
            return
        if self.game_over:
            self.restart_game()
            return
        self.session_player = self.active_player
        self.session_best_entry = None
        self.running = True
        self.status_var.set(f"游戏进行中 {self.difficulty_var.get()}")
        self.sound.play_pattern("start")
        self.sound.start_bgm(MUSIC_FILE)
        self.continue_button.config(state="disabled")
        self._save_progress()
        self._draw_scene()
        self._schedule_tick()
        self._schedule_spawn()

    def continue_level(self) -> None:
        if not self.awaiting_continue or self.game_over:
            return
        self.session_player = self.active_player
        self.session_best_entry = None
        self.awaiting_continue = False
        self.running = True
        self.status_var.set(f"游戏进行中 第 {self.level} 关")
        self.sound.start_bgm(MUSIC_FILE)
        self.continue_button.config(state="disabled")
        self._save_progress()
        self._draw_scene()
        self._schedule_tick()
        self._schedule_spawn()

    def load_progress(self) -> None:
        if not self.active_player:
            self.status_var.set("请先新建玩家")
            return
        progress = self.save_data["players"][self.active_player].get("progress")
        if not progress:
            progress = self._default_progress()
            self.save_data["players"][self.active_player]["progress"] = progress
            self._write_save_data()

        self._cancel_timers()
        self.sound.stop_bgm()
        self.score = int(progress.get("score", 0))
        self.level = int(progress.get("level", 1))
        self.level_score = int(progress.get("level_score", 0))
        self.level_target = int(progress.get("level_target", LEVEL_TARGET))
        self.lives = int(progress.get("lives", INITIAL_LIVES))
        self.coins = int(self.save_data["players"][self.active_player].get("coins", 0))
        self.inventory = dict(self.save_data["players"][self.active_player].get("inventory", {}))

        self.running = False
        self.game_over = False
        self.awaiting_continue = True
        self.session_player = self.active_player
        self.session_best_entry = None
        self.result_saved = False
        self.balloons = []
        self.explosions = []
        self.smokes = []
        self.projectiles = []
        self.pending_shots = []
        self.cannon_angle = -math.pi / 2
        self.cannon_target_angle = -math.pi / 2
        self.cannon_recoil = 0.0
        self.muzzle_flash_frames = 0
        self.wheel_spin = 0.0

        self.score_var.set(f"分数 {self.score}")
        self.level_var.set(f"关卡 {self.level}")
        self.coin_var.set(f"金币 {self.coins}")
        self.lives_var.set(f"失误余量 {self.lives}")
        self.status_var.set(f"已读取 {self.active_player} 的存档，点击继续恢复游戏")
        self.continue_button.config(state="normal")
        self._refresh_leaderboard()
        self._draw_scene()
        self._draw_message(f"继续第 {self.level} 关", f"{self.active_player} 当前金币 {self.coins}，本关进度 {self.level_score}/{self.level_target}")

    def restart_game(self) -> None:
        self._cancel_timers()
        self.sound.stop_bgm()
        self.score = 0
        self.level = 1
        self.level_score = 0
        self.level_target = LEVEL_TARGET
        self.lives = INITIAL_LIVES
        self.running = False
        self.game_over = False
        self.awaiting_continue = False
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

        self.score_var.set("分数 0")
        self.level_var.set("关卡 1")
        self.coin_var.set(f"金币 {self.coins}")
        self.lives_var.set(f"失误余量 {self.lives}")
        self.status_var.set("请选择玩家后开始")
        if self.active_player:
            self._clear_progress()
            self._save_player_profile()
            self._write_save_data()
        self.continue_button.config(state="disabled")
        self._draw_scene()
        self._draw_message("打字打气球", "点击开始后直接按字母键开炮")

    def hit_letter(self, letter: str) -> None:
        if not self.running or self.game_over:
            return
        if len(self.pending_shots) + len(self.projectiles) >= MAX_BURST_SHOTS:
            self.status_var.set(f"连发队列已满，最多 {MAX_BURST_SHOTS} 发")
            return
        target = next((balloon for balloon in self.balloons if balloon["letter"] == letter and not balloon["targeted"]), None)
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
            self._refresh_leaderboard()
            if self.lives <= 0:
                self._end_game("失误次数用完了")
                return
            self._save_progress()
            self._draw_scene()
            return

        target["targeted"] = True
        self.pending_shots.append({"target_id": target["id"], "color": target["color"], "letter": letter})
        if len(self.pending_shots) == 1:
            self.cannon_target_angle = math.atan2(target["y"] - self.pivot_y, target["x"] - self.pivot_x)
        self.status_var.set(f"已加入连发队列 {len(self.pending_shots)}/{MAX_BURST_SHOTS}")
        self._save_progress()
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
            self.balloons.append({"id": self.next_balloon_id, "x": x, "y": y, "speed": speed, "letter": random.choice(choices or list(string.ascii_lowercase)), "color": random.choice(BALLOON_COLORS), "targeted": False})
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

        while self.pending_shots and self.pending_shots[0]["target_id"] not in balloon_map:
            self.pending_shots.pop(0)

        if self.pending_shots:
            shot = self.pending_shots[0]
            target = balloon_map.get(shot["target_id"])
            if target is not None:
                self.cannon_target_angle = math.atan2(target["y"] - self.pivot_y, target["x"] - self.pivot_x)
            if target is not None and self._angle_diff(self.cannon_target_angle, self.cannon_angle) < 0.05:
                muzzle_x, muzzle_y = self._get_cannon_muzzle()
                self.projectiles.append({"x": muzzle_x, "y": muzzle_y, "target_id": target["id"], "color": shot["color"], "letter": shot["letter"]})
                self.cannon_recoil = 16.0
                self.muzzle_flash_frames = 5
                self.wheel_spin += 0.9
                self.sound.play_effect_now(FIRE_SOUND_FILE, fallback_name="start")
                self.status_var.set(f"炮弹已发射，目标 {shot['letter'].upper()}，剩余队列 {len(self.pending_shots) - 1}")
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
                self.sound.play_effect_now(EXPLOSION_SOUND_FILE, fallback_name="lose")
                self.score += 1
                self.level_score += 1
                self.score_var.set(f"分数 {self.score}")
                self.status_var.set(f"炮弹命中 {projectile['letter'].upper()} 气球")
                self._refresh_leaderboard()
                if self.level_score >= self.level_target:
                    self._advance_level()
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

        self.explosions = [self._advance_frame(item) for item in self.explosions if item["frame"] < EXPLOSION_DURATION]
        self.smokes = [self._advance_frame(item) for item in self.smokes if item["frame"] < SMOKE_DURATION]

        if escaped:
            self.lives -= escaped
            self.lives_var.set(f"失误余量 {self.lives}")
            self.status_var.set(f"有 {escaped} 个气球飞走了")
            self._refresh_leaderboard()
            if self.lives <= 0:
                self._end_game("气球飞走太多，游戏结束")
                return

        self._save_progress()
        self._draw_scene()
        self._schedule_tick()

    def _advance_frame(self, item: dict) -> dict:
        item["frame"] += 1
        return item

    def _update_cannon_motion(self) -> None:
        diff = self._normalize_angle(self.cannon_target_angle - self.cannon_angle)
        turn_speed = BURST_TURN_SPEED if self.pending_shots else CANNON_TURN_SPEED
        if abs(diff) > turn_speed:
            self.cannon_angle += turn_speed if diff > 0 else -turn_speed
        else:
            self.cannon_angle = self.cannon_target_angle
        self.cannon_angle = self._normalize_angle(self.cannon_angle)
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
        self.awaiting_continue = False
        self._cancel_timers()
        self.sound.stop_bgm()
        self.continue_button.config(state="disabled")
        self.status_var.set("你已通关")
        self.sound.play_pattern("win")
        self._record_result()
        self._draw_scene()
        self._draw_message("挑战成功", "你已经完成 100 关")

    def _advance_level(self) -> None:
        if self.level >= MAX_LEVEL:
            self.status_var.set("已完成第 100 关")
            self._win_game()
            return
        self.coins += 1
        self.level += 1
        self.level_score = 0
        self.level_target = LEVEL_TARGET
        self.lives = min(MAX_MISTAKES, self.lives + 1)
        self.level_var.set(f"关卡 {self.level}")
        self.coin_var.set(f"金币 {self.coins}")
        self.lives_var.set(f"失误余量 {self.lives}")
        self.status_var.set(f"已通过上一关，点击继续进入第 {self.level} 关")
        self.balloons = []
        self.explosions = []
        self.smokes = []
        self.projectiles = []
        self.pending_shots = []
        self.cannon_target_angle = self.cannon_angle
        self.running = False
        self.awaiting_continue = True
        self._save_progress()
        self.continue_button.config(state="normal")
        self._cancel_timers()
        self._draw_scene()
        self._draw_message(f"第 {self.level} 关", f"奖励 1 金币，点击继续开始，本关需命中 {self.level_target} 个字母")

    def _end_game(self, reason: str) -> None:
        self.running = False
        self.game_over = True
        self.awaiting_continue = False
        self._cancel_timers()
        self.sound.stop_bgm()
        self.continue_button.config(state="disabled")
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
        self.canvas.create_text(WINDOW_WIDTH - 180, WINDOW_HEIGHT - 34, text=f"第 {self.level} 关 {self.level_score}/{self.level_target}", fill="#166534", font=("Microsoft YaHei UI", 12, "bold"))
        self.canvas.create_text(WINDOW_WIDTH - 50, WINDOW_HEIGHT - 34, text=f"总分 {self.score}", fill="#166534", font=("Microsoft YaHei UI", 12, "bold"))

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
        barrel_length = 78
        barrel_half_width = 15

        rear_left = (pivot_x - perp_x * barrel_half_width, pivot_y - perp_y * barrel_half_width)
        rear_right = (pivot_x + perp_x * barrel_half_width, pivot_y + perp_y * barrel_half_width)
        front_center = (pivot_x + dir_x * barrel_length, pivot_y + dir_y * barrel_length)
        front_left = (front_center[0] - perp_x * 13, front_center[1] - perp_y * 13)
        front_right = (front_center[0] + perp_x * 13, front_center[1] + perp_y * 13)

        self.canvas.create_oval(self.cannon_x - 84, self.carriage_y + 26, self.cannon_x + 84, self.carriage_y + 76, fill="#000000", outline="", stipple="gray25")
        self._draw_wheel(self.cannon_x - 54, self.carriage_y + 26, 28)
        self._draw_wheel(self.cannon_x + 54, self.carriage_y + 26, 28)
        self.canvas.create_polygon(self.cannon_x - 46, self.carriage_y + 18, self.cannon_x + 46, self.carriage_y + 18, self.cannon_x + 26, self.carriage_y - 8, self.cannon_x - 26, self.carriage_y - 8, fill="#475569", outline="")
        self.canvas.create_rectangle(self.cannon_x - 28, self.carriage_y - 18, self.cannon_x + 28, self.carriage_y + 10, fill="#64748b", outline="")
        self.canvas.create_oval(self.cannon_x - 44, self.carriage_y - 52, self.cannon_x + 44, self.carriage_y + 6, fill="#475569", outline="")
        self.canvas.create_oval(self.cannon_x - 30, self.carriage_y - 44, self.cannon_x + 30, self.carriage_y - 8, fill="#94a3b8", outline="")
        self.canvas.create_polygon(rear_left[0] + 7, rear_left[1] + 10, rear_right[0] + 7, rear_right[1] + 10, front_right[0] + 7, front_right[1] + 10, front_left[0] + 7, front_left[1] + 10, fill="#0f172a", outline="", stipple="gray50")
        self.canvas.create_polygon(rear_left[0], rear_left[1], rear_right[0], rear_right[1], front_right[0], front_right[1], front_left[0], front_left[1], fill="#334155", outline="")
        self.canvas.create_oval(pivot_x - 18, pivot_y - 18, pivot_x + 18, pivot_y + 18, fill="#334155", outline="")
        self.canvas.create_polygon(rear_left[0] - dir_x * 8 + perp_x * 4, rear_left[1] - dir_y * 8 + perp_y * 4, rear_right[0] - dir_x * 8 + perp_x * 4, rear_right[1] - dir_y * 8 + perp_y * 4, rear_right[0], rear_right[1], rear_left[0], rear_left[1], fill="#94a3b8", outline="")
        self.canvas.create_polygon(front_left[0], front_left[1], front_right[0], front_right[1], front_center[0] + dir_x * 14, front_center[1] + dir_y * 14, fill="#111827", outline="")
        self.canvas.create_oval(pivot_x - 14, pivot_y - 14, pivot_x + 14, pivot_y + 14, fill="#94a3b8", outline="")
        self.canvas.create_oval(pivot_x - 6, pivot_y - 6, pivot_x + 6, pivot_y + 6, fill="#e2e8f0", outline="")
        if self.muzzle_flash_frames > 0:
            scale = 1 + self.muzzle_flash_frames * 0.16
            tip_x = front_center[0] + dir_x * (28 * scale)
            tip_y = front_center[1] + dir_y * (28 * scale)
            side = 18 * scale
            back = 12 * scale
            self.canvas.create_polygon(front_center[0] + perp_x * side, front_center[1] + perp_y * side, tip_x, tip_y, front_center[0] - perp_x * side, front_center[1] - perp_y * side, front_center[0] - dir_x * back, front_center[1] - dir_y * back, fill="#f97316", outline="")
            self.canvas.create_polygon(front_center[0] + perp_x * (side * 0.55), front_center[1] + perp_y * (side * 0.55), front_center[0] + dir_x * (34 * scale), front_center[1] + dir_y * (34 * scale), front_center[0] - perp_x * (side * 0.55), front_center[1] - perp_y * (side * 0.55), front_center[0] - dir_x * (5 * scale), front_center[1] - dir_y * (5 * scale), fill="#fde68a", outline="")

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
            self.canvas.create_oval(projectile["x"] - 8, projectile["y"] - 8, projectile["x"] + 8, projectile["y"] + 8, fill="#111827", outline="#f8fafc", width=1)

    def _get_cannon_pivot(self) -> tuple[float, float]:
        dir_x = math.cos(self.cannon_angle)
        dir_y = math.sin(self.cannon_angle)
        return self.pivot_x - dir_x * self.cannon_recoil, self.pivot_y - dir_y * self.cannon_recoil

    def _get_cannon_muzzle(self) -> tuple[float, float]:
        pivot_x, pivot_y = self._get_cannon_pivot()
        dir_x = math.cos(self.cannon_angle)
        dir_y = math.sin(self.cannon_angle)
        return pivot_x + dir_x * 84, pivot_y + dir_y * 84

    def _draw_explosions(self) -> None:
        for explosion in self.explosions:
            x = explosion["x"]
            y = explosion["y"]
            progress = explosion["frame"] / EXPLOSION_DURATION
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
            base = 16 + progress * 26
            color = "#cbd5e1" if progress < 0.45 else "#94a3b8"
            for dx, dy, scale in [(-18, -8, 0.9), (0, -18, 1.1), (16, -6, 0.8), (-6, 10, 0.7)]:
                radius = base * scale
                x = smoke["x"] + dx * progress
                y = smoke["y"] + dy * progress
                self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=color, outline="", stipple="gray25" if progress < 0.5 else "gray50")

    def _draw_message(self, title: str, subtitle: str) -> None:
        left = 220
        top = 180
        right = WINDOW_WIDTH - 220
        bottom = WINDOW_HEIGHT - 190
        self.canvas.create_rectangle(left, top, right, bottom, fill="#ffffff", outline="#60a5fa", width=3)
        self.canvas.create_text(WINDOW_WIDTH // 2, top + 52, text=title, fill="#1d4ed8", font=("Microsoft YaHei UI", 24, "bold"), width=right - left - 40)
        self.canvas.create_text(WINDOW_WIDTH // 2, top + 106, text=subtitle, fill=TEXT_MAIN, font=("Microsoft YaHei UI", 12), width=right - left - 40)
        self.canvas.create_text(WINDOW_WIDTH // 2, top + 148, text=f"玩家：{self.active_player or '未选择'} | 金币：{self.coins}", fill=TEXT_MUTED, font=("Microsoft YaHei UI", 10), width=right - left - 40)

    def request_exit(self) -> None:
        if self.exit_dialog is not None and self.exit_dialog.winfo_exists():
            self.exit_dialog.lift()
            self.exit_dialog.focus_force()
            return

        dialog = tk.Toplevel(self.root)
        self.exit_dialog = dialog
        dialog.title("退出游戏")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=PANEL_COLOR)
        dialog.geometry("480x200")

        tk.Label(
            dialog,
            text="是否退出当前游戏？",
            bg=PANEL_COLOR,
            fg=TEXT_MAIN,
            font=("Microsoft YaHei UI", 13, "bold"),
            pady=18,
        ).pack()
        tk.Label(
            dialog,
            text="你可以选择保存当前存档后退出，直接退出，或取消继续游戏。",
            bg=PANEL_COLOR,
            fg=TEXT_MUTED,
            font=("Microsoft YaHei UI", 10),
            wraplength=420,
            justify="center",
        ).pack()

        button_row = tk.Frame(dialog, bg=PANEL_COLOR, pady=20)
        button_row.pack(fill="x")

        def close_dialog() -> None:
            if dialog.winfo_exists():
                dialog.grab_release()
                dialog.destroy()
            self.exit_dialog = None

        def save_and_exit() -> None:
            if self.active_player:
                self._save_progress()
                self._write_save_data()
            close_dialog()
            self._force_close()

        def exit_without_save() -> None:
            close_dialog()
            self._force_close()

        def cancel_exit() -> None:
            close_dialog()
            self.root.focus_force()

        tk.Button(button_row, text="保存并退出", command=save_and_exit, width=12, bg=ACCENT, fg="white", activebackground="#1d4ed8", activeforeground="white", relief="flat", bd=0, font=("Microsoft YaHei UI", 10, "bold"), cursor="hand2").pack(side="left", padx=12)
        tk.Button(button_row, text="直接退出", command=exit_without_save, width=12, bg="#475569", fg="white", activebackground="#334155", activeforeground="white", relief="flat", bd=0, font=("Microsoft YaHei UI", 10, "bold"), cursor="hand2").pack(side="left", padx=12)
        tk.Button(button_row, text="取消", command=cancel_exit, width=12, bg="#94a3b8", fg="#0f172a", activebackground="#cbd5e1", activeforeground="#0f172a", relief="flat", bd=0, font=("Microsoft YaHei UI", 10, "bold"), cursor="hand2").pack(side="left", padx=12)

        dialog.protocol("WM_DELETE_WINDOW", cancel_exit)
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"480x200+{x}+{y}")
        dialog.focus_force()

    def _force_close(self) -> None:
        self._cancel_timers()
        self.sound.stop_bgm()
        self.root.destroy()

    def _on_close(self) -> None:
        self.request_exit()


def main() -> None:
    root = tk.Tk()
    BalloonTypingGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
