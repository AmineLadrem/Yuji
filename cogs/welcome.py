import discord
from discord.ext import commands
import json

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
        except Exception as e:
            print(f"Error loading config.json: {e}")
            config = {}
        
        self.welcome_message = config.get("welcome_message", "Welcome to the server, {member}!")
        self.welcome_channel_name = config.get("welcome_channel", "welcome")
        
        self.members_role_name = config.get("members_role_name", "Members")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild

        channel = discord.utils.get(guild.text_channels, name=self.welcome_channel_name)
        if channel:
            message = self.welcome_message.format(member=member.mention)
            try:
                await channel.send(message)
                print(f"Welcome message sent in #{channel.name} for {member}")
            except Exception as e:
                print(f"Error sending welcome message in #{channel.name}: {e}")
        else:
            print(f"Welcome channel '{self.welcome_channel_name}' not found in {guild.name}.")

        role = discord.utils.get(guild.roles, name=self.members_role_name)
        if role:
            try:
                await member.add_roles(role, reason="Automatic welcome role assignment")
                print(f"Assigned role '{role.name}' to {member}")
            except discord.Forbidden:
                print(f"Failed to assign role {role.name} to {member}: Missing permissions.")
            except Exception as e:
                print(f"An error occurred when assigning role to {member}: {e}")
        else:
            print(f"Role with ID {self.members_role_id} not found in guild: {guild.name}")

async def setup(bot):
    await bot.add_cog(Welcome(bot))
