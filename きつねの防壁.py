import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.gateway import DiscordWebSocket
from gtts import gTTS
import os
import asyncio
import json
import datetime
import random
import yt_dlp
import urllib.parse
import urllib.request
import json as js

# ==========================================
# 💾 設定の永久保存（JSON保存・読み込み）処理
# ==========================================
CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "en_rooms": {int(k): v for k, v in data.get("en_rooms", {}).items()},
                    "jp_rooms": {int(k): v for k, v in data.get("jp_rooms", {}).items()},
                    "tts_rooms": {int(k): v for k, v in data.get("tts_rooms", {}).items()},
                    "wiki_rooms": {int(k): v for k, v in data.get("wiki_rooms", {}).items()},
                    "voice_settings": {int(k): v for k, v in data.get("voice_settings", {}).items()},
                    "auth_roles": {int(k): v for k, v in data.get("auth_roles", {}).items()},
                    "passwords": {int(k): v for k, v in data.get("passwords", {}).items()},
                    "loop_settings": {int(k): v for k, v in data.get("loop_settings", {}).items()},
                }
        except Exception as e:
            print(f"設定ファイル読み込みエラー: {e}")
    return {"en_rooms": {}, "jp_rooms": {}, "tts_rooms": {}, "wiki_rooms": {}, "voice_settings": {}, "auth_roles": {}, "passwords": {}, "loop_settings": {}}

def save_config():
    try:
        data = {
            "en_rooms": {str(k): v for k, v in en_rooms.items()},
            "jp_rooms": {str(k): v for k, v in jp_rooms.items()},
            "tts_rooms": {str(k): v for k, v in tts_rooms.items()},
            "wiki_rooms": {str(k): v for k, v in wiki_rooms.items()},
            "voice_settings": {str(k): v for k, v in voice_settings.items()},
            "auth_roles": {str(k): v for k, v in auth_roles.items()},
            "passwords": {str(k): v for k, v in passwords.items()},
            "loop_settings": {str(k): v for k, v in loop_settings.items()},
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"設定ファイル保存エラー: {e}")

config = load_config()
en_rooms = config["en_rooms"]
jp_rooms = config["jp_rooms"]
tts_rooms = config["tts_rooms"]
wiki_rooms = config["wiki_rooms"]
voice_settings = config["voice_settings"]
auth_roles = config["auth_roles"]
passwords = config["passwords"]
loop_settings = config["loop_settings"]

# ==========================================
# 🔥 スマホマーク化（iOS偽装）処理
# ==========================================
async def identify_patched(self):
    payload = {
        'op': self.IDENTIFY,
        'd': {
            'token': self.token,
            'properties': {'$os': 'ios', '$browser': 'Discord iOS', '$device': 'iPhone'},
            'compress': self.sequence != 0,
            'large_threshold': 250,
            'intents': self._connection.intents.value
        }
    }
    connection = self._connection
    shard_id = getattr(connection, 'shard_id', None)
    shard_count = getattr(connection, 'shard_count', None)
    if shard_id is not None:
        payload['d']['shard'] = [shard_id, shard_count or 1]
    activity = getattr(connection, '_activity', None)
    status = getattr(connection, '_status', None)
    if activity is not None or status is not None:
        payload['d']['presence'] = {
            'status': status or 'online',
            'game': activity.to_dict() if activity else None,
            'since': 0, 'afk': False
        }
    await self.send_as_json(payload)

DiscordWebSocket.identify = identify_patched
# ==========================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

FFmpeg_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

message_records = {}
# 現在サーバーごとに再生している曲の情報を保持する辞書
current_playing_songs = {}

# ==========================================
# 📊 ステータス自動更新ループ
# ==========================================
@tasks.loop(minutes=5)
async def update_status():
    guild_count = len(bot.guilds)
    activity = discord.Activity(
        type=discord.ActivityType.playing,
        name=f"/help | サーバー数: {guild_count} | 荒らしを確認中..."
    )
    await bot.change_presence(status=discord.Status.online, activity=activity)

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"同期されたスラッシュコマンド数: {len(synced)}")
    except Exception as e:
        print(f"コマンド同期エラー: {e}")

    if not update_status.is_running():
        update_status.start()

    print(f"Botがログインしました: {bot.user}")

# ==========================================
# 🔐 認証パネル用 View
# ==========================================
class AuthView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="認証する", style=discord.ButtonStyle.green, custom_id="auth_button_main")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = interaction.guild.id
        role_id = auth_roles.get(guild_id)
        if role_id:
            role = interaction.guild.get_role(role_id)
            if role:
                try:
                    await interaction.user.add_roles(role)
                    await interaction.response.send_message("✅ 認証が完了しました！ロールが付与されました。", ephemeral=True)
                    return
                except Exception as e:
                    await interaction.response.send_message(f"❌ ロール付与に失敗しました: {e}", ephemeral=True)
                    return
        await interaction.response.send_message("⚠️ このサーバーでは認証ロールがまだ設定されていません。", ephemeral=True)

# --------------------------------------------------
# 📚 /help コマンド
# --------------------------------------------------
@bot.tree.command(name="help", description="Botの全コマンドと使い方を表示します")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📚 読み上げ・管理 bot ヘルプ", 
        description="各種セットアップや便利機能一覧です。", 
        color=discord.Color.from_rgb(255, 182, 193)
    )
    embed.add_field(name="⚙️ セットアップ管理", value="`/setup-eng` / `/setup-jp` : 翻訳設定\n`/setup-tts` : 読み上げ専用\n`/setup-wiki` : Wiki自動検索\n`/reset-setup` : 設定解除\n`/setup-auth` : 認証パネル設置", inline=False)
    embed.add_field(name="🎙 読み上げ・音声", value="`/join` / `/leave` : VC入退室\n`/voice` : 声質変更\n`/play` / `/stop` / `/loop` : 音楽・リピート", inline=False)
    embed.add_field(name="🛠 ツール・その他", value="`/wiki` : Wikipedia検索\n`/clear` : メッセージ削除\n`/dice` : サイコロ\n`/date` : 日時表示\n`/password` : パスワード生成\n`/verify` : パスワード認証", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# --------------------------------------------------
# ⚙️ セットアップ系コマンド
# --------------------------------------------------
@bot.tree.command(name="setup-eng", description="【管理者】このチャンネルを英語→日本語翻訳チャンネルに設定します")
@app_commands.checks.has_permissions(administrator=True)
async def setup_eng(interaction: discord.Interaction):
    en_rooms[interaction.guild.id] = interaction.channel.id
    save_config()
    await interaction.response.send_message("🌐 このチャンネルを**英語→日本語翻訳**に設定しました。", ephemeral=True)

@bot.tree.command(name="setup-jp", description="【管理者】このチャンネルを日本語→英語翻訳チャンネルに設定します")
@app_commands.checks.has_permissions(administrator=True)
async def setup_jp(interaction: discord.Interaction):
    jp_rooms[interaction.guild.id] = interaction.channel.id
    save_config()
    await interaction.response.send_message("🌐 このチャンネルを**日本語→英語翻訳**に設定しました。", ephemeral=True)

@bot.tree.command(name="setup-tts", description="【管理者】このチャンネルを読み上げ専用チャンネルに設定します")
@app_commands.checks.has_permissions(administrator=True)
async def setup_tts(interaction: discord.Interaction):
    tts_rooms[interaction.guild.id] = interaction.channel.id
    save_config()
    await interaction.response.send_message("🎙 このチャンネルを**読み上げ専用**に設定しました。", ephemeral=True)

@bot.tree.command(name="setup-wiki", description="【管理者】このチャンネルをWikipedia自動検索チャンネルに設定します")
@app_commands.checks.has_permissions(administrator=True)
async def setup_wiki(interaction: discord.Interaction):
    wiki_rooms[interaction.guild.id] = interaction.channel.id
    save_config()
    await interaction.response.send_message("📖 このチャンネルを**Wikipedia自動検索**に設定しました。", ephemeral=True)

@bot.tree.command(name="setup-auth", description="【管理者】認証パネルを送信します")
@app_commands.describe(role="付与する認証ロール")
@app_commands.checks.has_permissions(administrator=True)
async def setup_auth(interaction: discord.Interaction, role: discord.Role):
    auth_roles[interaction.guild.id] = role.id
    save_config()
    embed = discord.Embed(title="🔒 サーバー認証", description="下のボタンを押して認証を完了してください。", color=discord.Color.blue())
    await interaction.channel.send(embed=embed, view=AuthView())
    await interaction.response.send_message("✨ 認証パネルを送信しました！", ephemeral=True)

@bot.tree.command(name="reset-setup", description="【管理者】このサーバーの設定をすべて解除します")
@app_commands.checks.has_permissions(administrator=True)
async def reset_setup(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    en_rooms.pop(guild_id, None)
    jp_rooms.pop(guild_id, None)
    tts_rooms.pop(guild_id, None)
    wiki_rooms.pop(guild_id, None)
    auth_roles.pop(guild_id, None)
    passwords.pop(guild_id, None)
    loop_settings.pop(guild_id, None)
    save_config()
    await interaction.response.send_message("🗑 すべての設定をリセットしました。", ephemeral=True)

@bot.tree.command(name="clear", description="【管理者】指定した件数のメッセージを一括削除します")
@app_commands.describe(limit="削除する件数（1〜100）")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, limit: int):
    if limit < 1 or limit > 100:
        await interaction.response.send_message("❌ 1から100の間で指定してください。", ephemeral=True)
        return
    await interaction.channel.purge(limit=limit)
    await interaction.response.send_message(f"🧹 {limit}件のメッセージを削除しました。", ephemeral=True)

# --------------------------------------------------
# 🔍 便利機能・ツール系コマンド
# --------------------------------------------------
@bot.tree.command(name="wiki", description="Wikipediaを検索します")
@app_commands.describe(query="検索ワード")
async def wiki(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    try:
        url = f"https://ja.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&format=json"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = js.loads(response.read().decode('utf-8'))
            search_results = data.get('query', {}).get('search', [])
            if search_results:
                title = search_results[0]['title']
                page_url = f"https://ja.wikipedia.org/wiki/{urllib.parse.quote(title)}"
                await interaction.followup.send(f"📖 **{title}**\n{page_url}")
            else:
                await interaction.followup.send("❌ 該当するWikipedia記事が見つかりませんでした。")
    except Exception as e:
        await interaction.followup.send(f"❌ 検索エラーが発生しました: {e}")

@bot.tree.command(name="dice", description="サイコロを振ります（例: 1-6）")
@app_commands.describe(min_num="最小値", max_num="最大値")
async def dice(interaction: discord.Interaction, min_num: int = 1, max_num: int = 6):
    result = random.randint(min_num, max_num)
    await interaction.response.send_message(f"🎲 サイコロの結果: **{result}** （範囲: {min_num}〜{max_num}）")

@bot.tree.command(name="date", description="現在の日時を表示します")
async def date_cmd(interaction: discord.Interaction):
    now = datetime.datetime.now().strftime("%Y年%m月%d日 %H時%M分%s秒")
    await interaction.response.send_message(f"📅 現在の日時: **{now}**")

@bot.tree.command(name="password", description="ランダムなパスワードを生成します")
@app_commands.describe(length="文字数（デフォルト: 12）")
async def password_cmd(interaction: discord.Interaction, length: int = 12):
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
    pwd = "".join(random.choice(chars) for _ in range(length))
    await interaction.response.send_message(f"🔑 生成されたパスワード: ||`{pwd}`|| (タップして表示)", ephemeral=True)

@bot.tree.command(name="set_password", description="【管理者】認証用パスワードを設定します")
@app_commands.describe(password="パスワード", role="付与するロール")
@app_commands.checks.has_permissions(administrator=True)
async def set_password(interaction: discord.Interaction, password: str, role: discord.Role):
    passwords[interaction.guild.id] = password
    auth_roles[interaction.guild.id] = role.id
    save_config()
    await interaction.response.send_message(f"🔒 認証パスワードを設定しました！ `/verify` で認証できます。", ephemeral=True)

@bot.tree.command(name="verify", description="パスワードを入力して認証します")
@app_commands.describe(password="認証パスワード")
async def verify(interaction: discord.Interaction, password: str):
    guild_id = interaction.guild.id
    correct_password = passwords.get(guild_id)
    role_id = auth_roles.get(guild_id)
    if not correct_password:
        await interaction.response.send_message("❌ このサーバーにはパスワードが設定されていません。", ephemeral=True)
        return
    if password == correct_password and role_id:
        role = interaction.guild.get_role(role_id)
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("✅ パスワードが一致しました！認証が完了しました。", ephemeral=True)
            return
    await interaction.response.send_message("❌ パスワードが違います。", ephemeral=True)

# --------------------------------------------------
# 🎙 基本コマンド (/join, /voice, /leave)
# --------------------------------------------------
@bot.tree.command(name="join", description="読み上げVCに参加します")
async def join(interaction: discord.Interaction):
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.move_to(channel)
        else:
            await channel.connect()
        await interaction.response.send_message(f"🎙 {channel.name} に参加しました！")
    else:
        await interaction.response.send_message("❌ 先にボイスチャンネルに入ってください。", ephemeral=True)

@bot.tree.command(name="voice", description="読み上げの声質を設定します")
@app_commands.choices(style=[
    app_commands.Choice(name="標準（通常）", value="normal"),
    app_commands.Choice(name="ゆっくり（低速）", value="slow"),
])
async def voice(interaction: discord.Interaction, style: app_commands.Choice[str]):
    guild_id = interaction.guild_id
    if style.value == "slow":
        voice_settings[guild_id] = {"slow": True, "tld": "co.jp"}
        msg = "🐢 読み上げ音声を**ゆっくり**に設定しました！"
    else:
        voice_settings[guild_id] = {"slow": False, "tld": "co.jp"}
        msg = "🗣 読み上げ音声を**標準**に設定しました！"
    save_config()
    await interaction.response.send_message(msg)

@bot.tree.command(name="leave", description="読み上げVCから退出します")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("👋 退出しました。")
    else:
        await interaction.response.send_message("❌ ボイスチャンネルに参加していません。", ephemeral=True)

# --------------------------------------------------
# 🎵 音楽再生・リピート機能 (/play, /stop, /loop)
# --------------------------------------------------
def play_next_song(guild_id, voice_client):
    """ 曲が終了したときに呼び出されるコールバック関数 """
    if not voice_client or not voice_client.is_connected():
        return

    # リピートが有効で、直前に再生していた曲情報がある場合
    if loop_settings.get(guild_id, False) and guild_id in current_playing_songs:
        song_data = current_playing_songs[guild_id]
        source = discord.FFmpegPCMAudio(song_data['url'], **FFmpeg_OPTIONS)
        voice_client.play(source, after=lambda e: play_next_song(guild_id, voice_client))

@bot.tree.command(name="play", description="YouTubeの音楽を再生します")
@app_commands.describe(query="YouTubeのURLまたは曲名")
async def play(interaction: discord.Interaction, query: str):
    if not interaction.user.voice:
        await interaction.response.send_message("❌ 先にボイスチャンネルに入ってください。", ephemeral=True)
        return

    await interaction.response.defer()
    channel = interaction.user.voice.channel
    voice_client = interaction.guild.voice_client

    if voice_client is None:
        voice_client = await channel.connect()
    elif voice_client.channel != channel:
        await voice_client.move_to(channel)

    YDL_OPTIONS = {
        'format': 'bestaudio/best', 
        'noplaylist': True,
        'default_search': 'ytsearch',
        'socket_timeout': 30,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
    }

    def search_ytdl(q):
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            try:
                if not q.startswith("http"):
                    info = ydl.extract_info(f"ytsearch:{q}", download=False)['entries'][0]
                else:
                    info = ydl.extract_info(q, download=False)
                return info
            except Exception as e:
                print(f"ytdlエラー: {e}")
                return None

    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: search_ytdl(query))
        
        if not data:
            await interaction.followup.send("❌ 音楽の取得に失敗しました。")
            return

        song_url = data['url']
        song_title = data.get('title', '不明なタイトル')
        guild_id = interaction.guild.id

        # 現在再生中の曲情報を保存（リピート用）
        current_playing_songs[guild_id] = {'url': song_url, 'title': song_title}

        if voice_client.is_playing():
            voice_client.stop()

        source = discord.FFmpegPCMAudio(song_url, **FFmpeg_OPTIONS)
        voice_client.play(source, after=lambda e: play_next_song(guild_id, voice_client))

        loop_status = "🔁 (リピート有効)" if loop_settings.get(guild_id, False) else ""
        await interaction.followup.send(f"🎶 再生中: **{song_title}** {loop_status}")
    except Exception as e:
        print(f"再生エラー: {e}")
        await interaction.followup.send("❌ 音楽の再生中にエラーが発生しました。")

@bot.tree.command(name="loop", description="音楽のリピート（ループ）再生のON/OFFを切り替えます")
async def loop_cmd(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    current_state = loop_settings.get(guild_id, False)
    
    # 状態を反転
    new_state = not current_state
    loop_settings[guild_id] = new_state
    save_config()

    if new_state:
        await interaction.response.send_message("🔁 音楽の**リピート再生を有効**にしました！", ephemeral=False)
    else:
        await interaction.response.send_message("➡️ 音楽の**リピート再生を無効**にしました。", ephemeral=False)

@bot.tree.command(name="stop", description="音楽の再生を停止します")
async def stop(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        guild_id = interaction.guild.id
        # 停止時はリピート用キャッシュをクリアしておくことも可能
        if guild_id in current_playing_songs:
            current_playing_songs.pop(guild_id, None)
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("⏹ 音楽を停止しました。")
    else:
        await interaction.response.send_message("❌ ボイスチャンネルに参加していません。", ephemeral=True)

# --------------------------------------------------
# 💬 メッセージ処理（読み上げ・スパム・自動機能）
# --------------------------------------------------
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    # 荒らし対策（スパム検知：5秒間に5回以上で1週間タイムアウト）
    user_id = message.author.id
    now = datetime.datetime.now()
    if user_id not in message_records:
        message_records[user_id] = []
    message_records[user_id] = [t for t in message_records[user_id] if now - t < datetime.timedelta(seconds=5)]
    message_records[user_id].append(now)

    if len(message_records[user_id]) >= 5:
        try:
            await message.author.timeout(datetime.timedelta(weeks=1), reason="スパム自動検知")
            await message.channel.send(f"⚠️ {message.author.mention} さんが連続投稿（荒らし行為）のため、1週間のタイムアウトになりました。")
            message_records[user_id] = []
        except Exception as e:
            print(f"タイムアウトエラー: {e}")

    await bot.process_commands(message)

    guild_id = message.guild.id
    text = message.content.strip()
    if not text or text.startswith("!"):
        return

    # 1. Wikipedia自動検索チャンネルの処理
    if message.channel.id == wiki_rooms.get(guild_id):
        try:
            url = f"https://ja.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(text)}&format=json"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                data = js.loads(response.read().decode('utf-8'))
                search_results = data.get('query', {}).get('search', [])
                if search_results:
                    title = search_results[0]['title']
                    page_url = f"https://ja.wikipedia.org/wiki/{urllib.parse.quote(title)}"
                    await message.channel.send(f"📖 **{title}**\n{page_url}")
        except Exception as e:
            print(f"Wiki自動検索エラー: {e}")

    # 2. 読み上げ処理
    if message.guild.voice_client:
        vc = message.guild.voice_client
        target_tts_id = tts_rooms.get(guild_id)
        if target_tts_id is None or message.channel.id == target_tts_id:
            while vc.is_playing():
                await asyncio.sleep(0.5)
            try:
                setting = voice_settings.get(guild_id, {"slow": False, "tld": "co.jp"})
                tts = gTTS(text=text, lang="ja", tld=setting["tld"], slow=setting["slow"])
                tts.save("tts.mp3")
                vc.play(discord.FFmpegPCMAudio("tts.mp3", **FFmpeg_OPTIONS))
            except Exception as e:
                print(f"音声再生エラー: {e}")

bot.run("MTUzODEyMTY2MDI0MTE1ODIxNQ.GicZXH.AiQSj7h1YdsDfyA74WzwLEOzED2lD2gPH_KMe0")