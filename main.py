import asyncio
import os

import discord
import youtube_dl
from youtube_search import YoutubeSearch

from discord.ext import commands

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'extractor_retries': 'auto',
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn',
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue_songs = []
        self.playing_name = ''

    @commands.command()
    async def join(self, ctx, *, channel: discord.VoiceChannel):
        """Joins a voice channel"""

        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)

        await channel.connect()

    @commands.command()
    async def emo(self, ctx, *, query):
        """Plays a file from the local filesystem"""

        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(query))
        ctx.voice_client.play(source, after=lambda e: print(f'Player error: {e}') if e else None)

        await ctx.send(f'Now playing: {query}')

    @commands.command()
    async def play(self, ctx, *, url):
        async with ctx.typing():
            """Plays from a url (almost anything youtube_dl supports)"""
            if "youtu" not in url:
                results = YoutubeSearch(url, max_results=1).to_dict()
                url = "https://www.youtube.com/" + results[0]['url_suffix']
                player = await YTDLSource.from_url(url, loop=self.bot.loop)
                self.queue_songs.append(player)
            if ctx.voice_client.is_playing():

                await ctx.send(f'Added songs: {player.title}')
                return
            async with ctx.typing():
                await self.listSongs(ctx)

    @commands.command()
    async def list(self, ctx):
        async with ctx.typing():
            if len(self.queue_songs) > 0:
                song = ''
                id_queue = 0
                for value in self.queue_songs:
                    id_queue += 1
                    song = song + f'{id_queue}. {value.title}\n'
                await ctx.send(f'''```
Currently playing: {self.playing_name}\n
=============================================\n
Waiting songs:
{song}
```''')
            else:
                await ctx.send(f'No waiting song.')

    @commands.command()
    async def skip(self, ctx):
        async with ctx.typing():
            if len(self.queue_songs) > 0:
                ctx.voice_client.stop()
                await ctx.send(f'Oke skipped!')
                await self.listSongs(ctx)
            else:
                await ctx.send(f'No song for skipping!')

    async def listSongs(self, ctx):
        # async with ctx.typing():
        # test = os.listdir("./")
        # for item in test:
        #     if item.endswith(".m4a") or item.endswith(".webm"):
        #         os.remove(os.path.join("./", item))
        if not (len(self.queue_songs) > 0):
            return
        ctx.voice_client.play(self.queue_songs[0], after=lambda e: self.bot.loop.create_task(self.listSongs(ctx)))
        await ctx.send(f'Now playing: {self.queue_songs[0].title}')
        self.playing_name = self.queue_songs[0].title
        self.queue_songs.pop(0)

    @commands.command()
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""

        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")

        ctx.voice_client.source.volume = volume / 100
        await ctx.send(f"Changed volume to {volume}%")

    @commands.command()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""
        test = os.listdir("./")
        for item in test:
            if item.endswith(".m4a") or item.endswith(".webm"):
                os.remove(os.path.join("./", item))
        await ctx.voice_client.disconnect()

    @emo.before_invoke
    @play.before_invoke
    # @stream.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")
        elif ctx.voice_client.is_playing():
            # ctx.voice_client.stop()
            pass


intents = discord.Intents.all()
# intents.message_content = True

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("&"),
    description='Relatively simple music bot example',
    intents=intents,
)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')


async def main():
    async with bot:
        await bot.add_cog(Music(bot))
        await bot.start('')


asyncio.run(main())
