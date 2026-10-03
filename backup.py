"""Daily backup of data.db into backups/, keeping the newest 14 copies.

Uses SQLite's backup API, so it is safe to run while the bot is writing.
  python backup.py
"""
import sqlite3
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
DB = BASE / "data.db"
DIR = BASE / "backups"
KEEP = 14

if not DB.exists():
    raise SystemExit(f"{DB} not found (the bot has not run yet?)")
DIR.mkdir(parents=True, exist_ok=True)
dest = DIR / f"data-{datetime.now():%Y%m%d-%H%M%S}.db"
tmp = dest.with_suffix(".tmp")
src, dst = sqlite3.connect(DB), sqlite3.connect(tmp)
src.backup(dst)
src.close()
dst.close()
tmp.replace(dest)
for old in sorted(DIR.glob("data-*.db"), reverse=True)[KEEP:]:
    old.unlink()
print("backup ->", dest)
