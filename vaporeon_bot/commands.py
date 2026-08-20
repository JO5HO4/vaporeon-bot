"""Thin Discord slash-command layer for Vaporeon's personality."""

import os
import random
import time
from datetime import datetime, timezone

import discord
from discord import app_commands

from .constants import BOOP_OUTCOME_WEIGHTS, BOOP_COOLDOWN_SECONDS, FEED_COOLDOWN_SECONDS, INTERACTION_RARE_CHANCE, PET_COOLDOWN_SECONDS, SPLASH_COOLDOWN_SECONDS, WATER_BLUE
from .content import ContentError, ContentStore
from .database import apply_battle_status, apply_splash_damage, claim_cooldown, complete_daily_quest, consume_battle_status, get_active_status_details, get_battle_card, get_faint_protection, get_or_create_daily_encounter, get_or_create_daily_quest, get_user_stats, get_weather, leaderboard, recent_battle_history, record_battle_miss, record_boop, record_encounter, record_feed, record_hug, record_pet, record_photo, record_quest, record_splash, server_totals, start_rain
from .friendship import build_progress_bar, friendship_level, progress_to_next_tier
from .games import PlayView, random_scenario
from .logic import deterministic_rating, parse_options
from .photos import discover_photos
from .rarity import choose_weighted_item
from .splash import FAINT_MESSAGES, SPLASH_MOVES, next_splash, splash_by_name, unlocked_splash

PLAY_COOLDOWN_SECONDS = 10 * 60
DAILY_QUEST_REWARD = 5
RAIN_CHANCE = 0.05
SLIPPERY_MISS_CHANCE = 0.35
DAILY_QUESTS = {
    "pet": ("Give Vaporeon a pet", "/vaporeon-pet"),
    "boop": ("Give Vaporeon a boop", "/vaporeon-boop"),
    "feed": ("Give Vaporeon a snack", "/vaporeon-feed"),
    "hug": ("Give Vaporeon a hug", "/vaporeon-hug"),
    "splash": ("Use a Vaporeon water move", "/vaporeon-splash"),
    "encounter": ("Have a Vaporeon encounter", "/vaporeon-encounter"),
    "photo": ("Look at a Vaporeon photo", "/vaporeon-photo"),
}


class VaporeonCommands:
    def __init__(self, content: ContentStore, owner_id: int | None) -> None:
        self.content, self.owner_id = content, owner_id
        self.passive_last_response = 0.0

    def embed(self, title: str, description: str) -> discord.Embed:
        return discord.Embed(title=title, description=description, color=discord.Color(WATER_BLUE))

    @staticmethod
    def leaderboard_text(counter: str) -> str:
        entries = leaderboard(counter)
        if not entries:
            return "No entries yet. Be the first!"
        medals = ("🥇", "🥈", "🥉")
        return "\n".join(
            f"{medals[index]} {discord.utils.escape_mentions(discord.utils.escape_markdown(name))} — **{count:,}**"
            for index, (name, count) in enumerate(entries)
        )

    def personal_stats_embed(self, user_id: int, display_name: str, guild_id: int | None = None) -> discord.Embed:
        stats = get_user_stats(user_id)
        tier = friendship_level(stats.affection)
        move, next_move = unlocked_splash(stats.affection), next_splash(stats.affection)
        flavor = random.choice(self.content.friendship.get(tier.name, ["a lovely friend."]))
        battle = get_battle_card(user_id)
        now = datetime.now(timezone.utc)
        statuses = get_active_status_details(user_id, now=now)
        status_line = ", ".join(f"{status.title()} ({max(0, int((expires - now).total_seconds() // 60))}m)" for status, expires in sorted(statuses.items())) if statuses else "None"
        attacker = discord.utils.escape_mentions(discord.utils.escape_markdown(battle.last_attacker)) if battle.last_attacker else "None yet"
        last_move = battle.last_move or "None yet"
        weather = get_weather(guild_id)
        weather_line = "Rainy (+15% water damage)" if weather else "Clear"
        protection_line = f" · Rescue Bubble: **{max(0, int((battle.protection_until - now).total_seconds() // 60))}m**" if battle.protection_until else ""
        history = recent_battle_history(user_id)
        history_line = "\n".join(f"• {event.attacker_name}: {event.move_name} — {event.outcome}{f' ({event.damage} damage)' if event.damage else ''}" for event in history) if history else "No splashes received yet."
        splash_status = (
            "**Battle card**\n"
            f"HP: **{battle.hp} / 100**{protection_line}\n"
            f"Wins: **{battle.wins}** · Losses: **{battle.losses}** · Streak: **{battle.current_streak}** (best {battle.best_streak})\n"
            f"Unlocked move: **{move.name}** ({move.fictional_damage} damage · {move.accuracy:.0%} accuracy)\n"
            f"Splashes: **{stats.splashes:,}** · Hits: **{battle.hits}** · Misses: **{battle.misses}** · Crits: **{battle.critical_hits}**\n"
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
            f"`{build_progress_bar(progress_to_next_tier(stats.affection))}`\n\n"
            f"Pets: **{stats.pets:,}** · Boops: **{stats.boops:,}** · Feeds: **{stats.feeds:,}**\n"
            f"Hugs: **{stats.hugs:,}** · Splashes: **{stats.splashes:,}**\n"
            f"Encounters: **{stats.encounters:,}** · Photos: **{stats.photos:,}**\n"
            f"Plays: **{stats.plays:,}** · Daily quests: **{stats.quests:,}**\n\n"
            f"{splash_status}\n\n"
            f"Vaporeon thinks you are {flavor}",
        )

    def daily_bonus(self, user_id: int, display_name: str, action: str) -> str:
        today = datetime.now(timezone.utc).date().isoformat()
        if not complete_daily_quest(user_id, action, today):
            return ""
        stats = record_quest(user_id, DAILY_QUEST_REWARD, display_name=display_name)
        return f"\n🌟 **{display_name} completed their daily quest!** Affection **+{DAILY_QUEST_REWARD}** · Quests: **{stats.quests:,}**"

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

        async def splash_move_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
            needle = current.casefold()
            return [
                app_commands.Choice(name=f"{move.name} · unlocks at {move.affection_required} affection", value=move.name)
                for move in SPLASH_MOVES
                if needle in move.name.casefold()
            ][:25]

        @command(name="vaporeon-help", description="See what Vaporeon can do.")
        async def help_command(interaction: discord.Interaction) -> None:
            embed = self.embed("💧 Vaporeon's Complete Guide", "A cozy friendship bot with playful water battles. Your personal stats and move list are private; shared activities and server leaderboards are public.")
            embed.add_field(
                name="💙 How to earn affection",
                value=(
                    "`/vaporeon-pet` — **+1** affection; occasional **+5** · 5-minute cooldown\n"
                    "`/vaporeon-boop` — usually **+1** (sometimes 0) · 5-minute cooldown\n"
                    "`/vaporeon-feed` — **+2** affection; occasional **+10** · 1-hour cooldown\n"
                    "`/vaporeon-play` — **+2–3** affection · 10-minute cooldown\n"
                    "`/vaporeon-dailyquest` — one task per day for **+5** affection"
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
                    "`/vaporeon-splash @user [move]` — 3-minute personal cooldown. Moves unlock at affection **0 → 10 → 25 → 50 → 100 → 200 → 300 → 500 → 750 → 1,000**.\n"
                    "Targets have 100 HP and fully recover after 30 minutes without a hit. Fainting gives the attacker a win and the target a 15-minute Rescue Bubble.\n"
                    "Moves can miss, crit, cause statuses, and get a boost from rare Rainy weather. Splashing, hugs, photos, and encounters are tracked, but do **not** themselves grant affection."
                ),
                inline=False,
            )
            embed.add_field(
                name="📊 Your progress",
                value="`/vaporeon-stats` — private friendship and battle card\n`/vaporeon-friendship` — same private progress view\n`/vaporeon-moves` — private move stats, effects, and unlocks\n`/vaporeon-serverstats` — public server totals and top-three leaderboards",
                inline=False,
            )
            embed.add_field(
                name="🌟 Daily and shared content",
                value="`/vaporeon-dailyquest` — receive/check your private daily task; assignment and completion are announced in the channel\n`/vaporeon-daily` — the server's shared daily encounter",
                inline=False,
            )
            embed.add_field(name="🫧 Special", value="`/vaporeon-summon` — caretaker-only special appearance", inline=False)
            embed.set_footer(text="Vaporeon is here for snacks, naps, and extremely serious water-balloon battles.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
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
            gain = 0 if outcome == "offended" else 1
            reaction, _ = self.content.random_reaction(f"boop_{outcome}")
            stats = record_boop(interaction.user.id, gain, display_name=interaction.user.display_name)
            await interaction.response.send_message(embed=self.embed("💧 Boop!", f'{reaction["text"]}\n\nAffection **+{gain}** · Boops: **{stats.boops}**{self.daily_bonus(interaction.user.id, interaction.user.display_name, "boop")}'))

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

        @command(name="vaporeon-splash", description="Use your unlocked playful Vaporeon water move.")
        @app_commands.describe(move="Optional unlocked water move; defaults to your strongest")
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
            protection = get_faint_protection(user.id)
            if protection:
                minutes = max(1, int((protection - datetime.now(timezone.utc)).total_seconds() // 60) + 1)
                await interaction.response.send_message(f"🫧 Vaporeon has placed {user.mention} inside a **Rescue Bubble** after their faint. Try again in **{minutes} minutes**.", ephemeral=True)
                return
            if not await self.check_cooldown(interaction, "splash", SPLASH_COOLDOWN_SECONDS):
                return
            reaction, _ = self.content.random_reaction("splash")
            record_splash(interaction.user.id, display_name=interaction.user.display_name)
            weather = get_weather(interaction.guild_id)
            rain_started = False
            if weather is None and random.random() < RAIN_CHANCE:
                weather = start_rain(interaction.guild_id)
                rain_started = weather is not None

            target_card = get_battle_card(user.id)
            soaked_bonus = consume_battle_status(interaction.user.id, "soaked")
            slippery = False if selected.ignores_slippery else consume_battle_status(user.id, "slippery")
            slippery_miss = slippery and random.random() < SLIPPERY_MISS_CHANCE
            accuracy_miss = not slippery_miss and random.random() > selected.accuracy
            opener = f"💦 Vaporeon uses **{selected.name}** on {user.mention}!"
            weather_line = "\n🌧️ **Rainy weather began!** Water moves deal **+15% damage** in this server for one hour." if rain_started else ""
            bonus = self.daily_bonus(interaction.user.id, interaction.user.display_name, "splash")
            if slippery_miss or accuracy_miss:
                reason = f"{user.display_name} was slippery and evaded it!" if slippery_miss else f"**{selected.name}** missed!"
                soaked_line = " The Soaked boost splashed harmlessly away." if soaked_bonus else ""
                record_battle_miss(interaction.user.id, user.id, interaction.user.display_name, selected.name)
                await interaction.response.send_message(f"{opener}\n💨 {reason}{soaked_line}\n{reaction['text']}{weather_line}{bonus}")
                return

            critical = random.random() < selected.critical_chance
            multiplier = 1.5 if critical else 1.0
            modifiers: list[str] = []
            if critical:
                modifiers.append("✨ Critical hit ×1.5")
            if soaked_bonus:
                multiplier *= 1.10
                modifiers.append("💧 Soaked boost +10%")
            if weather:
                multiplier *= selected.rain_multiplier
                modifiers.append(f"🌧️ Rain boost +{(selected.rain_multiplier - 1) * 100:.0f}%")
            if target_card.hp <= 50 and selected.low_hp_multiplier > 1:
                multiplier *= selected.low_hp_multiplier
                modifiers.append(f"🧂 Brine bonus +{(selected.low_hp_multiplier - 1) * 100:.0f}%")
            damage = max(1, round(selected.fictional_damage * multiplier))
            hit = apply_splash_damage(
                user.id,
                damage,
                attacker_id=interaction.user.id,
                attacker_name=interaction.user.display_name,
                move_name=selected.name,
                critical=critical,
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
                status_line = f"\n💦 **{user.display_name} is {selected.status.title()}** for 5 minutes — {status_descriptions[selected.status]}."
            modifier_line = f"\n{' · '.join(modifiers)}" if modifiers else ""
            revenge_line = "\n⚔️ **REVENGE SPLASH!**" if target_card.last_attacker and target_card.last_attacker.casefold() == interaction.user.display_name.casefold() else ""
            if hit.fainted:
                hp_line += f"\n💫 **{user.display_name} {random.choice(FAINT_MESSAGES)}** HP recovers after 30 minutes without a hit."
                hp_line += " A **Rescue Bubble** protects them from splashes for 15 minutes."
            await interaction.response.send_message(f"{opener}{revenge_line}\n{hp_line}{modifier_line}{status_line}\n{reaction['text']}\n{effect['text']}{weather_line}{bonus}")

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
            embed = self.embed("💧 Vaporeon Play", f"{scenario['prompt']}\n\nChoose what to do. Each choice earns **2–3 affection**.")
            await interaction.response.send_message(embed=embed, view=PlayView(interaction.user.id, interaction.user.display_name, scenario))

        @command(name="vaporeon-friendship", description="See your friendship with Vaporeon.")
        async def friendship(interaction: discord.Interaction) -> None:
            await interaction.response.send_message(embed=self.personal_stats_embed(interaction.user.id, interaction.user.display_name, interaction.guild_id), ephemeral=True)

        @command(name="vaporeon-stats", description="See your private Vaporeon stats.")
        async def stats(interaction: discord.Interaction) -> None:
            await interaction.response.send_message(embed=self.personal_stats_embed(interaction.user.id, interaction.user.display_name, interaction.guild_id), ephemeral=True)

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
                lines.append(f"{prefix} **{move.name}** — {move.fictional_damage} damage · {move.accuracy:.0%} accuracy · unlocks at **{move.affection_required}**\n{state}. {move.special}")
            description = (
                f"**Your affection:** {affection:,}\n"
                f"**Current move:** {current_move.name}\n"
                f"{next_line}\n"
                f"**Unlock path:** {unlock_path}\n\n"
                + "\n\n".join(lines)
            )
            await interaction.response.send_message(embed=self.embed("💧 Your Vaporeon Moves", description), ephemeral=True)

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
            line, _ = self.content.random_speak()
            created = {"text": line["text"], "mood": random.choice(self.content.encounters["moods"]), "activity": random.choice(self.content.encounters["activities"])}
            encounter = get_or_create_daily_encounter(interaction.guild_id, datetime.now(timezone.utc).date().isoformat(), created)
            await interaction.response.send_message(embed=self.embed("💧 Today's Vaporeon encounter", f'“{encounter["text"]}”\n\n**Mood:** {encounter["mood"]}\n**Activity:** {encounter["activity"]}'))

        @command(name="vaporeon-dailyquest", description="See your daily Vaporeon quest for affection.")
        async def dailyquest(interaction: discord.Interaction) -> None:
            today = datetime.now(timezone.utc).date().isoformat()
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
            embed = self.embed("💧 Vaporeon Server Stats", f"Friends: **{totals['friends']:,}** · Affection earned: **{totals['affection']:,}**")
            embed.add_field(name="All activity", value=f"Pets: **{totals['pets']:,}** · Boops: **{totals['boops']:,}** · Feeds: **{totals['feeds']:,}**\nHugs: **{totals['hugs']:,}** · Splashes: **{totals['splashes']:,}**\nEncounters: **{totals['encounters']:,}** · Photos: **{totals['photos']:,}**\nPlays: **{totals['plays']:,}** · Daily quests: **{totals['quests']:,}**", inline=False)
            embed.add_field(name="🏆 Friendship Leaderboard", value=self.leaderboard_text("affection"), inline=False)
            for counter, title in (("pets", "🐾 Pets"), ("feeds", "🍓 Feeds"), ("boops", "👆 Boops"), ("hugs", "🤗 Hugs"), ("splashes", "💦 Splashes"), ("encounters", "✨ Encounters"), ("photos", "📸 Photos"), ("plays", "🎲 Plays"), ("quests", "🌟 Quests")):
                embed.add_field(name=f"Top 3 — {title}", value=self.leaderboard_text(counter), inline=True)
            await interaction.response.send_message(embed=embed)

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
