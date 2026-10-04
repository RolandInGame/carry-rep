"""
CarryRep: a cross-server reputation bot for game boosters, running inside Discord.
One bot (one Discord application) per game. All bots run from this folder and share one database,
so the same booster can be looked up per game, and cards also show their ratings in other games.

Boosters opt in with /register. Buyers leave one review per booster with /vouch.
Anyone can look a booster up with /rep. Reviews are stored in one database, so a booster's
reputation follows them to every server where the bot (or their own user install) is present.

Commands
  /register            booster opt-in: services, platform, where to find you (run again to edit)
  /vouch user          review a registered booster: 1-5 star buttons, then an optional comment; again = update
  /rep user            look up a booster (only you see the answer)
  /myrep               post your own reputation card in the channel
  /deletemydata        erase, in every game, your registration and the reviews you received and gave
  /help                short explanation
  /panel [language]    (admins) post a panel with buttons for the same actions
  /stats               (admins) activity on this server

Rules
  - only registered boosters can be reviewed or looked up
  - no self-reviews; one review per buyer per booster; reviewer account must be min_account_days old (config.txt)
  - at most daily_review_limit new reviews per reviewer per 24 h
  - 4-5 star reviews are announced in the channel; 1-3 star reviews are recorded quietly
  - cards quote only 4-5 star comments; every rating counts in the average

Languages: English, French, German, Spanish, Portuguese (each user's Discord language; fallback English).

Configuration: config.txt next to bot.py (see CONFIG_TEMPLATE below): a [common] section with shared
settings and one [<game id>] section per bot with its token. If config.txt does not exist, the first run
creates it with every setting at its default value. All bots share data.db next to bot.py.

Run: python bot.py <game id>      e.g. python bot.py d4   (run_d4.bat does this on Windows)
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import discord
from discord import app_commands

BASE = Path(__file__).parent


CONFIG_PATH = BASE / "config.txt"
CONFIG_TEMPLATE = """\
# CarryRep settings. "key = value" per line. Lines starting with # are comments.
# [common] applies to every bot; a game section can override any of these keys for that bot.

[common]
# Reviewer's Discord account must be at least this many days old (not checked in the test server).
min_account_days = 30

# Maximum new reviews per reviewer per 24 hours (per game).
daily_review_limit = 10

# Link shown at the bottom of reputation cards, e.g. the GitHub repository. Empty = none.
project_url =

# HTTP proxy for reaching Discord, e.g. http://127.0.0.1:7890 (the local HTTP port of your VPN client).
# Empty = connect directly.
proxy =

# One section per game bot. The section name is the game id passed to bot.py / used in run_<id>.bat.
# Built-in ids: d4 (Diablo IV), poe2 (Path of Exile 2), wow (World of Warcraft);
# any other id works with generic wording (set game_name).
[d4]
# Bot token of this game's Discord application (Developer Portal > your app > Bot > Reset Token).
token =
# Display name of the game. Empty = built-in name (Diablo IV for d4).
game_name =
# Test server ID: slash commands appear there instantly; there you can also review yourself and
# min_account_days does not apply (for testing and demos). Empty = none.
guild =
"""


def read_config():
    """Parse config.txt into {section: {key: value}}. Keys before any [section] count as [common].
    Creates config.txt from CONFIG_TEMPLATE if it does not exist."""
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(CONFIG_TEMPLATE, encoding="utf-8")
    sections, current = {"common": {}}, "common"
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
    # Old single-bot config.txt (no sections): its bot keys belong to that one game (default d4).
    if len(sections) == 1:
        common = sections["common"]
        sections[(common.get("game") or "d4").lower()] = {
            k: common.pop(k) for k in ("token", "guild", "game_name") if k in common}
    return sections


CONF_ALL = read_config()
# Game id: first command-line argument (python bot.py d4). Default d4.
GAME = (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "d4").strip().lower()
CONF = {**CONF_ALL.get("common", {}), **CONF_ALL.get(GAME, {})}
BOT_ONLY = ("token", "guild", "game_name")  # never inherited from [common]: each bot has its own


def cfg(key, default=None):
    """Setting for this bot: its game section first, then [common]; default if missing or empty."""
    if key in BOT_ONLY:
        return CONF_ALL.get(GAME, {}).get(key) or default
    return CONF.get(key) or default


DB_PATH = str(BASE / "data.db")
TOKEN = cfg("token")
DEV_GUILD_ID = cfg("guild")
MIN_ACCOUNT_DAYS = int(cfg("min_account_days", "30"))
DAILY_REVIEW_LIMIT = int(cfg("daily_review_limit", "10"))
PROJECT_URL = cfg("project_url", "")
PROXY = cfg("proxy")

# ---------------------------------------------------------------- storage
NOW = "strftime('%Y-%m-%dT%H:%M:%SZ','now')"
# Every row carries the game id, so all game bots can share this one database.
SCHEMA = f"""
CREATE TABLE IF NOT EXISTS boosters (
  game TEXT NOT NULL, user_id TEXT NOT NULL, username TEXT,
  services TEXT NOT NULL, platform TEXT, contact TEXT, note TEXT,
  reg_guild_id TEXT,                         -- server where they first registered ('' = DM / user install)
  created_at TEXT NOT NULL DEFAULT ({NOW}), updated_at TEXT,
  PRIMARY KEY(game, user_id));
CREATE TABLE IF NOT EXISTS reviews (
  id INTEGER PRIMARY KEY, game TEXT NOT NULL,
  reviewer_id TEXT NOT NULL, booster_id TEXT NOT NULL,
  rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5), comment TEXT,
  guild_id TEXT,                             -- server where the review was written
  created_at TEXT NOT NULL DEFAULT ({NOW}), updated_at TEXT,
  UNIQUE(game, reviewer_id, booster_id));
CREATE TABLE IF NOT EXISTS events (           -- for measuring the experiment
  id INTEGER PRIMARY KEY, ts TEXT NOT NULL DEFAULT ({NOW}), game TEXT,
  name TEXT NOT NULL, user_id TEXT, guild_id TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS guilds (           -- servers that installed a game's bot
  game TEXT NOT NULL, guild_id TEXT NOT NULL, name TEXT, member_count INTEGER,
  joined_at TEXT NOT NULL DEFAULT ({NOW}), left_at TEXT,
  PRIMARY KEY(game, guild_id));
"""
# Older single-game databases (no game column) are converted once; their rows become game 'd4'.
OLD_COLUMNS = {
    "boosters": "user_id,username,services,platform,contact,note,reg_guild_id,created_at,updated_at",
    "reviews": "id,reviewer_id,booster_id,rating,comment,guild_id,created_at,updated_at",
    "events": "id,ts,name,user_id,guild_id,detail",
    "guilds": "guild_id,name,member_count,joined_at,left_at",
}


def db():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")  # several bots write to the same file
    return con


def init_db():
    con = db()
    con.isolation_level = None
    con.execute("BEGIN IMMEDIATE")  # only one bot creates or converts the tables at a time
    try:
        old = [tbl for tbl in OLD_COLUMNS
               if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tbl,)).fetchone()
               and "game" not in [r[1] for r in con.execute(f"PRAGMA table_info({tbl})")]]
        for tbl in old:
            con.execute(f"ALTER TABLE {tbl} RENAME TO {tbl}_old")
        for stmt in SCHEMA.split(";"):
            if stmt.strip():
                con.execute(stmt)
        for tbl in old:
            cols = OLD_COLUMNS[tbl]
            con.execute(f"INSERT INTO {tbl}({cols},game) SELECT {cols},'d4' FROM {tbl}_old")
            con.execute(f"DROP TABLE {tbl}_old")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()


init_db()


def log_event(name, user_id=None, guild_id=None, detail=None):
    try:
        with db() as c:
            c.execute("INSERT INTO events(game,name,user_id,guild_id,detail) VALUES(?,?,?,?,?)",
                      (GAME, name, str(user_id) if user_id else None, str(guild_id or ""), detail))
    except Exception as e:  # measurement must never break the user flow
        print("[event] failed:", e)


def get_booster(user_id):
    with db() as c:
        c.row_factory = sqlite3.Row
        return c.execute("SELECT * FROM boosters WHERE game=? AND user_id=?", (GAME, str(user_id))).fetchone()


def register_booster(user_id, username, guild_id, services, platform, contact, note):
    with db() as c:
        c.execute(f"""
          INSERT INTO boosters(game,user_id,username,services,platform,contact,note,reg_guild_id)
          VALUES(?,?,?,?,?,?,?,?)
          ON CONFLICT(game,user_id) DO UPDATE SET updated_at={NOW}, username=excluded.username,
            services=excluded.services, platform=excluded.platform,
            contact=excluded.contact, note=excluded.note""",
                  (GAME, str(user_id), username, services, platform, contact, note, str(guild_id or "")))


def in_test_server(guild_id):
    """True inside this bot's test server (guild in config.txt). There, for testing and demos,
    you may review yourself and the minimum account age does not apply."""
    return bool(DEV_GUILD_ID) and str(guild_id or "") == str(DEV_GUILD_ID)


def review_blocker(reviewer_id, booster_id, reviewer_age_days, guild_id=None):
    """Why this reviewer can't review this booster right now (self | young | not_booster | limit), or None."""
    reviewer_id, booster_id = str(reviewer_id), str(booster_id)
    test = in_test_server(guild_id)
    if reviewer_id == booster_id and not test:
        return "self"
    if reviewer_age_days < MIN_ACCOUNT_DAYS and not test:
        return "young"
    if not get_booster(booster_id):
        return "not_booster"
    with db() as c:
        exists = c.execute("SELECT 1 FROM reviews WHERE game=? AND reviewer_id=? AND booster_id=?",
                           (GAME, reviewer_id, booster_id)).fetchone()
        if not exists:  # updating an existing review never counts against the daily limit
            recent = c.execute("SELECT COUNT(*) FROM reviews WHERE game=? AND reviewer_id=? AND "
                               "created_at >= strftime('%Y-%m-%dT%H:%M:%SZ','now','-1 day')",
                               (GAME, reviewer_id)).fetchone()[0]
            if recent >= DAILY_REVIEW_LIMIT:
                return "limit"
    return None


def add_review(reviewer_id, booster_id, rating, comment, guild_id, reviewer_age_days):
    """Returns 'saved' | 'updated' or an error key: self | not_booster | young | limit | rating."""
    reviewer_id, booster_id = str(reviewer_id), str(booster_id)
    if not 1 <= int(rating) <= 5:
        return "rating"
    blocker = review_blocker(reviewer_id, booster_id, reviewer_age_days, guild_id)
    if blocker:
        return blocker
    with db() as c:
        exists = c.execute("SELECT 1 FROM reviews WHERE game=? AND reviewer_id=? AND booster_id=?",
                           (GAME, reviewer_id, booster_id)).fetchone()
        c.execute(f"""
          INSERT INTO reviews(game,reviewer_id,booster_id,rating,comment,guild_id) VALUES(?,?,?,?,?,?)
          ON CONFLICT(game,reviewer_id,booster_id) DO UPDATE SET updated_at={NOW},
            rating=excluded.rating, comment=excluded.comment, guild_id=excluded.guild_id""",
                  (GAME, reviewer_id, booster_id, int(rating), (comment or "").strip()[:200], str(guild_id or "")))
    return "updated" if exists else "saved"


def card_data(booster_id):
    b = get_booster(booster_id)
    if not b:
        return None
    with db() as c:
        n, avg, servers = c.execute(
            "SELECT COUNT(*), AVG(rating), COUNT(DISTINCT NULLIF(guild_id,'')) FROM reviews "
            "WHERE game=? AND booster_id=?", (GAME, str(booster_id))).fetchone()
        recent = c.execute(
            "SELECT reviewer_id, rating, comment, COALESCE(updated_at, created_at) AS ts FROM reviews "
            "WHERE game=? AND booster_id=? AND rating>=4 AND comment<>'' ORDER BY ts DESC LIMIT 3",
            (GAME, str(booster_id))).fetchall()
        other = c.execute(  # the same booster's ratings in the other games' bots
            "SELECT game, COUNT(*), AVG(rating) FROM reviews WHERE game<>? AND booster_id=? "
            "GROUP BY game ORDER BY COUNT(*) DESC", (GAME, str(booster_id))).fetchall()
    return {"booster": b, "n": n, "avg": avg, "servers": servers, "recent": recent, "other": other}


def delete_user(user_id):
    """Erase everything tied to this Discord user, in every game. Returns number of rows removed."""
    u = str(user_id)
    with db() as c:
        n = c.execute("DELETE FROM boosters WHERE user_id=?", (u,)).rowcount
        n += c.execute("DELETE FROM reviews WHERE booster_id=? OR reviewer_id=?", (u, u)).rowcount
        c.execute("DELETE FROM events WHERE user_id=?", (u,))
    return n


# ---------------------------------------------------------------- texts
# Discord limits: modal title / field label <= 45 chars, placeholder <= 100, button label <= 80.
LANGS = {"en": "English", "fr": "Français", "de": "Deutsch", "es": "Español", "pt": "Português"}
DEFAULT_LANG = "en"

# Per-game wording: display name, examples of services, and an example of a finished job.
GAMES = {
    "d4": {
        "name": "Diablo IV",
        "services": {"en": "Pit pushes, T12 unlock, Uber bosses, leveling 1–70…",
                     "fr": "Push Fosse, déblocage T12, boss Uber, leveling 1–70…",
                     "de": "Grube-Push, T12-Freischaltung, Uber-Bosse, Leveling 1–70…",
                     "es": "Push de Foso, desbloqueo T12, jefes Uber, subir 1–70…",
                     "pt": "Push de Fosso, desbloqueio T12, chefes Uber, upar 1–70…"},
        "done": {"en": "Pit 100 push", "fr": "push Fosse 100", "de": "Grube 100 Push",
                 "es": "push Foso 100", "pt": "push Fosso 100"}},
    "poe2": {
        "name": "Path of Exile 2",
        "services": {"en": "Campaign, Atlas/maps, pinnacle bosses, leveling…",
                     "fr": "Campagne, Atlas/cartes, boss pinnacle, leveling…",
                     "de": "Kampagne, Atlas/Karten, Pinnacle-Bosse, Leveling…",
                     "es": "Campaña, Atlas/mapas, jefes pinnacle, subir de nivel…",
                     "pt": "Campanha, Atlas/mapas, chefes pinnacle, upar…"},
        "done": {"en": "campaign carry", "fr": "campagne complète", "de": "Kampagne komplett",
                 "es": "campaña completa", "pt": "campanha completa"}},
    "wow": {
        "name": "World of Warcraft",
        "services": {"en": "Mythic+ keys, raids, leveling, PvP rating…",
                     "fr": "Clés Mythique+, raids, leveling, cote JcJ…",
                     "de": "Mythisch+-Schlüssel, Raids, Leveling, PvP-Wertung…",
                     "es": "Llaves Míticas+, bandas, subir de nivel, índice JcJ…",
                     "pt": "Chaves Míticas+, raides, upar, índice JxJ…"},
        "done": {"en": "+10 key", "fr": "clé +10", "de": "+10-Schlüssel", "es": "llave +10", "pt": "chave +10"}},
    "_generic": {
        "name": "",
        "services": {"en": "Leveling, dungeons, raids, bosses, achievements…",
                     "fr": "Leveling, donjons, raids, boss, succès…",
                     "de": "Leveling, Dungeons, Raids, Bosse, Erfolge…",
                     "es": "Subir de nivel, mazmorras, bandas, jefes, logros…",
                     "pt": "Upar, masmorras, raides, chefes, conquistas…"},
        "done": {"en": "dungeon carry", "fr": "passage de donjon", "de": "Dungeon-Carry",
                 "es": "mazmorra completada", "pt": "masmorra concluída"}},
}
GAME_CFG = GAMES.get(GAME, GAMES["_generic"])
GAME_NAME = cfg("game_name") or GAME_CFG["name"] or GAME.upper()


def game_display(game_id):
    """Display name of any game id: its section's game_name, the built-in name, or the id itself."""
    return (CONF_ALL.get(game_id, {}).get("game_name") or GAMES.get(game_id, {}).get("name")
            or game_id.upper())

T = {
    "panel_title": {
        "en": "{game} booster reputation", "fr": "Réputation des boosters {game}",
        "de": "{game} Booster-Bewertungen", "es": "Reputación de boosters de {game}",
        "pt": "Reputação de boosters de {game}"},
    "panel_text": {
        "en": "Vouches that follow boosters from server to server.\n"
              "• **Boosters:** register once, collect reviews everywhere.\n"
              "• **Buyers:** check a booster before you pay, and leave a review after.\n\n"
              "*One review per buyer. We store your Discord ID, name and what you enter here. "
              "“Delete my data” erases everything.*",
        "fr": "Des avis qui suivent les boosters de serveur en serveur.\n"
              "• **Boosters :** inscris-toi une fois, récolte des avis partout.\n"
              "• **Acheteurs :** vérifie un booster avant de payer, laisse un avis après.\n\n"
              "*Un avis par acheteur. On enregistre ton ID Discord, ton pseudo et ce que tu saisis ici. "
              "« Supprimer mes données » efface tout.*",
        "de": "Bewertungen, die Boostern von Server zu Server folgen.\n"
              "• **Booster:** einmal registrieren, überall Bewertungen sammeln.\n"
              "• **Käufer:** Booster vor dem Bezahlen prüfen, danach bewerten.\n\n"
              "*Eine Bewertung pro Käufer. Gespeichert werden deine Discord-ID, dein Name und deine Eingaben. "
              "„Meine Daten löschen“ entfernt alles.*",
        "es": "Valoraciones que acompañan a los boosters de servidor en servidor.\n"
              "• **Boosters:** regístrate una vez y recibe valoraciones en todas partes.\n"
              "• **Compradores:** revisa a un booster antes de pagar y valóralo después.\n\n"
              "*Una valoración por comprador. Guardamos tu ID de Discord, tu nombre y lo que escribas aquí. "
              "«Borrar mis datos» lo elimina todo.*",
        "pt": "Avaliações que acompanham os boosters de servidor em servidor.\n"
              "• **Boosters:** registre-se uma vez e receba avaliações em todo lugar.\n"
              "• **Compradores:** confira um booster antes de pagar e avalie depois.\n\n"
              "*Uma avaliação por comprador. Guardamos seu ID do Discord, seu nome e o que você digitar aqui. "
              "“Apagar meus dados” apaga tudo.*"},
    "btn_register": {"en": "I'm a booster", "fr": "Je suis booster", "de": "Ich bin Booster",
                     "es": "Soy booster", "pt": "Sou booster"},
    "btn_vouch": {"en": "Review a booster", "fr": "Noter un booster", "de": "Booster bewerten",
                  "es": "Valorar a un booster", "pt": "Avaliar um booster"},
    "btn_lookup": {"en": "Check a booster", "fr": "Vérifier un booster", "de": "Booster prüfen",
                   "es": "Consultar a un booster", "pt": "Consultar um booster"},
    "btn_delete": {"en": "Delete my data", "fr": "Supprimer mes données", "de": "Meine Daten löschen",
                   "es": "Borrar mis datos", "pt": "Apagar meus dados"},
    "pick_vouch": {"en": "Which booster do you want to review?", "fr": "Quel booster veux-tu noter ?",
                   "de": "Welchen Booster möchtest du bewerten?", "es": "¿A qué booster quieres valorar?",
                   "pt": "Qual booster você quer avaliar?"},
    "pick_lookup": {"en": "Which booster do you want to check?", "fr": "Quel booster veux-tu vérifier ?",
                    "de": "Welchen Booster möchtest du prüfen?", "es": "¿A qué booster quieres consultar?",
                    "pt": "Qual booster você quer consultar?"},
    "pick_ph": {"en": "Choose a member", "fr": "Choisis un membre", "de": "Mitglied wählen",
                "es": "Elige un miembro", "pt": "Escolha um membro"},
    "reg_title": {"en": "Booster registration", "fr": "Inscription booster", "de": "Booster-Registrierung",
                  "es": "Registro de booster", "pt": "Registro de booster"},
    "reg_done": {"en": "You're registered ✅ Buyers can now review you with `/vouch` and check you with `/rep`. "
                       "Show your card anywhere with `/myrep`.",
                 "fr": "Tu es inscrit ✅ Les acheteurs peuvent te noter avec `/vouch` et te vérifier avec `/rep`. "
                       "Montre ta carte partout avec `/myrep`.",
                 "de": "Du bist registriert ✅ Käufer können dich mit `/vouch` bewerten und mit `/rep` prüfen. "
                       "Zeig deine Karte überall mit `/myrep`.",
                 "es": "Ya estás registrado ✅ Los compradores pueden valorarte con `/vouch` y consultarte con `/rep`. "
                       "Muestra tu tarjeta en cualquier sitio con `/myrep`.",
                 "pt": "Você está registrado ✅ Compradores podem te avaliar com `/vouch` e te consultar com `/rep`. "
                       "Mostre seu cartão em qualquer lugar com `/myrep`."},
    "vouch_title": {"en": "Review {name}", "fr": "Noter {name}", "de": "{name} bewerten",
                    "es": "Valorar a {name}", "pt": "Avaliar {name}"},
    "pick_stars": {"en": "How many stars for {booster}?", "fr": "Combien d'étoiles pour {booster} ?",
                   "de": "Wie viele Sterne für {booster}?", "es": "¿Cuántas estrellas para {booster}?",
                   "pt": "Quantas estrelas para {booster}?"},
    "f_comment": {"en": ("Comment (optional)", "What did they do? e.g. {done}, fast and friendly"),
                  "fr": ("Commentaire (facultatif)", "Qu'a-t-il fait ? ex : {done}, rapide et sympa"),
                  "de": ("Kommentar (optional)", "Was wurde gemacht? z. B. {done}, schnell und nett"),
                  "es": ("Comentario (opcional)", "¿Qué hizo? ej.: {done}, rápido y amable"),
                  "pt": ("Comentário (opcional)", "O que foi feito? ex.: {done}, rápido e gentil")},
    "saved_public": {"en": "{stars} {reviewer} vouched for {booster}", "fr": "{stars} {reviewer} recommande {booster}",
                     "de": "{stars} {reviewer} empfiehlt {booster}", "es": "{stars} {reviewer} recomienda a {booster}",
                     "pt": "{stars} {reviewer} recomenda {booster}"},
    "saved": {"en": "Thanks, your review of {booster} is saved. Sending another one later updates it.",
              "fr": "Merci, ton avis sur {booster} est enregistré. En renvoyer un plus tard le met à jour.",
              "de": "Danke, deine Bewertung für {booster} ist gespeichert. Eine neue ersetzt sie später.",
              "es": "Gracias, tu valoración de {booster} se ha guardado. Si envías otra, se actualiza.",
              "pt": "Obrigado, sua avaliação de {booster} foi salva. Enviar outra depois a atualiza."},
    "err_self": {"en": "You can't review yourself.", "fr": "Tu ne peux pas te noter toi-même.",
                 "de": "Du kannst dich nicht selbst bewerten.", "es": "No puedes valorarte a ti mismo.",
                 "pt": "Você não pode se avaliar."},
    "err_not_booster": {"en": "{booster} isn't registered as a booster yet. They can join with `/register`.",
                        "fr": "{booster} n'est pas encore inscrit comme booster. Il peut le faire avec `/register`.",
                        "de": "{booster} ist noch nicht als Booster registriert. Das geht mit `/register`.",
                        "es": "{booster} aún no está registrado como booster. Puede hacerlo con `/register`.",
                        "pt": "{booster} ainda não está registrado como booster. Pode fazer isso com `/register`."},
    "err_young": {"en": "Your Discord account must be at least {days} days old to leave reviews.",
                  "fr": "Ton compte Discord doit avoir au moins {days} jours pour laisser des avis.",
                  "de": "Dein Discord-Konto muss mindestens {days} Tage alt sein, um zu bewerten.",
                  "es": "Tu cuenta de Discord debe tener al menos {days} días para dejar valoraciones.",
                  "pt": "Sua conta do Discord precisa ter pelo menos {days} dias para avaliar."},
    "err_limit": {"en": "You've reached today's review limit. Try again tomorrow.",
                  "fr": "Tu as atteint la limite d'avis pour aujourd'hui. Réessaie demain.",
                  "de": "Du hast das heutige Bewertungslimit erreicht. Versuch es morgen wieder.",
                  "es": "Has alcanzado el límite de valoraciones de hoy. Inténtalo mañana.",
                  "pt": "Você atingiu o limite de avaliações de hoje. Tente amanhã."},
    "err_rating": {"en": "The rating must be a number from 1 to 5.", "fr": "La note doit être un chiffre de 1 à 5.",
                   "de": "Die Bewertung muss eine Zahl von 1 bis 5 sein.",
                   "es": "La puntuación debe ser un número del 1 al 5.", "pt": "A nota deve ser um número de 1 a 5."},
    "not_registered_self": {"en": "You're not registered as a booster yet. Use `/register`.",
                            "fr": "Tu n'es pas encore inscrit comme booster. Utilise `/register`.",
                            "de": "Du bist noch nicht als Booster registriert. Nutze `/register`.",
                            "es": "Aún no estás registrado como booster. Usa `/register`.",
                            "pt": "Você ainda não está registrado como booster. Use `/register`."},
    "card_title": {"en": "{name} · {game} booster", "fr": "{name} · booster {game}",
                   "de": "{name} · {game} Booster", "es": "{name} · booster de {game}",
                   "pt": "{name} · booster de {game}"},
    "card_rating": {"en": "Rating", "fr": "Note", "de": "Bewertung", "es": "Puntuación", "pt": "Nota"},
    "card_reviews": {"en": "{avg} / 5 · {n} review(s)", "fr": "{avg} / 5 · {n} avis", "de": "{avg} / 5 · {n} Bewertung(en)",
                     "es": "{avg} / 5 · {n} valoración(es)", "pt": "{avg} / 5 · {n} avaliação(ões)"},
    "card_none": {"en": "No reviews yet", "fr": "Pas encore d'avis", "de": "Noch keine Bewertungen",
                  "es": "Aún sin valoraciones", "pt": "Ainda sem avaliações"},
    "card_servers": {"en": "Reviewed on", "fr": "Noté sur", "de": "Bewertet auf", "es": "Valorado en",
                     "pt": "Avaliado em"},
    "card_servers_v": {"en": "{n} server(s)", "fr": "{n} serveur(s)", "de": "{n} Server", "es": "{n} servidor(es)",
                       "pt": "{n} servidor(es)"},
    "card_since": {"en": "Registered", "fr": "Inscrit le", "de": "Registriert", "es": "Registrado",
                   "pt": "Registrado"},
    "card_services": {"en": "Services", "fr": "Services", "de": "Leistungen", "es": "Servicios", "pt": "Serviços"},
    "card_platform": {"en": "Platform / region", "fr": "Plateforme / région", "de": "Plattform / Region",
                      "es": "Plataforma / región", "pt": "Plataforma / região"},
    "card_contact": {"en": "Where to find them", "fr": "Où le trouver", "de": "Wo zu finden",
                     "es": "Dónde encontrarlo", "pt": "Onde encontrar"},
    "card_other": {"en": "Other games", "fr": "Autres jeux", "de": "Andere Spiele",
                   "es": "Otros juegos", "pt": "Outros jogos"},
    "card_recent": {"en": "Recent vouches", "fr": "Derniers avis", "de": "Neueste Bewertungen",
                    "es": "Valoraciones recientes", "pt": "Avaliações recentes"},
    "card_footer": {"en": "One review per buyer · reviewer accounts ≥ {days} days old",
                    "fr": "Un avis par acheteur · comptes de plus de {days} jours",
                    "de": "Eine Bewertung pro Käufer · Konten ab {days} Tagen",
                    "es": "Una valoración por comprador · cuentas de al menos {days} días",
                    "pt": "Uma avaliação por comprador · contas com pelo menos {days} dias"},
    "confirm_delete": {"en": "This erases, in every game, your booster registration, the reviews you received and the reviews you gave. Continue?",
                       "fr": "Cela efface, dans tous les jeux, ton inscription, les avis reçus et les avis donnés. Continuer ?",
                       "de": "Das löscht in allen Spielen deine Registrierung, erhaltene und abgegebene Bewertungen. Fortfahren?",
                       "es": "Esto borra, en todos los juegos, tu registro, las valoraciones recibidas y las que diste. ¿Continuar?",
                       "pt": "Isso apaga, em todos os jogos, seu registro, as avaliações recebidas e as que você deu. Continuar?"},
    "btn_confirm": {"en": "Yes, delete everything", "fr": "Oui, tout supprimer", "de": "Ja, alles löschen",
                    "es": "Sí, borrar todo", "pt": "Sim, apagar tudo"},
    "deleted": {"en": "Done: {n} record(s) deleted.", "fr": "C'est fait : {n} élément(s) supprimé(s).",
                "de": "Erledigt: {n} Eintrag/Einträge gelöscht.", "es": "Hecho: {n} registro(s) borrado(s).",
                "pt": "Pronto: {n} registro(s) apagado(s)."},
    "nothing": {"en": "No data under your name.", "fr": "Aucune donnée à ton nom.", "de": "Keine Daten unter deinem Namen.",
                "es": "No hay datos a tu nombre.", "pt": "Nenhum dado em seu nome."},
    "posted": {"en": "Panel posted.", "fr": "Panneau publié.", "de": "Panel veröffentlicht.",
               "es": "Panel publicado.", "pt": "Painel publicado."},
    "help": {
        "en": "**Boosters:** `/register` once, then share `/myrep` anywhere.\n"
              "**Buyers:** `/rep @booster` before you pay, `/vouch @booster` after.\n"
              "Reviews follow boosters across every server that uses this bot. `/deletemydata` erases everything.",
        "fr": "**Boosters :** `/register` une fois, puis partage `/myrep` partout.\n"
              "**Acheteurs :** `/rep @booster` avant de payer, `/vouch @booster` après.\n"
              "Les avis suivent les boosters sur tous les serveurs qui utilisent ce bot. `/deletemydata` efface tout.",
        "de": "**Booster:** einmal `/register`, dann `/myrep` überall teilen.\n"
              "**Käufer:** `/rep @booster` vor dem Bezahlen, `/vouch @booster` danach.\n"
              "Bewertungen folgen Boostern auf alle Server mit diesem Bot. `/deletemydata` löscht alles.",
        "es": "**Boosters:** `/register` una vez y luego comparte `/myrep` donde quieras.\n"
              "**Compradores:** `/rep @booster` antes de pagar, `/vouch @booster` después.\n"
              "Las valoraciones siguen a los boosters en todos los servidores que usan este bot. `/deletemydata` lo borra todo.",
        "pt": "**Boosters:** `/register` uma vez e depois compartilhe `/myrep` em qualquer lugar.\n"
              "**Compradores:** `/rep @booster` antes de pagar, `/vouch @booster` depois.\n"
              "As avaliações acompanham os boosters em todos os servidores que usam este bot. `/deletemydata` apaga tudo."},
    "stats": {"en": "**This server**\nBoosters registered here: {reg}\nReviews written here: {rev}\n"
                    "Lookups here: {look}\nPanel clicks: {clicks}",
              "fr": "**Ce serveur**\nBoosters inscrits ici : {reg}\nAvis écrits ici : {rev}\n"
                    "Consultations ici : {look}\nClics sur le panneau : {clicks}",
              "de": "**Dieser Server**\nHier registrierte Booster: {reg}\nHier geschriebene Bewertungen: {rev}\n"
                    "Abfragen hier: {look}\nPanel-Klicks: {clicks}",
              "es": "**Este servidor**\nBoosters registrados aquí: {reg}\nValoraciones escritas aquí: {rev}\n"
                    "Consultas aquí: {look}\nClics en el panel: {clicks}",
              "pt": "**Este servidor**\nBoosters registrados aqui: {reg}\nAvaliações escritas aqui: {rev}\n"
                    "Consultas aqui: {look}\nCliques no painel: {clicks}"},
}

# Registration form: key -> (required, paragraph, max_length, {lang: (label, placeholder)})
REG_FIELDS = {
    "services": (True, True, 300, {  # placeholders come from GAMES
        "en": ("What you offer", GAME_CFG["services"]["en"]),
        "fr": ("Ce que tu proposes", GAME_CFG["services"]["fr"]),
        "de": ("Was du anbietest", GAME_CFG["services"]["de"]),
        "es": ("Qué ofreces", GAME_CFG["services"]["es"]),
        "pt": ("O que você oferece", GAME_CFG["services"]["pt"])}),
    "platform": (False, False, 60, {
        "en": ("Platform / region", "PC · EU"), "fr": ("Plateforme / région", "PC · EU"),
        "de": ("Plattform / Region", "PC · EU"), "es": ("Plataforma / región", "PC · EU"),
        "pt": ("Plataforma / região", "PC · EU")}),
    "contact": (False, False, 100, {
        "en": ("Where buyers can find you", "Servers where you take orders, your shop…"),
        "fr": ("Où les acheteurs te trouvent", "Serveurs où tu prends des commandes, ta boutique…"),
        "de": ("Wo Käufer dich finden", "Server, auf denen du Aufträge annimmst, dein Shop…"),
        "es": ("Dónde te encuentran", "Servidores donde aceptas pedidos, tu tienda…"),
        "pt": ("Onde compradores te acham", "Servidores onde você aceita pedidos, sua loja…")}),
    "note": (False, True, 200, {
        "en": ("Anything else?", "Experience, availability, languages…"),
        "fr": ("Autre chose ?", "Expérience, disponibilités, langues…"),
        "de": ("Sonst noch etwas?", "Erfahrung, Verfügbarkeit, Sprachen…"),
        "es": ("¿Algo más?", "Experiencia, disponibilidad, idiomas…"),
        "pt": ("Mais alguma coisa?", "Experiência, disponibilidade, idiomas…")}),
}


def lang_of(locale) -> str:
    """'fr', 'en-US', 'es-ES', 'es-419', 'pt-BR', 'de' ... -> supported code, else English."""
    code = str(locale or "").split("-")[0].split("_")[0].lower()
    return code if code in LANGS else DEFAULT_LANG


def t(key, lang, **kw):
    return T[key][lang].format(game=GAME_NAME, **kw)


def stars(r):
    return "★" * r + "☆" * (5 - r)


def age_days(user: discord.abc.User):
    return (discord.utils.utcnow() - user.created_at).days


NO_PINGS = discord.AllowedMentions.none()


def card_embed(user: discord.abc.User, lang):
    d = card_data(user.id)
    if not d:
        return None
    b = d["booster"]
    e = discord.Embed(title=t("card_title", lang, name=user.display_name)[:256], color=0xB33A3A)
    e.set_thumbnail(url=user.display_avatar.url)
    rating = (t("card_reviews", lang, avg=f"{d['avg']:.1f}", n=d["n"]) + "\n" + stars(round(d["avg"]))
              if d["n"] else t("card_none", lang))
    e.add_field(name=t("card_rating", lang), value=rating, inline=True)
    e.add_field(name=t("card_servers", lang), value=t("card_servers_v", lang, n=d["servers"]), inline=True)
    e.add_field(name=t("card_since", lang), value=b["created_at"][:10], inline=True)
    e.add_field(name=t("card_services", lang), value=b["services"][:1024], inline=False)
    if b["platform"]:
        e.add_field(name=t("card_platform", lang), value=b["platform"][:1024], inline=True)
    if b["contact"]:
        e.add_field(name=t("card_contact", lang), value=b["contact"][:1024], inline=True)
    if d["recent"]:
        lines = [f"{stars(r)} <@{rid}> · {ts[:10]}\n“{c}”" for rid, r, c, ts in d["recent"]]
        e.add_field(name=t("card_recent", lang), value="\n".join(lines)[:1024], inline=False)
    if d["other"]:
        lines = [f"{game_display(g)}: {avg:.1f} ★ ({n})" for g, n, avg in d["other"]]
        e.add_field(name=t("card_other", lang), value="\n".join(lines)[:1024], inline=False)
    footer = t("card_footer", lang, days=MIN_ACCOUNT_DAYS)
    e.set_footer(text=f"{footer} · {PROJECT_URL}" if PROJECT_URL else footer)
    return e


# ---------------------------------------------------------------- shared actions
def error_text(status, lang, target):
    return {"self": t("err_self", lang), "rating": t("err_rating", lang),
            "young": t("err_young", lang, days=MIN_ACCOUNT_DAYS), "limit": t("err_limit", lang),
            "not_booster": t("err_not_booster", lang, booster=target.mention)}.get(status)


async def start_vouch(it: discord.Interaction, target: discord.abc.User, edit=False):
    """Step 1 of a review: check the reviewer may review this booster, then show 1-5 star buttons.
    edit=True replaces the member-picker message (panel flow) instead of sending a new one."""
    lang = lang_of(it.locale)
    blocker = review_blocker(it.user.id, target.id, age_days(it.user), it.guild_id)
    if blocker:
        log_event(f"vouch_{blocker}", it.user.id, it.guild_id, str(target.id))
        content, view = error_text(blocker, lang, target), None
    else:
        content, view = t("pick_stars", lang, booster=target.mention), StarPicker(target)
    if edit:
        await it.response.edit_message(content=content, view=view, allowed_mentions=NO_PINGS)
    elif view:
        await it.response.send_message(content, view=view, ephemeral=True, allowed_mentions=NO_PINGS)
    else:
        await it.response.send_message(content, ephemeral=True, allowed_mentions=NO_PINGS)


async def do_vouch(it: discord.Interaction, target: discord.abc.User, rating, comment):
    """Step 3 of a review: save it and announce it (4-5 stars) or confirm quietly (1-3 stars)."""
    lang = lang_of(it.locale)
    status = add_review(it.user.id, target.id, rating, comment, it.guild_id, age_days(it.user))
    log_event("vouch" if status in ("saved", "updated") else f"vouch_{status}", it.user.id, it.guild_id,
              str(target.id))
    if error_text(status, lang, target):
        return await it.response.send_message(error_text(status, lang, target), ephemeral=True,
                                              allowed_mentions=NO_PINGS)
    if rating >= 4:  # good reviews are announced in the channel, low ones are recorded quietly
        msg = t("saved_public", lang, stars=stars(rating), reviewer=it.user.mention, booster=target.mention)
        comment = (comment or "").strip()[:200]
        if comment:
            msg += f"\n> {comment}"
        await it.response.send_message(msg, allowed_mentions=NO_PINGS)
    else:
        await it.response.send_message(t("saved", lang, booster=target.mention), ephemeral=True,
                                       allowed_mentions=NO_PINGS)


async def do_lookup(it: discord.Interaction, target: discord.abc.User, public=False):
    lang = lang_of(it.locale)
    log_event("myrep" if public else "lookup", it.user.id, it.guild_id, str(target.id))
    e = card_embed(target, lang)
    if not e:
        key = "not_registered_self" if target.id == it.user.id else "err_not_booster"
        return await it.response.send_message(t(key, lang, booster=target.mention), ephemeral=True,
                                              allowed_mentions=NO_PINGS)
    await it.response.send_message(embed=e, ephemeral=not public, allowed_mentions=NO_PINGS)


class RegisterForm(discord.ui.Modal):
    def __init__(self, lang, current=None):
        super().__init__(title=t("reg_title", lang))
        self.inputs = {}
        for key, (required, paragraph, max_len, texts) in REG_FIELDS.items():
            label, placeholder = texts[lang]
            box = discord.ui.TextInput(
                label=label, placeholder=placeholder, required=required, max_length=max_len,
                default=(current[key] if current and current[key] else None),
                style=discord.TextStyle.paragraph if paragraph else discord.TextStyle.short)
            self.inputs[key] = box
            self.add_item(box)

    async def on_submit(self, it: discord.Interaction):
        v = {k: box.value.strip() for k, box in self.inputs.items()}
        register_booster(it.user.id, str(it.user), it.guild_id, v["services"], v["platform"], v["contact"], v["note"])
        log_event("register", it.user.id, it.guild_id)
        await it.response.send_message(t("reg_done", lang_of(it.locale)), ephemeral=True)


class StarPicker(discord.ui.View):
    """Step 2 of a review: five grey buttons "1 ★" ... "5 ★". A click opens the comment form."""

    def __init__(self, target: discord.abc.User):
        super().__init__(timeout=300)
        self.target = target
        for n in range(1, 6):
            button = discord.ui.Button(label=f"{n} ★", row=0, style=discord.ButtonStyle.secondary)
            button.callback = self.make_callback(n)
            self.add_item(button)

    def make_callback(self, n):
        async def callback(it: discord.Interaction):
            await it.response.send_modal(VouchForm(self.target, lang_of(it.locale), n))
        return callback


class VouchForm(discord.ui.Modal):
    """Optional comment for a review whose star rating was already chosen."""

    def __init__(self, target: discord.abc.User, lang, rating):
        title = f"{stars(rating)} · " + t("vouch_title", lang, name=target.display_name)
        super().__init__(title=title[:45])
        self.target, self.rating = target, rating
        label, ph = T["f_comment"][lang]
        ph = ph.format(done=GAME_CFG["done"][lang])
        self.comment = discord.ui.TextInput(label=label, placeholder=ph, required=False, max_length=200,
                                            style=discord.TextStyle.paragraph)
        self.add_item(self.comment)

    async def on_submit(self, it: discord.Interaction):
        await do_vouch(it, self.target, self.rating, self.comment.value)


class PickUser(discord.ui.View):
    """Ephemeral member picker used by the panel's 'Review' and 'Check' buttons."""

    def __init__(self, mode, lang):
        super().__init__(timeout=300)
        self.mode = mode
        sel = discord.ui.UserSelect(placeholder=t("pick_ph", lang), min_values=1, max_values=1)
        sel.callback = self.picked
        self.sel = sel
        self.add_item(sel)

    async def picked(self, it: discord.Interaction):
        target = self.sel.values[0]
        if self.mode == "vouch":
            await start_vouch(it, target, edit=True)
        else:
            await do_lookup(it, target)


class ConfirmDelete(discord.ui.View):
    def __init__(self, lang):
        super().__init__(timeout=120)
        self.go.label = t("btn_confirm", lang)

    @discord.ui.button(style=discord.ButtonStyle.danger)
    async def go(self, it: discord.Interaction, _):
        n = delete_user(it.user.id)
        lang = lang_of(it.locale)
        await it.response.edit_message(content=t("deleted", lang, n=n) if n else t("nothing", lang), view=None)


class Panel(discord.ui.View):
    """Persistent view: callbacks are matched by custom_id, so one registered instance serves
    panels posted in any language; `lang` only changes the button labels."""

    def __init__(self, lang=DEFAULT_LANG):
        super().__init__(timeout=None)
        self.register.label = t("btn_register", lang)
        self.vouch.label = t("btn_vouch", lang)
        self.lookup.label = t("btn_lookup", lang)
        self.delete.label = t("btn_delete", lang)

    @discord.ui.button(emoji="⚔️", style=discord.ButtonStyle.success, custom_id="rep:register")
    async def register(self, it: discord.Interaction, _):
        log_event("click_register", it.user.id, it.guild_id)
        await it.response.send_modal(RegisterForm(lang_of(it.locale), get_booster(it.user.id)))

    @discord.ui.button(emoji="⭐", style=discord.ButtonStyle.primary, custom_id="rep:vouch")
    async def vouch(self, it: discord.Interaction, _):
        log_event("click_vouch", it.user.id, it.guild_id)
        lang = lang_of(it.locale)
        await it.response.send_message(t("pick_vouch", lang), view=PickUser("vouch", lang), ephemeral=True)

    @discord.ui.button(emoji="🔎", style=discord.ButtonStyle.primary, custom_id="rep:lookup")
    async def lookup(self, it: discord.Interaction, _):
        log_event("click_lookup", it.user.id, it.guild_id)
        lang = lang_of(it.locale)
        await it.response.send_message(t("pick_lookup", lang), view=PickUser("lookup", lang), ephemeral=True)

    @discord.ui.button(style=discord.ButtonStyle.secondary, custom_id="rep:delete")
    async def delete(self, it: discord.Interaction, _):
        lang = lang_of(it.locale)
        await it.response.send_message(t("confirm_delete", lang), view=ConfirmDelete(lang), ephemeral=True)


# ---------------------------------------------------------------- bot
class Bot(discord.Client):
    def __init__(self):
        # no privileged intents needed; proxy (if set) is used for both the API and the gateway connection
        super().__init__(intents=discord.Intents.default(), proxy=PROXY)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        self.add_view(Panel())
        if DEV_GUILD_ID:
            g = discord.Object(id=int(DEV_GUILD_ID))
            self.tree.copy_global_to(guild=g)
            await self.tree.sync(guild=g)
        await self.tree.sync()

    async def on_ready(self):
        print(f"[bot] logged in as {self.user} · game={GAME_NAME} · in {len(self.guilds)} server(s) · db={DB_PATH}")
        with db() as c:  # servers joined while the bot was offline
            for g in self.guilds:
                c.execute("INSERT OR IGNORE INTO guilds(game,guild_id,name,member_count) VALUES(?,?,?,?)",
                          (GAME, str(g.id), g.name, g.member_count))

    async def on_guild_join(self, g: discord.Guild):
        with db() as c:
            c.execute("""INSERT INTO guilds(game,guild_id,name,member_count) VALUES(?,?,?,?)
                         ON CONFLICT(game,guild_id) DO UPDATE SET name=excluded.name,
                           member_count=excluded.member_count, left_at=NULL""",
                      (GAME, str(g.id), g.name, g.member_count))
        log_event("guild_join", None, g.id, g.name)

    async def on_guild_remove(self, g: discord.Guild):
        with db() as c:
            c.execute(f"UPDATE guilds SET left_at={NOW} WHERE game=? AND guild_id=?", (GAME, str(g.id)))
        log_event("guild_leave", None, g.id, g.name)


bot = Bot()

# Everyday commands work where the bot is installed in the server, and also for people who
# installed the app on their own account (user install), in any server that allows external apps.
everywhere = [app_commands.allowed_installs(guilds=True, users=True),
              app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)]
server_admin = [app_commands.allowed_installs(guilds=True, users=False),
                app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False),
                app_commands.default_permissions(manage_guild=True)]


def apply(decorators):
    def wrap(f):
        for d in reversed(decorators):
            f = d(f)
        return f
    return wrap


@bot.tree.command(name="register", description=f"Register or edit your {GAME_NAME} booster profile"[:100])
@apply(everywhere)
async def register_cmd(it: discord.Interaction):
    log_event("click_register", it.user.id, it.guild_id, "command")
    await it.response.send_modal(RegisterForm(lang_of(it.locale), get_booster(it.user.id)))


@bot.tree.command(name="vouch", description="Review a registered booster: pick 1-5 stars, add a comment")
@app_commands.describe(user="The booster")
@apply(everywhere)
async def vouch_cmd(it: discord.Interaction, user: discord.User):
    await start_vouch(it, user)


@bot.tree.command(name="rep", description="Check a booster's reputation (only you see it)")
@app_commands.describe(user="The booster")
@apply(everywhere)
async def rep_cmd(it: discord.Interaction, user: discord.User):
    await do_lookup(it, user)


@bot.tree.command(name="myrep", description="Post your booster reputation card in this channel")
@apply(everywhere)
async def myrep_cmd(it: discord.Interaction):
    await do_lookup(it, it.user, public=True)


@bot.tree.command(name="deletemydata", description="Erase everything stored about you")
@apply(everywhere)
async def delete_cmd(it: discord.Interaction):
    lang = lang_of(it.locale)
    await it.response.send_message(t("confirm_delete", lang), view=ConfirmDelete(lang), ephemeral=True)


@bot.tree.command(name="help", description="How this reputation bot works")
@apply(everywhere)
async def help_cmd(it: discord.Interaction):
    await it.response.send_message(t("help", lang_of(it.locale)), ephemeral=True)


@bot.tree.command(name="panel", description="Post the reputation panel in this channel")
@app_commands.describe(language="Panel language (default: this server's language)")
@app_commands.choices(language=[app_commands.Choice(name=n, value=c) for c, n in LANGS.items()])
@apply(server_admin)
async def panel_cmd(it: discord.Interaction, language: app_commands.Choice[str] | None = None):
    lang = language.value if language else lang_of(it.guild_locale)
    embed = discord.Embed(title=t("panel_title", lang), description=t("panel_text", lang), color=0xB33A3A)
    await it.channel.send(embed=embed, view=Panel(lang))
    await it.response.send_message(t("posted", lang_of(it.locale)), ephemeral=True)


@bot.tree.command(name="stats", description="Reputation activity on this server")
@apply(server_admin)
async def stats_cmd(it: discord.Interaction):
    g = str(it.guild_id)
    with db() as c:
        reg = c.execute("SELECT COUNT(*) FROM boosters WHERE game=? AND reg_guild_id=?", (GAME, g)).fetchone()[0]
        rev = c.execute("SELECT COUNT(*) FROM reviews WHERE game=? AND guild_id=?", (GAME, g)).fetchone()[0]
        look = c.execute("SELECT COUNT(*) FROM events WHERE game=? AND name IN ('lookup','myrep') AND guild_id=?",
                         (GAME, g)).fetchone()[0]
        clicks = c.execute("SELECT COUNT(DISTINCT user_id) FROM events WHERE game=? AND name LIKE 'click_%' "
                           "AND guild_id=?", (GAME, g)).fetchone()[0]
    await it.response.send_message(t("stats", lang_of(it.locale), reg=reg, rev=rev, look=look, clicks=clicks),
                                   ephemeral=True)


class Tee:
    """Writes to the console and to logs/bot-<game>.log at the same time."""

    def __init__(self, stream, logfile):
        self.stream, self.logfile = stream, logfile

    def write(self, text):
        for out in (self.stream, self.logfile):
            try:
                out.write(text)
                out.flush()
            except Exception:
                pass  # a closed console must not stop the bot
        return len(text)

    def flush(self):
        for out in (self.stream, self.logfile):
            try:
                out.flush()
            except Exception:
                pass

    def isatty(self):
        return False  # no colour codes, so the log file stays readable


if __name__ == "__main__":
    (BASE / "logs").mkdir(exist_ok=True)
    log = open(BASE / "logs" / f"bot-{GAME}.log", "a", encoding="utf-8")
    sys.stdout, sys.stderr = Tee(sys.__stdout__, log), Tee(sys.__stderr__, log)
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] starting · game={GAME_NAME} · config={CONFIG_PATH}"
          + (f" · proxy={PROXY}" if PROXY else ""))
    if DEV_GUILD_ID:
        print(f"test server {DEV_GUILD_ID}: self-reviews allowed and no minimum account age there (testing/demos)")
    if not TOKEN:
        print(f"Fill in the token under [{GAME}] in {CONFIG_PATH} "
              f"(Discord Developer Portal > your app > Bot > Reset Token).")
        sys.exit(2)  # exit code 2 = configuration problem: run_bot.bat stops instead of retrying
    print("connecting to Discord ...")
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print(f"Discord rejected the [{GAME}] token. Copy a fresh one into {CONFIG_PATH} "
              f"(Developer Portal > Bot > Reset Token).")
        sys.exit(2)
