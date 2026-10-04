"""Experiment numbers for all game bots (they share data.db), per game and per server, plus CSV exports.

  python rep_export.py            -> prints the summary, writes servers.csv / boosters.csv / reviews.csv / leads.csv
"""
import csv
import sqlite3
from pathlib import Path

BASE = Path(__file__).parent
con = sqlite3.connect(BASE / "data.db")


def one(sql, *a):
    return con.execute(sql, a).fetchone()[0]


games = [g for (g,) in con.execute(
    "SELECT game FROM boosters UNION SELECT game FROM guilds UNION SELECT game FROM events "
    "WHERE game IS NOT NULL ORDER BY 1")]
for g in games:
    print(f"== {g} ==")
    print("  servers with the bot installed :", one("SELECT COUNT(*) FROM guilds WHERE game=? AND left_at IS NULL", g),
          f"(ever: {one('SELECT COUNT(*) FROM guilds WHERE game=?', g)})")
    print("  registered boosters            :", one("SELECT COUNT(*) FROM boosters WHERE game=?", g))
    print("  reviews                        :", one("SELECT COUNT(*) FROM reviews WHERE game=?", g),
          f"from {one('SELECT COUNT(DISTINCT reviewer_id) FROM reviews WHERE game=?', g)} buyers")
    print("  boosters with >=1 review       :", one("SELECT COUNT(DISTINCT booster_id) FROM reviews WHERE game=?", g))
    print("  boosters reviewed on >=2 servers:",
          one("SELECT COUNT(*) FROM (SELECT booster_id FROM reviews WHERE game=? AND guild_id<>'' "
              "GROUP BY booster_id HAVING COUNT(DISTINCT guild_id)>=2)", g))
    print("  lookups (/rep, panel)          :", one("SELECT COUNT(*) FROM events WHERE game=? AND name='lookup'", g))
    print("  cards shared (/myrep)          :", one("SELECT COUNT(*) FROM events WHERE game=? AND name='myrep'", g))
    print("  card 'Review' clicks           :", one("SELECT COUNT(*) FROM events WHERE game=? AND name='cardbtn_vouch'", g))
    print("  reviews saved via a card       :", one("SELECT COUNT(*) FROM events WHERE game=? AND name='cardbtn_vouch_saved'", g))
    print("  'Get your own card' clickers   :",
          one("SELECT COUNT(DISTINCT user_id) FROM events WHERE game=? AND name='cardbtn_getcard'", g),
          "· registered afterwards:",
          one("SELECT COUNT(DISTINCT c.user_id) FROM events c JOIN events r ON r.user_id=c.user_id AND r.game=c.game "
              "AND r.name='register' AND r.ts>=c.ts WHERE c.game=? AND c.name='cardbtn_getcard'", g))
    print("  rejected reviews               :", dict(con.execute(
        "SELECT name, COUNT(*) FROM events WHERE game=? AND name LIKE 'vouch\\_%' ESCAPE '\\' GROUP BY name",
        (g,)).fetchall()))

print("\n== All games ==")
print("boosters registered in >=2 games:",
      one("SELECT COUNT(*) FROM (SELECT user_id FROM boosters GROUP BY user_id HAVING COUNT(*)>=2)"))

rows = con.execute("""
  SELECT g.game, g.guild_id, g.name, g.member_count, g.joined_at, g.left_at,
    (SELECT COUNT(*) FROM boosters b WHERE b.game=g.game AND b.reg_guild_id=g.guild_id),
    (SELECT COUNT(*) FROM reviews r WHERE r.game=g.game AND r.guild_id=g.guild_id),
    (SELECT COUNT(*) FROM events e WHERE e.game=g.game AND e.guild_id=g.guild_id AND e.name IN ('lookup','myrep')),
    (SELECT COUNT(DISTINCT user_id) FROM events e WHERE e.game=g.game AND e.guild_id=g.guild_id
       AND e.name LIKE 'click%')
  FROM guilds g ORDER BY g.game, g.joined_at""").fetchall()
head = ["game", "guild_id", "name", "members", "joined_at", "left_at", "boosters_registered", "reviews",
        "lookups", "panel_users"]
print("\n== Per server ==")
for r in rows:
    print(f"{r[0]:6} {(r[2] or '')[:30]:30}  members={r[3]}  boosters={r[6]}  reviews={r[7]}  lookups={r[8]}"
          f"  panel_users={r[9]}" + ("  (left)" if r[5] else ""))

# Warm leads: servers where people used the bot through their own (user) install,
# but the bot itself is not installed. Names are unknown there; ask the listed users which server it is.
leads = con.execute("""
  SELECT e.game, e.guild_id, COUNT(*) AS uses, COUNT(DISTINCT e.user_id) AS users,
    SUM(e.name='suggest') AS suggestions, MAX(e.ts) AS last_seen,
    GROUP_CONCAT(DISTINCT b.username) AS boosters
  FROM events e LEFT JOIN boosters b ON b.game=e.game AND b.user_id=e.user_id
  WHERE e.guild_id<>'' AND e.name NOT IN ('guild_join','guild_leave')
    AND NOT EXISTS (SELECT 1 FROM guilds g WHERE g.game=e.game AND g.guild_id=e.guild_id AND g.left_at IS NULL)
  GROUP BY e.game, e.guild_id ORDER BY users DESC, uses DESC""").fetchall()
lead_head = ["game", "guild_id", "uses", "users", "suggestions", "last_seen", "registered_boosters_seen"]
print("\n== Warm leads (used via user install, bot not installed) ==")
for l in leads[:20]:
    print(f"{l[0]:6} {l[1]}  users={l[3]}  uses={l[2]}  suggestions={l[4]}  last={l[5]}  boosters={l[6] or '-'}")
with open(BASE / "leads.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(lead_head); w.writerows(leads)

with open(BASE / "servers.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(head); w.writerows(rows)
for table in ("boosters", "reviews"):
    cur = con.execute(f"SELECT * FROM {table} ORDER BY game")
    with open(BASE / f"{table}.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow([d[0] for d in cur.description]); w.writerows(cur.fetchall())
print("\nwritten: servers.csv, boosters.csv, reviews.csv, leads.csv")
