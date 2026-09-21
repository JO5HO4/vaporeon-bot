"""Thin Discord slash-command layer for Vaporeon's personality."""

import os
import random
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands

from .constants import BOOP_OUTCOME_WEIGHTS, BOOP_COOLDOWN_SECONDS, DIVE_COOLDOWN_SECONDS, FEED_COOLDOWN_SECONDS, INTERACTION_RARE_CHANCE, PET_COOLDOWN_SECONDS, SPLASH_COOLDOWN_SECONDS, WATER_BLUE
from .content import ContentError, ContentStore
from .database import MASTERY_STATUS_DURATION, add_discovery, add_inventory_item, adjust_affection, apply_battle_status, apply_splash_damage, claim_cooldown, clear_battle_statuses, complete_daily_quest, consume_battle_status, consume_inventory_item, cooldown_remaining, daily_quest_status, discovery_details_for_user, discovery_count, get_active_status_details, get_battle_card, get_faint_protection, get_or_create_daily_encounter, get_or_create_daily_quest, get_ripple_duel_stats, get_user_stats, get_weather, heal_battle_hp, inventory_for_user, leaderboard_with_titles, recent_battle_history, record_battle_miss, record_boop, record_daily_participation, record_dive, record_encounter, record_feed, record_hug, record_pet, record_photo, record_quest, record_splash, schedule_respawn_notification, schedule_weather_notification, server_totals, set_equipped_title, start_weather, tide_duel_move_uses, transfer_affection, transfer_discovery, transfer_inventory_item
from .friendship import build_progress_bar, friendship_level, progress_to_next_tier
from .games import PlayView, random_scenario
from .game_time import game_day, seconds_until_next_game_day
from .logic import deterministic_rating, parse_options
from .discoveries import ALL_COLLECTIBLES, COLLECTION_SETS, COLLECTIBLES, COLLECTIBLE_RARITIES, COLLECTIBLE_WEIGHTS, RARE_COLLECTIBLES, completed_set_titles
from .duels import DuelManager, MOVE_DEFINITIONS, move_detail
from .duel_views import DuelChallengeView, DuelView, duel_embed, rules_embed
from .items import ITEMS, ITEM_DROP_WEIGHTS, TRASH_FINDS
from .photos import discover_photos
from .rarity import choose_weighted_item
from .splash import CRITICAL_MESSAGES, FAINT_MESSAGES, HUGE_MISS_MESSAGES, MISS_MESSAGES, MOVE_FLAVOR, NEAR_FAINT_MESSAGES, SPLASH_MOVES, next_splash, splash_by_name, unlocked_splash
from .titles import unlocked_titles

PLAY_COOLDOWN_SECONDS = 30 * 60
PRANK_COOLDOWN_SECONDS = 10 * 60
DAILY_QUEST_REWARD = 10
RAIN_CHANCE = 0.05
RARE_DISCOVERY_CHANCE = 0.02
GIFTABLE_ITEM_NAMES = {"Potion", "Super Potion", "Full Heal"}
NEAR_FAINT_COMMENTARY_CHANCE = 0.35
SLIPPERY_MISS_CHANCE = 0.35
WEATHER_WEIGHTS = {
    "rainy": 20,
    "misty": 20,
    "drizzle": 20,
    "perfect_puddle_weather": 20,
    "suspiciously_dry": 20,
}
WEATHER_DETAILS = {
    "rainy": ("🌧️ Rainy", "Water moves deal **+15% damage** in this server for one hour."),
    "misty": ("🌫️ Misty", "Everything is slightly mysterious. Mechanical effect: **absolutely nothing**."),
    "drizzle": ("🌦️ Drizzle", "The air is politely damp. Mechanical effect: **absolutely nothing**."),
    "perfect_puddle_weather": ("💧 Perfect Puddle Weather", "Every puddle is at peak puddle. Mechanical effect: **absolutely nothing**."),
    "suspiciously_dry": ("☀️ Suspiciously Dry", "Vaporeon is monitoring this concerning lack of water. Mechanical effect: **absolutely nothing**."),
    "swift_current": ("🌊 Swift Current", "For **1 hour**, new non-Gentle Splash cooldowns are **5 minutes** for everyone."),
    "monsoon": ("⛈️ Monsoon", "For **1 hour**, all splash damage is **+25%** for everyone."),
    "calm_waters": ("🫧 Calm Waters", "For **1 hour**, all incoming splash damage is **−25%** for everyone."),
    "stormfront": ("⚡ Stormfront", "For **1 hour**, splash accuracy is **−20 points** and critical chance is **doubled** for everyone."),
    "foam_festival": ("🎉 Foam Festival", "For **1 hour**, successful splashes have a **25%** chance to apply Soaked, Slippery, or Waterlogged."),
    "clear_skies": ("🌤️ Clear Skies", "For **1 hour**, random weather cannot begin. The weather has been politely dismissed."),
}
DAILY_QUESTS = {
    "pet": ("Give Vaporeon a pet", "/vaporeon-pet"),
    "boop": ("Give Vaporeon a boop", "/vaporeon-boop"),
    "feed": ("Give Vaporeon a snack", "/vaporeon-feed"),
    "hug": ("Give Vaporeon a hug", "/vaporeon-hug"),
    "splash": ("Use a Vaporeon water move", "/vaporeon-splash"),
    "encounter": ("Have a Vaporeon encounter", "/vaporeon-encounter"),
    "photo": ("Look at a Vaporeon photo", "/vaporeon-photo"),
}
HACK_AFFECTION_GAIN_LINES = (
    "The official friendship tide rises.",
    "Vaporeon has reviewed the evidence and awarded additional friendship.",
    "A small ceremonial splash confirms the affection adjustment.",
    "Vaporeon adds this to the Very Good Human ledger.",
    "The puddle council has voted in their favor.",
    "Vaporeon gives one approving fin tap.",
)
HACK_AFFECTION_LOSS_LINES = (
    "Vaporeon has filed a tiny complaint.",
    "The friendship tide recedes a little.",
    "A concerned splash has been issued.",
    "Their berry privileges are under review.",
    "Vaporeon has made a note. The note is damp.",
    "The puddle council requests an explanation.",
)
HACK_AFFECTION_MAJOR_GAIN_LINES = (
    "A major friendship event has been recorded. Vaporeon is visibly pleased.",
    "The friendship tide rises dramatically. This has become an official occasion.",
)
HACK_AFFECTION_MAJOR_LOSS_LINES = (
    "This has been escalated to the Department of Water.",
    "Vaporeon has called an emergency puddle-council meeting.",
)
PRANK_STEAL_LINES = (
    "Vaporeon performed a suspicious berry audit and redirected some friendship to {actor}.",
    "A tiny whirlpool carried a few affection points from {target} to {actor}.",
    "Vaporeon borrowed {target}'s imaginary wallet and found only friendship inside.",
    "The puddle council ruled that {actor} gets a small reimbursement from {target}.",
)
PRANK_GIVE_LINES = (
    "Vaporeon distracted {actor} with a shiny pebble and quietly gifted friendship to {target}.",
    "A charitable little splash transferred some affection from {actor} to {target}.",
    "Vaporeon declared {target} deserving of a small friendship grant, funded by {actor}.",
    "The puddle council approved a tiny aid package for {target}, courtesy of {actor}.",
)
MOVE_CHOICE_HINTS = {
    "Tidal Blessing": "next splash ×2",
    "Aqua Ring": "next hit −50% damage",
    "Mist Veil": "next splash: 50% miss",
    "Soak": "next hit +50% damage",
    "Raincall": "next splash +25%; ignores Slippery",
}
WEATHER_CHOICE_HINTS = {
    "Swift Current": "1h: splash cooldowns 5m",
    "Monsoon": "1h: all splash damage +25%",
    "Calm Waters": "1h: incoming damage −25%",
    "Stormfront": "1h: −20 accuracy; crits ×2",
    "Foam Festival": "1h: 25% random status",
    "Clear Skies": "1h: blocks random weather",
}


class VaporeonCommands:
    def __init__(self, content: ContentStore, owner_id: int | None) -> None:
        self.content, self.owner_id = content, owner_id
        self.passive_last_response = 0.0
        self.duel_manager = DuelManager()

    def embed(self, title: str, description: str) -> discord.Embed:
        return discord.Embed(title=title, description=description, color=discord.Color(WATER_BLUE))

    @staticmethod
    def weather_text(weather: tuple[str, datetime] | None) -> str:
        if weather is None:
            return "Clear"
        name, effect = WEATHER_DETAILS[weather[0]]
        return f"{name} ({effect.replace('**', '')})"

    @staticmethod
    def maybe_start_weather(guild_id: int | None, channel_id: int | None = None) -> tuple[tuple[str, datetime] | None, str]:
        weather = get_weather(guild_id)
        if weather is not None or random.random() >= RAIN_CHANCE:
            return weather, ""
        kind = random.choices(tuple(WEATHER_WEIGHTS), weights=tuple(WEATHER_WEIGHTS.values()), k=1)[0]
        weather = start_weather(guild_id, kind)
        if weather is None:
            return None, ""
        schedule_weather_notification(guild_id, channel_id, kind, weather[1])
        name, effect = WEATHER_DETAILS[kind]
        return weather, f"\n\n{name} **weather began!** {effect}"

    @staticmethod
    def add_collection_discovery(user_id: int, discovery: str) -> str:
        """Add a find and return any newly completed-set titles."""
        before = set(completed_set_titles(set(discovery_details_for_user(user_id))))
        add_discovery(user_id, discovery)
        unlocked = set(completed_set_titles(set(discovery_details_for_user(user_id)))) - before
        if not unlocked:
            return ""
        return f"\n\n🏆 **Set complete!** New title: **{', '.join(sorted(unlocked))}**"

    def duel_is_active(self, *user_ids: int) -> bool:
        return any(self.duel_manager.is_active(user_id) for user_id in user_ids)

    def reserve_duel_players(self, *user_ids: int) -> None:
        if len(user_ids) != 2 or not self.duel_manager.create_invitation(*user_ids):
            raise ValueError("One of you is already in a Ripple Duel.")

    def release_duel_players(self, *user_ids: int) -> None:
        self.duel_manager.remove_duel(*user_ids)

    @staticmethod
    def leaderboard_text(counter: str) -> str:
        entries = leaderboard_with_titles(counter)
        if not entries:
            return "No entries yet. Be the first!"
        medals = ("🥇", "🥈", "🥉")
        return "\n".join(
            f"{medals[index]} {discord.utils.escape_mentions(discord.utils.escape_markdown(name))}{f' · *{discord.utils.escape_mentions(discord.utils.escape_markdown(title))}*' if title else ''} — **{count:,}**"
            for index, (name, count, title) in enumerate(entries)
        )

    def personal_stats_embed(self, user_id: int, display_name: str, guild_id: int | None = None) -> discord.Embed:
        stats = get_user_stats(user_id)
        tier = friendship_level(stats.affection)
        move, next_move = unlocked_splash(stats.affection), next_splash(stats.affection)
        flavor = random.choice(self.content.friendship.get(tier.name, ["a lovely friend."]))
        battle = get_battle_card(user_id)
        collection_titles = completed_set_titles(set(discovery_details_for_user(user_id)))
        titles = unlocked_titles(stats, battle, collection_titles)
        now = datetime.now(timezone.utc)
        statuses = get_active_status_details(user_id, now=now)
        status_line = ", ".join(f"{status.replace('_', ' ').title()} ({max(0, int((expires - now).total_seconds() // 60))}m)" for status, expires in sorted(statuses.items())) if statuses else "None"
        attacker = discord.utils.escape_mentions(discord.utils.escape_markdown(battle.last_attacker)) if battle.last_attacker else "None yet"
        last_move = battle.last_move or "None yet"
        weather = get_weather(guild_id)
        weather_line = self.weather_text(weather)
        protection_line = f" · Recovery Bubble: **{max(0, int((battle.protection_until - now).total_seconds() // 60))}m**" if battle.protection_until else ""
        history = recent_battle_history(user_id)
        history_line = "\n".join(f"• {event.attacker_name}: {event.move_name} — {event.outcome}{f' ({event.damage} damage)' if event.damage else ''}" for event in history) if history else "No splashes received yet."
        splash_status = (
            "**Battle card**\n"
            f"HP: **{battle.hp} / 100**{protection_line}\n"
            f"Wins: **{battle.wins}** · Losses: **{battle.losses}** · Streak: **{battle.current_streak}** (best {battle.best_streak})\n"
            f"Unlocked move: **{move.name}** ({move.fictional_damage} damage · {move.accuracy:.0%} accuracy)\n"
            f"Splashes: **{stats.splashes:,}** · Hits: **{battle.hits}** · Misses: **{battle.misses}** · Crits: **{battle.critical_hits}**\n"
            f"Rainy splashes: **{stats.rainy_splashes:,}** · Hydro Pump survivals: **{battle.hydro_pump_survivals:,}**\n"
            f"Status: **{status_line}**\n"
            f"Last attacker: **{attacker}** · Last move: **{last_move}**\n"
            f"Weather: **{weather_line}**\n"
            f"Recent received splashes:\n{history_line}"
        )
        if next_move:
            splash_status += f"\nNext move: **{next_move.name}** at **{next_move.affection_required} affection**"
        return self.embed(
            f"💧 Your Vaporeon Stats",
            f"**Affection:** {stats.affection:,}\n**Level:** {tier.name}\n"
            f"**Equipped title:** {stats.equipped_title or 'None'}\n"
            f"`{build_progress_bar(progress_to_next_tier(stats.affection))}`\n\n"
            f"Pets: **{stats.pets:,}** · Boops: **{stats.boops:,}** · Feeds: **{stats.feeds:,}**\n"
            f"Hugs: **{stats.hugs:,}** · Splashes: **{stats.splashes:,}**\n"
            f"Encounters: **{stats.encounters:,}** · Photos: **{stats.photos:,}** · Dives: **{stats.dives:,}** · Finds: **{discovery_count(user_id):,}**\n"
            f"Plays: **{stats.plays:,}** · Daily quests: **{stats.quests:,}** · Duels: **{stats.duels:,}** ({stats.duel_wins}W–{stats.duel_losses}L)\n"
            f"Shared dailies: **{stats.daily_participations:,}** · Current streak: **{stats.daily_current_streak}** · Best streak: **{stats.daily_best_streak}**\n"
            f"Unlocked titles: **{', '.join(titles) if titles else 'None yet'}**\n\n"
            f"{splash_status}\n\n"
            f"Vaporeon thinks you are {flavor}",
        )

    def daily_bonus(self, user_id: int, display_name: str, action: str) -> str:
        today = game_day()
        if not complete_daily_quest(user_id, action, today):
            return ""
        stats = record_quest(user_id, DAILY_QUEST_REWARD, display_name=display_name)
        return f"\n🌟 **{display_name} completed their daily quest!** Affection **+{DAILY_QUEST_REWARD}** · Quests: **{stats.quests:,}**"

    @staticmethod
    def cooldown_text(seconds: int) -> str:
        if seconds <= 0:
            return "✅ Ready"
        minutes, leftover = divmod(seconds, 60)
        return f"⏳ {minutes}m {leftover}s" if minutes else f"⏳ {leftover}s"

    async def check_cooldown(self, interaction: discord.Interaction, action: str, seconds: int) -> bool:
        remaining = claim_cooldown(interaction.user.id, action, seconds)
        if not remaining:
            return True
        minutes, leftover = divmod(remaining, 60)
        wait = f"{minutes}m {leftover}s" if minutes else f"{leftover}s"
        await interaction.response.send_message(f"💧 Vaporeon needs a little breather. Try again in **{wait}**.", ephemeral=True)
        return False

    def register(self, tree: app_commands.CommandTree[discord.Client]) -> None:
        command = tree.command

        def splash_choice_name(move) -> str:
            if move.support_status:
                return f"{move.name} · {MOVE_CHOICE_HINTS[move.name]}"
            return f"{move.name} · {move.fictional_damage} dmg · {move.accuracy:.0%} acc"

        async def splash_move_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
            needle = current.casefold()
            return [
                app_commands.Choice(name=splash_choice_name(move), value=move.name)
                for move in SPLASH_MOVES
                if not move.weather and needle in move.name.casefold()
            ][:25]

        async def weather_move_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
            needle = current.casefold()
            return [
                app_commands.Choice(name=f"{move.name} · {WEATHER_CHOICE_HINTS[move.name]}", value=move.name)
                for move in SPLASH_MOVES
                if move.weather and needle in move.name.casefold()
            ]

        async def bag_item_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
            needle = current.casefold()
            bag = inventory_for_user(interaction.user.id)
            return [
                app_commands.Choice(name=f"{name} · {bag[name]} in bag", value=name)
                for name in ITEMS
                if name in bag and needle in name.casefold()
            ][:25]

        async def gift_item_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
            needle = current.casefold()
            bag = inventory_for_user(interaction.user.id)
            discoveries = discovery_details_for_user(interaction.user.id)
            choices = [
                app_commands.Choice(name=f"Item · {name} ×{bag[name]}", value=name)
                for name in GIFTABLE_ITEM_NAMES
                if bag.get(name, 0) > 0 and needle in name.casefold()
            ]
            choices.extend(
                app_commands.Choice(name=f"Spare cosmetic · {name} ×{discovery.quantity}", value=name)
                for name, discovery in discoveries.items()
                if name in COLLECTIBLES and discovery.quantity >= 2 and needle in name.casefold()
            )
            return choices[:25]

        async def title_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
            stats = get_user_stats(interaction.user.id)
            titles = unlocked_titles(stats, get_battle_card(interaction.user.id), completed_set_titles(set(discovery_details_for_user(interaction.user.id))))
            choices = ["None", *titles]
            needle = current.casefold()
            return [app_commands.Choice(name=title, value=title) for title in choices if needle in title.casefold()][:25]

        @command(name="vaporeon-help", description="See what Vaporeon can do.")
        async def help_command(interaction: discord.Interaction) -> None:
            embed = self.embed("💧 Vaporeon's Complete Guide", "A cozy friendship bot with playful water battles. Your personal stats and move list are private; shared activities and server leaderboards are public.")
            embed.add_field(
                name="💙 How to earn affection",
                value=(
                    "`/vaporeon-boop` — usually **+1**; sometimes **0** or **−1** · 5-minute cooldown\n"
                    "`/vaporeon-pet` — **+1** affection; occasional **+5** · 10-minute cooldown\n"
                    "`/vaporeon-play` — choose Vaporeon's next move · 30-minute cooldown\n"
                    "`/vaporeon-feed` — **+2** affection; occasional **+10** · 1-hour cooldown\n"
                    "`/vaporeon-dive` — every hour, Vaporeon may find **+1–10 affection**, a useful item, cosmetic treasure, harmless trash, or a very rare named collectible\n"
                    "`/vaporeon-dailyquest` — one task per day for **+10** affection\n"
                    "`/vaporeon-prank @user` — a harmless 50/50 1–5 affection transfer · 10-minute cooldown"
                ),
                inline=False,
            )
            embed.add_field(
                name="✨ Hang out and chat",
                value="`/vaporeon-speak [mood]` · `/vaporeon-photo` · `/vaporeon-encounter` · `/vaporeon-sleep`\n`/vaporeon-vibe` · `/vaporeon-daily` · `/vaporeon-ask` · `/vaporeon-fortune` · `/vaporeon-rate` · `/vaporeon-choose`",
                inline=False,
            )
            embed.add_field(
                name="💦 Splash battles",
                value=(
                    "`/vaporeon-splash @user [move]` — **Gentle Splash has no cooldown**; every other move has a 10-minute personal cooldown. Damage moves unlock at affection **0 → 10 → 25 → 50 → 100 → 200 → 300 → 500 → 750 → 1,000**; all five Mastery Moves unlock together at **1,000**.\n"
                    "Targets have 100 HP and fully recover after 1 hour without a hit. Fainting gives the attacker a win and puts the target in a **30-minute Recovery Bubble** (or **5 minutes** during Swift Current): they cannot use Vaporeon commands until it ends, except private `/vaporeon-cd` status checks; when it ends, they return at **100 HP**.\n"
                    "Mastery buffs and all casual splash statuses last **1 hour** and are consumed on their first stated trigger; one power and one defense status can be active at once. Moves can miss, crit, and cause statuses. Splashing, hugs, photos, and encounters are tracked, but do **not** themselves grant affection."
                ),
                inline=False,
            )
            embed.add_field(
                name="🌦️ Mastery weather",
                value="At **1,000 affection**, `/vaporeon-weather move: Monsoon` replaces existing weather for one hour and announces its start and end. It shares Splash's cooldown. **Swift Current** (5-minute splash cooldowns), **Monsoon** (+25% damage), **Calm Waters** (−25% damage), **Stormfront** (−20 accuracy, double crit chance), **Foam Festival** (25% random status), and **Clear Skies** (blocks random weather).",
                inline=False,
            )
            embed.add_field(
                name="⚔️ Optional duels",
                value="`/vaporeon-duel @user` — public ordered **Tide Duel**. Each player starts at 100 HP and 25 Tide. Every round has a 50% chance of public, symmetrical weather; its exact modifier is shown before moves are selected. Basic moves can trigger transparent Ripple Effects such as Soaked, Slippery, Drenched, Foamy, or cosmetic Waterlogged. A coin flip chooses who acts first in Round 1; the first-picker role alternates after that. The responder may use one private Ripple Read after the first move locks. Every move is available regardless of affection; Tide and cooldowns determine legality. Challenge **@Vaporeon** to practice against the CPU. `/vaporeon-duelrules` gives full rules; `/vaporeon-duelstats` shows private stats. It is separate from casual splash HP and gives no affection.",
                inline=False,
            )
            embed.add_field(
                name="📊 Your progress",
                value="`/vaporeon-stats` — private friendship, battle card, and equipped title\n`/vaporeon-title` — privately equip an unlocked cosmetic title\n`/vaporeon-profile @user` — public view of a user's equipped title\n`/vaporeon-friendship` — same private progress view\n`/vaporeon-moves` — private move stats, effects, and unlocks\n`/vaporeon-bag` — private item bag\n`/vaporeon-collection` — private dive finds, themed sets, and title progress\n`/vaporeon-gift @user item` — give a safe bag item or spare common cosmetic\n`/vaporeon-use item` — use a healing or status-clearing item on yourself\n`/vaporeon-cd` — private cooldown and Recovery Bubble status\n`/vaporeon-serverstats` — public server totals and top-three leaderboards",
                inline=False,
            )
            embed.add_field(
                name="🌟 Daily and shared content",
                value="`/vaporeon-dailyquest` — receive/check your private daily task; assignment and completion are announced in the channel\n`/vaporeon-daily` — the server's shared daily encounter; each day's visit tracks total, current, and best participation streaks without removing your best streak for a missed day",
                inline=False,
            )
            embed.add_field(
                name="🏷️ Achievement titles",
                value="Titles are cosmetic and can be equipped privately with `/vaporeon-title`. Earn **First Splash** (1 splash), **Rain Dancer** (10 rainy splashes), **Hydro Pump Survivor** (survive one), **Berry Benefactor** (25 feeds), **Frequently Damp** (25 splashes), **Professional Menace** (100 splashes), **Nap Enthusiast** (25 encounters), **1000 Pets**, **Deep Sea Regular** (50 dives), **Quest Keeper** (25 quests), **Duelist** (1 duel win), or **Puddle Champion** (10 duel wins). Collection-set titles come from `/vaporeon-collection`.",
                inline=False,
            )
            embed.add_field(name="🫧 Special", value="`/vaporeon-summon` — caretaker-only special appearance", inline=False)
            embed.set_footer(text="Vaporeon is here for snacks, naps, and extremely serious water-balloon battles.")
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @command(name="vaporeon-title", description="Equip one unlocked cosmetic Vaporeon title.")
        @app_commands.describe(title="An unlocked title, or None to clear your title")
        @app_commands.autocomplete(title=title_autocomplete)
        async def title(interaction: discord.Interaction, title: str) -> None:
            stats = get_user_stats(interaction.user.id)
            unlocked = unlocked_titles(stats, get_battle_card(interaction.user.id), completed_set_titles(set(discovery_details_for_user(interaction.user.id))))
            if title.casefold() == "none":
                set_equipped_title(interaction.user.id, None)
                await interaction.response.send_message("💧 Your Vaporeon title is now clear.", ephemeral=True)
                return
            selected = next((candidate for candidate in unlocked if candidate.casefold() == title.casefold()), None)
            if selected is None:
                await interaction.response.send_message("That title is not unlocked yet. Use `/vaporeon-stats` to see your available titles.", ephemeral=True)
                return
            set_equipped_title(interaction.user.id, selected)
            await interaction.response.send_message(f"🏷️ Equipped title: **{selected}**", ephemeral=True)

        @command(name="vaporeon-cd", description="See your private Vaporeon cooldowns.")
        async def cooldowns(interaction: discord.Interaction) -> None:
            weather = get_weather(interaction.guild_id)
            splash_cooldown = SPLASH_COOLDOWN_SECONDS // 2 if weather and weather[0] == "swift_current" else SPLASH_COOLDOWN_SECONDS
            cooldowns = (
                ("👆 Boop", "boop", BOOP_COOLDOWN_SECONDS),
                ("🐾 Pet", "pet", PET_COOLDOWN_SECONDS),
                (f"💦 Splash moves ({splash_cooldown // 60}m)", "splash", splash_cooldown),
                ("🎲 Play", "play", PLAY_COOLDOWN_SECONDS),
                ("🍓 Feed", "feed", FEED_COOLDOWN_SECONDS),
                ("🌊 Dive", "dive", DIVE_COOLDOWN_SECONDS),
                ("😈 Prank", "prank", PRANK_COOLDOWN_SECONDS),
            )
            lines = ["**💧 Gentle Splash:** ✅ No cooldown"]
            lines.extend(f"**{label}:** {self.cooldown_text(cooldown_remaining(interaction.user.id, action, seconds))}" for label, action, seconds in cooldowns)
            today = game_day()
            quest_status = daily_quest_status(interaction.user.id, today)
            if quest_status is None:
                lines.append("**🌟 Daily Quest:** ✅ Ready — use `/vaporeon-dailyquest`")
            else:
                action, completed = quest_status
                quest, command_name = DAILY_QUESTS[action]
                if completed:
                    lines.append(f"**🌟 Daily Quest:** ✅ Completed · next quest {self.cooldown_text(seconds_until_next_game_day())}")
                else:
                    lines.append(f"**🌟 Daily Quest:** 📝 {quest} — use `{command_name}`")
            now = datetime.now(timezone.utc)
            statuses = get_active_status_details(interaction.user.id, now=now)
            if statuses:
                status_text = " · ".join(
                    f"{status.replace('_', ' ').title()} ({max(0, int((expires - now).total_seconds() // 60))}m)"
                    for status, expires in sorted(statuses.items())
                )
                lines.append(f"**💦 Active splash status:** {status_text}")
            if weather:
                name, _ = WEATHER_DETAILS[weather[0]]
                seconds = max(0, int((weather[1] - now).total_seconds()))
                lines.append(f"**🌦️ Server weather:** {name} · {self.cooldown_text(seconds)}")
            death_timer = get_faint_protection(interaction.user.id)
            if death_timer:
                seconds = max(1, int((death_timer - datetime.now(timezone.utc)).total_seconds()))
                lines.append(f"**🫧 Recovery Bubble:** {self.cooldown_text(seconds)}")
            else:
                lines.append("**🫧 Recovery Bubble:** ✅ Clear")
            await interaction.response.send_message(embed=self.embed("⏱️ Your Vaporeon Cooldowns", "\n".join(lines)), ephemeral=True)
        @command(name="vaporeon-speak", description="Hear a curated Vaporeon thought.")
        @app_commands.describe(mood="Optional mood, such as happy, sleepy, chaotic, or encouraging")
        async def speak(interaction: discord.Interaction, mood: str | None = None) -> None:
            try:
                line, rarity = self.content.random_speak(mood.casefold() if mood else None)
                prefix = "✨ Legendary Vaporeon response! ✨\n" if rarity == "legendary" else ""
                text = line["text"] if line.get("quote", True) is False else f'"{line["text"]}"'
                await interaction.response.send_message(embed=self.embed("💧 Vaporeon", f"{prefix}{text}"))
            except ContentError as error:
                await interaction.response.send_message(str(error), ephemeral=True)

        @command(name="vaporeon-photo", description="See a random Vaporeon photo.")
        async def photo(interaction: discord.Interaction) -> None:
            photos = discover_photos()
            if not photos:
                await interaction.response.send_message("Vaporeon's photo album is empty here. Add images under `data/photos/` first.", ephemeral=True)
                return
            photo = random.choice(photos)
            caption, _ = self.content.random_reaction("photo")
            record_photo(interaction.user.id, display_name=interaction.user.display_name)
            await interaction.response.send_message(f"💧 {caption['text']}{self.daily_bonus(interaction.user.id, interaction.user.display_name, 'photo')}", file=discord.File(photo.path))

        @command(name="vaporeon-dive", description="Let Vaporeon dive for affection, items, or strange trash.")
        async def dive(interaction: discord.Interaction) -> None:
            if not await self.check_cooldown(interaction, "dive", DIVE_COOLDOWN_SECONDS):
                return
            weather, weather_line = self.maybe_start_weather(interaction.guild_id, interaction.channel_id)
            roll = random.random()
            if roll < 0.45:
                gain = random.randint(1, 10)
                stats = record_dive(interaction.user.id, gain, display_name=interaction.user.display_name)
                await interaction.response.send_message(embed=self.embed("🌊 Vaporeon Dive", f"Vaporeon dives deep, returns with a proud little splash, and shares a good feeling with you.\n\nAffection **+{gain}** · Total: **{stats.affection:,}**{weather_line}"))
            elif roll < 0.75:
                item_name = random.choices(tuple(ITEM_DROP_WEIGHTS), weights=tuple(ITEM_DROP_WEIGHTS.values()), k=1)[0]
                add_inventory_item(interaction.user.id, item_name)
                stats = record_dive(interaction.user.id, display_name=interaction.user.display_name)
                await interaction.response.send_message(embed=self.embed("🌊 Vaporeon Dive", f"Vaporeon surfaces triumphantly with **{item_name}**!\n\nAdded to your private bag · Dives: **{stats.dives:,}**{weather_line}"))
            elif roll < 0.90 - RARE_DISCOVERY_CHANCE:
                discovery = random.choices(tuple(COLLECTIBLE_WEIGHTS), weights=tuple(COLLECTIBLE_WEIGHTS.values()), k=1)[0]
                title_line = self.add_collection_discovery(interaction.user.id, discovery)
                stats = record_dive(interaction.user.id, display_name=interaction.user.display_name)
                await interaction.response.send_message(embed=self.embed("🌊 Vaporeon Dive", f"✨ Vaporeon found **{discovery}** — a cosmetic treasure for your collection!\n\nView it privately with `/vaporeon-collection` · Dives: **{stats.dives:,}**{title_line}{weather_line}"))
            elif roll < 0.90:
                discovery = random.choice(tuple(RARE_COLLECTIBLES))
                title_line = self.add_collection_discovery(interaction.user.id, discovery)
                stats = record_dive(interaction.user.id, display_name=interaction.user.display_name)
                await interaction.response.send_message(embed=self.embed("🌟 Rare Dive Discovery!", f"Vaporeon surfaces with **{discovery}**!\n\nIt is a **Rare** cosmetic treasure. It has been added to your private collection with today's discovery date.\n\nDives: **{stats.dives:,}**{title_line}{weather_line}"))
            else:
                found = random.choice(TRASH_FINDS)
                stats = record_dive(interaction.user.id, display_name=interaction.user.display_name)
                await interaction.response.send_message(embed=self.embed("🌊 Vaporeon Dive", f"Vaporeon found {found}\n\nIt is not going in the bag. Dives: **{stats.dives:,}**{weather_line}"))

        @command(name="vaporeon-bag", description="See your private Vaporeon item bag.")
        async def bag(interaction: discord.Interaction) -> None:
            bag_items = inventory_for_user(interaction.user.id)
            if not bag_items:
                description = "Your bag is empty. Try `/vaporeon-dive` to let Vaporeon search for something useful."
            else:
                description = "\n".join(f"**{name} ×{bag_items.get(name, 0)}** — {item.description}" for name, item in ITEMS.items() if bag_items.get(name, 0))
                description += "\n\nUse an item with `/vaporeon-use item`."
            await interaction.response.send_message(embed=self.embed("🎒 Your Vaporeon Bag", description), ephemeral=True)

        @command(name="vaporeon-gift", description="Gift a safe item or spare common cosmetic to a friend.")
        @app_commands.describe(user="The friend receiving the gift", item="A transferable item from your bag or collection")
        @app_commands.autocomplete(item=gift_item_autocomplete)
        async def gift(interaction: discord.Interaction, user: discord.Member, item: str) -> None:
            if user.bot:
                await interaction.response.send_message("Vaporeon cannot deliver gifts to bots.", ephemeral=True)
                return
            if user.id == interaction.user.id:
                await interaction.response.send_message("You already have that gift. Vaporeon suggests admiring it instead.", ephemeral=True)
                return
            item_name = next((name for name in GIFTABLE_ITEM_NAMES | set(COLLECTIBLES) if name.casefold() == item.casefold()), None)
            if item_name is None:
                await interaction.response.send_message("That item cannot be gifted. Gifts are limited to Potions, Super Potions, Full Heals, and spare common cosmetics.", ephemeral=True)
                return
            if item_name in GIFTABLE_ITEM_NAMES:
                transferred = transfer_inventory_item(interaction.user.id, user.id, item_name)
                kind = "item"
            else:
                transferred = transfer_discovery(interaction.user.id, user.id, item_name)
                kind = "spare cosmetic"
            if not transferred:
                requirement = "one in your bag" if kind == "item" else "at least two copies so you can keep one"
                await interaction.response.send_message(f"You need {requirement} of **{item_name}** to gift it.", ephemeral=True)
                return
            await interaction.response.send_message(f"🎁 {interaction.user.mention} gave {user.mention} **{item_name}**! Vaporeon handled the delivery very carefully.")

        @command(name="vaporeon-collection", description="See your private cosmetic dive collection.")
        async def collection(interaction: discord.Interaction) -> None:
            found = discovery_details_for_user(interaction.user.id)
            lines = []
            for name, description in ALL_COLLECTIBLES.items():
                discovery = found.get(name)
                rarity = COLLECTIBLE_RARITIES[name]
                if discovery:
                    date = "Unknown" if discovery.first_found_at is None else f"{discovery.first_found_at:%b} {discovery.first_found_at.day}, {discovery.first_found_at:%Y}"
                    icon = "🌟" if rarity == "Rare" else "✨"
                    lines.append(f"{icon} **{name} ×{discovery.quantity}** — **{rarity}** · found {date}\n{description}")
                else:
                    lines.append(f"❔ **{name}** — **{rarity}** · not found yet\n{description}")
            set_lines = []
            for set_name, details in COLLECTION_SETS.items():
                items = details["items"]
                completed = set(items).issubset(found)
                icon = "🏆" if completed else "▫️"
                state = f"complete — title unlocked: **{details['title']}**" if completed else f"{sum(name in found for name in items)} / {len(items)} found"
                set_lines.append(f"{icon} **{set_name} Set** — {state}")
            await interaction.response.send_message(embed=self.embed("✨ Your Vaporeon Dive Collection", f"**Treasures found:** {sum(item.quantity for item in found.values())} · **Unique:** {len(found)} / {len(ALL_COLLECTIBLES)}\n\n**Collection Sets**\n" + "\n".join(set_lines) + "\n\n" + "\n\n".join(lines)), ephemeral=True)

        @command(name="vaporeon-use", description="Use a battle item from your private bag.")
        @app_commands.describe(item="The item to use on yourself")
        @app_commands.autocomplete(item=bag_item_autocomplete)
        async def use_item(interaction: discord.Interaction, item: str) -> None:
            selected = next((bag_item for name, bag_item in ITEMS.items() if name.casefold() == item.casefold()), None)
            if selected is None or inventory_for_user(interaction.user.id).get(selected.name, 0) < 1:
                await interaction.response.send_message("That item is not in your bag. Try `/vaporeon-bag`.", ephemeral=True)
                return
            if selected.clears_statuses:
                active = get_active_status_details(interaction.user.id)
                if not active:
                    await interaction.response.send_message("You have no active battle statuses to heal.", ephemeral=True)
                    return
                clear_battle_statuses(interaction.user.id)
                consume_inventory_item(interaction.user.id, selected.name)
                await interaction.response.send_message(embed=self.embed("💊 Full Heal", f"Vaporeon carefully applies a **Full Heal**. Cleared: **{', '.join(status.title() for status in sorted(active))}**."), ephemeral=True)
                return
            before, after = heal_battle_hp(interaction.user.id, selected.heal_amount)
            if before == after:
                await interaction.response.send_message("Your battle HP is already full, so Vaporeon saved the item.", ephemeral=True)
                return
            consume_inventory_item(interaction.user.id, selected.name)
            await interaction.response.send_message(embed=self.embed(f"💊 {selected.name}", f"Vaporeon uses **{selected.name}** on you.\n\nHP: **{before} → {after} / 100**"), ephemeral=True)

        @command(name="vaporeon-pet", description="Pet Vaporeon.")
        async def pet(interaction: discord.Interaction) -> None:
            if not await self.check_cooldown(interaction, "pet", PET_COOLDOWN_SECONDS): return
            reaction, rarity = self.content.random_reaction("pet")
            gain = 5 if rarity != "common" and random.random() < INTERACTION_RARE_CHANCE else 1
            stats = record_pet(interaction.user.id, gain, display_name=interaction.user.display_name)
            await interaction.response.send_message(embed=self.embed(f"💧 {interaction.user.display_name} pets Vaporeon", f'{reaction["text"]}\n\nAffection **+{gain}** · Total: **{stats.affection}**{self.daily_bonus(interaction.user.id, interaction.user.display_name, "pet")}'))

        @command(name="vaporeon-boop", description="Boop Vaporeon.")
        async def boop(interaction: discord.Interaction) -> None:
            if not await self.check_cooldown(interaction, "boop", BOOP_COOLDOWN_SECONDS): return
            outcome = choose_weighted_item(BOOP_OUTCOME_WEIGHTS, BOOP_OUTCOME_WEIGHTS.values())
            gain = {"accept": 1, "splash": 1, "neutral": 0, "offended": -1}[outcome]
            reaction, _ = self.content.random_reaction(f"boop_{outcome}")
            stats = record_boop(interaction.user.id, gain, display_name=interaction.user.display_name)
            await interaction.response.send_message(embed=self.embed("💧 Boop!", f'{reaction["text"]}\n\nAffection **{gain:+d}** · Boops: **{stats.boops}**{self.daily_bonus(interaction.user.id, interaction.user.display_name, "boop")}'))

        @command(name="vaporeon-feed", description="Give Vaporeon a snack.")
        async def feed(interaction: discord.Interaction, food: str | None = None) -> None:
            if not await self.check_cooldown(interaction, "feed", FEED_COOLDOWN_SECONDS): return
            reaction, rarity = self.content.random_reaction("feed")
            gain = 10 if rarity != "common" and random.random() < INTERACTION_RARE_CHANCE else 2
            stats = record_feed(interaction.user.id, gain, display_name=interaction.user.display_name)
            snack = food or "a tasty berry"
            await interaction.response.send_message(embed=self.embed("🍓 Snack time", f'You give Vaporeon **{snack}**.\n\n{reaction["text"]}\n\nAffection **+{gain}** · Feeds: **{stats.feeds}**{self.daily_bonus(interaction.user.id, interaction.user.display_name, "feed")}'))

        @command(name="vaporeon-hug", description="Give Vaporeon (or a friend) a friendly hug.")
        async def hug(interaction: discord.Interaction, user: discord.Member | None = None) -> None:
            reaction, _ = self.content.random_reaction("hug")
            record_hug(interaction.user.id, display_name=interaction.user.display_name)
            target = user.mention if user else "you"
            await interaction.response.send_message(f"💧 Vaporeon wraps a fin around {target}.\n{reaction['text']}{self.daily_bonus(interaction.user.id, interaction.user.display_name, 'hug')}")

        @command(name="vaporeon-prank", description="Play a harmless affection prank on a friend.")
        async def prank(interaction: discord.Interaction, user: discord.Member) -> None:
            if user.bot:
                await interaction.response.send_message("Vaporeon only pranks real trainers.", ephemeral=True)
                return
            if user.id == interaction.user.id:
                await interaction.response.send_message("Vaporeon cannot prank you on your own behalf. That would be administrative paperwork.", ephemeral=True)
                return
            actor_affection = get_user_stats(interaction.user.id).affection
            target_affection = get_user_stats(user.id).affection
            max_transfer = min(5, actor_affection, target_affection)
            if max_transfer < 1:
                await interaction.response.send_message("A balanced prank needs both trainers to have at least 1 affection available. No cooldown was used.", ephemeral=True)
                return
            if not await self.check_cooldown(interaction, "prank", PRANK_COOLDOWN_SECONDS):
                return
            # The amount is chosen before the fair coin flip and is affordable in either
            # direction, so each player's expected affection change is exactly zero.
            amount = random.randint(1, max_transfer)
            steal = random.choice((True, False))
            if steal:
                moved = transfer_affection(user.id, interaction.user.id, amount, sender_name=user.display_name, recipient_name=interaction.user.display_name)
                flavor = random.choice(PRANK_STEAL_LINES).format(actor=interaction.user.mention, target=user.mention)
                direction = f"{user.mention} **−{moved}** · {interaction.user.mention} **+{moved}**"
            else:
                moved = transfer_affection(interaction.user.id, user.id, amount, sender_name=interaction.user.display_name, recipient_name=user.display_name)
                flavor = random.choice(PRANK_GIVE_LINES).format(actor=interaction.user.mention, target=user.mention)
                direction = f"{interaction.user.mention} **−{moved}** · {user.mention} **+{moved}**"
            await interaction.response.send_message(f"💧 {flavor}\n\n**Affection transferred:** {direction}")

        @command(name="vaporeon-weather", description="Call one hour of server-wide Mastery weather.")
        @app_commands.describe(move="A weather move unlocked at 1,000 affection")
        @app_commands.autocomplete(move=weather_move_autocomplete)
        async def weather(interaction: discord.Interaction, move: str) -> None:
            selected = splash_by_name(move)
            affection = get_user_stats(interaction.user.id).affection
            if selected is None or not selected.weather:
                await interaction.response.send_message("Choose a weather move from the suggestions.", ephemeral=True)
                return
            if selected.affection_required > affection:
                await interaction.response.send_message(f"**{selected.name}** unlocks at **{selected.affection_required} affection**.", ephemeral=True)
                return
            if interaction.guild_id is None:
                await interaction.response.send_message("Vaporeon can only call weather inside a server.", ephemeral=True)
                return
            active_weather = get_weather(interaction.guild_id)
            splash_cooldown = SPLASH_COOLDOWN_SECONDS // 2 if active_weather and active_weather[0] == "swift_current" else SPLASH_COOLDOWN_SECONDS
            if not await self.check_cooldown(interaction, "splash", splash_cooldown):
                return
            started = start_weather(interaction.guild_id, selected.weather)
            assert started is not None
            schedule_weather_notification(interaction.guild_id, interaction.channel_id, selected.weather, started[1])
            name, detail = WEATHER_DETAILS[selected.weather]
            reaction, _ = self.content.random_reaction("splash")
            await interaction.response.send_message(
                f"🌦️ Vaporeon uses **{selected.name}**!\n_{random.choice(MOVE_FLAVOR[selected.name])}_\n\n{name} **weather has begun for the whole server!** {detail}\nIt replaces any previous weather and will announce when it ends.\n{reaction['text']}"
            )

        @command(name="vaporeon-splash", description="Use your unlocked playful Vaporeon water move.")
        @app_commands.describe(user="Trainer to splash", move="Optional unlocked water move; defaults to your strongest")
        @app_commands.autocomplete(move=splash_move_autocomplete)
        async def splash(interaction: discord.Interaction, user: discord.Member, move: str | None = None) -> None:
            current_stats = get_user_stats(interaction.user.id)
            selected = unlocked_splash(current_stats.affection) if move is None else splash_by_name(move)
            if selected is None:
                await interaction.response.send_message("That is not a Vaporeon splash move. Choose one from the suggestions.", ephemeral=True)
                return
            if selected.affection_required > current_stats.affection:
                await interaction.response.send_message(f"**{selected.name}** unlocks at **{selected.affection_required} affection**. Your current move is **{unlocked_splash(current_stats.affection).name}**.", ephemeral=True)
                return
            if selected.weather:
                await interaction.response.send_message(f"**{selected.name}** is server weather. Use `/vaporeon-weather move: {selected.name}` instead.", ephemeral=True)
                return
            protection = get_faint_protection(user.id)
            if protection:
                minutes = max(1, int((protection - datetime.now(timezone.utc)).total_seconds() // 60) + 1)
                await interaction.response.send_message(f"🫧 {user.mention} is still recovering in their **Recovery Bubble**. Try again in **{minutes} minutes**.", ephemeral=True)
                return
            active_weather = get_weather(interaction.guild_id)
            splash_cooldown = SPLASH_COOLDOWN_SECONDS // 2 if active_weather and active_weather[0] == "swift_current" else SPLASH_COOLDOWN_SECONDS
            if selected.name != "Gentle Splash" and not await self.check_cooldown(interaction, "splash", splash_cooldown):
                return
            weather, weather_line = self.maybe_start_weather(interaction.guild_id, interaction.channel_id)
            reaction, _ = self.content.random_reaction("splash")
            record_splash(interaction.user.id, display_name=interaction.user.display_name, rainy=bool(weather and weather[0] == "rainy"))

            opener = f"💦 Vaporeon uses **{selected.name}** on {user.mention}!"
            move_flavor = random.choice(MOVE_FLAVOR[selected.name])
            weather_line = weather_line.replace("\n\n", "\n")
            bonus = self.daily_bonus(interaction.user.id, interaction.user.display_name, "splash")
            target_card = get_battle_card(user.id)
            if selected.support_status:
                apply_battle_status(user.id, selected.support_status, duration=MASTERY_STATUS_DURATION)
                support_descriptions = {
                    "tidal_blessing": "their next splash deals **2× damage**; it is consumed on that attempt, hit or miss",
                    "aqua_ring": "their next successful incoming splash takes **50% less damage**",
                    "mist_veil": "their next incoming splash has a **50% chance to miss**",
                    "soak": "their next successful incoming splash takes **50% more damage**",
                    "raincall": "their next splash gets **+25% damage** and ignores **Slippery**",
                }
                await interaction.response.send_message(
                    f"{opener}\n_{move_flavor}_\n💧 **{user.display_name} is {selected.support_status.replace('_', ' ').title()}** for 1 hour — {support_descriptions[selected.support_status]}.\n{reaction['text']}{weather_line}{bonus}"
                )
                return

            soaked_bonus = consume_battle_status(interaction.user.id, "soaked")
            tidal_blessing = consume_battle_status(interaction.user.id, "tidal_blessing")
            raincall = consume_battle_status(interaction.user.id, "raincall")
            ignores_slippery = selected.ignores_slippery or raincall
            mist_veil = consume_battle_status(user.id, "mist_veil")
            slippery = False if ignores_slippery else consume_battle_status(user.id, "slippery")
            mist_miss = mist_veil and random.random() < 0.50
            slippery_miss = not mist_miss and slippery and random.random() < SLIPPERY_MISS_CHANCE
            stormfront_penalty = bool(weather and weather[0] == "stormfront")
            effective_accuracy = max(0.0, selected.accuracy - (0.20 if stormfront_penalty else 0.0))
            accuracy_miss = not mist_miss and not slippery_miss and random.random() > effective_accuracy
            if mist_miss or slippery_miss or accuracy_miss:
                reason = f"{user.display_name}'s Mist Veil made it miss!" if mist_miss else f"{user.display_name} was slippery and evaded it!" if slippery_miss else f"**{selected.name}** missed!"
                used_power = " The Tidal Blessing washed away after this attempt." if tidal_blessing else " The Raincall faded after this attempt." if raincall else " The Soaked boost splashed harmlessly away." if soaked_bonus else ""
                record_battle_miss(interaction.user.id, user.id, interaction.user.display_name, selected.name)
                miss_flavor = random.choice(HUGE_MISS_MESSAGES.get(selected.name, MISS_MESSAGES))
                await interaction.response.send_message(f"{opener}\n_{move_flavor}_\n💨 {reason} {miss_flavor}{used_power}\n{reaction['text']}{weather_line}{bonus}")
                return

            critical_chance = min(1.0, selected.critical_chance * (2 if weather and weather[0] == "stormfront" else 1))
            critical = random.random() < critical_chance
            multiplier = 1.5 if critical else 1.0
            modifiers: list[str] = []
            if critical:
                modifiers.append("✨ Critical hit ×1.5")
            if soaked_bonus:
                multiplier *= 1.10
                modifiers.append("💧 Soaked boost +10%")
            if tidal_blessing:
                multiplier *= 2.0
                modifiers.append("🌊 Tidal Blessing ×2")
            if raincall:
                multiplier *= 1.25
                modifiers.append("🌧️ Raincall +25% · ignores Slippery")
            if weather and weather[0] == "rainy":
                multiplier *= selected.rain_multiplier
                modifiers.append(f"🌧️ Rain boost +{(selected.rain_multiplier - 1) * 100:.0f}%")
            if weather and weather[0] == "monsoon":
                multiplier *= 1.25
                modifiers.append("⛈️ Monsoon +25%")
            if weather and weather[0] == "calm_waters":
                multiplier *= 0.75
                modifiers.append("🫧 Calm Waters −25%")
            if target_card.hp <= 50 and selected.low_hp_multiplier > 1:
                multiplier *= selected.low_hp_multiplier
                modifiers.append(f"🧂 Brine bonus +{(selected.low_hp_multiplier - 1) * 100:.0f}%")
            soaked_target = consume_battle_status(user.id, "soak")
            aqua_ring = consume_battle_status(user.id, "aqua_ring")
            if soaked_target:
                multiplier *= 1.50
                modifiers.append("💦 Soak vulnerability +50%")
            if aqua_ring:
                multiplier *= 0.50
                modifiers.append("⭕ Aqua Ring armor −50%")
            damage = max(1, round(selected.fictional_damage * multiplier))
            hit = apply_splash_damage(
                user.id,
                damage,
                attacker_id=interaction.user.id,
                attacker_name=interaction.user.display_name,
                move_name=selected.name,
                critical=critical,
                death_timer=timedelta(minutes=5) if weather and weather[0] == "swift_current" else timedelta(minutes=30),
            )
            effect, _ = self.content.random_reaction("splash_effect")
            hp_line = f"**{hit.damage_dealt} damage!** {user.display_name}'s HP: **{hit.hp_before} → {hit.hp_after} / 100**"
            if hit.recovered:
                hp_line = f"{user.display_name} had recovered. {hp_line}"
            status_line = ""
            if selected.status and random.random() < selected.status_chance:
                apply_battle_status(user.id, selected.status)
                status_descriptions = {
                    "soaked": "their next splash gets **+10% damage**",
                    "slippery": "their next incoming splash has a **35% chance to miss**",
                    "waterlogged": "mechanical effect: **absolutely nothing**",
                }
                status_line = f"\n💦 **{user.display_name} is {selected.status.title()}** for 1 hour — {status_descriptions[selected.status]}."
            if weather and weather[0] == "foam_festival" and random.random() < 0.25:
                foam_status = random.choice(("soaked", "slippery", "waterlogged"))
                apply_battle_status(user.id, foam_status)
                status_line += f"\n🎉 **Foam Festival:** {user.display_name} is also **{foam_status.title()}** for 1 hour."
            modifier_line = f"\n{' · '.join(modifiers)}" if modifiers else ""
            critical_line = f"\n✨ {random.choice(CRITICAL_MESSAGES)}" if critical else ""
            revenge_line = "\n⚔️ **REVENGE SPLASH!**" if target_card.last_attacker and target_card.last_attacker.casefold() == interaction.user.display_name.casefold() else ""
            near_faint_line = ""
            if 1 <= hit.hp_after <= 10 and random.random() < NEAR_FAINT_COMMENTARY_CHANCE:
                near_faint_line = f"\n💧 {random.choice(NEAR_FAINT_MESSAGES).format(hp=hit.hp_after)}"
            if hit.fainted:
                if interaction.channel_id is not None:
                    protection = get_faint_protection(user.id)
                    if protection is not None:
                        schedule_respawn_notification(user.id, interaction.channel_id, user.display_name, protection)
                bubble_minutes = 5 if weather and weather[0] == "swift_current" else 30
                hp_line += f"\n💫 **{user.display_name} {random.choice(FAINT_MESSAGES)}** They are now in a **{bubble_minutes}-minute Recovery Bubble** and cannot use Vaporeon commands until it ends."
                hp_line += " They will return at **100 HP** when the bubble clears."
            await interaction.response.send_message(f"{opener}{revenge_line}\n_{move_flavor}_\n{hp_line}{near_faint_line}{modifier_line}{critical_line}{status_line}\n{reaction['text']}\n{effect['text']}{weather_line}{bonus}")

        @command(name="vaporeon-ask", description="Ask Vaporeon a magical question.")
        async def ask(interaction: discord.Interaction, question: str) -> None:
            answer = random.choice(self.content.ask)["text"]
            await interaction.response.send_message(embed=self.embed("💧 You ask Vaporeon", f'“{question}”\n\nVaporeon considers this carefully…\n\n“{answer}”'))

        @command(name="vaporeon-fortune", description="Receive a small Vaporeon fortune.")
        async def fortune(interaction: discord.Interaction) -> None:
            await interaction.response.send_message(embed=self.embed("💧 Vaporeon's Fortune", f'“{random.choice(self.content.fortunes)["text"]}”'))

        @command(name="vaporeon-rate", description="Have Vaporeon give something a playful rating.")
        async def rate(interaction: discord.Interaction, thing: str) -> None:
            rating = deterministic_rating(thing)
            category = "rate_low" if rating < 3 else "rate_mid" if rating < 7 else "rate_high"
            reaction, _ = self.content.random_reaction(category)
            await interaction.response.send_message(embed=self.embed(f"💧 Vaporeon rates {thing}", f"**{rating:.1f} / 10**\n\n“{reaction['text']}”"))

        @command(name="vaporeon-choose", description="Let Vaporeon choose between options separated by |.")
        async def choose(interaction: discord.Interaction, options: str) -> None:
            try:
                choice = random.choice(parse_options(options))
            except ValueError as error:
                await interaction.response.send_message(str(error), ephemeral=True)
                return
            reaction, _ = self.content.random_reaction("choose")
            await interaction.response.send_message(embed=self.embed("💧 Vaporeon chooses…", f"**{choice}**\n\n{reaction['text']}"))

        @command(name="vaporeon-play", description="Play a small Vaporeon encounter for affection.")
        async def play(interaction: discord.Interaction) -> None:
            if not await self.check_cooldown(interaction, "play", PLAY_COOLDOWN_SECONDS):
                return
            scenario = random_scenario()
            embed = self.embed("💧 Vaporeon Play", f"{scenario['prompt']}\n\nWhat should you do?")
            await interaction.response.send_message(embed=embed, view=PlayView(interaction.user.id, interaction.user.display_name, scenario))

        @command(name="vaporeon-friendship", description="See your friendship with Vaporeon.")
        async def friendship(interaction: discord.Interaction) -> None:
            await interaction.response.send_message(embed=self.personal_stats_embed(interaction.user.id, interaction.user.display_name, interaction.guild_id), ephemeral=True)

        @command(name="vaporeon-stats", description="See your private Vaporeon stats.")
        async def stats(interaction: discord.Interaction) -> None:
            await interaction.response.send_message(embed=self.personal_stats_embed(interaction.user.id, interaction.user.display_name, interaction.guild_id), ephemeral=True)

        @command(name="vaporeon-duel", description="Challenge someone to a turn-based Vaporeon duel.")
        async def duel(interaction: discord.Interaction, user: discord.Member) -> None:
            is_cpu = interaction.client.user is not None and user.id == interaction.client.user.id
            if user.bot and not is_cpu:
                await interaction.response.send_message("Vaporeon does not duel bots. Their battle faces are too hard to read.", ephemeral=True)
                return
            if user.id == interaction.user.id:
                await interaction.response.send_message("Vaporeon recommends finding an actual opponent instead of dueling yourself.", ephemeral=True)
                return
            if not is_cpu and get_faint_protection(user.id):
                await interaction.response.send_message(f"🫧 {user.mention} is still resting in a Recovery Bubble and cannot duel yet.", ephemeral=True)
                return
            if self.duel_is_active(interaction.user.id, user.id):
                await interaction.response.send_message("One of you is already in a Vaporeon duel. Finish it or wait a few minutes for an inactive duel to clear.", ephemeral=True)
                return
            self.reserve_duel_players(interaction.user.id, user.id)

            def release() -> None:
                self.release_duel_players(interaction.user.id, user.id)

            def accept_duel():
                return self.duel_manager.accept_invitation(interaction.user.id, interaction.user.display_name, get_user_stats(interaction.user.id).affection, user.id, "Vaporeon (CPU)" if is_cpu else user.display_name, 1000 if is_cpu else get_user_stats(user.id).affection, opponent_cpu=is_cpu)

            if is_cpu:
                state = accept_duel()
                state.lock_cpu_move()
                first = state.player(state.first_picker_id)
                cpu_note = " It has locked a legal move." if state.has_locked(user.id) else " You choose first."
                await interaction.response.send_message(embed=duel_embed(state, f"🤖 **Vaporeon CPU accepted immediately.** 🎲 Coin flip: **{first.name}** chooses and resolves first in Round 1.{cpu_note}"), view=DuelView(state, release))
                return

            view = DuelChallengeView(interaction.user.id, user.id, accept_duel, release)
            await interaction.response.send_message(f"⚔️ {user.mention}, **{interaction.user.display_name}** has challenged you to a **Tide Duel**!\n\nBoth players begin at **100 HP** and **0 Tide**. Move choices are hidden, but every move rule is shown in a private panel before committing. Use `/vaporeon-duelrules` for the complete rules and move table.", view=view)
            view.message = await interaction.original_response()

        @command(name="vaporeon-duelrules", description="See private Tide Duel rules and the move table.")
        async def duelrules(interaction: discord.Interaction) -> None:
            await interaction.response.send_message(embed=rules_embed(), ephemeral=True)

        @command(name="vaporeon-duelstats", description="See your private Ripple Duel statistics.")
        async def duelstats(interaction: discord.Interaction) -> None:
            stats = get_ripple_duel_stats(interaction.user.id)
            uses = tide_duel_move_uses(interaction.user.id)
            total = sum(uses.values())
            most_used = max(uses, key=uses.get) if total else "No moves used yet"
            usage = "\n".join(f"{move}: **{count / total:.0%}** ({count})" for move, count in uses.items()) if total else "No resolved rounds yet."
            await interaction.response.send_message(embed=self.embed("💦 Your Tide Duel Stats", f"Duels: **{stats.duels_played}**\nWins: **{stats.duels_won}** · Losses: **{stats.duels_lost}** · Draws: **{stats.draws}**\nRounds played: **{stats.rounds_played}** · Ties: **{stats.ties}**\n\nMost-used move: **{most_used}**\n\n**Move usage**\n{usage}\n\nRipple Reads used: **{stats.ripple_reads_used}**\n\nNo affection, casual splash HP, or generic critical hits are used in Tide Duel."), ephemeral=True)

        @command(name="vaporeon-profile", description="See a user's public equipped Vaporeon title.")
        async def profile(interaction: discord.Interaction, user: discord.Member) -> None:
            stats = get_user_stats(user.id)
            name = discord.utils.escape_mentions(discord.utils.escape_markdown(user.display_name))
            title = stats.equipped_title or "No title equipped"
            await interaction.response.send_message(embed=self.embed("💧 Vaporeon Profile", f"**Trainer:** {name}\n**Equipped title:** {title}"))

        @command(name="vaporeon-moves", description="See your private Vaporeon move list and unlocks.")
        async def moves(interaction: discord.Interaction) -> None:
            affection = get_user_stats(interaction.user.id).affection
            current_move = unlocked_splash(affection)
            next_move = next_splash(affection)
            unlock_path = " → ".join(str(move.affection_required) for move in SPLASH_MOVES)
            next_line = f"Next: **{next_move.name}** at **{next_move.affection_required} affection**" if next_move else "You have unlocked every move."
            lines = []
            for move in SPLASH_MOVES:
                unlocked = move.affection_required <= affection
                prefix = "✅" if unlocked else "🔒"
                state = "Unlocked" if unlocked else "Locked"
                details = f"{move.fictional_damage} damage · {move.accuracy:.0%} accuracy" if not move.support_status else "Mastery support move · always succeeds"
                lines.append(f"{prefix} **{move.name}** — {details} · unlocks at **{move.affection_required}**\n{state}. {move.special}")
            duel_lines = []
            for definition in MOVE_DEFINITIONS.values():
                duel_lines.append(move_detail(definition, available=True))
            casual_description = (
                f"**Your affection:** {affection:,}\n"
                f"**Current move:** {current_move.name}\n"
                f"{next_line}\n"
                f"**Unlock path:** {unlock_path}\n\n"
                + "\n\n".join(lines)
            )
            duel_description = (
                "All Tide Duel moves are available in `/vaporeon-duel`, regardless of affection; Tide and cooldowns still apply.\n\n"
                + "\n\n".join(duel_lines)
            )
            await interaction.response.send_message(
                embeds=[
                    self.embed("💧 Your Casual Splash Moves", casual_description),
                    self.embed("💦 Your Tide Duel Moves", duel_description),
                ],
                ephemeral=True,
            )

        @command(name="vaporeon-encounter", description="Have a charming Vaporeon encounter.")
        async def vaporeon(interaction: discord.Interaction) -> None:
            record_encounter(interaction.user.id, display_name=interaction.user.display_name)
            line, rarity = self.content.random_speak()
            mood, activity = random.choice(self.content.encounters["moods"]), random.choice(self.content.encounters["activities"])
            tier = friendship_level(get_user_stats(interaction.user.id).affection).name
            prefix = "✨ Legendary encounter! ✨\n" if rarity == "legendary" else ""
            text = line["text"] if line.get("quote", True) is False else f'“{line["text"]}”'
            embed = self.embed("💧 A wild Vaporeon appeared!", f"{prefix}{text}\n\n**Mood:** {mood}\n**Activity:** {activity}\n**Friendship:** {tier}{self.daily_bonus(interaction.user.id, interaction.user.display_name, 'encounter')}")
            photos = discover_photos()
            if photos:
                await interaction.response.send_message(embed=embed, file=discord.File(random.choice(photos).path))
            else:
                await interaction.response.send_message(embed=embed)

        @command(name="vaporeon-vibe", description="See today's Vaporeon vibe.")
        async def vibe(interaction: discord.Interaction) -> None:
            await interaction.response.send_message(embed=self.embed("💧 Today's Vaporeon vibe", f"**Mood:** {random.choice(self.content.encounters['moods'])}\n**Activity:** {random.choice(self.content.encounters['activities'])}\n**Energy:** {random.randint(1, 10)}/10"))

        @command(name="vaporeon-daily", description="Meet today's shared Vaporeon encounter.")
        async def daily(interaction: discord.Interaction) -> None:
            if interaction.guild_id is None:
                await interaction.response.send_message("Vaporeon's daily encounter is shared per server, so please use this in a server.", ephemeral=True)
                return
            record_encounter(interaction.user.id, display_name=interaction.user.display_name)
            today = game_day()
            participation, added_participation = record_daily_participation(interaction.user.id, today, display_name=interaction.user.display_name)
            line, _ = self.content.random_speak()
            created = {"text": line["text"], "mood": random.choice(self.content.encounters["moods"]), "activity": random.choice(self.content.encounters["activities"])}
            encounter = get_or_create_daily_encounter(interaction.guild_id, today, created)
            streak_line = f"**Shared-daily participation:** {participation.daily_participations} total · current streak **{participation.daily_current_streak}** · best **{participation.daily_best_streak}**" if added_participation else f"**Shared-daily participation:** already counted today · current streak **{participation.daily_current_streak}** · best **{participation.daily_best_streak}**"
            await interaction.response.send_message(embed=self.embed("💧 Today's Vaporeon encounter", f'“{encounter["text"]}”\n\n**Mood:** {encounter["mood"]}\n**Activity:** {encounter["activity"]}\n{streak_line}'))

        @command(name="vaporeon-dailyquest", description="See your daily Vaporeon quest for affection.")
        async def dailyquest(interaction: discord.Interaction) -> None:
            today = game_day()
            action, completed, created = get_or_create_daily_quest(interaction.user.id, today, random.choice(tuple(DAILY_QUESTS)))
            quest, command_name = DAILY_QUESTS[action]
            status = "**Completed ✓**" if completed else "Not completed yet"
            await interaction.response.send_message(embed=self.embed("🌟 Your Daily Vaporeon Quest", f"**Quest:** {quest}\nUse {command_name} to complete it.\n\n**Reward:** +{DAILY_QUEST_REWARD} affection\n**Status:** {status}"), ephemeral=True)
            if created and interaction.channel is not None:
                try:
                    name = discord.utils.escape_mentions(discord.utils.escape_markdown(interaction.user.display_name))
                    await interaction.channel.send(f"🌟 **{name}** received a Vaporeon daily quest: **{quest}** (+{DAILY_QUEST_REWARD} affection).")
                except discord.Forbidden:
                    pass

        @command(name="vaporeon-sleep", description="Hear a sleepy Vaporeon thought.")
        async def sleep(interaction: discord.Interaction) -> None:
            line, _ = self.content.random_speak("sleepy")
            await interaction.response.send_message(f"🌙 “{line['text']}”")

        @command(name="vaporeon-serverstats", description="See Vaporeon activity totals and leaderboards.")
        async def serverstats(interaction: discord.Interaction) -> None:
            totals = server_totals()
            embed = self.embed("💧 Vaporeon Server Stats", f"Friends: **{totals['friends']:,}** · Affection earned: **{totals['affection']:,}** · Cosmetic finds: **{discovery_count():,}**")
            embed.add_field(name="All activity", value=f"Pets: **{totals['pets']:,}** · Boops: **{totals['boops']:,}** · Feeds: **{totals['feeds']:,}**\nHugs: **{totals['hugs']:,}** · Splashes: **{totals['splashes']:,}** · Duels: **{totals['duels']:,}**\nEncounters: **{totals['encounters']:,}** · Photos: **{totals['photos']:,}** · Dives: **{totals['dives']:,}**\nPlays: **{totals['plays']:,}** · Daily quests: **{totals['quests']:,}**", inline=False)
            embed.add_field(name="🏆 Friendship Leaderboard", value=self.leaderboard_text("affection"), inline=False)
            embed.add_field(name="⚔️ Tide Duel Wins Leaderboard", value=self.leaderboard_text("duel_wins"), inline=False)
            for counter, title in (("pets", "🐾 Pets"), ("feeds", "🍓 Feeds"), ("boops", "👆 Boops"), ("hugs", "🤗 Hugs"), ("splashes", "💦 Splashes"), ("encounters", "✨ Encounters"), ("photos", "📸 Photos"), ("dives", "🌊 Dives"), ("plays", "🎲 Plays"), ("quests", "🌟 Quests")):
                embed.add_field(name=f"Top 3 — {title}", value=self.leaderboard_text(counter), inline=True)
            await interaction.response.send_message(embed=embed)

        @command(name="vaporeon-hack", description="Check or adjust affection (caretaker only).")
        @app_commands.describe(user="Trainer whose affection to check or adjust", amount="Signed affection change, for example 10 or -5; omit to check")
        async def hack(interaction: discord.Interaction, user: discord.User, amount: int | None = None) -> None:
            if self.owner_id is None or interaction.user.id != self.owner_id:
                await interaction.response.send_message("Only Vaporeon's caretaker can use this command.", ephemeral=True)
                return
            name = discord.utils.escape_mentions(discord.utils.escape_markdown(user.display_name))
            before = get_user_stats(user.id).affection
            if amount is None:
                await interaction.response.send_message(f"💧 **{name}** has **{before:,} affection**.", ephemeral=True)
                return
            if amount == 0:
                await interaction.response.send_message("Use a non-zero amount to adjust affection, or omit it to check the current total.", ephemeral=True)
                return
            after = adjust_affection(user.id, amount, display_name=user.display_name).affection
            applied = after - before
            if abs(applied) >= 25:
                flavor = random.choice(HACK_AFFECTION_MAJOR_GAIN_LINES if applied > 0 else HACK_AFFECTION_MAJOR_LOSS_LINES)
            else:
                flavor = random.choice(HACK_AFFECTION_GAIN_LINES if applied > 0 else HACK_AFFECTION_LOSS_LINES)
            await interaction.response.send_message(f"🛠️ {flavor}\n\n**{name}**'s affection: **{before:,} → {after:,}** ({applied:+d}).")

        @command(name="vaporeon-summon", description="Ask Vaporeon to make a special appearance (owner only).")
        async def summon(interaction: discord.Interaction) -> None:
            allowed = interaction.user.id == self.owner_id if self.owner_id else bool(getattr(interaction.user.guild_permissions, "administrator", False))
            if not allowed:
                await interaction.response.send_message("Only Vaporeon's caretaker can summon her.", ephemeral=True)
                return
            line, rarity = self.content.random_speak()
            prefix = "✨ Legendary appearance! ✨\n" if rarity == "legendary" else ""
            await interaction.response.send_message(embed=self.embed("💧 Vaporeon was summoned!", f'{prefix}“{line["text"]}”'))

    def _choose(self, candidates: list[dict]) -> tuple[dict, str]:
        from .rarity import choose_item_by_rarity
        return choose_item_by_rarity(candidates)
