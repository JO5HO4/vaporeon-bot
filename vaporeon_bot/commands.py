"""Thin Discord slash-command layer for Vaporeon's personality."""

import os
import random
import time
from datetime import datetime, timezone

import discord
from discord import app_commands

from .constants import BOOP_OUTCOME_WEIGHTS, BOOP_COOLDOWN_SECONDS, FEED_COOLDOWN_SECONDS, INTERACTION_RARE_CHANCE, PET_COOLDOWN_SECONDS, SPLASH_COOLDOWN_SECONDS, WATER_BLUE
from .content import ContentError, ContentStore
from .database import apply_splash_damage, claim_cooldown, complete_daily_quest, get_battle_hp, get_or_create_daily_encounter, get_or_create_daily_quest, get_user_stats, leaderboard, record_boop, record_encounter, record_feed, record_hug, record_pet, record_photo, record_quest, record_splash, server_totals
from .friendship import build_progress_bar, friendship_level, progress_to_next_tier
from .games import PlayView, random_scenario
from .logic import deterministic_rating, parse_options
from .photos import discover_photos
from .rarity import choose_weighted_item
from .splash import SPLASH_MOVES, next_splash, splash_by_name, unlocked_splash

PLAY_COOLDOWN_SECONDS = 10 * 60
DAILY_QUEST_REWARD = 5
DAILY_QUESTS = {
    "pet": ("Give Vaporeon a pet", "/vaporeon-pet"),
    "boop": ("Give Vaporeon a boop", "/vaporeon-boop"),
    "feed": ("Give Vaporeon a snack", "/vaporeon-feed"),
    "hug": ("Give Vaporeon a hug", "/vaporeon-hug"),
    "splash": ("Create a harmless splash", "/vaporeon-splash"),
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

    def personal_stats_embed(self, user_id: int, display_name: str) -> discord.Embed:
        stats = get_user_stats(user_id)
        tier = friendship_level(stats.affection)
        move, next_move = unlocked_splash(stats.affection), next_splash(stats.affection)
        flavor = random.choice(self.content.friendship.get(tier.name, ["a lovely friend."]))
        splash_status = f"**Splash move:** {move.name} ({move.fictional_damage} damage)\n**Battle HP:** {get_battle_hp(user_id)} / 100"
        if next_move:
            splash_status += f" · Next: {next_move.name} at {next_move.affection_required} affection"
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
            embed = self.embed("💧 Vaporeon's Little Guide", "Splashes, snacks, encouragement, and gentle silliness. Your private stats stay private; server leaderboards are public.")
            embed.add_field(name="Hang out", value="`/vaporeon-speak` · `/vaporeon-photo` · `/vaporeon-encounter`\n`/vaporeon-vibe` · `/vaporeon-daily` · `/vaporeon-sleep`", inline=False)
            embed.add_field(name="Interact", value="`/vaporeon-pet` · `/vaporeon-boop` · `/vaporeon-feed`\n`/vaporeon-hug` · `/vaporeon-splash`", inline=False)
            embed.add_field(name="Ask and play", value="`/vaporeon-ask` · `/vaporeon-fortune` · `/vaporeon-rate` · `/vaporeon-choose`\n`/vaporeon-play` — a 10-minute-cooldown mini encounter", inline=False)
            embed.add_field(name="Stats", value="`/vaporeon-stats` — your private friendship and activity stats\n`/vaporeon-serverstats` — totals and top-three leaderboards", inline=False)
            embed.add_field(name="Daily quest", value="`/vaporeon-dailyquest` — get one personal quest worth **+5 affection**", inline=False)
            embed.add_field(name="Special", value="`/vaporeon-summon` — caretaker only", inline=False)
            embed.set_footer(text="Pet + boop: every 5 minutes · Feed: every hour · Splash: every minute.")
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
            if not await self.check_cooldown(interaction, "splash", SPLASH_COOLDOWN_SECONDS):
                return
            reaction, _ = self.content.random_reaction("splash")
            effect, _ = self.content.random_reaction("splash_effect")
            record_splash(interaction.user.id, display_name=interaction.user.display_name)
            hit = apply_splash_damage(user.id, selected.fictional_damage)
            hp_line = f"**{hit.damage_dealt} damage!** {user.display_name}'s HP: **{hit.hp_before} → {hit.hp_after} / 100**"
            if hit.recovered:
                hp_line = f"{user.display_name} had recovered. {hp_line}"
            if hit.hp_after == 0:
                hp_line += "\n💫 **{0} fainted!** Their HP recovers after 30 minutes without a hit.".format(user.display_name)
            await interaction.response.send_message(f"💦 Vaporeon uses **{selected.name}** on {user.mention}!\n{hp_line}\n{reaction['text']}\n{effect['text']}{self.daily_bonus(interaction.user.id, interaction.user.display_name, 'splash')}")

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
            await interaction.response.send_message(embed=self.personal_stats_embed(interaction.user.id, interaction.user.display_name), ephemeral=True)

        @command(name="vaporeon-stats", description="See your private Vaporeon stats.")
        async def stats(interaction: discord.Interaction) -> None:
            await interaction.response.send_message(embed=self.personal_stats_embed(interaction.user.id, interaction.user.display_name), ephemeral=True)

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
