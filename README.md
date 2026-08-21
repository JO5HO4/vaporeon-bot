# Vaporeon Bot

A charming, data-driven Discord bot designed to feel like Vaporeon lives in your server. Its personality comes from editable JSON and your own local images; friendship progress is stored privately in SQLite.

## Commands

`/vaporeon-help`, `/vaporeon-speak`, `/vaporeon-photo`, `/vaporeon-pet`, `/vaporeon-boop`, `/vaporeon-feed`, `/vaporeon-hug`, `/vaporeon-splash`, `/vaporeon-ask`, `/vaporeon-fortune`, `/vaporeon-rate`, `/vaporeon-choose`, `/vaporeon-friendship`, `/vaporeon-encounter`, `/vaporeon-daily`, `/vaporeon-vibe`, `/vaporeon-sleep`, `/vaporeon-serverstats`, and owner-only `/vaporeon-summon`.

Petting and booping have a five-minute per-user cooldown; feeding has a one-hour cooldown. The limits are persisted in `data/vaporeon.db`, so restarting the bot does not bypass them. `/vaporeon-daily` is one shared encounter per server per UTC day. Friendship tiers range from Stranger through Vaporeon's Chosen Human, with a 20-cell progress bar.

## Ripple Duel

`/vaporeon-duel @user` starts a public Ripple Duel after the invited player presses **Accept**. It is a separate, friendly RPS minigame: no affection, casual splash HP, weather, items, crits, or damage are involved.

```text
Aqua Jet > Hydro Charge
Hydro Charge > Water Veil
Water Veil > Aqua Jet
```

Both players secretly lock one of those full move names each round. The shared duel message only shows who is locked in; moves reveal together once both players choose. First to three round wins takes the best-of-five match; ties award no point. The shared embed always shows each player's last four **revealed** moves, never their current hidden one.

Each player gets one private **Ripple Read**. It is available only after the opponent locks in and before the reader does. It returns a truthful clue with exactly two explicit possible moves, never the move itself. `/vaporeon-duelrules` shows the full rules privately and `/vaporeon-duelstats` shows private wins, rounds, ties, move-use percentages, and Ripple Reads used.

Example:

```text
Alex locks in.
Joshua uses Ripple Read.

"The water feels strangely patient."

Possible moves:
• Hydro Charge
• Water Veil

Joshua chooses Hydro Charge. Alex chose Water Veil.
Hydro Charge beats Water Veil.
Joshua wins the round.
Score: Joshua 2 — 2 Alex
```

## Personality and photos

Edit `data/speak.json`, `ask.json`, `fortunes.json`, `reactions.json`, `friendship.json`, and `encounters.json` to change Vaporeon's voice without editing Python. Speak lines can include `category` and `rarity` (`common`, `rare`, or `legendary`).

Add your own images—do not add copyrighted art you do not have permission to use—directly under `data/photos/`. Supported formats: PNG, JPG, JPEG, WEBP, and GIF. Every discovered image has equal probability in `/vaporeon-photo` and `/vaporeon-encounter`; an empty album produces a friendly message instead of an error.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

On Windows activate with `.venv\Scripts\activate`. Set `DISCORD_TOKEN`; optionally set `OWNER_ID` (enable Developer Mode, then copy your user ID) and `TEST_GUILD_IDS` (a comma-separated list of server IDs) for fast development command sync. Keep `.env` private.

Create a Discord application and bot in the Developer Portal, then invite it with `bot` and `applications.commands` OAuth scopes. No privileged intent is needed unless you set `PASSIVE_RESPONSES_ENABLED=true`; that optional 1%-chance mention response requires Message Content Intent to be enabled in both `.env` and the Developer Portal.

The bot needs outbound internet only—no web server or public domain. SQLite data lives in `data/vaporeon.db`; back it up before replacing a VM or deleting the data directory.

## Content editing

Add speak lines as objects such as `{"text":"A tiny splash approves.","category":"happy","rarity":"common"}`. Optional `context` values (`morning`, `late_night`, `weekday`, `weekend`) let a line appear occasionally at the appropriate local server time. Add short `{ "text": "…" }` entries to `fortunes.json` and `ask.json`; use `reactions.json` for interaction text and `friendship.json` for tier-specific descriptions. Invalid or malformed JSON stops the bot at startup with the filename and error, so a broken personality file never produces mysterious chat failures.

Put friend-specific lines and inside jokes in `data/custom.json`. It supports `speak` entries with the same format as `speak.json`, optional `tags` such as `["inside_joke", "friend_name"]`, optional `quote: false` to suppress automatic dialogue quotes, `fortunes` entries with `text`, and plain-string `activities`. Start with the copy/paste snippets in [INSIDE_JOKES_TEMPLATE.md](data/INSIDE_JOKES_TEMPLATE.md); keeping custom material in this file makes future updates easy.

Images are discovered recursively, but no folder naming is required. Place files directly in `data/photos/` for the simplest workflow. `/vaporeon-photo` and `/vaporeon-encounter` work without photos, but explain that the album is empty.

## Privacy and operations

Only Discord user IDs, affection/counters, and UTC first/last interaction timestamps are stored. The bot never stores message text, email addresses, or IP addresses. `/summon` checks `OWNER_ID` on every use; if no owner is set, it requires a server administrator. The passive reply is disabled by default and has a server-wide cooldown.

For production, run one bot process with a process manager such as systemd and inspect its logs after restart. Global Discord commands can take time to refresh; `TEST_GUILD_IDS` makes development command updates appear quickly.
