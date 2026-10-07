# Setup guide

Step-by-step instructions for running CarryRep. See `README.md` for what the bot does.

## How it is organised

- **One folder, one database.** All game bots run from the same folder and share `data.db`. Every row records its game, so `rep_export.py` can show all games together, and a booster's card also lists their ratings in the other games.
- **One bot per game.** Each game has its own Discord application (own name, own token, own Install Link) and runs as its own process. `run_bot.bat` starts all of them together in one window; `run_d4.bat` and friends start a single game when you want to look at one on its own.
- **One settings file.** `config.txt` has a `[common]` section for shared settings and one `[<game id>]` section per bot.

| Game id | Game |
|---|---|
| `d4` | Diablo IV |
| `poe2` | Path of Exile 2 |
| `wow` | World of Warcraft |
| anything else | generic wording; set `game_name`, e.g. `[lastepoch]` with `game_name = Last Epoch` |

## First-time setup (per game)

1. Open https://discord.com/developers/applications and click **New Application**. Use a neutral name that tells the game apart, e.g. `CarryRep D4`.
2. **Bot** page: click **Reset Token** and save the token (it is shown only once). Leave all three Privileged Gateway Intents **off**.
3. **Installation** page:
   - Under Installation Contexts, enable **Guild Install** and **User Install**.
   - Guild Install scopes: `bot` and `applications.commands`; permissions: `View Channels`, `Send Messages`, `Embed Links`.
   - User Install scope: `applications.commands`.
   - Copy the **Install Link**.
4. **General Information** page: set the Privacy Policy URL to the link of `PRIVACY.md` in your repository.
5. Use the Install Link to add the bot to your own test server. In Discord, turn on Settings → Advanced → Developer Mode, then right-click the test server → Copy Server ID.

**About User Install:** boosters can add the app to their own account and use `/myrep`, `/rep` and `/vouch` in servers that haven't installed the bot, as long as those servers allow external apps. Some servers show these replies only to the person who ran the command.

## Settings (config.txt)

`config.example.txt` contains every key with its default value; copy it to `config.txt`. If `config.txt` is missing, the bot creates it on the first run. `#` starts a comment.

```
[common]
min_account_days = 30
daily_review_limit = 10
project_url =
proxy =

[d4]
token = <Diablo IV bot token>
game_name =
guild =
```

| Key | Section | Value | Default |
|---|---|---|---|
| `min_account_days` | common | minimum reviewer account age in days (not checked in the test server) | `30` |
| `daily_review_limit` | common | new reviews per reviewer per 24 h, per game | `10` |
| `project_url` | common | link shown on cards, e.g. the repository | empty |
| `proxy` | common | HTTP proxy for reaching Discord, e.g. `http://127.0.0.1:7890` | empty = direct |
| `token` | game | this game's bot token | required |
| `game_name` | game | display name of the game | built-in name |
| `guild` | game | test server ID: commands appear there instantly; self-reviews allowed and no minimum account age there (testing/demos) | empty |
| `vote_url` | game | upvote page on a bot list, shown at the end of `/help` | empty |

A game section may also override any `[common]` key for that bot only. `token`, `game_name` and `guild` are never taken from `[common]`. An old `config.txt` without sections still works: it is treated as the `[d4]` bot.

`config.txt` is excluded from git, so tokens are never published.

## Adding a game

1. Create a new Discord application for it (steps above) and copy its token.
2. Add a section to `config.txt`, e.g.
   ```
   [poe2]
   token = <Path of Exile 2 bot token>
   ```
3. Add the new id to `games` under `[common]` in `config.txt`, e.g. `games = d4, wow, poe2`.
4. Start everything with `run_bot.bat`. To run only the new game, use `run_bot.bat poe2` (or copy `run_d4.bat` to `run_poe2.bat` and change `d4` inside).

## Test run (macOS / Linux)

1. Copy `config.example.txt` to `config.txt`. Under `[d4]`, fill in `token` and `guild` (your test server ID).
2. In the test server (`guild`) you can review yourself and new accounts can review, so one account is enough for testing.
3. Run:
   ```
   cd carry-rep
   pip install -r requirements.txt
   python bot.py d4
   ```

You should see `[bot] logged in as ...`. Test with two Discord accounts: account A runs `/register`, account B runs `/vouch` on A, then `/rep` on A.

## Running permanently on Windows

No public IP is needed, only an internet connection.

1. Install Python 3.10 or newer from python.org and tick **Add python.exe to PATH**. Do not use the Microsoft Store version.
2. Copy the folder to the PC, e.g. `C:\carry-rep`, and run `python -m pip install -r requirements.txt` inside it.
3. Copy `config.example.txt` to `config.txt` and fill in the tokens (see above).
4. Double-click `run_bot.bat` for a trial run. One window starts every game listed in `games` and prefixes each line with the game id; each bot also keeps its own `logs\bot-<game id>.log`. When a bot shows `[bot] logged in as ...`, it is online. Ctrl+C or closing the window stops them all. A bot that stops on its own is restarted after 30 s; one with a missing or wrong token says so and stays stopped while the others keep running. To watch a single game on its own, use `run_d4.bat`.
5. Open PowerShell as Administrator, go to the folder and run:
   ```
   powershell -ExecutionPolicy Bypass -File install_windows.ps1
   ```
   This registers one startup task per `run_<game id>.bat` (**CarryRep-d4**, **CarryRep-poe2**, ...; each restarts its bot 30 s after a crash), a daily 04:00 backup task **CarryRep-Backup** for the shared database (keeps 14 backups), turns off sleep while on AC power, and starts the bots. Run it again after adding a game.

To remove a bot from startup: delete its task in Task Scheduler, or run e.g. `Unregister-ScheduledTask CarryRep-d4`.

## Checking the numbers

```
python rep_export.py
```

For each game: servers with the bot installed, registered boosters, reviews and reviewers, boosters with at least one review, boosters reviewed on two or more servers, lookups, `/myrep` shares and rejected reviews. Then boosters registered in two or more games, and a breakdown per game and server. It also writes `servers.csv`, `boosters.csv` and `reviews.csv`.

## Publishing the code

Never commit tokens or data. `.gitignore` already excludes `config.txt`, `data.db`, CSV files, logs and backups; only `config.example.txt` (no tokens) is published. Check with `git status` before pushing.

## Troubleshooting: the bot can't reach Discord

If the window stops after `connecting to Discord ...` with a timeout or connection error, the network is probably blocking Discord. A VPN client in its usual "system proxy" mode only covers browsers; Python ignores it. Either:

- set `proxy` under `[common]` in `config.txt` to the VPN client's local **HTTP** proxy address, e.g. `proxy = http://127.0.0.1:7890` (the port is shown in the client's settings; SOCKS-only ports don't work), or
- switch the VPN client to TUN / global / "enhanced" mode so all programs go through it.

Then start the bot again. The first line of output shows the proxy in use.
