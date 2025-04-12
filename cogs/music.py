import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
import logging

youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',  
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'options': '-vn'
}


ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    """
    A helper class representing an audio source from YouTube.
    It uses yt_dlp to extract audio info and creates a FFmpeg audio source.
    """
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        """
        Asynchronously extract audio info from a URL or search query.
        """
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            data = data['entries'][0]
        
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

class Music(commands.Cog):
    """
    A Music cog that supports:
      • !play [query] - plays a YouTube URL or search query.
      • !pause - pauses the current track (queue remains).
      • !resume - resumes a paused track.
      • !stop - stops playback without clearing the queue.
      • !skip - skips the current track (auto‑plays next track if in queue).
      • !queue - displays the current music queue.
      • !clearqueue - clears the queue.
      • !join, !disc (alias for disconnect) and !leave.
    """
    def __init__(self, bot):
        self.bot = bot
        self.music_queues = {}
        self.stop_flags = {}
        logging.info("Music cog initialized.")

    @commands.command(name="join")
    async def join(self, ctx):
        """Joins the voice channel of the command caller."""
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            await channel.connect()
            logging.info(f"Joined voice channel: {channel.name} in {ctx.guild.name}")
        else:
            await ctx.send("You need to join a voice channel first.")

    @commands.command(name="leave")
    async def leave(self, ctx):
        """Disconnects the bot from the voice channel and (optionally) preserves the queue."""
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            logging.info(f"Disconnected from voice channel in {ctx.guild.name}")
        else:
            await ctx.send("I'm not in a voice channel.")

    @commands.command(name="disc")
    async def disc(self, ctx):
        """Alias for disconnecting the bot (same as !leave)."""
        await self.leave(ctx)

    async def check_queue(self, ctx):
        """Plays the next track in the queue if available unless a stop was requested."""
        guild_id = ctx.guild.id
        if self.stop_flags.get(guild_id, False):
            self.stop_flags[guild_id] = False
            return

        if guild_id in self.music_queues and self.music_queues[guild_id]:
            next_source = self.music_queues[guild_id].pop(0)
            ctx.voice_client.play(
                next_source,
                after=lambda e: self.bot.loop.create_task(self.check_queue(ctx))
            )
            await ctx.send(f"Now playing: **{next_source.title}**")
            logging.info(f"Started playing: {next_source.title}")

    @commands.command(name="play")
    async def play(self, ctx, *, query: str):
        """
        Plays audio based on the provided query (a YouTube URL or search query).
        If nothing is playing, playback starts immediately; otherwise the track is queued.
        """
        if not ctx.author.voice:
            return await ctx.send("Please join a voice channel first.")

        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()
            logging.info(f"Connected to voice channel: {ctx.author.voice.channel.name}")

        await ctx.send("Searching for the song...")
        try:
            source = await YTDLSource.from_url(query, loop=self.bot.loop, stream=True)
        except Exception as e:
            await ctx.send("An error occurred while processing the song.")
            logging.error(f"Error in play command: {e}")
            return

        guild_id = ctx.guild.id
        if guild_id not in self.music_queues:
            self.music_queues[guild_id] = []
        if guild_id not in self.stop_flags:
            self.stop_flags[guild_id] = False

        if not ctx.voice_client.is_playing():
            ctx.voice_client.play(
                source,
                after=lambda e: self.bot.loop.create_task(self.check_queue(ctx))
            )
            await ctx.send(f"Now playing: **{source.title}**")
            logging.info(f"Started playing: {source.title}")
        else:
            self.music_queues[guild_id].append(source)
            await ctx.send(f"**{source.title}** has been added to the queue.")
            logging.info(f"Added to queue: {source.title}")

    @commands.command(name="pause")
    async def pause(self, ctx):
        """Pauses the current track without clearing the queue."""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("Music paused.")
            logging.info(f"Paused music in {ctx.guild.name}")
        else:
            await ctx.send("No music is playing to pause.")

    @commands.command(name="resume")
    async def resume(self, ctx):
        """Resumes playback if music is paused."""
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("Music resumed.")
            logging.info(f"Resumed music in {ctx.guild.name}")
        else:
            await ctx.send("No music is paused.")

    @commands.command(name="stop")
    async def stop(self, ctx):
        """
        Stops the current track without clearing the queue.
        A stop flag is set to prevent auto-playing the next track.
        """
        if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            self.stop_flags[ctx.guild.id] = True
            ctx.voice_client.stop()
            await ctx.send("Stopped the current track. The queue is preserved.")
            logging.info(f"Stopped track in {ctx.guild.name} (queue preserved)")
        else:
            await ctx.send("No music is playing.")

    @commands.command(name="skip")
    async def skip(self, ctx):
        """
        Skips the current track.
        The auto-play mechanism then checks the queue to play the next track.
        """
        if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            ctx.voice_client.stop() 
            await ctx.send("Skipped the current track.")
            logging.info(f"Skipped track in {ctx.guild.name}")
        else:
            await ctx.send("No track is playing.")

    @commands.command(name="queue")
    async def queue_(self, ctx):
        """Displays the current music queue."""
        guild_id = ctx.guild.id
        if guild_id in self.music_queues and self.music_queues[guild_id]:
            queue_list = "\n".join(f"{i+1}. {source.title}" for i, source in enumerate(self.music_queues[guild_id]))
            await ctx.send(f"**Current Queue:**\n{queue_list}")
        else:
            await ctx.send("The queue is empty.")

    @commands.command(name="clearqueue")
    async def clearqueue(self, ctx):
        """Clears the music queue."""
        self.music_queues[ctx.guild.id] = []
        await ctx.send("The music queue has been cleared.")
        logging.info(f"Cleared queue in {ctx.guild.name}")

async def setup(bot):
    await bot.add_cog(Music(bot))
    logging.info("Music cog loaded successfully.")
