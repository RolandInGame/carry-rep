"""Publish this bot's slash-command list to discordbotlist.com.

  python post_commands.py [game id]      (default: d4)

Reads from config.txt, in the game's section:
  token     = the Discord bot token (already there)
  dbl_token = the discordbotlist.com token (bot page > Edit > Webhooks / API token)
The command list is fetched from Discord, so it always matches what the bot has registered.
Uses [common] proxy if set.
"""
import configparser
import json
import sys
import urllib.request
from pathlib import Path

GAME = sys.argv[1] if len(sys.argv) > 1 else "d4"
conf = configparser.ConfigParser(inline_comment_prefixes=("#",))
conf.read(Path(__file__).parent / "config.txt", encoding="utf-8")
sec = conf[GAME] if conf.has_section(GAME) else {}
common = conf["common"] if conf.has_section("common") else {}
token = (sec.get("token") or "").strip()
dbl_token = (sec.get("dbl_token") or "").strip()
proxy = (sec.get("proxy") or common.get("proxy") or "").strip()
if not token or not dbl_token:
    sys.exit(f"Fill in token and dbl_token under [{GAME}] in config.txt")

handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy})] if proxy else []
opener = urllib.request.build_opener(*handlers)
UA = "CarryRep (https://github.com/RolandInGame/carry-rep, 1.0)"


def call(method, url, auth, body=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": auth, "User-Agent": UA,
                                          "Content-Type": "application/json"})
    with opener.open(req, timeout=30) as r:
        text = r.read().decode() or "null"
        return r.status, json.loads(text) if text.strip()[:1] in "[{" else text


_, app = call("GET", "https://discord.com/api/v10/applications/@me", f"Bot {token}")
_, cmds = call("GET", f"https://discord.com/api/v10/applications/{app['id']}/commands", f"Bot {token}")
keep = ("name", "description", "type", "options")
payload = [{k: c[k] for k in keep if k in c} for c in cmds]
print(f"{app['name']} ({app['id']}): {len(payload)} commands ->", ", ".join("/" + c["name"] for c in payload))
status, resp = call("POST", f"https://discordbotlist.com/api/v1/bots/{app['id']}/commands", f"Bot {dbl_token}", payload)
print("discordbotlist.com:", status, resp)
