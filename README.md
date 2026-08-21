# Vaporeon Bot

A charming, data-driven Discord bot designed to feel like Vaporeon lives in your server. Its personality comes from editable JSON and your own local images; friendship progress is stored privately in SQLite.

## Commands

`/vaporeon-help`, `/vaporeon-speak`, `/vaporeon-photo`, `/vaporeon-pet`, `/vaporeon-boop`, `/vaporeon-feed`, `/vaporeon-hug`, `/vaporeon-splash`, `/vaporeon-ask`, `/vaporeon-fortune`, `/vaporeon-rate`, `/vaporeon-choose`, `/vaporeon-friendship`, `/vaporeon-encounter`, `/vaporeon-daily`, `/vaporeon-vibe`, `/vaporeon-sleep`, `/vaporeon-serverstats`, and owner-only `/vaporeon-summon`.

Petting and booping have a five-minute per-user cooldown; feeding has a one-hour cooldown. The limits are persisted in `data/vaporeon.db`, so restarting the bot does not bypass them. `/vaporeon-daily` is one shared encounter per server per UTC day. Friendship tiers range from Stranger through Vaporeon's Chosen Human, with a 20-cell progress bar.

## Tide Duel

`/vaporeon-duel @user` starts a public, self-contained Tide Duel after the invited player presses **Accept**. Both players begin at 100 HP and 0–100 Tide. Every round is a simultaneous hidden choice: selections only reveal when both players lock in, so callback timing never decides an attack.

Every Tide Duel move is available regardless of affection. Weak moves generate Tide, while stronger attacks deliberately spend it and can have round cooldowns. No generic critical hits, items, casual splash HP, or affection rewards are used. The shared duel panel shows HP, Tide, statuses, Rain, Ripple Read availability, lock status, and each player’s last four revealed moves.

| Move | Damage | Accuracy | Tide | Cooldown |
| --- | ---: | ---: | ---: | --- |
| Gentle Splash | 6 | 100% | +25 | none |
| Water Gun | 12 | 95% | +15 | none |
| Bubble Beam | 16 | 90% | +10 | 1 round |
| Aqua Jet | 20 | 100% | −10 | 1 round |
| Water Veil | 0 | automatic | −15 | 2 rounds |
| Muddy Water | 25 | 85% | −25 | 2 rounds |
| Surf | 32 | 90% | −40 | 2 rounds |
| Rain Dance | 0 | automatic | −40 | once per duel |
| Hydro Pump | 45 | 70% | −65 | 3 rounds |
| Hydro Cannon | 60 | 60% | −100 | once per duel |

Bubble Beam has a 25% chance to apply **Soaked**: the next successful outgoing damaging move gets +10% damage, while a miss keeps Soaked. Muddy Water has a 30% chance to apply **Slippery**: the next incoming damaging attack loses 35 percentage points of accuracy, then consumes Slippery. Water Veil halves same-round incoming damage, rounded down. Rain Dance starts three rounds of symmetrical Rain, giving both players’ damaging moves +15% damage.

Players alternate who chooses first each round. The responding player gets one private **Ripple Read**, usable after the first move locks but before responding. It reveals one or more truthful mechanical properties and lists every remaining possible move; it never directly reveals the selected move. The compact private chooser shows state plus a dropdown, with a **View move details** button for the complete table. `/vaporeon-duelrules` gives full private rules and `/vaporeon-duelstats` shows private aggregate results.

All move properties are visible while choosing a move. There are no intentionally hidden damage values, accuracy rates, Tide costs, cooldowns, or status probabilities.

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
