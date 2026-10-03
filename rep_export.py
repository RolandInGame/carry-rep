"""Experiment numbers, per server and overall, plus CSV exports.

  python rep_export.py            -> prints the summary, writes servers.csv / boosters.csv / reviews.csv
"""
import csv
import sqlite3
from pathlib import Path

BASE = Path(__file__).parent
DB = BASE / "data.db"
con = sqlite3.connect(DB)


def one(sql, *a):
    return con.execute(sql, a).fetchone()[0]


print("== Overall ==")
print("servers with the bot installed :", one("SELECT COUNT(*) FROM guilds WHERE left_at IS NULL"),
      f"(ever: {one('SELECT COUNT(*) FROM guilds')})")
print("registered boosters            :", one("SELECT COUNT(*) FROM boosters"))
print("reviews                        :", one("SELECT COUNT(*) FROM reviews"),
      f"from {one('SELECT COUNT(DISTINCT reviewer_id) FROM reviews')} buyers")
print("boosters with >=1 review       :", one("SELECT COUNT(DISTINCT booster_id) FROM reviews"))
print("boosters reviewed on >=2 servers:",
      one("SELECT COUNT(*) FROM (SELECT booster_id FROM reviews WHERE guild_id<>'' "
          "GROUP BY booster_id HAVING COUNT(DISTINCT guild_id)>=2)"))
print("lookups (/rep, panel)          :", one("SELECT COUNT(*) FROM events WHERE name='lookup'"))
print("cards shared (/myrep)          :", one("SELECT COUNT(*) FROM events WHERE name='myrep'"))
print("rejected reviews               :", dict(con.execute(
    "SELECT name, COUNT(*) FROM events WHERE name LIKE 'vouch\\_%' ESCAPE '\\' GROUP BY name").fetchall()))

rows = con.execute("""
  SELECT g.guild_id, g.name, g.member_count, g.joined_at, g.left_at,
    (SELECT COUNT(*) FROM boosters b WHERE b.reg_guild_id=g.guild_id),
    (SELECT COUNT(*) FROM reviews r WHERE r.guild_id=g.guild_id),
    (SELECT COUNT(*) FROM events e WHERE e.guild_id=g.guild_id AND e.name IN ('lookup','myrep')),
    (SELECT COUNT(DISTINCT user_id) FROM events e WHERE e.guild_id=g.guild_id AND e.name LIKE 'click%')
  FROM guilds g ORDER BY g.joined_at""").fetchall()
head = ["guild_id", "name", "members", "joined_at", "left_at", "boosters_registered", "reviews",
        "lookups", "panel_users"]
print("\n== Per server ==")
for r in rows:
    print(f"{r[1][:30]:30}  members={r[2]}  boosters={r[5]}  reviews={r[6]}  lookups={r[7]}  panel_users={r[8]}"
          + ("  (left)" if r[4] else ""))

with open(BASE / "servers.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(head); w.writerows(rows)
for table in ("boosters", "reviews"):
    cur = con.execute(f"SELECT * FROM {table}")
    with open(BASE / f"{table}.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow([d[0] for d in cur.description]); w.writerows(cur.fetchall())
print("\nwritten: servers.csv, boosters.csv, reviews.csv")
