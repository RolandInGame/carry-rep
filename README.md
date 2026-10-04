# CarryRep

A Discord bot that gives game boosters a reputation that follows them from server to server.
Each game gets its own bot (Diablo IV built in; see [Games](#games)); all bots run from one folder and share one database.

- **Boosters** register once with `/register`, then show their card anywhere with `/myrep`.
- **Buyers** check a booster with `/rep @user` before paying, and leave one review with `/vouch @user` after.
- All servers share one database, so reviews collected in one server show up everywhere. Cards also show the booster's ratings in the other games.
- Server admins can post a button panel with `/panel` and see activity with `/stats`.
- Every card has a **Review** button (anyone who sees it can review that booster) and a **Get your own card** button (how to add the app and register), so cards spread the bot on their own.

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
- No self-reviews (except in the test server set by `guild`, for demos). One review per buyer per booster (a new one replaces the old one).
- Reviewer accounts must be at least 30 days old (`min_account_days` in `config.txt`; not checked in the test server).
- At most 10 new reviews per reviewer per day (`daily_review_limit` in `config.txt`).
- 4–5 star reviews are announced in the channel; 1–3 star reviews are recorded quietly and only count in the average.
- Cards show how many different servers the reviews came from.

Known limitation: a booster who deletes their data also deletes the reviews they received and can register again from zero.

## Run it

Requires Python 3.10+.

```bash
pip install -r requirements.txt
cp config.example.txt config.txt   # then fill in the token under [d4]
python bot.py d4                   # on Windows: double-click run_d4.bat
```

### Configuration

All settings live in `config.txt` next to `bot.py`: a `[common]` section shared by all bots and one `[<game id>]` section per bot. `config.example.txt` lists every key with its default value; copy it to `config.txt` (or just run the bot once, which creates it). `config.txt` is excluded from git.

| Key | Section | Value | Default |
|---|---|---|---|
| `min_account_days` | common | minimum reviewer account age in days | `30` |
| `daily_review_limit` | common | new reviews per reviewer per 24 h, per game | `10` |
| `project_url` | common | link shown on cards, e.g. this repository | empty |
| `proxy` | common | HTTP proxy for reaching Discord, e.g. `http://127.0.0.1:7890` | empty = direct |
| `token` | game | that game's bot token | required |
| `game_name` | game | display name of the game | built-in name |
| `guild` | game | test server ID: commands appear there instantly; self-reviews allowed and no minimum account age there (testing/demos) | empty |

A game section can also override any `[common]` key for that bot. Data for all games is stored in `data.db` next to `bot.py`.

`python rep_export.py` prints the numbers per game and per server and writes CSV exports. `python backup.py` makes a database backup (keeps 14).

### Games

| Game id | Game |
|---|---|
| `d4` | Diablo IV |
| `poe2` | Path of Exile 2 |
| `wow` | World of Warcraft |
| anything else | generic wording; set `game_name`, e.g. `[lastepoch]` with `game_name = Last Epoch` |

To add a game: create a separate Discord application for it, add a `[<game id>]` section with its token to `config.txt`, and copy `run_d4.bat` to `run_<game id>.bat` (change `d4` inside). Each bot is a separate process and Discord connection.

### Discord Developer Portal

1. Create an application, add a bot, copy the token.
2. **Installation:** enable both **Guild Install** (scopes `bot`, `applications.commands`; permissions *View Channels*, *Send Messages*, *Embed Links*) and **User Install** (scope `applications.commands`).
3. No privileged intents are needed.
4. Set the privacy policy URL to this repository's `PRIVACY.md`.

With **User Install**, people can add the app to their own account and use `/rep`, `/vouch` and `/myrep` in servers that haven't installed the bot, as long as the server allows external apps. Discord may show those replies only to the person who ran the command, depending on the server's settings.

### Windows, always on

`install_windows.ps1` registers one startup task per `run_<game id>.bat` (restarted if it crashes) and a daily backup of the shared database. Fill in the tokens in `config.txt` first. See `SETUP.md` for step-by-step instructions.

## License

MIT
