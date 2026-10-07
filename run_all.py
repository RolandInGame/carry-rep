"""Run every game's bot from one window.

  python run_all.py              # every game listed in "games" in config.txt
  python run_all.py d4 wow       # only these games

Each game still runs as its own process, so one bot crashing or being rate-limited
never touches the others, and each keeps writing its own logs/bot-<game>.log.
This script only starts them, prefixes their output with the game id so one window
stays readable, and restarts a bot that stops. A bot that exits with code 2 has a
configuration problem: it is not restarted, because retrying cannot fix it.

Stop everything with Ctrl+C, or by closing the window.
"""
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

BASE = Path(__file__).parent
CONFIG_PATH = BASE / "config.txt"
RESTART_DELAY = 30  # seconds to wait before restarting a bot that stopped
CONFIG_EXIT_CODE = 2  # bot.py uses this for "fix config.txt first"

# Start each bot in its own process group, so Ctrl+C in this window reaches only this script.
# Otherwise the bots would die from the Ctrl+C first, and be restarted by their own threads
# a moment before the shutdown below runs, leaving stray bots behind.
if os.name == "nt":
    DETACH = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
else:
    DETACH = {"start_new_session": True}


def read_config():
    """Parse config.txt into {section: {key: value}}. Keys before any [section] count as [common]."""
    sections, current = {"common": {}}, "common"
    if not CONFIG_PATH.exists():
        return sections
    for line in CONFIG_PATH.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip().lower()
            sections.setdefault(current, {})
        elif "=" in line:
            key, value = line.split("=", 1)
            sections[current][key.strip().lower()] = value.strip()
    return sections


def games_to_run(conf, from_args):
    """The game ids to start: the command line, else "games" in [common], else every
    game section that has a token filled in."""
    if from_args:
        return from_args
    listed = conf.get("common", {}).get("games", "")
    if listed.strip():
        return [g for g in listed.replace(",", " ").split() if g]
    return [name for name, sec in conf.items() if name != "common" and sec.get("token")]


class Bot(threading.Thread):
    """Keeps one game's bot running and prints its output with a "[game]" prefix."""

    def __init__(self, game, stop_event, width):
        super().__init__(name=game, daemon=True)
        self.game, self.stop_event, self.width = game, stop_event, width
        self.process = None
        self.config_problem = False

    def log(self, text):
        print(f"[{self.game:<{self.width}}] {text}", flush=True)

    def run(self):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        while not self.stop_event.is_set():
            try:
                self.process = subprocess.Popen(
                    [sys.executable, "-u", str(BASE / "bot.py"), self.game],
                    cwd=str(BASE), env=env, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace", bufsize=1, **DETACH)
            except OSError as error:
                self.log(f"could not start: {error}")
                return
            for line in self.process.stdout:
                self.log(line.rstrip())
            code = self.process.wait()
            self.process = None
            if self.stop_event.is_set():
                return
            if code == CONFIG_EXIT_CODE:
                # Restarting cannot fix a missing token: say so once and leave this bot stopped.
                self.config_problem = True
                self.log(f"stopped: fix the [{self.game}] section in config.txt, then run this again.")
                return
            self.log(f"stopped (exit code {code}). Restarting in {RESTART_DELAY} s ...")
            if self.stop_event.wait(RESTART_DELAY):
                return

    def stop(self):
        process = self.process
        if not process:
            return
        try:
            process.terminate()
            process.wait(timeout=10)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass


def main():
    conf = read_config()
    if not CONFIG_PATH.exists():
        print(f"{CONFIG_PATH} not found. Copy config.example.txt to config.txt and fill in the tokens.")
        return CONFIG_EXIT_CODE

    games = games_to_run(conf, [a for a in sys.argv[1:] if not a.startswith("-")])
    if not games:
        print("No bots to run. In config.txt, set e.g. 'games = d4, wow, poe2' under [common], "
              "and give each of those sections a token.")
        return CONFIG_EXIT_CODE

    missing = [g for g in games if not conf.get(g, {}).get("token")]
    if missing:
        print(f"No token for: {', '.join(missing)}. Add a [{missing[0]}] section with a token "
              f"to config.txt, or drop it from 'games'.")
        return CONFIG_EXIT_CODE

    width = max(len(g) for g in games)
    print(f"Starting {len(games)} bot(s): {', '.join(games)} · config={CONFIG_PATH}")
    print("Each bot also writes its own logs\\bot-<game>.log. Press Ctrl+C to stop them all.\n")

    stop_event = threading.Event()

    def shut_down(signum, frame):
        if not stop_event.is_set():
            print("\nStopping ...", flush=True)
        stop_event.set()

    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), shut_down)

    bots = [Bot(game, stop_event, width) for game in games]
    try:
        for bot in bots:
            if stop_event.is_set():
                break
            bot.start()
            stop_event.wait(1)  # stagger the logins so Discord does not see three at once
        while not stop_event.is_set() and any(bot.is_alive() for bot in bots):
            time.sleep(0.5)
    except KeyboardInterrupt:
        shut_down(None, None)
    finally:
        stop_event.set()
        for bot in bots:
            bot.stop()
        for bot in bots:
            bot.join(timeout=15)

    if any(bot.config_problem for bot in bots):
        return CONFIG_EXIT_CODE
    return 0


if __name__ == "__main__":
    sys.exit(main())
