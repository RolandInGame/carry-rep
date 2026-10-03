# CarryRep

A Discord bot that gives game boosters a reputation that follows them from server to server.
One bot serves one game (Diablo IV by default, see [Choosing the game](#choosing-the-game)).

- **Boosters** register once with `/register`, then show their card anywhere with `/myrep`.
- **Buyers** check a booster with `/rep @user` before paying, and leave one review with `/vouch @user` after.
- All servers share one database, so reviews collected in one server show up everywhere.
- Server admins can post a button panel with `/panel` and see activity with `/stats`.

No web page, no payments, no direct messages. Languages: English, French, German, Spanish, Portuguese (follows each user's Discord language).

## Commands

| Command | Who | What it does |
|---|---|---|
| `/register` | boosters | create or edit your booster profile (opt-in) |
| `/vouch user` | buyers | review a registered booster: click 1–5 stars, then add an optional comment; again = update |
| `/rep user` | anyone | see a booster's card (only you see it) |
| `/myrep` | boosters | post your own card in the channel |
| `/deletemydata` | anyone | erase everything stored about you |
| `/help` | anyone | short explanation |
| `/panel [language]` | admins | post a panel with buttons for the above |
| `/stats` | admins | activity on this server |

## Anti-abuse rules

- Only registered boosters can be reviewed or looked up.
- No self-reviews. One review per buyer per booster (a new one replaces the old one).
- Reviewer accounts must be at least 30 days old (`min_account_days` in `config.txt`).
- At most 10 new reviews per reviewer per day (`daily_review_limit` in `config.txt`).
- 4–5 star reviews are announced in the channel; 1–3 star reviews are recorded quietly and only count in the average.
- Cards show how many different servers the reviews came from.

Known limitation: a booster who deletes their data also deletes the reviews they received and can register again from zero.

## Run it

Requires Python 3.10+.

```bash
pip install -r requirements.txt
cp config.example.txt config.txt   # then fill in the token
python bot.py
```

### Configuration

All settings live in `config.txt` next to `bot.py`, one `key = value` per line. `config.example.txt` lists every key with its default value; copy it to `config.txt` (or just run the bot once, which creates it) and fill in the token. `config.txt` is excluded from git.

| Key | Value | Default |
|---|---|---|
| `token` | the bot token | empty (required) |
| `game` | game id, see below | `d4` (Diablo IV) |
| `game_name` | display name of the game | empty = name of the game in `game` |
| `guild` | test server ID: commands appear there instantly | empty |
| `min_account_days` | minimum reviewer account age in days | `30` |
| `daily_review_limit` | new reviews per reviewer per 24 h | `10` |
| `project_url` | link shown on cards, e.g. this repository | empty |

Data is stored in `data.db` next to `bot.py`.

`python rep_export.py` prints the numbers per server and writes CSV exports. `python backup.py` makes a database backup (keeps 14).

### Choosing the game

Set `game` in `config.txt` to pick the game this bot serves. It changes the game name in panels, cards and commands, and the example text in the forms.

| `GAME` | Game |
|---|---|
| `d4` (default) | Diablo IV |
| `poe2` | Path of Exile 2 |
| `wow` | World of Warcraft |
| anything else | generic examples; set `game_name` too, e.g. `game = lastepoch` and `game_name = Last Epoch` |

`game_name` also overrides the display name of the built-in games. To support several games, run one bot per game: a separate Discord application, folder and database for each.

### Discord Developer Portal

1. Create an application, add a bot, copy the token.
2. **Installation:** enable both **Guild Install** (scopes `bot`, `applications.commands`; permissions *View Channels*, *Send Messages*, *Embed Links*) and **User Install** (scope `applications.commands`).
3. No privileged intents are needed.
4. Set the privacy policy URL to this repository's `PRIVACY.md`.

With **User Install**, people can add the app to their own account and use `/rep`, `/vouch` and `/myrep` in servers that haven't installed the bot, as long as the server allows external apps. Discord may show those replies only to the person who ran the command, depending on the server's settings.

### Windows, always on

`install_windows.ps1` registers two scheduled tasks named after the folder: the bot at startup (restarted if it crashes) and a daily backup. Fill in the token in `config.txt` first. See `SETUP.md` for step-by-step instructions.

## License

MIT
