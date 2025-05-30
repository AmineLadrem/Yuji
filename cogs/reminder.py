import os
import csv
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from zoneinfo import ZoneInfo 

COMMON_TIMEZONES = [
    "UTC", "Europe/London", "Europe/Paris",
    "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
    "Asia/Tokyo", "Asia/Shanghai", "Asia/Kolkata", "Australia/Sydney",
]
FREQ_OPTIONS = ["none", "daily", "weekly", "monthly", "yearly"]

CSV_PATH = "reminders.csv"
FIELDNAMES = [
    "id", "user_id", "name",
    "remind_utc",  
    "tz",         
    "details", "freq",
]

class Reminder(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if not os.path.isfile(CSV_PATH):
            with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=FIELDNAMES).writeheader()
        else:
            with open(CSV_PATH, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if "remind_time" in reader.fieldnames:
                    old_rows = list(reader)
                    new_rows = []
                    for r in old_rows:
                        new_rows.append({
                            "id":         r["id"],
                            "user_id":    r["user_id"],
                            "name":       r["name"],
                            "remind_utc": r["remind_time"],
                            "tz":         "UTC",
                            "details":    r.get("details", ""),
                            "freq":       r.get("freq", "none"),
                        })
                    with open(CSV_PATH, "w", newline="", encoding="utf-8") as fw:
                        w = csv.DictWriter(fw, fieldnames=FIELDNAMES)
                        w.writeheader()
                        w.writerows(new_rows)

    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.tree.sync()
        if not self.check_reminders.is_running():
            self.check_reminders.start()

    @app_commands.command(name="reminder", description="Open the Reminder menu")
    async def reminder_app(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🗓️ Reminder App",
            description="Use the buttons below to add or list your reminders."
        )
        await interaction.response.send_message(
            embed=embed,
            view=ReminderMenu(self),
            ephemeral=True
        )

    @tasks.loop(minutes=1.0)
    async def check_reminders(self):
        now_utc = datetime.now(timezone.utc)
        rows = self._read_all()
        changed = False

        for r in rows[:]:
            remind_dt = datetime.fromisoformat(r["remind_utc"])
            if remind_dt <= now_utc:
                user = self.bot.get_user(int(r["user_id"])) \
                       or await self.bot.fetch_user(int(r["user_id"]))
                if user:
                    user_tz = ZoneInfo(r["tz"])
                    local = remind_dt.astimezone(user_tz)
                    await user.send(
                        f"⏰ **{r['name']}**\n"
                        f"When: {local:%Y-%m-%d %H:%M} ({r['tz']})\n"
                        f"Details: {r['details']}"
                    )
                if r["freq"] == "none":
                    rows.remove(r)
                else:
                    delta = {
                        "daily":   relativedelta(days=1),
                        "weekly":  relativedelta(weeks=1),
                        "monthly": relativedelta(months=1),
                        "yearly":  relativedelta(years=1),
                    }[r["freq"]]
                    r["remind_utc"] = (remind_dt + delta).isoformat()
                changed = True

        if changed:
            self._write_all(rows)

    def _read_all(self):
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def _write_all(self, rows):
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDNAMES)
            w.writeheader()
            w.writerows(rows)

    def _next_id(self, rows):
        return 1 if not rows else max(int(r["id"]) for r in rows) + 1

    def _read_for_user(self, user_id):
        now_iso = datetime.now(timezone.utc).isoformat()
        return [
            r for r in self._read_all()
            if r["user_id"] == str(user_id) and r["remind_utc"] >= now_iso
        ]

    def _remove_by_id(self, user_id, rid):
        rows = self._read_all()
        for r in rows:
            if r["id"] == rid and r["user_id"] == str(user_id):
                rows.remove(r)
                self._write_all(rows)
                return r
        return None


class ReminderMenu(discord.ui.View):
    def __init__(self, cog: Reminder):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="➕ Add Reminder",
        style=discord.ButtonStyle.primary,
        custom_id="reminder_add",
    )
    async def add_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        embed = discord.Embed(
            title="➕ Add Reminder",
            description="Select your Time Zone & Frequency:"
        )
        await interaction.response.send_message(
            embed=embed,
            view=TimezoneFreqView(self.cog),
            ephemeral=True
        )

    @discord.ui.button(
        label="📋 List Reminders",
        style=discord.ButtonStyle.secondary,
        custom_id="reminder_list",
    )
    async def list_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        rows = self.cog._read_for_user(interaction.user.id)
        if not rows:
            return await interaction.response.send_message(
                "You have no upcoming reminders.", ephemeral=True
            )

        embed = discord.Embed(title="📋 Your Upcoming Reminders")
        for r in rows:
            dt = datetime.fromisoformat(r["remind_utc"])
            local = dt.astimezone(ZoneInfo(r["tz"]))
            embed.add_field(
                name=f"{r['id']}: {r['name']} ({r['freq']})",
                value=f"{local:%Y-%m-%d %H:%M} ({r['tz']})\n{r['details']}",
                inline=False
            )

        view = DeleteSelectView(self.cog, rows)
        await interaction.response.send_message(
            embed=embed, view=view, ephemeral=True
        )

class TimezoneFreqView(discord.ui.View):
    def __init__(self, cog: Reminder):
        super().__init__(timeout=None)
        self.cog = cog
        self.selected_tz = None
        self.selected_freq = None

        tz_opts = [discord.SelectOption(label=tz, value=tz) for tz in COMMON_TIMEZONES]
        self.tz_select = discord.ui.Select(
            placeholder="Time Zone…",
            options=tz_opts,
            custom_id="tz_select",
            min_values=1, max_values=1
        )
        self.tz_select.callback = self.on_tz_select
        self.add_item(self.tz_select)

        freq_opts = [discord.SelectOption(label=f.title(), value=f) for f in FREQ_OPTIONS]
        self.freq_select = discord.ui.Select(
            placeholder="Frequency…",
            options=freq_opts,
            custom_id="freq_select",
            min_values=1, max_values=1
        )
        self.freq_select.callback = self.on_freq_select
        self.add_item(self.freq_select)

    async def on_tz_select(self, interaction: discord.Interaction):
        self.selected_tz = self.tz_select.values[0]
        await interaction.response.send_message(
            f"🕑 Time Zone set to **{self.selected_tz}**", ephemeral=True
        )

    async def on_freq_select(self, interaction: discord.Interaction):
        self.selected_freq = self.freq_select.values[0]
        await interaction.response.send_message(
            f"🔁 Frequency set to **{self.selected_freq}**", ephemeral=True
        )

    @discord.ui.button(label="Next", style=discord.ButtonStyle.success)
    async def next_button(self, interaction: discord.Interaction, button):
        if not (self.selected_tz and self.selected_freq):
            return await interaction.response.send_message(
                "Please choose both Time Zone and Frequency first.",
                ephemeral=True
            )
        await interaction.response.send_modal(
            ReminderModal(self.cog, tz=self.selected_tz, freq=self.selected_freq)
        )
        self.stop()
class ReminderModal(discord.ui.Modal, title="➕ New Reminder"):
    name    = discord.ui.TextInput(label="Name", max_length=100)
    when    = discord.ui.TextInput(
        label="Date & Time (YYYY-MM-DD HH:MM)",
        placeholder="2025-06-15 09:00"
    )
    details = discord.ui.TextInput(
        label="Details", style=discord.TextStyle.paragraph, required=False
    )

    def __init__(self, cog: Reminder, tz: str, freq: str):
        super().__init__()
        self.cog = cog
        self.tz = tz
        self.freq = freq

    async def on_submit(self, interaction: discord.Interaction):
        try:
            naive = datetime.strptime(self.when.value, "%Y-%m-%d %H:%M")
        except ValueError:
            return await interaction.response.send_message(
                "❌ Invalid date/time. Use YYYY-MM-DD HH:MM", ephemeral=True
            )
        user_tz = ZoneInfo(self.tz)
        local_dt = naive.replace(tzinfo=user_tz)
        remind_utc = local_dt.astimezone(timezone.utc)

        rows = self.cog._read_all()
        new_id = self.cog._next_id(rows)
        rows.append({
            "id":         str(new_id),
            "user_id":    str(interaction.user.id),
            "name":       self.name.value,
            "remind_utc": remind_utc.isoformat(),
            "tz":         self.tz,
            "details":    self.details.value,
            "freq":       self.freq,
        })
        self.cog._write_all(rows)

        embed = discord.Embed(
            title="✅ Reminder Created",
            description=f"ID `{new_id}` • **{self.name.value}**",
            color=discord.Color.green()
        )
        embed.add_field(
            name="When",
            value=f"{local_dt:%Y-%m-%d %H:%M} ({self.tz})", inline=True
        )
        embed.add_field(name="Frequency", value=self.freq, inline=True)
        embed.add_field(name="Details", value=self.details.value or "_none_", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

class DeleteSelectView(discord.ui.View):
    def __init__(self, cog: Reminder, rows: list[dict]):
        super().__init__(timeout=None)
        self.add_item(ReminderDeleteSelect(rows, cog))

class ReminderDeleteSelect(discord.ui.Select):
    def __init__(self, rows: list[dict], cog: Reminder):
        options = []
        for r in rows:
            dt = datetime.fromisoformat(r["remind_utc"])
            local = dt.astimezone(ZoneInfo(r["tz"]))
            options.append(discord.SelectOption(
                label=f"{r['name']} @ {local:%Y-%m-%d %H:%M}",
                value=r["id"]
            ))
        super().__init__(
            placeholder="Select a reminder to delete",
            min_values=1, max_values=1,
            options=options
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        rid = self.values[0]
        removed = self.cog._remove_by_id(interaction.user.id, rid)
        if removed:
            await interaction.response.edit_message(
                content=f"🗑️ Removed **{removed['name']}**.", embed=None, view=None
            )
        else:
            await interaction.response.send_message(
                "❌ Could not find that reminder.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Reminder(bot))
