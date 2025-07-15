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
    'default_search': 'ytsearch5',  # Suche mit 5 Ergebnissen für Playlist-Funktion
    'noplaylist': True,
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

async def search_and_play(ctx, query: str, playlist=None, index=0):
    global looping

    if not ctx.user.voice:
        await ctx.response.send_message("❌ Du musst in einem Sprachkanal sein!", ephemeral=True)
        return

    channel = ctx.user.voice.channel

    if ctx.guild.voice_client is None:
        await channel.connect()

    voice_client = ctx.guild.voice_client

    if playlist is None:
        # Erster Suchlauf - Playlist mit mehreren Ergebnissen laden
        await ctx.response.send_message(f"🔍 Suche nach: `{query}`...", ephemeral=True)
        try:
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)
        except Exception as e:
            await ctx.followup.send(f"❌ Fehler bei der Suche: {e}", ephemeral=True)
            return
        if 'entries' not in info or len(info['entries']) == 0:
            await ctx.followup.send("❌ Keine Ergebnisse gefunden.", ephemeral=True)
            return
        playlist = info['entries']
        index = 0

    if index >= len(playlist):
        await ctx.followup.send("🎵 Playlist zu Ende.", ephemeral=True)
        await voice_client.disconnect()
        return

    info = playlist[index]

    # Prüfen, ob ein passendes Audioformat vorhanden ist
    formats = info.get('formats', [])
    audio_format = next((f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none'), None)

    if audio_format:
        url = audio_format['url']
    else:
        url = info.get('url')
        if not url:
            await ctx.followup.send("❌ Kein Audioformat gefunden.", ephemeral=True)
            return

    title = info.get('title', 'Unbekannt')

    source = discord.FFmpegPCMAudio(url, options='-vn')

    async def after_playing_callback(error):
        if error:
            print(f"Error: {error}")

        if looping:
            # Wiederhole aktuellen Song
            await search_and_play(ctx, query, playlist, index)
        else:
            # Spiele nächsten Song
            await search_and_play(ctx, query, playlist, index + 1)

    voice_client.stop()
    voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(after_playing_callback(e), client.loop))

    if index == 0:
        view = MusicView(ctx, source, voice_client)
        await ctx.followup.send(f"🎶 Jetzt läuft: **{title}**", view=view)
    else:
        # Optional: Nachrichten für weitere Songs unterdrücken oder senden
        pass

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
