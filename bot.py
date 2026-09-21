"""Vaporeon's Discord entry point."""
import asyncio
import logging
import os
import random
import time

import discord
from dotenv import load_dotenv

from vaporeon_bot.commands import VaporeonCommands
from vaporeon_bot.content import ContentError, ContentStore
from vaporeon_bot.database import claim_due_respawn_notifications, get_faint_protection, initialize_database, unknown_user_ids, update_display_name

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
LOGGER = logging.getLogger("vaporeon_bot")
load_dotenv()


class VaporeonCommandTree(discord.app_commands.CommandTree):
    """Apply the post-faint command lockout to every Vaporeon slash command."""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.type is discord.InteractionType.autocomplete:
            return True
        if interaction.data and interaction.data.get("name") == "vaporeon-cd":
            return True
        expires = get_faint_protection(interaction.user.id)
        if expires is None:
            return True
        remaining = max(1, int((expires - discord.utils.utcnow()).total_seconds() // 60) + 1)
        await interaction.response.send_message(
            f"🫧 You were defeated by dampness and are resting on the cozy shore. Your **Recovery Bubble** ends in **{remaining} minutes**.",
            ephemeral=True,
        )
        return False


class VaporeonBot(discord.Client):
    def __init__(self, commands: VaporeonCommands, passive_enabled: bool, chance: float, cooldown: int) -> None:
        intents = discord.Intents.none()
        intents.message_content = passive_enabled
        super().__init__(intents=intents)
        self.tree = VaporeonCommandTree(self)
        self.commands_layer, self.passive_enabled, self.chance, self.cooldown = commands, passive_enabled, chance, cooldown
        self.respawn_task: asyncio.Task[None] | None = None

    async def setup_hook(self) -> None:
        initialize_database()
        refreshed_names = 0
        for user_id in unknown_user_ids():
            try:
                user = await self.fetch_user(user_id)
            except discord.HTTPException:
                continue
            update_display_name(user_id, user.display_name)
            refreshed_names += 1
        if refreshed_names:
            LOGGER.info("Backfilled %s historic Vaporeon display names.", refreshed_names)
        self.commands_layer.register(self.tree)
        @self.tree.error
        async def command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
            LOGGER.exception("Application command failed", exc_info=error)
            message = "Vaporeon got a little splashed up. Please try again in a moment."
            if interaction.response.is_done(): await interaction.followup.send(message, ephemeral=True)
            else: await interaction.response.send_message(message, ephemeral=True)
        guild_ids = os.getenv("TEST_GUILD_IDS", os.getenv("TEST_GUILD_ID", ""))
        guild_ids = [guild_id.strip() for guild_id in guild_ids.split(",") if guild_id.strip()]
        if guild_ids:
            for guild_id in guild_ids:
                guild = discord.Object(id=int(guild_id))
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
            LOGGER.info("Synced commands to test guilds: %s.", ", ".join(guild_ids))
        else:
            await self.tree.sync(); LOGGER.info("Synced global commands.")
        self.respawn_task = asyncio.create_task(self._announce_respawns())

    async def _announce_respawns(self) -> None:
        while not self.is_closed():
            for respawn in claim_due_respawn_notifications():
                try:
                    channel = self.get_channel(respawn.channel_id) or await self.fetch_channel(respawn.channel_id)
                    name = discord.utils.escape_mentions(discord.utils.escape_markdown(respawn.display_name))
                    await channel.send(f"🫧 **{name}** has returned from the Recovery Bubble at **100 HP**! Vaporeon offers a welcoming splash.")
                except discord.HTTPException:
                    LOGGER.warning("Could not announce Vaporeon respawn for user %s", respawn.user_id)
            await asyncio.sleep(15)

    async def close(self) -> None:
        if self.respawn_task:
            self.respawn_task.cancel()
        await super().close()

    async def on_message(self, message: discord.Message) -> None:
        if not self.passive_enabled or message.author.bot or "vaporeon" not in message.content.casefold(): return
        if time.monotonic() - self.commands_layer.passive_last_response < self.cooldown or random.random() >= self.chance: return
        line, _ = self.commands_layer.content.random_speak()
        await message.channel.send(f"💧 {line['text']}")
        self.commands_layer.passive_last_response = time.monotonic()


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token: raise RuntimeError("DISCORD_TOKEN is missing; see .env.example.")
    try: content = ContentStore.load()
    except ContentError as error: raise RuntimeError(f"Content validation failed: {error}") from error
    owner = int(os.environ["OWNER_ID"]) if os.getenv("OWNER_ID", "").isdigit() else None
    enabled = os.getenv("PASSIVE_RESPONSES_ENABLED", "false").casefold() == "true"
    bot = VaporeonBot(VaporeonCommands(content, owner), enabled, float(os.getenv("PASSIVE_RESPONSE_CHANCE", "0.01")), int(os.getenv("PASSIVE_COOLDOWN_SECONDS", "600")))
    bot.run(token)

if __name__ == "__main__": main()
