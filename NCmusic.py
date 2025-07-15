import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import os

# ✅ Render-Webserver einbinden
from keep_alive import keep_alive

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
client = commands.Bot(command_prefix="!", intents=intents)

looping = False  # Globaler Loop-Modus

yt_opts = {
    'format': 'bestaudio/best',
    'quiet': True,
    'default_search': 'ytsearch',
    'noplaylist': True,
    'cachedir': False,          # Cache deaktivieren für schnellere Abfragen
    'extract_flat': True,       # Nur Metadaten laden (schneller)
}

ydl = yt_dlp.YoutubeDL(yt_opts)

class MusicView(discord.ui.View):
    def __init__(self, ctx, source, voice_client):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.source = source
        self.voice_client = voice_client

    @discord.ui.button(label="⏹ Stop", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.voice_client.is_playing():
            self.voice_client.stop()
            await interaction.response.send_message("⏹ Musik gestoppt.", ephemeral=True)

    @discord.ui.button(label="🔁 Reload", style=discord.ButtonStyle.success)
    async def reload_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        global looping
        looping = not looping
        if looping:
            await interaction.response.send_message("🔁 Wiederholung aktiviert.", ephemeral=True)
        else:
            await interaction.response.send_message("➡️ Wiederholung deaktiviert.", ephemeral=True)

async def search_and_play(ctx, query: str):
    global looping

    if not ctx.user.voice:
        await ctx.response.send_message("❌ Du musst in einem Sprachkanal sein!", ephemeral=True)
        return

    channel = ctx.user.voice.channel

    if ctx.guild.voice_client is None:
        await channel.connect()

    voice_client = ctx.guild.voice_client

    await ctx.response.send_message(f"🔍 Suche nach: `{query}`...", ephemeral=True)

    info = ydl.extract_info(query, download=False)
    if 'entries' in info:
        info = info['entries'][0]

    url = info['url']
    title = info['title']

    # FFmpeg Optionen mit reconnect für schnelleres und stabileres Streaming
    ffmpeg_options = '-vn -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'

    source = discord.FFmpegPCMAudio(url, options=ffmpeg_options)

    def after_playing(e):
        if e:
            print(f"Error: {e}")
        elif looping:
            asyncio.run_coroutine_threadsafe(search_and_play(ctx, query), client.loop)

    voice_client.stop()
    voice_client.play(source, after=after_playing)

    view = MusicView(ctx, source, voice_client)
    await ctx.followup.send(f"🎶 Jetzt läuft: **{title}**", view=view)

@client.event
async def on_ready():
    try:
        synced = await client.tree.sync()
        print(f"✅ Slash-Commands geladen: {len(synced)}")
    except Exception as e:
        print(f"Fehler beim Sync: {e}")
    print(f"Bot ist online als {client.user}")

@client.tree.command(name="play", description="Spielt Musik ab.")
@app_commands.describe(song="Name des Songs (optional mit Künstler)")
async def play(interaction: discord.Interaction, song: str):
    await search_and_play(interaction, song)

# ✅ Start Render-Webserver für "keep-alive"
keep_alive()

# ✅ Starte den Discord-Bot
TOKEN = os.getenv("DISCORD_TOKEN")
client.run(TOKEN)
