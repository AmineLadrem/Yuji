import discord
from discord.ext import commands
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(name)s: %(message)s',
    handlers=[
        logging.FileHandler("discord_events.log", mode="a"),  
        logging.StreamHandler()  
    ]
)

class LoggerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """
        Logs when the bot is fully connected and ready.
        """
        msg = f'Bot connected as {self.bot.user} (ID: {self.bot.user.id})'
        logging.info(msg)

    @commands.Cog.listener()
    async def on_message(self, message):
        """
        Logs each message sent in the server.
        """
        if message.author.bot:
            return

        if message.guild:  
            msg = (f'Message from {message.author} in {message.guild.name} '
                   f'(Channel: {message.channel.name}): "{message.content}"')
        else:
            msg = f'DM from {message.author}: "{message.content}"'

        logging.info(msg)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        msg = f'Member joined: {member} (ID: {member.id}) in {member.guild.name}'
        logging.info(msg)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        msg = f'Member left: {member} (ID: {member.id}) in {member.guild.name}'
        logging.info(msg)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        msg = f'Member update in {before.guild.name}: {before} -> {after}'
        logging.info(msg)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        guild_name = reaction.message.guild.name if reaction.message.guild else "DM"
        msg = (f'Reaction added: {reaction.emoji} on message ID {reaction.message.id} '
               f'by {user} in {guild_name}')
        logging.info(msg)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        guild_name = reaction.message.guild.name if reaction.message.guild else "DM"
        msg = (f'Reaction removed: {reaction.emoji} from message ID {reaction.message.id} '
               f'by {user} in {guild_name}')
        logging.info(msg)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        msg = f'Bot joined a new guild: {guild.name} (ID: {guild.id})'
        logging.info(msg)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        msg = f'Bot removed from guild: {guild.name} (ID: {guild.id})'
        logging.info(msg)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        msg = f'Channel created: {channel.name} (ID: {channel.id}) in {channel.guild.name}'
        logging.info(msg)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        msg = f'Channel deleted: {channel.name} (ID: {channel.id}) in {channel.guild.name}'
        logging.info(msg)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """
        Logs when members join, leave, or switch voice channels.
        """
        if before.channel is None and after.channel is not None:
            msg = f'{member} joined voice channel "{after.channel.name}" (ID: {after.channel.id}) in {member.guild.name}'
        elif before.channel is not None and after.channel is None:
            msg = f'{member} left voice channel "{before.channel.name}" (ID: {before.channel.id}) in {member.guild.name}'
        elif before.channel != after.channel:
            msg = (f'{member} moved from voice channel "{before.channel.name}" '
                   f'(ID: {before.channel.id}) to "{after.channel.name}" (ID: {after.channel.id}) in {member.guild.name}')
        else:
            msg = f'Voice state updated for {member} in {member.guild.name}'
        logging.info(msg)

async def setup(bot):
    await bot.add_cog(LoggerCog(bot))
