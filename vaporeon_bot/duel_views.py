"""Discord presentation for Tide Duels; all combat facts come from duels.py."""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable

import discord

from .database import record_tide_duel_result
from .duels import DuelState, Move, MOVE_DEFINITIONS, move_detail


def duel_embed(state: DuelState, result: str = "") -> discord.Embed:
    return discord.Embed(title="💦 Vaporeon Tide Duel", description=(f"{result}\n\n" if result else "") + state.card_text(), color=discord.Color.blue())


def round_results_embed(result: str) -> discord.Embed:
    return discord.Embed(title="💦 Tide Duel — Round Results", description=result, color=discord.Color.blue())


def final_results_embed(state: DuelState, result: str, winner_id: int | None) -> discord.Embed:
    if winner_id is None:
        outcome = "**Result: Draw** — both duelists reached 0 HP on the same round."
    else:
        winner = state.player(winner_id)
        outcome = f"🏆 **{winner.name} wins the Tide Duel!**\n💧 Vaporeon declares **{winner.name}** extremely splashworthy."
    summary = (f"{outcome}\n\n**Final state**\n"
               f"**{state.challenger.name}:** {state.challenger.hp}/100 HP · {state.challenger.tide}/100 Tide\n"
               f"**{state.opponent.name}:** {state.opponent.hp}/100 HP · {state.opponent.tide}/100 Tide\n\n"
               f"**Final round**\n{result}")
    return discord.Embed(title="🏆 Tide Duel Complete", description=summary, color=discord.Color.gold())


def rules_embed() -> discord.Embed:
    table = "\n".join(f"{d.move.value}: {d.damage} dmg · {'auto' if d.accuracy is None else f'{d.accuracy:.0%}'} · Tide {'+' if d.tide_change >= 0 else ''}{d.tide_change} · CD {'none' if not d.cooldown_rounds else d.cooldown_rounds}" for d in MOVE_DEFINITIONS.values())
    return discord.Embed(title="💦 Tide Duel Rules", description=("Each player starts at **100 HP** and **25 Tide**. A coin flip chooses the Round 1 first player; first-picker order then alternates. Choices stay hidden until both lock, but the first player's move resolves fully before the responder's move. If the responder is knocked out, their selected move does not resolve—there are no simultaneous-KO ties.\n\nWeak moves build Tide; strong moves spend Tide. Tide costs and cooldowns apply even on misses. Cooldowns are measured in duel rounds. No generic critical hits.\n\n**Round weather** — every round has a 50% chance of one public, symmetrical effect: Rain (+20% damage), Drizzle (+15 Tide from builders), Low Tide (+15 Tide costs), Mist (−15 accuracy), or Perfect Puddle Weather (cosmetic only).\n\n**Ripple Effects & statuses**\nGentle Splash has a 15% random Ripple Effect; Water Gun and Aqua Jet may apply Drenched, Bubble Beam may apply Soaked, Muddy Water may apply Slippery, and Surf may apply cosmetic Waterlogged.\n**Soaked:** next successful outgoing damaging move +10%; misses keep it. **Slippery:** next incoming damaging attack loses 35 accuracy points. **Drenched:** next successful incoming hit +15% damage. **Foamy:** next incoming damaging hit −25% damage. **Waterlogged:** no effect.\n**Water Veil:** reduces incoming damage only after it has resolved first that round, rounded down. **Rain Dance:** starts 3 symmetrical Rain rounds; all damaging moves deal +15%.\n\nLast four revealed moves are public. The responding player gets one private Ripple Read after the first move locks.\n\n**Move table**\n" + table), color=discord.Color.blue())


def move_panel_embed(state: DuelState, user_id: int) -> discord.Embed:
    player = state.player(user_id)
    opponent = state.other(user_id)
    own_status = ", ".join(status.value for status in sorted(player.statuses, key=str)) or "None"
    enemy_status = ", ".join(status.value for status in sorted(opponent.statuses, key=str)) or "None"
    order = "You choose **first** this round. Ripple Read is reserved for the responder." if state.first_picker_id == user_id else "You respond **second** this round. Once the first move locks, you may use Ripple Read before choosing."
    weather = state.weather_definition()
    weather_text = f"{weather.emoji} **{weather.weather.value}:** {weather.description}" if weather else "Clear — no round-weather modifier."
    rain_dance = "inactive" if not state.rain_rounds_remaining else f"+15% damage for {state.rain_rounds_remaining} rounds"
    header = f"**State — Round {state.round_number}**\n\n**You**\nHP: **{player.hp}/100** · Tide: **{player.tide}/100** · Status: **{own_status}**\n\n**Opponent**\nHP: **{opponent.hp}/100** · Tide: **{opponent.tide}/100** · Status: **{enemy_status}**\n\n**Round weather:** {weather_text}\n**Rain Dance:** {rain_dance}\n\n{order}\n\nChoose from the dropdown. Use **View move details** for every move's exact damage, accuracy, Tide, cooldown, and status rules."
    embed = discord.Embed(title="💦 Choose your Tide Duel move", description=header, color=discord.Color.blue())
    embed.add_field(name="Possible statuses", value="**Soaked:** next successful damaging move +10%. **Slippery:** next incoming attack −35 accuracy.\n**Drenched:** next successful incoming hit +15% damage. **Foamy:** next incoming hit −25% damage.\n**Waterlogged:** no mechanical effect.", inline=False)
    return embed


def move_details_embed(state: DuelState, user_id: int) -> discord.Embed:
    player = state.player(user_id)
    details = []
    for move, definition in MOVE_DEFINITIONS.items():
        available, reason = state.availability(player, move)
        details.append(move_detail(definition, available=available, reason=reason))
    return discord.Embed(title=f"📖 Tide Duel move details — Round {state.round_number}", description="\n\n".join(details), color=discord.Color.blue())


class DuelChallengeView(discord.ui.View):
    def __init__(self, challenger_id: int, opponent_id: int, on_accept: Callable[[], DuelState], release: Callable[[], None]) -> None:
        super().__init__(timeout=60); self.challenger_id, self.opponent_id, self.on_accept, self.release = challenger_id, opponent_id, on_accept, release; self.message: discord.Message | None = None
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.opponent_id: return True
        await interaction.response.send_message("This Tide Duel invitation is for someone else.", ephemeral=True); return False
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        try: state = self.on_accept()
        except ValueError as error: await interaction.response.send_message(str(error), ephemeral=True); return
        first = state.player(state.first_picker_id)
        self.stop(); await interaction.response.edit_message(embed=duel_embed(state, f"⚔️ **Tide Duel accepted!** 🎲 Coin flip: **{first.name}** chooses and resolves first in Round 1. Press **Choose move** for your private panel."), view=DuelView(state, self.release, interaction.message))
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.release(); self.stop(); await interaction.response.edit_message(content="💧 The Tide Duel invitation dissolves into a peaceful puddle.", embed=None, view=None)
    async def on_timeout(self) -> None:
        self.release()
        if self.message: await self.message.edit(content="💧 The Tide Duel invitation expired before the water could settle.", view=None)


class DuelView(discord.ui.View):
    def __init__(self, state: DuelState, release: Callable[[], None], message: discord.Message | None = None) -> None:
        super().__init__(timeout=120); self.state, self.release, self.message = state, release, message
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id in {self.state.challenger.user_id, self.state.opponent.user_id}: return True
        await interaction.response.send_message(f"This Tide Duel belongs to {self.state.challenger.name} and {self.state.opponent.name}. Start your own with /vaporeon-duel.", ephemeral=True); return False
    @discord.ui.button(label="Choose move", style=discord.ButtonStyle.primary)
    async def choose_move(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if self.state.has_locked(interaction.user.id): await interaction.response.send_message("Your move is already locked for this round.", ephemeral=True); return
        if not self.state.selections and interaction.user.id != self.state.first_picker_id:
            await interaction.response.send_message(f"Wait for **{self.state.player(self.state.first_picker_id).name}** to choose first this round.", ephemeral=True); return
        await interaction.response.send_message(embed=move_panel_embed(self.state, interaction.user.id), view=MovePanel(self.state, self.release, interaction.message, interaction.user.id, self), ephemeral=True)
    @discord.ui.button(label="💧 Ripple Read", style=discord.ButtonStyle.secondary)
    async def ripple_read(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        async with self.state.lock:
            try: clue = self.state.use_ripple_read(interaction.user.id)
            except ValueError as error: await interaction.response.send_message(str(error), ephemeral=True); return
            await interaction.response.send_message("💧 **Vaporeon studies the ripples…**\n\n" + f'“{clue.flavor}”\n\n**Known properties:**\n' + "\n".join(f"• {line}" for line in clue.properties) + "\n\n**Possible moves:**\n" + "\n".join(f"• **{move.value}**" for move in clue.possible_moves) + "\n\nThis clue is private.", ephemeral=True)
            reader = self.state.player(interaction.user.id)
            await interaction.message.channel.send(f"💧 **{reader.name}** used Ripple Read. The clue is private.")
            await interaction.message.edit(embed=duel_embed(self.state), view=DuelView(self.state, self.release, interaction.message)); self.stop()
    @discord.ui.button(label="📖 Full Rules", style=discord.ButtonStyle.secondary)
    async def rules(self, interaction: discord.Interaction, _: discord.ui.Button) -> None: await interaction.response.send_message(embed=rules_embed(), ephemeral=True)
    async def on_timeout(self) -> None:
        self.release()
        if self.message and not self.state.finished: await self.message.edit(content="💧 The ripples have gone still. The Tide Duel ended because a move was not selected in time.", embed=None, view=None)


class MoveSelect(discord.ui.Select):
    def __init__(self, state: DuelState, user_id: int) -> None:
        player = state.player(user_id); options = []
        for move, definition in MOVE_DEFINITIONS.items():
            legal, _ = state.availability(player, move)
            if not legal:
                continue
            tide_change = state.effective_tide_change(definition)
            tide = f"+{tide_change}" if tide_change >= 0 else str(tide_change)
            status = f" • {definition.status_chance:.0%} {definition.status.value}" if definition.status else ""
            accuracy = state.effective_accuracy(definition)
            options.append(discord.SelectOption(label=move.value, value=move.name, description=f"{definition.damage} dmg • {'auto' if accuracy is None else f'{accuracy:.0%}'} • Tide {tide}{status}", default=False))
        super().__init__(placeholder="Select a legal move", options=options)
    async def callback(self, interaction: discord.Interaction) -> None:
        if isinstance(self.view, MovePanel): await self.view.commit(interaction, Move[self.values[0]])


class MovePanel(discord.ui.View):
    def __init__(self, state: DuelState, release: Callable[[], None], public_message: discord.Message, owner_id: int, public_view: DuelView) -> None:
        super().__init__(timeout=120); self.state, self.release, self.public_message, self.owner_id, self.public_view = state, release, public_message, owner_id, public_view; self.add_item(MoveSelect(state, owner_id)); self.add_item(MoveDetailsButton())
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id: return True
        await interaction.response.send_message("This private move panel belongs to another duelist.", ephemeral=True); return False
    async def commit(self, interaction: discord.Interaction, move: Move) -> None:
        async with self.state.lock:
            try: update = self.state.lock_move(interaction.user.id, move)
            except ValueError as error: await interaction.response.send_message(str(error), ephemeral=True); return
            await interaction.response.edit_message(content=f"🔒 You locked in **{move.value}**. " + ("Waiting for the other duelist…" if not update.round_resolved else "Both moves are now revealed."), embed=None, view=None)
            self.public_view.stop()
            await self.public_message.edit(view=None)
            announcement = f"🔒 **{self.state.player(interaction.user.id).name}** has selected a move."
            cpu_just_selected = False
            if not update.round_resolved:
                cpu_update = self.state.lock_cpu_move()
                if cpu_update is not None:
                    update = cpu_update
                    cpu_just_selected = True
            if update.finished:
                first, second = self.state.challenger, self.state.opponent
                if update.draw:
                    record_tide_duel_result(None, first, second)
                    final = update.text
                else:
                    winner, loser = self.state.player(update.winner_id or 0), self.state.other(update.winner_id or 0)
                    record_tide_duel_result(winner.user_id, first, second)
                    final = update.text
                cpu = self.state.cpu_player()
                if cpu and cpu_just_selected:
                    announcement += f"\n🔒 **{cpu.name}** has selected a move."
                await self.public_message.channel.send(content=announcement)
                self.release(); await self.public_message.channel.send(embed=final_results_embed(self.state, final, update.winner_id)); return
            if update.round_resolved:
                cpu = self.state.cpu_player()
                if cpu and cpu_just_selected:
                    announcement += f"\n🔒 **{cpu.name}** has selected a move."
                await self.public_message.channel.send(content=announcement)
                await self.public_message.channel.send(embed=round_results_embed(update.text))
                cpu_next = self.state.lock_cpu_move()
                if cpu_next is not None:
                    first = self.state.player(self.state.first_picker_id)
                    responder = self.state.other(first.user_id)
                    next_announcement = f"🔒 **{self.state.cpu_player().name}** has selected a move.\n**{responder.name}**, choose your responding move."
                else:
                    first = self.state.player(self.state.first_picker_id)
                    next_announcement = f"💦 **Round {self.state.round_number} begins.** **{first.name}**, choose your move first."
                next_embed = duel_embed(self.state)
            else:
                responder = self.state.other(interaction.user.id)
                announcement += f"\n**{responder.name}**, choose your responding move."
                next_announcement = announcement
                next_embed = duel_embed(self.state)
            next_view = DuelView(self.state, self.release)
            next_message = await self.public_message.channel.send(content=next_announcement, embed=next_embed, view=next_view)
            next_view.message = next_message


class MoveDetailsButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="View move details", style=discord.ButtonStyle.secondary, row=1)
    async def callback(self, interaction: discord.Interaction) -> None:
        if isinstance(self.view, MovePanel):
            await interaction.response.send_message(embed=move_details_embed(self.view.state, interaction.user.id), ephemeral=True)
