# Setup guide

Step-by-step instructions for running CarryRep. See `README.md` for what the bot does.

## Choosing the game

Set `game` in `config.txt` to pick the game this bot serves. It changes the game name in panels, cards and command descriptions, and the example text in the forms.

| `GAME` | Game |
|---|---|
| `d4` (default) | Diablo IV |
| `poe2` | Path of Exile 2 |
| `wow` | World of Warcraft |
| anything else | generic examples; set `game_name` too, e.g. `game = lastepoch` and `game_name = Last Epoch` |

- The default is `game = d4` (Diablo IV).
- To serve several games, create one Discord application and one copy of the folder per game. Their databases are separate.

## First-time setup

1. Open https://discord.com/developers/applications and click **New Application**. Pick a neutral name, e.g. CarryRep (you can change it later).
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

All settings live in one file, `config.txt`, in the bot folder: one `key = value` per line, `#` for comments. `config.example.txt` contains every key with its default value. If `config.txt` is missing, the bot creates it from these defaults on the first run.

| Key | Value | Default |
|---|---|---|
| `token` | the bot token | empty (required) |
| `game` | game id, see below | `d4` (Diablo IV) |
| `game_name` | display name of the game | empty = name of the game in `game` |
| `guild` | test server ID: commands appear there instantly | empty |
| `min_account_days` | minimum reviewer account age in days | `30` |
| `daily_review_limit` | new reviews per reviewer per 24 h | `10` |
| `project_url` | link shown on cards, e.g. this repository | empty |

`config.txt` is excluded from git, so the token is never published.

## Test run (macOS / Linux)

1. In the `carry-rep-bot` folder, copy `config.example.txt` to `config.txt`. Fill in `token` and `guild` (your test server ID).
2. For testing with a new account, set `min_account_days = 0`. Set it back to `30` before going live.
3. Run:
   ```
   cd carry-rep-bot
   pip install -r requirements.txt
   python bot.py
   ```

You should see `[bot] logged in as ...`. Test with two Discord accounts: account A runs `/register`, account B runs `/vouch` on A, then `/rep` on A.

## Running permanently on Windows

No public IP is needed, only an internet connection.

1. Install Python 3.10 or newer from python.org and tick **Add python.exe to PATH**. Do not use the Microsoft Store version.
2. Copy the `carry-rep-bot` folder to the PC, e.g. `C:\carry-rep-bot`, and run `python -m pip install -r requirements.txt` inside it.
3. Copy `config.example.txt` to `config.txt` and fill in the token and any other settings (see above). If you skip this, `run_bot.bat` creates `config.txt` and asks you to fill it in.
4. Double-click `run_bot.bat` for a trial run. The window shows the bot's output (also saved in `logs\bot.log`). When it shows `[bot] logged in as ...`, the bot is online; close the window to stop it. If the token is missing or wrong, the window says so and waits.
5. Open PowerShell as Administrator, go to the folder and run:
   ```
   powershell -ExecutionPolicy Bypass -File install_windows.ps1
   ```
   This registers a startup task **CarryRep-&lt;folder name&gt;** (restarts the bot 30 s after a crash) and a daily 04:00 backup task **CarryRep-&lt;folder name&gt;-Backup** (keeps 14 backups), turns off sleep while on AC power, and starts the bot. Task names include the folder name, so bots for several games can run on the same PC.

To remove: delete both tasks in Task Scheduler, or run `Unregister-ScheduledTask CarryRep-<folder name>; Unregister-ScheduledTask CarryRep-<folder name>-Backup`.

## Checking the numbers

```
python rep_export.py
```

Shows the number of servers with the bot installed, registered boosters, reviews and reviewers, boosters with at least one review, boosters reviewed on two or more servers, lookups, `/myrep` shares, rejected reviews (self-reviews, accounts too new, etc.), and a breakdown per server. It also writes `servers.csv`, `boosters.csv` and `reviews.csv`.

## Publishing the code

Never commit the token or data. `.gitignore` already excludes `config.txt`, `data.db`, CSV files, logs and backups; only `config.example.txt` (no token) is published. Check with `git status` before the first push.

```
cd carry-rep-bot
git init
git add .
git status          # make sure config.txt, data.db and *.csv are not listed
git commit -m "Initial version"
git branch -M main
git remote add origin https://github.com/<your-account>/carry-rep.git
git push -u origin main
```
