"""Thin Discord slash-command layer for Vaporeon's personality."""

import os
import random
import time
from datetime import datetime, timezone

import discord
from discord import app_commands

from .constants import BOOP_OUTCOME_WEIGHTS, BOOP_COOLDOWN_SECONDS, FEED_COOLDOWN_SECONDS, INTERACTION_RARE_CHANCE, PET_COOLDOWN_SECONDS, WATER_BLUE
from .content import ContentError, ContentStore
from .database import claim_cooldown, get_or_create_daily_encounter, get_user_stats, record_boop, record_feed, record_pet, server_totals
from .friendship import build_progress_bar, friendship_level, progress_to_next_tier
from .logic import deterministic_rating, parse_options
from .photos import discover_photos
from .rarity import choose_weighted_item


class VaporeonCommands:
    def __init__(self, content: ContentStore, owner_id: int | None) -> None:
        self.content, self.owner_id = content, owner_id
        self.passive_last_response = 0.0

    def embed(self, title: str, description: str) -> discord.Embed:
        return discord.Embed(title=title, description=description, color=discord.Color(WATER_BLUE))

    async def check_cooldown(self, interaction: discord.Interaction, action: str, seconds: int) -> bool:
        remaining = claim_cooldown(interaction.user.id, action, seconds)
        if not remaining:
            return True
        minutes, leftover = divmod(remaining, 60)
        wait = f"{minutes}m {leftover}s" if minutes else f"{leftover}s"
        await interaction.response.send_message(f"💧 Vaporeon needs a little breather. Try again in **{wait}**.", ephemeral=True)
        return False

    def register(self, tree: app_commands.CommandTree[discord.Client]) -> None:
        @tree.command(name="vaporeon-help", description="See what Vaporeon can do.")
        async def help_command(interaction: discord.Interaction) -> None:
            embed = self.embed("💧 Vaporeon's Little Guide", "Vaporeon lives here for splashes, snacks, encouragement, and gentle silliness.")
            embed.add_field(name="Hang out", value="`/vaporeon-speak` · `/vaporeon-photo` · `/vaporeon-encounter` · `/vaporeon-vibe` · `/vaporeon-daily`", inline=False)
            embed.add_field(name="Interact", value="`/vaporeon-pet` · `/vaporeon-boop` · `/vaporeon-feed` · `/vaporeon-hug` · `/vaporeon-splash`", inline=False)
            embed.add_field(name="Ask and play", value="`/vaporeon-ask` · `/vaporeon-fortune` · `/vaporeon-rate` · `/vaporeon-choose`", inline=False)
            embed.add_field(name="Friendship", value="`/vaporeon-friendship` · `/vaporeon-serverstats`", inline=False)
            embed.set_footer(text="Pet and boop: every 5 minutes · Feed: every hour")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        @tree.command(name="vaporeon-speak", description="Hear a curated Vaporeon thought.")
        @app_commands.describe(mood="Optional mood, such as happy, sleepy, chaotic, or encouraging")
        async def speak(interaction: discord.Interaction, mood: str | None = None) -> None:
            try:
                line, rarity = self.content.random_speak(mood.casefold() if mood else None)
                prefix = "✨ Legendary Vaporeon response! ✨\n" if rarity == "legendary" else ""
                text = line["text"] if line.get("quote", True) is False else f'"{line["text"]}"'
                await interaction.response.send_message(embed=self.embed("💧 Vaporeon", f"{prefix}{text}"))
            except ContentError as error:
                await interaction.response.send_message(str(error), ephemeral=True)

        @tree.command(name="vaporeon-photo", description="See a random Vaporeon photo.")
        async def photo(interaction: discord.Interaction) -> None:
            photos = discover_photos()
            if not photos:
                await interaction.response.send_message("Vaporeon's photo album is empty here. Add images under `data/photos/` first.", ephemeral=True)
                return
            photo = random.choice(photos)
            await interaction.response.send_message("💧 Vaporeon photo", file=discord.File(photo.path))

        @tree.command(name="vaporeon-pet", description="Pet Vaporeon.")
        async def pet(interaction: discord.Interaction) -> None:
            if not await self.check_cooldown(interaction, "pet", PET_COOLDOWN_SECONDS): return
            reaction, rarity = self.content.random_reaction("pet")
            gain = 5 if rarity != "common" and random.random() < INTERACTION_RARE_CHANCE else 1
            stats = record_pet(interaction.user.id, gain)
            await interaction.response.send_message(embed=self.embed(f"💧 {interaction.user.display_name} pets Vaporeon", f'{reaction["text"]}\n\nAffection **+{gain}** · Total: **{stats.affection}**'))

        @tree.command(name="vaporeon-boop", description="Boop Vaporeon.")
        async def boop(interaction: discord.Interaction) -> None:
            if not await self.check_cooldown(interaction, "boop", BOOP_COOLDOWN_SECONDS): return
            outcome = choose_weighted_item(BOOP_OUTCOME_WEIGHTS, BOOP_OUTCOME_WEIGHTS.values())
            gain = 0 if outcome == "offended" else 1
            reaction, _ = self.content.random_reaction(f"boop_{outcome}")
            stats = record_boop(interaction.user.id, gain)
            await interaction.response.send_message(embed=self.embed("💧 Boop!", f'{reaction["text"]}\n\nAffection **+{gain}** · Boops: **{stats.boops}**'))

        @tree.command(name="vaporeon-feed", description="Give Vaporeon a snack.")
        async def feed(interaction: discord.Interaction, food: str | None = None) -> None:
            if not await self.check_cooldown(interaction, "feed", FEED_COOLDOWN_SECONDS): return
            reaction, rarity = self.content.random_reaction("feed")
            gain = 10 if rarity != "common" and random.random() < INTERACTION_RARE_CHANCE else 2
            stats = record_feed(interaction.user.id, gain)
            snack = food or "a tasty berry"
            await interaction.response.send_message(embed=self.embed("🍓 Snack time", f'You give Vaporeon **{snack}**.\n\n{reaction["text"]}\n\nAffection **+{gain}** · Feeds: **{stats.feeds}**'))

        @tree.command(name="vaporeon-hug", description="Give Vaporeon (or a friend) a friendly hug.")
        async def hug(interaction: discord.Interaction, user: discord.Member | None = None) -> None:
            reaction, _ = self.content.random_reaction("hug")
            target = user.mention if user else "you"
            await interaction.response.send_message(f"💧 Vaporeon wraps a fin around {target}.\n{reaction['text']}")

        @tree.command(name="vaporeon-splash", description="Splash someone harmlessly.")
        async def splash(interaction: discord.Interaction, user: discord.Member) -> None:
            reaction, _ = self.content.random_reaction("splash")
            await interaction.response.send_message(f"💦 Vaporeon splashes {user.mention}!\n{reaction['text']}")

        @tree.command(name="vaporeon-ask", description="Ask Vaporeon a magical question.")
        async def ask(interaction: discord.Interaction, question: str) -> None:
            answer = random.choice(self.content.ask)["text"]
            await interaction.response.send_message(embed=self.embed("💧 You ask Vaporeon", f'“{question}”\n\nVaporeon considers this carefully…\n\n“{answer}”'))

        @tree.command(name="vaporeon-fortune", description="Receive a small Vaporeon fortune.")
        async def fortune(interaction: discord.Interaction) -> None:
            await interaction.response.send_message(embed=self.embed("💧 Vaporeon's Fortune", f'“{random.choice(self.content.fortunes)["text"]}”'))

        @tree.command(name="vaporeon-rate", description="Have Vaporeon give something a playful rating.")
        async def rate(interaction: discord.Interaction, thing: str) -> None:
            rating = deterministic_rating(thing)
            category = "rate_low" if rating < 3 else "rate_mid" if rating < 7 else "rate_high"
            reaction, _ = self.content.random_reaction(category)
            await interaction.response.send_message(embed=self.embed(f"💧 Vaporeon rates {thing}", f"**{rating:.1f} / 10**\n\n“{reaction['text']}”"))

        @tree.command(name="vaporeon-choose", description="Let Vaporeon choose between options separated by |.")
        async def choose(interaction: discord.Interaction, options: str) -> None:
            try:
                choice = random.choice(parse_options(options))
            except ValueError as error:
                await interaction.response.send_message(str(error), ephemeral=True)
                return
            reaction, _ = self.content.random_reaction("choose")
            await interaction.response.send_message(embed=self.embed("💧 Vaporeon chooses…", f"**{choice}**\n\n{reaction['text']}"))

        @tree.command(name="vaporeon-friendship", description="See your friendship with Vaporeon.")
        async def friendship(interaction: discord.Interaction) -> None:
            stats = get_user_stats(interaction.user.id)
            tier = friendship_level(stats.affection)
            flavor = random.choice(self.content.friendship.get(tier.name, ["a lovely friend."]))
            embed = self.embed(f"💧 Vaporeon's Friendship with {interaction.user.display_name}", f"**Affection:** {stats.affection:,}\n**Level:** {tier.name}\n`{build_progress_bar(progress_to_next_tier(stats.affection))}`\n\nPets: **{stats.pets:,}** · Boops: **{stats.boops:,}** · Feeds: **{stats.feeds:,}**\n\nVaporeon thinks you are {flavor}")
            await interaction.response.send_message(embed=embed)

        @tree.command(name="vaporeon-encounter", description="Have a charming Vaporeon encounter.")
        async def vaporeon(interaction: discord.Interaction) -> None:
            line, rarity = self.content.random_speak()
            mood, activity = random.choice(self.content.encounters["moods"]), random.choice(self.content.encounters["activities"])
            tier = friendship_level(get_user_stats(interaction.user.id).affection).name
            prefix = "✨ Legendary encounter! ✨\n" if rarity == "legendary" else ""
            text = line["text"] if line.get("quote", True) is False else f'“{line["text"]}”'
            embed = self.embed("💧 A wild Vaporeon appeared!", f"{prefix}{text}\n\n**Mood:** {mood}\n**Activity:** {activity}\n**Friendship:** {tier}")
            photos = discover_photos()
            if photos:
                await interaction.response.send_message(embed=embed, file=discord.File(random.choice(photos).path))
            else:
                await interaction.response.send_message(embed=embed)

        @tree.command(name="vaporeon-vibe", description="See today's Vaporeon vibe.")
        async def vibe(interaction: discord.Interaction) -> None:
            await interaction.response.send_message(embed=self.embed("💧 Today's Vaporeon vibe", f"**Mood:** {random.choice(self.content.encounters['moods'])}\n**Activity:** {random.choice(self.content.encounters['activities'])}\n**Energy:** {random.randint(1, 10)}/10"))

        @tree.command(name="vaporeon-daily", description="Meet today's shared Vaporeon encounter.")
        async def daily(interaction: discord.Interaction) -> None:
            if interaction.guild_id is None:
                await interaction.response.send_message("Vaporeon's daily encounter is shared per server, so please use this in a server.", ephemeral=True)
                return
            line, _ = self.content.random_speak()
            created = {"text": line["text"], "mood": random.choice(self.content.encounters["moods"]), "activity": random.choice(self.content.encounters["activities"])}
            encounter = get_or_create_daily_encounter(interaction.guild_id, datetime.now(timezone.utc).date().isoformat(), created)
            await interaction.response.send_message(embed=self.embed("💧 Today's Vaporeon encounter", f'“{encounter["text"]}”\n\n**Mood:** {encounter["mood"]}\n**Activity:** {encounter["activity"]}'))

        @tree.command(name="vaporeon-sleep", description="Hear a sleepy Vaporeon thought.")
        async def sleep(interaction: discord.Interaction) -> None:
            line, _ = self.content.random_speak("sleepy")
            await interaction.response.send_message(f"🌙 “{line['text']}”")

        @tree.command(name="vaporeon-serverstats", description="See wholesome Vaporeon server totals.")
        async def serverstats(interaction: discord.Interaction) -> None:
            totals = server_totals()
            await interaction.response.send_message(embed=self.embed("💧 Vaporeon Server Stats", f"Friends made: **{totals['friends']:,}**\nTotal pets: **{totals['pets']:,}**\nTotal boops: **{totals['boops']:,}**\nBerries eaten: **{totals['feeds']:,}"))

        @tree.command(name="vaporeon-summon", description="Ask Vaporeon to make a special appearance (owner only).")
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
