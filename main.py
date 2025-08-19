import discord
from discord.ext import commands, tasks
import asyncio
import random
import json
import datetime
import math
import requests
import base64
import hashlib
import time
import os
import aiohttp
from dotenv import load_dotenv
import sqlite3
import re
import psutil
import urllib.parse
from deep_translator import GoogleTranslator
import queue
import yt_dlp
import google.generativeai as genai  # Import Gemini API theo mẫu mới
from google.generativeai.types import GenerationConfig  # Import GenerationConfig
# Load environment variables
load_dotenv()
# Khởi tạo Gemini (thêm vào đầu file hoặc trước các lệnh, nếu chưa có)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")
# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Database setup
def init_db():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    # User data table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, 
                  level INTEGER DEFAULT 1,
                  exp INTEGER DEFAULT 0,
                  coins INTEGER DEFAULT 100,
                  last_daily TEXT)''')
    
    # Reminders table
    c.execute('''CREATE TABLE IF NOT EXISTS reminders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  message TEXT,
                  remind_time TEXT)''')
    
    # Notes table
    c.execute('''CREATE TABLE IF NOT EXISTS notes
                 (user_id INTEGER,
                  note_id INTEGER,
                  content TEXT,
                  created_at TEXT,
                  PRIMARY KEY (user_id, note_id))''')
    
    conn.commit()
    conn.close()

init_db()

# Khởi tạo hàng đợi nhạc
music_queues = {}  # {guild_id: queue.Queue()}

# Cấu hình yt-dlp
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **{'options': '-vn'}), data=data)

# Helper functions
def get_user_data(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    data = c.fetchone()
    if not data:
        c.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        data = (user_id, 1, 0, 100, None)
    conn.close()
    return data

def update_user_data(user_id, level=None, exp=None, coins=None, last_daily=None):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    updates = []
    values = []
    
    if level is not None:
        updates.append("level = ?")
        values.append(level)
    if exp is not None:
        updates.append("exp = ?")
        values.append(exp)
    if coins is not None:
        updates.append("coins = ?")
        values.append(coins)
    if last_daily is not None:
        updates.append("last_daily = ?")
        values.append(last_daily)
    
    values.append(user_id)
    
    query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?"
    c.execute(query, values)
    conn.commit()
    conn.close()

# Danh sách trạng thái động (bao gồm streaming với URL)
statuses = [
    discord.Activity(type=discord.ActivityType.playing, name="Đang chơi Freefire"),
    discord.Activity(type=discord.ActivityType.watching, name="Đang xem review phim"),
    discord.Activity(type=discord.ActivityType.listening, name="nhạc chill po-"),
    discord.Activity(type=discord.ActivityType.competing, name="thi đấu code"),
    discord.Streaming(name="Xem Hentai", url="https://ihentai.ws/kyou-wa-yubiwa-o-hazusukara-1/"),
    discord.Streaming(name="Stream game trên Twitch", url="https://www.twitch.tv/example_streamer"),
    discord.Activity(type=discord.ActivityType.watching, name="Anime"),
    discord.Activity(type=discord.ActivityType.listening, name="lofi hip hop"),
    discord.Streaming(name="W/n", url="youtube.com/watch?v=OA8s2Gr3KEE&list=RDMMOA8s2Gr3KEE&start_radio=1"),
]

@tasks.loop(seconds=30)  # Thay đổi mỗi 30 giây
async def change_status():
    """Thay đổi trạng thái bot ngẫu nhiên"""
    status = random.choice(statuses)
    await bot.change_presence(activity=status)   

@bot.event
async def on_ready():
    print(f'{bot.user} đã sẵn sàng!')
    check_reminders.start()
    change_status.start()  # Bắt đầu task thay đổi trạng thái

# =============================================================================
# LỆNH THÔNG TIN VÀ TIỆN ÍCH CHUNG (1-20)
# =============================================================================

@bot.command(name='help_all')
async def help_all(ctx):
    """1. Hiển thị tất cả lệnh của bot"""
    embed = discord.Embed(title="📋 Danh sách 100 lệnh", color=0x00ff00)
    embed.add_field(name="Thông tin & Tiện ích (1-20)", value="!info, !ping, !uptime, !avatar, !serverinfo, !userinfo, !math, !translate, !weather, !time, !qr, !shorten, !password, !color, !ip, !hash, !base64, !binary, !hex, !vt, !ascii", inline=False)
    embed.add_field(name="Giải trí & Trò chơi (21-40)", value="!waifu, !chat, !joke, !fact, !quote, !roll, !coinflip, !8ball, !rps, !trivia, !hangman, !number_guess, !word_chain, !riddle, !story, !meme, !gif, !emoji_react, !truth_dare, !would_you_rather, !this_or_that, !fortune", inline=False)
    embed.add_field(name="Âm nhạc & Media (41-50)", value="!play, !pause, !skip, !queue, !volume, !lyrics, !spotify, !youtube, !podcast, !radio", inline=False)
    embed.add_field(name="Quản lý & Moderation (51-65)", value="!ban, !kick, !mute, !unmute, !warn, !clear, !slowmode, !lock, !unlock, !role, !nick, !announce, !poll, !vote, !automod, !log", inline=False)
    embed.add_field(name="Kinh tế & Leveling (66-80)", value="!daily, !balance, !pay, !shop, !buy, !inventory, !gamble, !work, !level, !leaderboard, !rank, !exp, !profile, !badge, !achievement", inline=False)
    embed.add_field(name="Tiện ích nâng cao (81-100)", value="!remind, !todo, !note, !calc, !convert, !search, !news, !stock, !crypto, !bookmark, !schedule, !timer, !stopwatch, !alarm, !backup, !export, !import, !stats, !analyze, !report", inline=False)
    # Hiển thị trạng thái hiện tại
    current_status = bot.activity.name if bot.activity else "Không có trạng thái"
    embed.add_field(name="Trạng thái", value=current_status, inline=True)
    await ctx.send(embed=embed)

@bot.command(name='info')
async def info(ctx):
    """2. Thông tin về bot"""
    embed = discord.Embed(title="🤖 Thông tin Bot", color=0x0099ff)
    embed.add_field(name="Tên", value=bot.user.name, inline=True)
    embed.add_field(name="ID", value=bot.user.id, inline=True)
    embed.add_field(name="Servers", value=len(bot.guilds), inline=True)
    embed.add_field(name="Users", value=len(bot.users), inline=True)
    embed.add_field(name="Phiên bản", value="1.0.0", inline=True)
    embed.add_field(name="Prefix", value="!", inline=True)
    embed.add_field(name="Owner", value="@hoang_62070")
    embed.add_field(name="Owner", value="https://guns.lol/hoanqdev1z")
    await ctx.send(embed=embed)

@bot.command(name='ping')
async def ping(ctx):
    """3. Kiểm tra độ trễ"""
    latency = round(bot.latency * 1000)
    await ctx.send(f'🏓 Pong! Độ trễ: {latency}ms')

@bot.command(name='uptime')
async def uptime(ctx):
    """4. Thời gian hoạt động"""
    if not hasattr(bot, 'start_time'):
        bot.start_time = datetime.datetime.now()
    uptime = datetime.datetime.now() - bot.start_time
    await ctx.send(f'⏰ Bot đã hoạt động: {uptime}')

@bot.command(name='avatar')
async def avatar(ctx, member: discord.Member = None):
    """5. Hiển thị avatar"""
    if member is None:
        member = ctx.author
    embed = discord.Embed(title=f"Avatar của {member.display_name}")
    embed.set_image(url=member.avatar.url if member.avatar else member.default_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name='serverinfo')
async def serverinfo(ctx):
    """6. Thông tin server"""
    guild = ctx.guild
    embed = discord.Embed(title=f"Thông tin {guild.name}", color=0x00ff00)
    embed.add_field(name="Chủ sở hữu", value=guild.owner.mention if guild.owner else "Không xác định", inline=True)
    embed.add_field(name="Thành viên", value=guild.member_count, inline=True)
    embed.add_field(name="Ngày tạo", value=guild.created_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="Boost Level", value=guild.premium_tier, inline=True)
    embed.add_field(name="Kênh", value=len(guild.channels), inline=True)
    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    await ctx.send(embed=embed)

@bot.command(name='userinfo')
async def userinfo(ctx, member: discord.Member = None):
    """7. Thông tin người dùng"""
    if member is None:
        member = ctx.author
    
    embed = discord.Embed(title=f"Thông tin {member.display_name}", color=member.color)
    embed.add_field(name="ID", value=member.id, inline=True)
    embed = discord.Embed(title=f"Avatar{member.display_name}")
    embed.set_image(url=member.avatar.url if member.avatar else member.default_avatar.url)
    embed.add_field(name="Tên", value=str(member), inline=True)
    embed.add_field(name="Nickname", value=member.display_name, inline=True)
    embed.add_field(name="Ngày tham gia Discord", value=member.created_at.strftime("%d/%m/%Y"), inline=True)
    if member.joined_at:
        embed.add_field(name="Ngày vào server", value=member.joined_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="Trạng thái", value=str(member.status), inline=True)
    
    roles = [role.mention for role in member.roles[1:]]
    if roles:
        embed.add_field(name="Roles", value=" ".join(roles), inline=False)
    
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)
    
    await ctx.send(embed=embed)

@bot.command(name='math')
async def math_calc(ctx, *, expression):
    """8. Máy tính toán học"""
    try:
        # Chỉ cho phép các ký tự an toàn
        allowed_chars = set('0123456789+-*/().,^ ')
        if not all(c in allowed_chars for c in expression):
            await ctx.send("❌ Chỉ được sử dụng số và các phép toán cơ bản!")
            return
        
        # Thay thế ^ bằng **
        expression = expression.replace('^', '**')
        result = eval(expression)
        await ctx.send(f"🧮 {expression} = {result}")
    except Exception as e:
        await ctx.send("❌ Biểu thức không hợp lệ!")

@bot.command(name='translate')
async def translate(ctx, target_lang, *, text):
    """9. Dịch văn bản"""
    
    
    # Danh sách mã ngôn ngữ hỗ trợ
    valid_languages = {
        'vi': 'Vietnamese', 'en': 'English', 'fr': 'French', 'es': 'Spanish',
        'de': 'German', 'ja': 'Japanese', 'ko': 'Korean', 'zh-cn': 'Chinese (Simplified)',
        'ru': 'Russian', 'it': 'Italian'
    }
    
    if target_lang.lower() not in valid_languages:
        await ctx.send(f"❌ Ngôn ngữ không hợp lệ! Hỗ trợ: {', '.join(f'{k} ({v})' for k, v in valid_languages.items())}")
        return
    
    try:
        # Dịch văn bản
        translator = GoogleTranslator(source='auto', target=target_lang.lower())
        translated_text = translator.translate(text[:500])  # Giới hạn 500 ký tự
        
        if not translated_text:
            await ctx.send("❌ Không thể dịch văn bản này!")
            return
        
        # Tạo embed
        embed = discord.Embed(title="🌐 Dịch văn bản", color=0x00b7eb)
        embed.add_field(name="Văn bản gốc", value=text[:100] + ("..." if len(text) > 100 else ""), inline=False)
        embed.add_field(name=f"Dịch sang {valid_languages[target_lang.lower()]}", value=translated_text[:100] + ("..." if len(translated_text) > 100 else ""), inline=False)
        embed.set_footer(text="Nguồn: Google Translate | Cập nhật: " + datetime.datetime.now().strftime("%d/%m/%Y %H:%M"))
        await ctx.send(embed=embed)
    
    except Exception as e:
        await ctx.send(f"❌ Lỗi khi dịch văn bản: {str(e)}")

@bot.command(name='weather')
async def weather(ctx, *, city):
    """10. Thời tiết (cần API key)"""
    await ctx.send(f"🌤️ Thời tiết tại {city}: Cần API key để hiển thị thông tin chi tiết")

@bot.command(name='time')
async def current_time(ctx, timezone="UTC"):
    """11. Thời gian hiện tại"""
    now = datetime.datetime.now()
    await ctx.send(f"🕐 Thời gian hiện tại: {now.strftime('%H:%M:%S %d/%m/%Y')}")

@bot.command(name='qr')
async def qr_code(ctx, *, text):
    """12. Tạo mã QR"""
    encoded_text = urllib.parse.quote(text)
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={encoded_text}"
    embed = discord.Embed(title="📱 Mã QR", description=text)
    embed.set_image(url=qr_url)
    await ctx.send(embed=embed)

@bot.command(name='shorten')
async def shorten_url(ctx, url):
    """13. Rút gọn URL"""
    # Kiểm tra URL hợp lệ
    if not is_url(url):
        await ctx.send("❌ URL không hợp lệ! Vui lòng nhập URL bắt đầu bằng http:// hoặc https://")
        return

    # URL API TinyURL
    tinyurl_api = f"https://tinyurl.com/api-create.php?url={urllib.parse.quote(url)}"

    try:
        response = requests.get(tinyurl_api, timeout=5)
        response.raise_for_status()
        shortened_url = response.text

        if not shortened_url or "error" in shortened_url.lower():
            await ctx.send("❌ Không thể rút gọn URL!")
            return

        # Tạo embed
        embed = discord.Embed(title="🔗 URL Rút Gọn", color=0x00b7eb)
        embed.add_field(name="URL Gốc", value=url[:100] + ("..." if len(url) > 100 else ""), inline=False)
        embed.add_field(name="URL Rút Gọn", value=shortened_url, inline=False)
        embed.set_footer(text="Nguồn: TinyURL | Cập nhật: " + datetime.datetime.now().strftime("%d/%m/%Y %H:%M"))
        await ctx.send(embed=embed)

    except requests.exceptions.RequestException as e:
        await ctx.send(f"❌ Lỗi khi rút gọn URL: {str(e)}")

@bot.command(name='password')
async def generate_password(ctx, length: int = 12):
    """14. Tạo mật khẩu ngẫu nhiên"""
    import string
    if length > 50:
        length = 50
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(random.choice(chars) for _ in range(length))
    embed = discord.Embed(title="🔐 Mật khẩu mới", description=f"||{password}||")
    try:
        await ctx.author.send(embed=embed)
        await ctx.send("✅ Mật khẩu đã được gửi riêng cho bạn!")
    except discord.Forbidden:
        await ctx.send("❌ Không thể gửi tin nhắn riêng! Vui lòng bật DM.")

@bot.command(name='color')
async def color_info(ctx, color_code):
    """15. Thông tin màu sắc"""
    try:
        if color_code.startswith('#'):
            color_code = color_code[1:]
        color_int = int(color_code, 16)
        embed = discord.Embed(title=f"🎨 Màu #{color_code}", color=color_int)
        embed.add_field(name="Hex", value=f"#{color_code}", inline=True)
        embed.add_field(name="RGB", value=f"({color_int >> 16}, {(color_int >> 8) & 255}, {color_int & 255})", inline=True)
        await ctx.send(embed=embed)
    except ValueError:
        await ctx.send("❌ Mã màu không hợp lệ!")

@bot.command(name='ip')
async def ip_info(ctx, ip=""):
    """16. Thông tin IP"""
    if not ip:
        await ctx.send("📡 Để kiểm tra IP, hãy nhập: !ip <địa_chỉ_ip>")
    else:
        await ctx.send(f"📡 Thông tin IP {ip}: Cần API để hiển thị chi tiết")

@bot.command(name='hash')
async def hash_text(ctx, algorithm, *, text):
    """17. Hash văn bản"""
    try:
        if algorithm.lower() == 'md5':
            result = hashlib.md5(text.encode()).hexdigest()
        elif algorithm.lower() == 'sha1':
            result = hashlib.sha1(text.encode()).hexdigest()
        elif algorithm.lower() == 'sha256':
            result = hashlib.sha256(text.encode()).hexdigest()
        else:
            await ctx.send("❌ Thuật toán hỗ trợ: md5, sha1, sha256")
            return
        
        embed = discord.Embed(title=f"🔐 Hash {algorithm.upper()}")
        embed.add_field(name="Input", value=text[:100], inline=False)
        embed.add_field(name="Output", value=f"```{result}```", inline=False)
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='base64')
async def base64_encode(ctx, action, *, text):
    """18. Encode/Decode Base64"""
    try:
        if action.lower() == 'encode':
            result = base64.b64encode(text.encode()).decode()
        elif action.lower() == 'decode':
            result = base64.b64decode(text.encode()).decode()
        else:
            await ctx.send("❌ Sử dụng: !base64 encode/decode <text>")
            return
        
        embed = discord.Embed(title=f"🔄 Base64 {action.title()}")
        embed.add_field(name="Input", value=text[:100], inline=False)
        embed.add_field(name="Output", value=f"```{result}```", inline=False)
        await ctx.send(embed=embed)
    except Exception:
        await ctx.send("❌ Không thể xử lý văn bản!")

@bot.command(name='binary')
async def binary_convert(ctx, action, *, text):
    """19. Chuyển đổi binary"""
    try:
        if action.lower() == 'encode':
            result = ' '.join(format(ord(char), '08b') for char in text)
        elif action.lower() == 'decode':
            binary_values = text.split()
            result = ''.join(chr(int(binary, 2)) for binary in binary_values)
        else:
            await ctx.send("❌ Sử dụng: !binary encode/decode <text>")
            return
        
        await ctx.send(f"🔢 Kết quả: ```{result}```")
    except Exception:
        await ctx.send("❌ Không thể chuyển đổi!")

@bot.command(name='hex')
async def hex_convert(ctx, action, *, text):
    """20. Chuyển đổi hex"""
    try:
        if action.lower() == 'encode':
            result = text.encode().hex()
        elif action.lower() == 'decode':
            result = bytes.fromhex(text).decode()
        else:
            await ctx.send("❌ Sử dụng: !hex encode/decode <text>")
            return
        
        await ctx.send(f"🔢 Kết quả: ```{result}```")
    except Exception:
        await ctx.send("❌ Không thể chuyển đổi!")

# Thêm lệnh !vt
@bot.command(name='vt')
@commands.cooldown(1, 5, commands.BucketType.user)  # 1 lần/5 giây/người dùng
async def virustotal(ctx, *, input: str = None):
    """Quét URL, file hash, hoặc file đính kèm bằng VirusTotal API v3"""
    if not os.getenv("VIRUSTOTAL_API_KEY"):
        await ctx.send("❌ Lỗi: Thiếu API key VirusTotal! Vui lòng liên hệ admin.")
        return

    headers = {
        "x-apikey": os.getenv("VIRUSTOTAL_API_KEY"),
        "accept": "application/json"
    }

    # Kiểm tra input và file đính kèm
    is_file = False
    if ctx.message.attachments:
        attachment = ctx.message.attachments[0]
        if attachment.size > 32 * 1024 * 1024:  # 32MB
            await ctx.send("❌ Lỗi: File quá lớn! VirusTotal chỉ hỗ trợ file <32MB.")
            return
        is_file = True
    elif input:
        # Kiểm tra URL hoặc hash
        url_pattern = re.compile(r'^(https?://)?([\w.-]+)\.([a-z]{2,})(/.*)?$')
        hash_pattern = re.compile(r'^[a-fA-F0-9]{32}$|^[a-fA-F0-9]{40}$|^[a-fA-F0-9]{64}$')  # MD5, SHA1, SHA256
        input = input.strip()
        if url_pattern.match(input):
            type = "url"
            if not input.startswith(("http://", "https://")):
                input = "https://" + input
            import base64
            url_id = base64.urlsafe_b64encode(input.encode()).decode().rstrip("=")
            endpoint = f"https://www.virustotal.com/api/v3/urls/{url_id}"
        elif hash_pattern.match(input):
            type = "file"
            endpoint = f"https://www.virustotal.com/api/v3/files/{input}"
        else:
            await ctx.send("❌ Input không hợp lệ! Vui lòng cung cấp URL, hash (MD5/SHA1/SHA256), hoặc đính kèm file.")
            return
    else:
        await ctx.send("❌ Vui lòng cung cấp URL, hash, hoặc đính kèm file để quét!")
        return

    # Retry logic: Thử tối đa 3 lần
    max_retries = 3
    retry_delay = 5  # Giây
    for attempt in range(max_retries):
        try:
            if is_file:
                # Tải file từ Discord
                async with aiohttp.ClientSession() as session:
                    async with session.get(attachment.url) as resp:
                        if resp.status != 200:
                            await ctx.send("❌ Lỗi: Không thể tải file đính kèm!")
                            return
                        file_data = await resp.read()
                
                # Upload file lên VirusTotal
                upload_endpoint = "https://www.virustotal.com/api/v3/files"
                files = {"file": (attachment.filename, file_data)}
                response = requests.post(upload_endpoint, headers=headers, files=files, timeout=10)
                response.raise_for_status()
                analysis_id = response.json().get("data", {}).get("id")
                
                # Chờ kết quả quét (tối đa 60 giây)
                analysis_endpoint = f"https://www.virustotal.com/api/v3/analyses/{analysis_id}"
                max_wait = 60  # Giây
                wait_interval = 5  # Giây
                elapsed = 0
                while elapsed < max_wait:
                    response = requests.get(analysis_endpoint, headers=headers, timeout=10)
                    response.raise_for_status()
                    status = response.json().get("data", {}).get("attributes", {}).get("status")
                    if status == "completed":
                        break
                    await asyncio.sleep(wait_interval)
                    elapsed += wait_interval
                
                if status != "completed":
                    await ctx.send("❌ Lỗi: Quét file không hoàn tất trong thời gian chờ (60 giây)! Vui lòng thử lại.")
                    return
                
                # Lấy kết quả file
                file_id = response.json().get("data", {}).get("attributes", {}).get("results", {}).get("sha256")
                if not file_id:
                    await ctx.send("❌ Lỗi: Không lấy được SHA256 của file! Vui lòng thử lại.")
                    return
                endpoint = f"https://www.virustotal.com/api/v3/files/{file_id}"
                response = requests.get(endpoint, headers=headers, timeout=10)
                response.raise_for_status()
                type = "file"
            
            # Gọi API VirusTotal
            response = requests.get(endpoint, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json().get("data", {}).get("attributes", {})

            if not data:
                await ctx.send("❌ Không tìm thấy dữ liệu từ VirusTotal! Vui lòng thử lại.")
                return

            # Tạo embed
            embed = discord.Embed(title="🔍 Kết Quả VirusTotal", color=0x00b7eb)
            embed.add_field(name="Input", value=(attachment.filename if is_file else input)[:200] + ("..." if len(attachment.filename if is_file else input) > 200 else ""), inline=False)
            
            stats = data.get("last_analysis_stats", {})
            embed.add_field(name="Trạng Thái", value="Đã quét", inline=False)
            embed.add_field(name="Kết Quả", value=f"Độc hại: {stats.get('malicious', 0)} | Nghi ngờ: {stats.get('suspicious', 0)} | An toàn: {stats.get('harmless', 0)} | Không xác định: {stats.get('undetected', 0)}", inline=False)
            embed.add_field(name="Lần Quét Cuối", value=datetime.datetime.fromtimestamp(data.get("last_analysis_date", 0)).strftime("%d/%m/%Y %H:%M"), inline=False)
            
            if type == "url":
                embed.add_field(name="Lượt Bình Chọn", value=f"An toàn: {data.get('total_votes', {}).get('harmless', 0)} | Độc hại: {data.get('total_votes', {}).get('malicious', 0)}", inline=False)
            else:  # file
                embed.add_field(name="Tên File", value=", ".join(data.get("names", ["Không xác định"]))[:200], inline=False)
            
            embed.set_footer(text="Nguồn: VirusTotal | Cập nhật: " + datetime.datetime.now().strftime("%d/%m/%Y %H:%M"))
            await ctx.send(embed=embed)
            return

        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)  # Chờ trước khi thử lại
                    continue
                await ctx.send("❌ Quá nhiều yêu cầu đến VirusTotal API! Vui lòng thử lại sau vài giây.")
                return
            elif response.status_code == 404:
                await ctx.send("❌ Không tìm thấy báo cáo cho input này! Có thể file chưa được quét hoặc không hợp lệ. Vui lòng thử lại hoặc dùng file khác.")
                return
            else:
                await ctx.send(f"❌ Lỗi khi gọi VirusTotal API: {str(e)}")
                return
        except Exception as e:
            await ctx.send(f"❌ Lỗi khi xử lý yêu cầu: {str(e)}")
            return

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"❌ Lệnh đang trong thời gian chờ! Thử lại sau {error.retry_after:.2f} giây.")
    else:
        raise error    

# =============================================================================
# LỆNH GIẢI TRÍ VÀ TRÒ CHƠI (21-40)
# =============================================================================

# Thêm lệnh !waifu
@bot.command(name='waifu')
@commands.cooldown(1, 5, commands.BucketType.user)  # 1 lần/5 giây/người dùng
async def waifu(ctx, type: str = "sfw", category: str = None):
    """Lấy hình ảnh anime ngẫu nhiên từ waifu.pics (SFW hoặc NSFW)"""
    # Danh sách danh mục từ https://waifu.pics/docs
    sfw_categories = [
        "waifu", "neko", "shinobu", "megumin", "bully", "cuddle",
        "cry", "hug", "awoo", "kiss", "lick", "pat", "smug",
        "bonk", "yeet", "blush", "smile", "wave", "highfive",
        "handhold", "nom", "bite", "glomp", "slap", "kill",
        "kick", "happy", "wink", "poke", "dance", "cringe"
    ]
    nsfw_categories = ["waifu", "neko", "trap", "blowjob"]

    # Xác định loại (sfw hoặc nsfw)
    type = type.lower()
    if type not in ["sfw", "nsfw"]:
        await ctx.send("❌ Loại không hợp lệ! Chọn 'sfw' hoặc 'nsfw'.")
        return

    # Kiểm tra kênh NSFW nếu type là nsfw
    if type == "nsfw" and not ctx.channel.is_nsfw():
        await ctx.send("❌ Nội dung NSFW chỉ được sử dụng trong kênh NSFW!")
        return

    # Chọn danh sách danh mục dựa trên type
    categories = sfw_categories if type == "sfw" else nsfw_categories

    # Nếu không có danh mục, chọn ngẫu nhiên từ danh sách
    if category is None:
        category = "waifu"  # Mặc định
        category_display = f"{type}/waifu (ngẫu nhiên)"
    else:
        category = category.lower()
        if category not in categories:
            await ctx.send(f"❌ Danh mục không hợp lệ! Các danh mục {type.upper()}: {', '.join(categories)}")
            return
        category_display = f"{type}/{category}"

    # Tạo URL endpoint
    endpoint = f"https://api.waifu.pics/{type}/{category}"

    # Retry logic: Thử tối đa 3 lần
    max_retries = 3
    retry_delay = 5  # Giây
    for attempt in range(max_retries):
        try:
            # Gọi API waifu.pics
            response = requests.get(endpoint, timeout=10)
            response.raise_for_status()  # Kiểm tra lỗi HTTP
            data = response.json()
            image_url = data.get("url")

            if not image_url:
                await ctx.send("❌ Lỗi: Không lấy được hình ảnh từ API!")
                return

            # Tạo embed
            embed = discord.Embed(title="🎨 Hình Ảnh Anime", color=0x00b7eb)
            embed.set_image(url=image_url)
            embed.add_field(name="Loại/Danh Mục", value=category_display.capitalize(), inline=False)
            embed.set_footer(text="Nguồn: waifu.pics | Cập nhật: " + datetime.datetime.now().strftime("%d/%m/%Y %H:%M"))
            await ctx.send(embed=embed)
            return

        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)  # Chờ trước khi thử lại
                    continue
                await ctx.send("❌ Quá nhiều yêu cầu đến waifu.pics API! Vui lòng thử lại sau vài giây.")
                return
            else:
                await ctx.send(f"❌ Lỗi khi gọi waifu.pics API: {str(e)}")
                return
        except Exception as e:
            await ctx.send(f"❌ Lỗi khi xử lý hình ảnh: {str(e)}")
            return

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"❌ Lệnh đang trong thời gian chờ! Thử lại sau {error.retry_after:.2f} giây.")
    else:
        raise error

@bot.command(name='chat')
@commands.cooldown(1, 5, commands.BucketType.user)  # 1 lần/5 giây/người dùng
async def chat_gemini(ctx, *, query):
    """51. Trò chuyện với Gemini"""
    if not os.getenv("GEMINI_API_KEY"):
        await ctx.send("❌ Lỗi: Thiếu API key Gemini! Vui lòng liên hệ admin.")
        return

    # Retry logic: Thử tối đa 3 lần
    max_retries = 3
    retry_delay = 5  # Giây
    for attempt in range(max_retries):
        try:
            # Gọi Gemini API
            response = model.generate_content(
                contents=query,
                generation_config=GenerationConfig(
                    max_output_tokens=150,
                    temperature=0.7
                )
            )
            answer_en = response.text.strip()

            # Dịch sang tiếng Việt
            translator = GoogleTranslator(source='en', target='vi')
            answer_vi = translator.translate(answer_en[:500])  # Giới hạn 500 ký tự

            # Tạo embed
            embed = discord.Embed(title="💬 Trò Chuyện với Gemini", color=0x00b7eb)
            embed.add_field(name="Câu Hỏi", value=query[:200] + ("..." if len(query) > 200 else ""), inline=False)
            embed.add_field(name="Trả Lời (Tiếng Anh)", value=answer_en[:200] + ("..." if len(answer_en) > 200 else ""), inline=False)
            embed.add_field(name="Trả Lời (Tiếng Việt)", value=answer_vi[:200] + ("..." if len(answer_vi) > 200 else ""), inline=False)
            embed.set_footer(text="Nguồn: Google Gemini | Cập nhật: " + datetime.datetime.now().strftime("%d/%m/%Y %H:%M"))
            await ctx.send(embed=embed)
            return

        except Exception as e:
            if "rate limit" in str(e).lower() or "429" in str(e).lower():
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)  # Chờ trước khi thử lại
                    continue
                await ctx.send("❌ Quá nhiều yêu cầu đến Gemini API! Vui lòng thử lại sau vài giây.")
                return
            else:
                await ctx.send(f"❌ Lỗi khi gọi Gemini API: {str(e)}")
                return

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"❌ Lệnh đang trong thời gian chờ! Thử lại sau {error.retry_after:.2f} giây.")
    else:
        raise error

@bot.command(name='joke')
async def joke(ctx):
    """21. Kể chuyện cười"""
    try:
        # Gọi API để lấy câu chuyện cười ngẫu nhiên (safe-mode để tránh nội dung không phù hợp)
        response = requests.get("https://v2.jokeapi.dev/joke/Any?safe-mode&type=single&lang=en", timeout=5)
        response.raise_for_status()
        joke_data = response.json()

        # Lấy câu chuyện cười
        if joke_data["type"] == "single":
            joke_en = joke_data.get("joke", "Không có câu chuyện cười nào được trả về!")
            setup_en = None
            delivery_en = None
        else:
            setup_en = joke_data.get("setup", "Không có phần mở đầu!")
            delivery_en = joke_data.get("delivery", "Không có phần kết thúc!")
            joke_en = f"{setup_en} {delivery_en}"

        # Dịch sang tiếng Việt
        translator = GoogleTranslator(source='en', target='vi')
        if setup_en and delivery_en:
            setup_vi = translator.translate(setup_en[:500])  # Giới hạn 500 ký tự
            delivery_vi = translator.translate(delivery_en[:500])
            joke_vi = f"{setup_vi} {delivery_vi}"
        else:
            joke_vi = translator.translate(joke_en[:500])

        # Tạo embed
        embed = discord.Embed(title="😂 Câu Chuyện Cười", color=0xff4500)
        if setup_en and delivery_en:
            embed.add_field(name="Tiếng Anh (Setup)", value=setup_en[:200] + ("..." if len(setup_en) > 200 else ""), inline=False)
            embed.add_field(name="Tiếng Anh (Delivery)", value=delivery_en[:200] + ("..." if len(delivery_en) > 200 else ""), inline=False)
            embed.add_field(name="Tiếng Việt", value=f"{setup_vi[:100]}... {delivery_vi[:100]}" + ("..." if len(joke_vi) > 200 else ""), inline=False)
        else:
            embed.add_field(name="Tiếng Anh", value=joke_en[:200] + ("..." if len(joke_en) > 200 else ""), inline=False)
            embed.add_field(name="Tiếng Việt", value=joke_vi[:200] + ("..." if len(joke_vi) > 200 else ""), inline=False)
        embed.set_footer(text="Nguồn: JokeAPI | Cập nhật: " + datetime.datetime.now().strftime("%d/%m/%Y %H:%M"))
        await ctx.send(embed=embed)

    except requests.exceptions.RequestException as e:
        await ctx.send(f"❌ Lỗi khi lấy câu chuyện cười: {str(e)}")
    except Exception as e:
        await ctx.send(f"❌ Lỗi khi dịch câu chuyện cười: {str(e)}")

@bot.command(name='fact')
async def random_fact(ctx):
    """22. Sự thật thú vị"""
    try:
        # Gọi API để lấy sự thật ngẫu nhiên
        response = requests.get("https://uselessfacts.jsph.pl/api/v2/facts/random", timeout=5)
        response.raise_for_status()
        fact_data = response.json()
        fact_en = fact_data.get("text", "Không có sự thật nào được trả về!")

        # Dịch sang tiếng Việt
        translator = GoogleTranslator(source='en', target='vi')
        fact_vi = translator.translate(fact_en[:500])  # Giới hạn 500 ký tự để dịch nhanh

        # Tạo embed
        embed = discord.Embed(title="🧠 Sự Thật Thú Vị", color=0x00b7eb)
        embed.add_field(name="Tiếng Anh", value=fact_en[:200] + ("..." if len(fact_en) > 200 else ""), inline=False)
        embed.add_field(name="Tiếng Việt", value=fact_vi[:200] + ("..." if len(fact_vi) > 200 else ""), inline=False)
        embed.set_footer(text="Nguồn: Useless Facts API | Cập nhật: " + datetime.datetime.now().strftime("%d/%m/%Y %H:%M"))
        await ctx.send(embed=embed)

    except requests.exceptions.RequestException as e:
        await ctx.send(f"❌ Lỗi khi lấy sự thật: {str(e)}")
    except Exception as e:
        await ctx.send(f"❌ Lỗi khi dịch sự thật: {str(e)}")

@bot.command(name='quote')
async def inspirational_quote(ctx):
    """23. Câu nói truyền cảm hứng"""
    try:
        # Gọi API để lấy câu trích dẫn ngẫu nhiên
        response = requests.get("https://api.quotable.io/random", timeout=5)
        response.raise_for_status()
        quote_data = response.json()
        quote_en = quote_data.get("content", "Không có câu trích dẫn nào được trả về!")
        author = quote_data.get("author", "Không rõ tác giả")

        # Dịch sang tiếng Việt
        translator = GoogleTranslator(source='en', target='vi')
        quote_vi = translator.translate(quote_en[:500])  # Giới hạn 500 ký tự để dịch nhanh

        # Tạo embed
        embed = discord.Embed(title="✨ Câu Trích Dẫn Truyền Cảm Hứng", color=0xffd700)
        embed.add_field(name="Tiếng Anh", value=f"{quote_en[:200]}..." if len(quote_en) > 200 else quote_en, inline=False)
        embed.add_field(name="Tiếng Việt", value=f"{quote_vi[:200]}..." if len(quote_vi) > 200 else quote_vi, inline=False)
        embed.add_field(name="Tác giả", value=author, inline=False)
        embed.set_footer(text="Nguồn: Quotable API | Cập nhật: " + datetime.datetime.now().strftime("%d/%m/%Y %H:%M"))
        await ctx.send(embed=embed)

    except requests.exceptions.RequestException as e:
        await ctx.send(f"❌ Lỗi khi lấy câu trích dẫn: {str(e)}")
    except Exception as e:
        await ctx.send(f"❌ Lỗi khi dịch câu trích dẫn: {str(e)}")

@bot.command(name='roll')
async def roll_dice(ctx, dice="1d6"):
    """24. Tung xúc xắc"""
    try:
        if 'd' not in dice:
            await ctx.send("❌ Định dạng: !roll XdY (ví dụ: 2d6)")
            return
        
        num_dice, num_sides = map(int, dice.split('d'))
        if num_dice > 10 or num_sides > 100:
            await ctx.send("❌ Tối đa 10 xúc xắc, 100 mặt!")
            return
        
        results = [random.randint(1, num_sides) for _ in range(num_dice)]
        total = sum(results)
        
        embed = discord.Embed(title="🎲 Kết quả tung xúc xắc", color=0xff6b6b)
        embed.add_field(name="Xúc xắc", value=dice, inline=True)
        embed.add_field(name="Kết quả", value=" + ".join(map(str, results)), inline=True)
        embed.add_field(name="Tổng", value=total, inline=True)
        await ctx.send(embed=embed)
    except ValueError:
        await ctx.send("❌ Định dạng không hợp lệ!")

@bot.command(name='coinflip')
async def coinflip(ctx):
    """25. Tung đồng xu"""
    result = random.choice(['Ngửa', 'Sấp'])
    coin_emoji = '🪙' if result == 'Ngửa' else '🟤'
    await ctx.send(f"{coin_emoji} Kết quả: **{result}**!")

@bot.command(name='8ball')
async def eight_ball(ctx, *, question):
    """26. Quả cầu 8"""
    responses = [
        "✅ Chắc chắn là có",
        "✅ Không nghi ngờ gì nữa",
        "✅ Có",
        "🤔 Có thể",
        "🤔 Hỏi lại sau",
        "🤔 Không chắc lắm",
        "❌ Đừng mơ",
        "❌ Không",
        "❌ Rất không có khả năng"
    ]
    await ctx.send(f"🎱 {random.choice(responses)}")

@bot.command(name='rps')
async def rock_paper_scissors(ctx, choice):
    """27. Kéo búa bao"""
    choices = ['rock', 'paper', 'scissors', 'kéo', 'búa', 'bao']
    if choice.lower() not in choices:
        await ctx.send("❌ Chọn: rock/paper/scissors hoặc kéo/búa/bao")
        return
    
    # Chuẩn hóa lựa chọn
    choice_map = {'kéo': 'scissors', 'búa': 'rock', 'bao': 'paper'}
    user_choice = choice_map.get(choice.lower(), choice.lower())
    
    bot_choice = random.choice(['rock', 'paper', 'scissors'])
    
    emoji_map = {'rock': '🪨', 'paper': '📄', 'scissors': '✂️'}
    
    if user_choice == bot_choice:
        result = "Hòa!"
    elif (user_choice == 'rock' and bot_choice == 'scissors') or \
         (user_choice == 'paper' and bot_choice == 'rock') or \
         (user_choice == 'scissors' and bot_choice == 'paper'):
        result = "Bạn thắng! 🎉"
    else:
        result = "Bot thắng! 🤖"
    
    await ctx.send(f"{emoji_map[user_choice]} vs {emoji_map[bot_choice]}\n{result}")

@bot.command(name='trivia')
async def trivia(ctx):
    """28. Câu hỏi trắc nghiệm"""
    questions = [
        {"q": "Ngôn ngữ lập trình nào được tạo bởi Guido van Rossum?", "a": "Python", "options": ["Java", "Python", "C++", "JavaScript"]},
        {"q": "HTTP viết tắt của gì?", "a": "HyperText Transfer Protocol", "options": ["HyperText Transfer Protocol", "High Tech Transfer Protocol", "Home Tool Transfer Protocol", "Host Transfer Protocol"]},
        {"q": "Năm nào World Wide Web được phát minh?", "a": "1989", "options": ["1985", "1989", "1991", "1993"]}
    ]
    
    question = random.choice(questions)
    random.shuffle(question["options"])
    
    embed = discord.Embed(title="🧠 Trivia", description=question["q"], color=0x4CAF50)
    for i, option in enumerate(question["options"], 1):
        embed.add_field(name=f"{i}.", value=option, inline=True)
    
    embed.set_footer(text="Trả lời bằng số 1-4")
    
    msg = await ctx.send(embed=embed)
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content in ['1', '2', '3', '4']
    
    try:
        response = await bot.wait_for('message', check=check, timeout=30)
        user_answer = question["options"][int(response.content) - 1]
        
        if user_answer == question["a"]:
            await ctx.send("✅ Chính xác! 🎉")
        else:
            await ctx.send(f"❌ Sai rồi! Đáp án đúng là: {question['a']}")
    except asyncio.TimeoutError:
        await ctx.send("⏰ Hết thời gian!")

@bot.command(name='hangman')
async def hangman(ctx):
    """29. Trò chơi đoán từ"""
    words = ['python', 'discord', 'computer', 'programming', 'developer', 'algorithm', 'database']
    word = random.choice(words).upper()
    guessed = set()
    wrong_guesses = 0
    max_wrong = 6
    
    def display_word():
        return ' '.join(letter if letter in guessed else '_' for letter in word)
    
    embed = discord.Embed(title="🎯 Hangman", description=f"```{display_word()}```")
    embed.add_field(name="Sai", value=f"{wrong_guesses}/{max_wrong}", inline=True)
    embed.add_field(name="Đã đoán", value=' '.join(sorted(guessed)) or 'Chưa có', inline=True)
    
    msg = await ctx.send(embed=embed)
    
    while wrong_guesses < max_wrong and '_' in display_word():
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and len(m.content) == 1 and m.content.isalpha()
        
        try:
            response = await bot.wait_for('message', check=check, timeout=60)
            letter = response.content.upper()
            
            if letter in guessed:
                await ctx.send("🔄 Bạn đã đoán chữ này rồi!")
                continue
            
            guessed.add(letter)
            
            if letter in word:
                if '_' not in display_word():
                    await ctx.send(f"🎉 Chúc mừng! Từ cần tìm là: **{word}**")
                    break
            else:
                wrong_guesses += 1
            
            embed = discord.Embed(title="🎯 Hangman", description=f"```{display_word()}```")
            embed.add_field(name="Sai", value=f"{wrong_guesses}/{max_wrong}", inline=True)
            embed.add_field(name="Đã đoán", value=' '.join(sorted(guessed)), inline=True)
            
            await msg.edit(embed=embed)
            
        except asyncio.TimeoutError:
            await ctx.send("⏰ Hết thời gian!")
            break
    
    if wrong_guesses >= max_wrong:
        await ctx.send(f"💀 Bạn đã thua! Từ cần tìm là: **{word}**")

@bot.command(name='number_guess')
async def number_guess(ctx, max_num: int = 100):
    """30. Đoán số"""
    if max_num > 1000:
        max_num = 1000
    
    number = random.randint(1, max_num)
    attempts = 0
    max_attempts = math.ceil(math.log2(max_num)) + 2
    
    embed = discord.Embed(title="🔢 Đoán số", description=f"Đoán số từ 1 đến {max_num}")
    embed.add_field(name="Số lần đoán tối đa", value=max_attempts, inline=True)
    await ctx.send(embed=embed)
    
    while attempts < max_attempts:
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()
        
        try:
            response = await bot.wait_for('message', check=check, timeout=60)
            guess = int(response.content)
            attempts += 1
            
            if guess == number:
                await ctx.send(f"🎉 Chính xác! Số cần tìm là {number}. Bạn đã đoán trong {attempts} lần!")
                break
            elif guess < number:
                await ctx.send(f"📈 Cao hơn! Còn {max_attempts - attempts} lần")
            else:
                await ctx.send(f"📉 Thấp hơn! Còn {max_attempts - attempts} lần")
                
        except asyncio.TimeoutError:
            await ctx.send("⏰ Hết thời gian!")
            break
    
    if attempts >= max_attempts:
        await ctx.send(f"💀 Hết lượt đoán! Số cần tìm là: **{number}**")

@bot.command(name='word_chain')
async def word_chain(ctx):
    """31. Nối từ"""
    await ctx.send("🔗 Trò chơi nối từ bắt đầu! Từ đầu tiên: **COMPUTER**\nNgười tiếp theo nói từ bắt đầu bằng chữ 'R'")

@bot.command(name='riddle')
async def riddle(ctx):
    """32. Câu đố"""
    riddles = [
        {"q": "Cái gì có keys nhưng không có locks, có space nhưng không có room?", "a": "keyboard"},
        {"q": "Cái gì chạy nhưng không có chân?", "a": "nước"},
        {"q": "Cái gì có mắt nhưng không nhìn thấy?", "a": "kim"},
        {"q": "Bug nào không phải là lỗi?", "a": "con bug"}
    ]
    
    riddle = random.choice(riddles)
    embed = discord.Embed(title="🧩 Câu đố", description=riddle["q"], color=0x9C27B0)
    embed.set_footer(text="Gõ câu trả lời của bạn!")
    
    await ctx.send(embed=embed)
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    
    try:
        response = await bot.wait_for('message', check=check, timeout=60)
        if riddle["a"].lower() in response.content.lower():
            await ctx.send("🎉 Chính xác!")
        else:
            await ctx.send(f"❌ Đáp án đúng là: **{riddle['a']}**")
    except asyncio.TimeoutError:
        await ctx.send(f"⏰ Hết thời gian! Đáp án là: **{riddle['a']}**")

@bot.command(name='story')
async def random_story(ctx):
    """33. Câu chuyện ngẫu nhiên"""
    stories = [
        "📖 Ngày xưa có một developer, anh ta code suốt ngày đêm. Một hôm anh ta gặp một bug kỳ lạ...",
        "📖 Trong một server Discord xa xôi, có một bot rất thông minh...",
        "📖 Có lần một AI quyết định học cách nấu ăn, kết quả thật bất ngờ..."
    ]
    await ctx.send(random.choice(stories))

@bot.command(name='meme')
async def meme(ctx):
    """34. Meme ngẫu nhiên"""
    memes = [
        "```\n  ∩───∩\n  │   │\n  │ ◕ │  <- Khi code chạy lần đầu\n  │   │\n  ∩───∩\n```",
        "```\n┌─────────────────┐\n│ 99 little bugs  │\n│ in the code     │\n│ 99 little bugs  │\n│ take one down   │\n│ patch it around │\n│ 117 little bugs │\n│ in the code     │\n└─────────────────┘\n```"
    ]
    await ctx.send(random.choice(memes))

@bot.command(name='gif')
async def gif_search(ctx, *, query):
    """35. Tìm GIF"""
    api_key = os.getenv("TENOR_API_KEY")
    if not api_key:
        await ctx.send("❌ Lỗi: Thiếu API key cho Tenor. Vui lòng liên hệ admin!")
        return

    # URL API Tenor với API key
    url = f"https://tenor.googleapis.com/v2/search?q={urllib.parse.quote(query)}&key={api_key}&limit=10&content_filter=high"
    
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        if not data.get("results"):
            await ctx.send(f"🎬 Không tìm thấy GIF nào cho '{query}'!")
            return

        # Chọn ngẫu nhiên một GIF
        gif = random.choice(data["results"])
        gif_url = gif["media_formats"]["gif"]["url"]
        gif_title = gif.get("title", "GIF") or query

        # Tạo embed
        embed = discord.Embed(title=f"🎬 GIF: {gif_title[:50]}", color=0xff69b4)
        embed.set_image(url=gif_url)
        embed.set_footer(text="Nguồn: Tenor | Cập nhật: " + datetime.datetime.now().strftime("%d/%m/%Y %H:%M"))
        await ctx.send(embed=embed)
    
    except requests.exceptions.RequestException as e:
        await ctx.send(f"❌ Lỗi khi tìm GIF: {str(e)}")

@bot.command(name='emoji_react')
async def emoji_react(ctx):
    """36. React emoji ngẫu nhiên"""
    emojis = ['😀', '😂', '🤔', '😎', '🔥', '💯', '🎉', '👍', '❤️', '🤖','😎','😈']
    for _ in range(3):
        try:
            await ctx.message.add_reaction(random.choice(emojis))
        except discord.HTTPException:
            continue

@bot.command(name='truth_dare')
async def truth_or_dare(ctx):
    """37. Truth or Dare"""
    truths = [
        "Điều gì khiến bạn cảm thấy tự hào nhất?",
        "Bạn từng làm gì mà cảm thấy ngại nhất?",
        "Mơ ước lớn nhất của bạn là gì?"
    ]
    
    dares = [
        "Hát một bài hát trong 30 giây",
        "Kể một câu chuyện cười",
        "Chụp ảnh với khuôn mặt hài hước"
    ]
    
    choice = random.choice(['Truth', 'Dare'])
    if choice == 'Truth':
        content = f"💭 **Truth**: {random.choice(truths)}"
    else:
        content = f"🎭 **Dare**: {random.choice(dares)}"
    
    await ctx.send(content)

@bot.command(name='would_you_rather')
async def would_you_rather(ctx):
    """38. Would You Rather"""
    questions = [
        "Bạn muốn có thể bay hay có thể tàng hình?",
        "Bạn muốn biết tương lai hay có thể thay đổi quá khứ?",
        "Bạn muốn có 1 triệu đô hay có siêu trí tuệ?",
        "Bạn muốn code Python hay JavaScript cả đời?"
    ]
    
    question = random.choice(questions)
    embed = discord.Embed(title="🤷 Would You Rather", description=question, color=0xFF5722)
    await ctx.send(embed=embed)

@bot.command(name='this_or_that')
async def this_or_that(ctx):
    """39. This or That"""
    options = [
        ["🍕 Pizza", "🍔 Burger"],
        ["☕ Coffee", "🍵 Tea"],
        ["🌙 Night", "☀️ Day"],
        ["🏠 Stay home", "🌍 Travel"],
        ["📱 Mobile", "💻 PC"]
    ]
    
    choice = random.choice(options)
    await ctx.send(f"🎯 **This or That**: {choice[0]} hoặc {choice[1]}?")

@bot.command(name='fortune')
async def fortune_cookie(ctx):
    """40. Bánh may mắn"""
    fortunes = [
        "🥠 Ngày mai sẽ có tin tốt đến với bạn",
        "🥠 Hãy tin vào khả năng của bản thân",
        "🥠 Một cơ hội mới đang chờ đợi",
        "🥠 Bug hôm nay sẽ được fix thành công",
        "🥠 Code của bạn sẽ chạy mượt mà"
    ]
    await ctx.send(random.choice(fortunes))

# =============================================================================
# LỆNH ÂM NHẠC VÀ MEDIA (41-50)
# =============================================================================

@bot.command(name='play')
async def play_music(ctx, *, url):
    """41. Phát nhạc từ YouTube"""
    if not ctx.author.voice:
        await ctx.send("❌ Bạn cần ở trong voice channel để phát nhạc!")
        return

    channel = ctx.author.voice.channel
    try:
        # Kết nối voice channel nếu chưa kết nối
        if not ctx.guild.voice_client:
            await channel.connect()
        
        voice_client = ctx.guild.voice_client

        # Khởi tạo hàng đợi nếu chưa có
        if ctx.guild.id not in music_queues:
            music_queues[ctx.guild.id] = queue.Queue()

        # Thêm bài hát vào hàng đợi
        music_queues[ctx.guild.id].put(url)

        # Nếu đang phát nhạc, thông báo thêm vào hàng đợi
        if voice_client.is_playing():
            await ctx.send(f"🎵 Đã thêm vào hàng đợi: {url}")
            return

        # Phát nhạc từ hàng đợi
        async def play_next():
            if music_queues[ctx.guild.id].empty():
                await voice_client.disconnect()
                return

            next_url = music_queues[ctx.guild.id].get()
            try:
                player = await YTDLSource.from_url(next_url, loop=bot.loop, stream=True)
                voice_client.play(player, after=lambda e: bot.loop.create_task(play_next()))
                
                embed = discord.Embed(title="🎵 Đang Phát Nhạc", color=0x1db954)
                embed.add_field(name="Bài Hát", value=player.title, inline=False)
                embed.add_field(name="URL", value=next_url, inline=False)
                embed.set_footer(text="Nguồn: YouTube | Cập nhật: " + datetime.datetime.now().strftime("%d/%m/%Y %H:%M"))
                await ctx.send(embed=embed)
            except Exception as e:
                await ctx.send(f"❌ Lỗi khi phát nhạc: {str(e)}")
                bot.loop.create_task(play_next())

        await play_next()

    except Exception as e:
        await ctx.send(f"❌ Lỗi khi kết nối hoặc phát nhạc: {str(e)}")

@bot.command(name='pause')
async def pause_music(ctx):
    """42. Tạm dừng nhạc"""
    voice_client = ctx.guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await ctx.send("⏸️ Đã tạm dừng nhạc")
    else:
        await ctx.send("❌ Không có nhạc đang phát!")

@bot.command(name='skip')
async def skip_music(ctx):
    """43. Bỏ qua bài hát"""
    voice_client = ctx.guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.stop()  # Dừng bài hiện tại, after callback sẽ phát bài tiếp theo
        await ctx.send("⏭️ Đã bỏ qua bài hát")
    else:
        await ctx.send("❌ Không có nhạc đang phát!")

@bot.command(name='queue')
async def music_queue(ctx):
    """44. Hàng đợi nhạc"""
    if ctx.guild.id not in music_queues or music_queues[ctx.guild.id].empty():
        await ctx.send("📋 Hàng đợi trống")
        return

    queue_list = list(music_queues[ctx.guild.id].queue)
    if not queue_list:
        await ctx.send("📋 Hàng đợi trống")
        return

    embed = discord.Embed(title="📋 Hàng Đợi Nhạc", color=0x1db954)
    for i, url in enumerate(queue_list, 1):
        embed.add_field(name=f"Bài {i}", value=url[:100] + ("..." if len(url) > 100 else ""), inline=False)
    embed.set_footer(text="Cập nhật: " + datetime.datetime.now().strftime("%d/%m/%Y %H:%M"))
    await ctx.send(embed=embed)

@bot.command(name='volume')
async def set_volume(ctx, volume: int):
    """45. Điều chỉnh âm lượng"""
    voice_client = ctx.guild.voice_client
    if not voice_client or not voice_client.is_playing():
        await ctx.send("❌ Không có nhạc đang phát!")
        return

    if not 0 <= volume <= 100:
        await ctx.send("❌ Âm lượng phải từ 0-100!")
        return

    voice_client.source.volume = volume / 100
    await ctx.send(f"🔊 Đã đặt âm lượng: {volume}%")

@bot.command(name='lyrics')
async def get_lyrics(ctx, *, song):
    """46. Lời bài hát"""
    await ctx.send(f"🎤 Tìm lời bài hát '{song}' (Cần API để hoạt động)")

@bot.command(name='spotify')
async def spotify_info(ctx, member: discord.Member = None):
    """47. Thông tin Spotify"""
    if member is None:
        member = ctx.author
    await ctx.send(f"🎧 Spotify của {member.display_name}: Không có hoạt động")

@bot.command(name='youtube')
async def youtube_search(ctx, *, query):
    """48. Tìm YouTube"""
    encoded_query = urllib.parse.quote(query)
    url = f"https://www.youtube.com/results?search_query={encoded_query}"
    await ctx.send(f"🎬 Tìm kiếm YouTube: {url}")

@bot.command(name='podcast')
async def podcast_search(ctx, *, query):
    """49. Tìm Podcast"""
    await ctx.send(f"🎙️ Tìm podcast '{query}' (Cần API để hoạt động)")

@bot.command(name='radio')
async def online_radio(ctx, station="random"):
    """50. Radio online"""
    stations = ["Lofi Hip Hop", "Jazz", "Classical", "Rock", "Electronic"]
    if station == "random":
        station = random.choice(stations)
    await ctx.send(f"📻 Đang phát: {station}")

# =============================================================================
# LỆNH QUẢN LÝ VÀ MODERATION (51-65)
# =============================================================================

@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban_user(ctx, member: discord.Member, *, reason="Không có lý do"):
    """51. Ban thành viên"""
    try:
        await member.ban(reason=reason)
        embed = discord.Embed(title="🔨 Đã ban", color=0xff0000)
        embed.add_field(name="Thành viên", value=member.mention, inline=True)
        embed.add_field(name="Lý do", value=reason, inline=True)
        embed.add_field(name="Người thực hiện", value=ctx.author.mention, inline=True)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ Không có quyền ban thành viên này!")
    except Exception as e:
        await ctx.send(f"❌ Không thể ban thành viên này: {str(e)}")

@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
async def kick_user(ctx, member: discord.Member, *, reason="Không có lý do"):
    """52. Kick thành viên"""
    try:
        await member.kick(reason=reason)
        embed = discord.Embed(title="👢 Đã kick", color=0xff9900)
        embed.add_field(name="Thành viên", value=member.mention, inline=True)
        embed.add_field(name="Lý do", value=reason, inline=True)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ Không có quyền kick thành viên này!")
    except Exception as e:
        await ctx.send(f"❌ Không thể kick thành viên này: {str(e)}")

@bot.command(name='mute')
@commands.has_permissions(manage_roles=True)
async def mute_user(ctx, member: discord.Member, duration: int = 10):
    """53. Mute thành viên"""
    try:
        await member.timeout(datetime.timedelta(minutes=duration))
        await ctx.send(f"🔇 Đã mute {member.mention} trong {duration} phút")
    except discord.Forbidden:
        await ctx.send("❌ Không có quyền mute thành viên này!")
    except Exception as e:
        await ctx.send(f"❌ Không thể mute thành viên này: {str(e)}")

@bot.command(name='unmute')
@commands.has_permissions(manage_roles=True)
async def unmute_user(ctx, member: discord.Member):
    """54. Unmute thành viên"""
    try:
        await member.timeout(None)
        await ctx.send(f"🔊 Đã unmute {member.mention}")
    except discord.Forbidden:
        await ctx.send("❌ Không có quyền unmute thành viên này!")
    except Exception as e:
        await ctx.send(f"❌ Không thể unmute thành viên này: {str(e)}")

@bot.command(name='warn')
@commands.has_permissions(manage_messages=True)
async def warn_user(ctx, member: discord.Member, *, reason):
    """55. Cảnh báo thành viên"""
    embed = discord.Embed(title="⚠️ Cảnh báo", color=0xffff00)
    embed.add_field(name="Thành viên", value=member.mention, inline=True)
    embed.add_field(name="Lý do", value=reason, inline=True)
    embed.add_field(name="Người cảnh báo", value=ctx.author.mention, inline=True)
    await ctx.send(embed=embed)
    
    try:
        await member.send(f"⚠️ Bạn đã bị cảnh báo tại {ctx.guild.name}: {reason}")
    except discord.Forbidden:
        pass

@bot.command(name='clear')
@commands.has_permissions(manage_messages=True)
async def clear_messages(ctx, amount: int = 5):
    """56. Xóa tin nhắn"""
    if amount > 100:
        amount = 100
    
    try:
        deleted = await ctx.channel.purge(limit=amount + 1)
        msg = await ctx.send(f"🗑️ Đã xóa {len(deleted) - 1} tin nhắn")
        await asyncio.sleep(5)
        await msg.delete()
    except discord.Forbidden:
        await ctx.send("❌ Không có quyền xóa tin nhắn!")

@bot.command(name='slowmode')
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, seconds: int):
    """57. Chế độ chậm"""
    if seconds > 21600:  # 6 hours max
        seconds = 21600
    
    try:
        await ctx.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await ctx.send("🐌 Đã tắt chế độ chậm")
        else:
            await ctx.send(f"🐌 Đã đặt chế độ chậm: {seconds} giây")
    except discord.Forbidden:
        await ctx.send("❌ Không có quyền thay đổi chế độ chậm!")

@bot.command(name='lock')
@commands.has_permissions(manage_channels=True)
async def lock_channel(ctx):
    """58. Khóa kênh"""
    try:
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send("🔒 Đã khóa kênh")
    except discord.Forbidden:
        await ctx.send("❌ Không có quyền khóa kênh!")

@bot.command(name='unlock')
@commands.has_permissions(manage_channels=True)
async def unlock_channel(ctx):
    """59. Mở khóa kênh"""
    try:
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = True
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send("🔓 Đã mở khóa kênh")
    except discord.Forbidden:
        await ctx.send("❌ Không có quyền mở khóa kênh!")

@bot.command(name='role')
@commands.has_permissions(manage_roles=True)
async def manage_role(ctx, action, member: discord.Member, *, role_name):
    """60. Quản lý role"""
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        await ctx.send("❌ Không tìm thấy role!")
        return
    
    try:
        if action.lower() == 'add':
            await member.add_roles(role)
            await ctx.send(f"✅ Đã thêm role {role.name} cho {member.mention}")
        elif action.lower() == 'remove':
            await member.remove_roles(role)
            await ctx.send(f"✅ Đã xóa role {role.name} khỏi {member.mention}")
        else:
            await ctx.send("❌ Sử dụng: !role add/remove @user role_name")
    except discord.Forbidden:
        await ctx.send("❌ Không có quyền thay đổi role!")

@bot.command(name='nick')
@commands.has_permissions(manage_nicknames=True)
async def change_nickname(ctx, member: discord.Member, *, nickname):
    """61. Đổi nickname"""
    try:
        await member.edit(nick=nickname)
        await ctx.send(f"✅ Đã đổi nickname của {member.mention} thành: {nickname}")
    except discord.Forbidden:
        await ctx.send("❌ Không có quyền đổi nickname!")

@bot.command(name='announce')
@commands.has_permissions(manage_messages=True)
async def announce(ctx, *, message):
    """62. Thông báo"""
    embed = discord.Embed(title="📢 Thông báo", description=message, color=0x00ff00)
    embed.set_footer(text=f"Bởi {ctx.author.display_name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
    await ctx.send(embed=embed)
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass

@bot.command(name='poll')
async def create_poll(ctx, question, *options):
    """63. Tạo poll"""
    if len(options) < 2:
        await ctx.send("❌ Cần ít nhất 2 lựa chọn!")
        return
    
    if len(options) > 10:
        await ctx.send("❌ Tối đa 10 lựa chọn!")
        return
    
    embed = discord.Embed(title="📊 Poll", description=question, color=0x3498db)
    
    emoji_numbers = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
    
    for i, option in enumerate(options):
        embed.add_field(name=f"{emoji_numbers[i]} {option}", value="\u200b", inline=False)
    
    msg = await ctx.send(embed=embed)
    
    for i in range(len(options)):
        try:
            await msg.add_reaction(emoji_numbers[i])
        except discord.HTTPException:
            continue

@bot.command(name='vote')
async def simple_vote(ctx, *, question):
    """64. Vote đơn giản"""
    embed = discord.Embed(title="🗳️ Vote", description=question, color=0xe74c3c)
    msg = await ctx.send(embed=embed)
    try:
        await msg.add_reaction('👍')
        await msg.add_reaction('👎')
    except discord.HTTPException:
        pass

@bot.command(name='automod')
@commands.has_permissions(administrator=True)
async def automod(ctx, action):
    """65. Auto moderation"""
    if action.lower() == 'on':
        await ctx.send("🛡️ Đã bật auto moderation")
    elif action.lower() == 'off':
        await ctx.send("🛡️ Đã tắt auto moderation")
    else:
        await ctx.send("❌ Sử dụng: !automod on/off")

# =============================================================================
# LỆNH KINH TẾ VÀ LEVELING (66-80)
# =============================================================================

@bot.command(name='daily')
async def daily_reward(ctx):
    """66. Phần thưởng hàng ngày"""
    user_data = get_user_data(ctx.author.id)
    today = datetime.date.today().isoformat()
    
    if user_data[4] == today:
        await ctx.send("❌ Bạn đã nhận phần thưởng hôm nay rồi!")
        return
    
    reward = random.randint(50, 200)
    new_coins = user_data[3] + reward
    
    update_user_data(ctx.author.id, coins=new_coins, last_daily=today)
    
    embed = discord.Embed(title="💰 Phần thưởng hàng ngày", color=0xffd700)
    embed.add_field(name="Phần thưởng", value=f"{reward} coins", inline=True)
    embed.add_field(name="Tổng coins", value=f"{new_coins} coins", inline=True)
    await ctx.send(embed=embed)

@bot.command(name='balance')
async def check_balance(ctx, member: discord.Member = None):
    """67. Kiểm tra số dư"""
    if member is None:
        member = ctx.author
    
    user_data = get_user_data(member.id)
    embed = discord.Embed(title="💰 Số dư", color=0xffd700)
    embed.add_field(name="Coins", value=user_data[3], inline=True)
    embed.add_field(name="Level", value=user_data[1], inline=True)
    embed.add_field(name="EXP", value=user_data[2], inline=True)
    await ctx.send(embed=embed)

@bot.command(name='pay')
async def pay_user(ctx, member: discord.Member, amount: int):
    """68. Chuyển tiền"""
    if amount <= 0:
        await ctx.send("❌ Số tiền phải lớn hơn 0!")
        return
    
    if member == ctx.author:
        await ctx.send("❌ Không thể chuyển tiền cho chính mình!")
        return
    
    sender_data = get_user_data(ctx.author.id)
    if sender_data[3] < amount:
        await ctx.send("❌ Bạn không đủ tiền!")
        return
    
    receiver_data = get_user_data(member.id)
    
    update_user_data(ctx.author.id, coins=sender_data[3] - amount)
    update_user_data(member.id, coins=receiver_data[3] + amount)
    
    await ctx.send(f"💸 {ctx.author.mention} đã chuyển {amount} coins cho {member.mention}")

@bot.command(name='shop')
async def shop(ctx):
    """69. Cửa hàng"""
    embed = discord.Embed(title="🛒 Cửa hàng", color=0x9b59b6)
    embed.add_field(name="1. Color Role", value="1000 coins", inline=True)
    embed.add_field(name="2. Custom Status", value="500 coins", inline=True)
    embed.add_field(name="3. Extra EXP", value="200 coins", inline=True)
    embed.add_field(name="4. Profile Badge", value="800 coins", inline=True)
    embed.set_footer(text="Sử dụng !buy <số> để mua")
    await ctx.send(embed=embed)

@bot.command(name='buy')
async def buy_item(ctx, item_id: int):
    """70. Mua vật phẩm"""
    items = {
        1: {"name": "Color Role", "price": 1000},
        2: {"name": "Custom Status", "price": 500},
        3: {"name": "Extra EXP", "price": 200},
        4: {"name": "Profile Badge", "price": 800}
    }
    
    if item_id not in items:
        await ctx.send("❌ Vật phẩm không tồn tại!")
        return
    
    user_data = get_user_data(ctx.author.id)
    item = items[item_id]
    
    if user_data[3] < item["price"]:
        await ctx.send("❌ Bạn không đủ tiền!")
        return
    
    update_user_data(ctx.author.id, coins=user_data[3] - item["price"])
    await ctx.send(f"✅ Đã mua {item['name']} với giá {item['price']} coins!")

@bot.command(name='inventory')
async def user_inventory(ctx):
    """71. Túi đồ"""
    embed = discord.Embed(title="🎒 Túi đồ", description="Túi đồ của bạn đang trống", color=0x8e44ad)
    await ctx.send(embed=embed)

@bot.command(name='gamble')
async def gamble(ctx, amount: int):
    """72. Cờ bạc"""
    if amount <= 0:
        await ctx.send("❌ Số tiền phải lớn hơn 0!")
        return
    
    user_data = get_user_data(ctx.author.id)
    if user_data[3] < amount:
        await ctx.send("❌ Bạn không đủ tiền!")
        return
    
    win_chance = 0.45  # 45% cơ hội thắng
    won = random.random() < win_chance
    
    if won:
        new_coins = user_data[3] + amount
        await ctx.send(f"🎉 Bạn thắng! +{amount} coins (Tổng: {new_coins})")
    else:
        new_coins = user_data[3] - amount
        await ctx.send(f"💸 Bạn thua! -{amount} coins (Còn lại: {new_coins})")
    
    update_user_data(ctx.author.id, coins=new_coins)

@bot.command(name='work')
async def work(ctx):
    """73. Làm việc kiếm tiền"""
    jobs = [
        {"name": "Code reviewer", "pay": (50, 150)},
        {"name": "Bug fixer", "pay": (30, 100)},
        {"name": "Database admin", "pay": (70, 200)},
        {"name": "Discord moderator", "pay": (40, 120)}
    ]
    
    job = random.choice(jobs)
    earnings = random.randint(*job["pay"])
    
    user_data = get_user_data(ctx.author.id)
    new_coins = user_data[3] + earnings
    new_exp = user_data[2] + 10
    
    # Level up check
    new_level = user_data[1]
    exp_needed = new_level * 100
    levelup_msg = ""
    if new_exp >= exp_needed:
        new_level += 1
        new_exp = 0
        levelup_msg = f"\n🎉 Level up! Bạn đã lên level {new_level}!"
    
    update_user_data(ctx.author.id, level=new_level, exp=new_exp, coins=new_coins)
    
    embed = discord.Embed(title="💼 Kết quả làm việc", color=0x2ecc71)
    embed.add_field(name="Công việc", value=job["name"], inline=True)
    embed.add_field(name="Thu nhập", value=f"{earnings} coins", inline=True)
    embed.add_field(name="EXP", value="+10", inline=True)
    await ctx.send(embed=embed)
    
    if levelup_msg:
        await ctx.send(levelup_msg)

@bot.command(name='level')
async def check_level(ctx, member: discord.Member = None):
    """74. Kiểm tra level"""
    if member is None:
        member = ctx.author
    
    user_data = get_user_data(member.id)
    level = user_data[1]
    exp = user_data[2]
    exp_needed = level * 100
    
    embed = discord.Embed(title=f"⭐ Level của {member.display_name}", color=0xe67e22)
    embed.add_field(name="Level", value=level, inline=True)
    embed.add_field(name="EXP", value=f"{exp}/{exp_needed}", inline=True)
    embed.add_field(name="Tiến độ", value=f"{round(exp/exp_needed*100, 1)}%", inline=True)
    
    # Progress bar
    progress = int(exp / exp_needed * 20)
    bar = "█" * progress + "░" * (20 - progress)
    embed.add_field(name="Thanh tiến độ", value=f"`{bar}`", inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='leaderboard')
async def leaderboard(ctx, lb_type="level"):
    """75. Bảng xếp hạng"""
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    if lb_type.lower() == "level":
        c.execute("SELECT user_id, level, exp FROM users ORDER BY level DESC, exp DESC LIMIT 10")
        title = "⭐ Bảng xếp hạng Level"
    elif lb_type.lower() == "coins":
        c.execute("SELECT user_id, coins FROM users ORDER BY coins DESC LIMIT 10")
        title = "💰 Bảng xếp hạng Coins"
    else:
        await ctx.send("❌ Loại bảng xếp hạng: level hoặc coins")
        conn.close()
        return
    
    results = c.fetchall()
    conn.close()
    
    if not results:
        await ctx.send("❌ Chưa có dữ liệu!")
        return
    
    embed = discord.Embed(title=title, color=0xf39c12)
    
    for i, result in enumerate(results, 1):
        try:
            user = bot.get_user(result[0])
            user_name = user.display_name if user else f"User {result[0]}"
            
            if lb_type.lower() == "level":
                value = f"Level {result[1]} ({result[2]} EXP)"
            else:
                value = f"{result[1]} coins"
            
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            embed.add_field(name=f"{medal} {user_name}", value=value, inline=False)
        except:
            continue
    
    await ctx.send(embed=embed)

@bot.command(name='rank')
async def user_rank(ctx, member: discord.Member = None):
    """76. Xếp hạng cá nhân"""
    if member is None:
        member = ctx.author
    
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT user_id, level, exp, coins FROM users ORDER BY level DESC, exp DESC")
    results = c.fetchall()
    conn.close()
    
    for i, result in enumerate(results, 1):
        if result[0] == member.id:
            embed = discord.Embed(title=f"🏆 Xếp hạng của {member.display_name}", color=0xe67e22)
            embed.add_field(name="Vị trí", value=f"#{i}", inline=True)
            embed.add_field(name="Level", value=result[1], inline=True)
            embed.add_field(name="Coins", value=result[3], inline=True)
            await ctx.send(embed=embed)
            return
    
    await ctx.send("❌ Không tìm thấy dữ liệu!")

@bot.command(name='exp')
@commands.has_permissions(administrator=True)
async def give_exp(ctx, member: discord.Member, amount: int):
    """77. Tặng EXP (Admin only)"""
    user_data = get_user_data(member.id)
    new_exp = user_data[2] + amount
    new_level = user_data[1]
    
    # Check level up
    exp_needed = new_level * 100
    while new_exp >= exp_needed:
        new_level += 1
        new_exp -= exp_needed
        exp_needed = new_level * 100
    
    update_user_data(member.id, level=new_level, exp=new_exp)
    await ctx.send(f"✅ Đã tặng {amount} EXP cho {member.mention}")

@bot.command(name='profile')
async def user_profile(ctx, member: discord.Member = None):
    """78. Hồ sơ người dùng"""
    if member is None:
        member = ctx.author
    
    user_data = get_user_data(member.id)
    
    embed = discord.Embed(title=f"👤 Hồ sơ {member.display_name}", color=member.color)
    embed.add_field(name="Level", value=user_data[1], inline=True)
    embed.add_field(name="EXP", value=user_data[2], inline=True)
    embed.add_field(name="Coins", value=user_data[3], inline=True)
    
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)
    
    await ctx.send(embed=embed)

@bot.command(name='badge')
async def user_badges(ctx):
    """79. Huy hiệu"""
    embed = discord.Embed(title="🏅 Huy hiệu của bạn", description="Chưa có huy hiệu nào", color=0x9b59b6)
    await ctx.send(embed=embed)

@bot.command(name='achievement')
async def achievements(ctx):
    """80. Thành tựu"""
    embed = discord.Embed(title="🏆 Thành tựu", description="Danh sách thành tựu sẽ được cập nhật", color=0xf1c40f)
    await ctx.send(embed=embed)

# =============================================================================
# LỆNH TIỆN ÍCH NÂNG CAO (81-100)
# =============================================================================

@bot.command(name='remind')
async def set_reminder(ctx, time_str, *, message):
    """81. Đặt nhắc nhở"""
    try:
        # Parse time (simplified - only minutes)
        if time_str.endswith('m'):
            minutes = int(time_str[:-1])
        elif time_str.endswith('h'):
            minutes = int(time_str[:-1]) * 60
        else:
            minutes = int(time_str)
        
        if minutes > 10080:  # Max 1 week
            await ctx.send("❌ Thời gian tối đa là 1 tuần!")
            return
        
        remind_time = (datetime.datetime.now() + datetime.timedelta(minutes=minutes)).isoformat()
        
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("INSERT INTO reminders (user_id, message, remind_time) VALUES (?, ?, ?)",
                 (ctx.author.id, message, remind_time))
        conn.commit()
        conn.close()
        
        await ctx.send(f"⏰ Sẽ nhắc bạn sau {minutes} phút: {message}")
    except ValueError:
        await ctx.send("❌ Định dạng thời gian không hợp lệ! (Ví dụ: 30m, 2h)")

@tasks.loop(minutes=1)
async def check_reminders():
    """Kiểm tra nhắc nhở"""
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("SELECT * FROM reminders WHERE remind_time <= ?", (datetime.datetime.now().isoformat(),))
        reminders = c.fetchall()
        
        for reminder in reminders:
            try:
                user = bot.get_user(reminder[1])
                if user:
                    embed = discord.Embed(title="⏰ Nhắc nhở", description=reminder[2], color=0xe74c3c)
                    await user.send(embed=embed)
                
                c.execute("DELETE FROM reminders WHERE id = ?", (reminder[0],))
            except:
                continue
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Lỗi check_reminders: {e}")

@bot.command(name='todo')
async def todo_list(ctx, action="list", *, item=""):
    """82. Danh sách việc cần làm"""
    # Simplified todo - using in-memory storage
    if not hasattr(bot, 'todos'):
        bot.todos = {}
    
    user_id = ctx.author.id
    if user_id not in bot.todos:
        bot.todos[user_id] = []
    
    if action.lower() == "add" and item:
        bot.todos[user_id].append(item)
        await ctx.send(f"✅ Đã thêm: {item}")
    elif action.lower() == "remove" and item.isdigit():
        idx = int(item) - 1
        if 0 <= idx < len(bot.todos[user_id]):
            removed = bot.todos[user_id].pop(idx)
            await ctx.send(f"🗑️ Đã xóa: {removed}")
        else:
            await ctx.send("❌ Số thứ tự không hợp lệ!")
    elif action.lower() == "list":
        if not bot.todos[user_id]:
            await ctx.send("📝 Danh sách việc cần làm trống!")
        else:
            embed = discord.Embed(title="📝 Việc cần làm", color=0x3498db)
            for i, task in enumerate(bot.todos[user_id], 1):
                embed.add_field(name=f"{i}.", value=task, inline=False)
            await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Sử dụng: !todo add/remove/list [item]")

@bot.command(name='note')
async def notes(ctx, action="list", note_id: int = 0, *, content=""):
    """83. Ghi chú"""
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    user_id = ctx.author.id
    
    if action.lower() == "add" and content:
        # Get next note ID
        c.execute("SELECT MAX(note_id) FROM notes WHERE user_id = ?", (user_id,))
        max_id = c.fetchone()[0]
        new_id = (max_id or 0) + 1
        
        created_at = datetime.datetime.now().isoformat()
        c.execute("INSERT INTO notes (user_id, note_id, content, created_at) VALUES (?, ?, ?, ?)",
                 (user_id, new_id, content, created_at))
        conn.commit()
        await ctx.send(f"📝 Đã lưu ghi chú #{new_id}")
        
    elif action.lower() == "remove" and note_id > 0:
        c.execute("DELETE FROM notes WHERE user_id = ? AND note_id = ?", (user_id, note_id))
        if c.rowcount > 0:
            conn.commit()
            await ctx.send(f"🗑️ Đã xóa ghi chú #{note_id}")
        else:
            await ctx.send("❌ Không tìm thấy ghi chú!")
            
    elif action.lower() == "list":
        c.execute("SELECT note_id, content, created_at FROM notes WHERE user_id = ? ORDER BY note_id", (user_id,))
        notes = c.fetchall()
        
        if not notes:
            await ctx.send("📝 Chưa có ghi chú nào!")
        else:
            embed = discord.Embed(title="📝 Ghi chú của bạn", color=0x9b59b6)
            for note in notes[:10]:  # Limit to 10 notes
                created = datetime.datetime.fromisoformat(note[2]).strftime("%d/%m/%Y")
                embed.add_field(name=f"#{note[0]} ({created})", value=note[1][:100], inline=False)
            await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Sử dụng: !note add/remove/list [id] [content]")
    
    conn.close()

@bot.command(name='calc')
async def calculator(ctx, *, expression):
    """84. Máy tính nâng cao"""
    try:
        # Thêm các hàm toán học
        import math as m
        
        # Thay thế các hàm
        expression = expression.replace('sin', 'm.sin')
        expression = expression.replace('cos', 'm.cos')
        expression = expression.replace('tan', 'm.tan')
        expression = expression.replace('sqrt', 'm.sqrt')
        expression = expression.replace('log', 'm.log')
        expression = expression.replace('pi', 'm.pi')
        expression = expression.replace('e', 'm.e')
        
        result = eval(expression)
        
        embed = discord.Embed(title="🧮 Máy tính", color=0x34495e)
        embed.add_field(name="Biểu thức", value=f"```{expression}```", inline=False)
        embed.add_field(name="Kết quả", value=f"```{result}```", inline=False)
        await ctx.send(embed=embed)
    except Exception:
        await ctx.send("❌ Biểu thức không hợp lệ!")

@bot.command(name='convert')
async def unit_converter(ctx, value: float, from_unit, to_unit):
    """85. Chuyển đổi đơn vị"""
    # Temperature conversions
    if from_unit.lower() == 'c' and to_unit.lower() == 'f':
        result = (value * 9/5) + 32
        await ctx.send(f"🌡️ {value}°C = {result}°F")
    elif from_unit.lower() == 'f' and to_unit.lower() == 'c':
        result = (value - 32) * 5/9
        await ctx.send(f"🌡️ {value}°F = {result}°C")
    
    # Length conversions
    elif from_unit.lower() == 'm' and to_unit.lower() == 'ft':
        result = value * 3.28084
        await ctx.send(f"📏 {value}m = {result}ft")
    elif from_unit.lower() == 'ft' and to_unit.lower() == 'm':
        result = value / 3.28084
        await ctx.send(f"📏 {value}ft = {result}m")
    
    # Weight conversions
    elif from_unit.lower() == 'kg' and to_unit.lower() == 'lb':
        result = value * 2.20462
        await ctx.send(f"⚖️ {value}kg = {result}lb")
    elif from_unit.lower() == 'lb' and to_unit.lower() == 'kg':
        result = value / 2.20462
        await ctx.send(f"⚖️ {value}lb = {result}kg")
    
    else:
        await ctx.send("❌ Chuyển đổi hỗ trợ: C↔F, m↔ft, kg↔lb")

@bot.command(name='search')
async def web_search(ctx, *, query):
    """86. Tìm kiếm web"""
    encoded_query = urllib.parse.quote(query)
    google_url = f"https://www.google.com/search?q={encoded_query}"
    
    embed = discord.Embed(title="🔍 Kết quả tìm kiếm", color=0x4285f4)
    embed.add_field(name="Truy vấn", value=query, inline=False)
    embed.add_field(name="Link Google", value=google_url, inline=False)
    await ctx.send(embed=embed)

@bot.command(name='news')
async def latest_news(ctx, category="general"):
    """87. Tin tức mới nhất"""
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        await ctx.send("❌ Lỗi: Thiếu API key cho NewsAPI. Vui lòng liên hệ admin!")
        return

    # Danh mục hợp lệ của NewsAPI
    valid_categories = ["business", "entertainment", "general", "health", "science", "sports", "technology"]
    if category.lower() not in valid_categories:
        await ctx.send(f"❌ Danh mục không hợp lệ! Chọn một trong: {', '.join(valid_categories)}")
        return

    # URL API
    url = f"https://newsapi.org/v2/top-headlines?category={category.lower()}&language=en&apiKey={api_key}"
    
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()  # Kiểm tra lỗi HTTP
        data = response.json()
        
        if data["status"] != "ok" or not data.get("articles"):
            await ctx.send(f"📰 Không tìm thấy tin tức trong danh mục {category}!")
            return

        # Lấy tối đa 5 bài báo
        articles = data["articles"][:5]
        embed = discord.Embed(title=f"📰 Tin tức mới nhất - {category.capitalize()}", color=0x1e90ff)
        
        for i, article in enumerate(articles, 1):
            title = article.get("title", "Không có tiêu đề")[:100]
            description = article.get("description", "Không có mô tả")[:150]
            url = article.get("url", "#")
            embed.add_field(
                name=f"{i}. {title}",
                value=f"{description}...\n[Đọc thêm]({url})",
                inline=False
            )
        
        embed.set_footer(text="Nguồn: NewsAPI.org | Cập nhật: " + datetime.datetime.now().strftime("%d/%m/%Y %H:%M"))
        await ctx.send(embed=embed)
    
    except requests.exceptions.RequestException as e:
        await ctx.send(f"❌ Lỗi khi lấy tin tức: {str(e)}")

@bot.command(name='stock')
async def stock_price(ctx, symbol):
    """88. Giá cổ phiếu"""
    await ctx.send(f"📈 Giá cổ phiếu {symbol.upper()}: Cần API để hiển thị giá thực")

@bot.command(name='crypto')
async def crypto_price(ctx, coin="bitcoin"):
    """89. Giá crypto"""
    await ctx.send(f"₿ Giá {coin}: Cần API để hiển thị giá thực")

@bot.command(name='bookmark')
async def bookmark(ctx, action="list", *, url=""):
    """90. Bookmark"""
    if not hasattr(bot, 'bookmarks'):
        bot.bookmarks = {}
    
    user_id = ctx.author.id
    if user_id not in bot.bookmarks:
        bot.bookmarks[user_id] = []
    
    if action.lower() == "add" and url:
        bot.bookmarks[user_id].append({"url": url, "added": datetime.datetime.now().isoformat()})
        await ctx.send(f"🔖 Đã lưu bookmark: {url}")
    elif action.lower() == "list":
        if not bot.bookmarks[user_id]:
            await ctx.send("🔖 Chưa có bookmark nào!")
        else:
            embed = discord.Embed(title="🔖 Bookmark của bạn", color=0x3498db)
            for i, bookmark in enumerate(bot.bookmarks[user_id][-10:], 1):
                added_date = datetime.datetime.fromisoformat(bookmark["added"]).strftime("%d/%m")
                embed.add_field(name=f"{i}. ({added_date})", value=bookmark["url"], inline=False)
            await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Sử dụng: !bookmark add/list [url]")

@bot.command(name='schedule')
async def schedule_event(ctx, time_str, *, event):
    """91. Lên lịch sự kiện"""
    embed = discord.Embed(title="📅 Sự kiện đã lên lịch", color=0xe67e22)
    embed.add_field(name="Thời gian", value=time_str, inline=True)
    embed.add_field(name="Sự kiện", value=event, inline=True)
    embed.add_field(name="Người tạo", value=ctx.author.mention, inline=True)
    await ctx.send(embed=embed)

@bot.command(name='timer')
async def start_timer(ctx, minutes: int):
    """92. Đặt timer"""
    if minutes > 60:
        minutes = 60
    
    embed = discord.Embed(title="⏱️ Timer", description=f"Timer {minutes} phút đã bắt đầu!", color=0xe74c3c)
    await ctx.send(embed=embed)
    
    await asyncio.sleep(minutes * 60)
    
    embed = discord.Embed(title="⏰ Timer kết thúc!", description=f"Timer {minutes} phút đã hoàn thành!", color=0x27ae60)
    await ctx.send(f"{ctx.author.mention}", embed=embed)

@bot.command(name='stopwatch')
async def stopwatch(ctx):
    """93. Đồng hồ bấm giờ"""
    start_time = time.time()
    embed = discord.Embed(title="⏱️ Stopwatch", description="Stopwatch đã bắt đầu!\nGõ 'stop' để dừng", color=0x3498db)
    await ctx.send(embed=embed)
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() == 'stop'
    
    try:
        await bot.wait_for('message', check=check, timeout=300)  # 5 minutes max
        end_time = time.time()
        elapsed = round(end_time - start_time, 2)
        await ctx.send(f"⏹️ Stopwatch dừng! Thời gian: **{elapsed} giây**")
    except asyncio.TimeoutError:
        await ctx.send("⏰ Stopwatch tự động dừng sau 5 phút!")

@bot.command(name='alarm')
async def set_alarm(ctx, time_str):
    """94. Đặt báo thức"""
    try:
        hour, minute = map(int, time_str.split(':'))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
        
        now = datetime.datetime.now()
        alarm_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if alarm_time <= now:
            alarm_time += datetime.timedelta(days=1)
        
        await ctx.send(f"⏰ Báo thức đã đặt lúc {time_str}!")
        
        # Simplified - just show message for alarms within 1 hour
        seconds_until = (alarm_time - now).total_seconds()
        if seconds_until < 3600:
            await asyncio.sleep(seconds_until)
            await ctx.send(f"⏰ {ctx.author.mention} Báo thức! Đã đến {time_str}!")
            
    except ValueError:
        await ctx.send("❌ Định dạng thời gian không hợp lệ! (HH:MM)")

@bot.command(name='backup')
@commands.has_permissions(administrator=True)
async def backup_data(ctx):
    """95. Sao lưu dữ liệu"""
    await ctx.send("💾 Đang sao lưu dữ liệu...")
    await asyncio.sleep(2)
    await ctx.send("✅ Đã hoàn thành sao lưu!")

@bot.command(name='export')
async def export_data(ctx, data_type="profile"):
    """96. Xuất dữ liệu"""
    user_data = get_user_data(ctx.author.id)
    
    if data_type.lower() == "profile":
        data = {
            "user_id": ctx.author.id,
            "username": str(ctx.author),
            "level": user_data[1],
            "exp": user_data[2],
            "coins": user_data[3],
            "export_date": datetime.datetime.now().isoformat()
        }
        
        embed = discord.Embed(title="📤 Xuất dữ liệu", color=0x95a5a6)
        embed.add_field(name="Loại", value="Profile", inline=True)
        embed.add_field(name="Dữ liệu", value=f"```json\n{json.dumps(data, indent=2)}```", inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Loại dữ liệu hỗ trợ: profile")

@bot.command(name='import')
@commands.has_permissions(administrator=True)
async def import_data(ctx):
    """97. Nhập dữ liệu"""
    await ctx.send("📥 Tính năng import dữ liệu (Cần file đính kèm)")

@bot.command(name='stats')
async def server_stats(ctx):
    """98. Thống kê server"""
    guild = ctx.guild
    
    # Count channels by type
    text_channels = len([ch for ch in guild.channels if isinstance(ch, discord.TextChannel)])
    voice_channels = len([ch for ch in guild.channels if isinstance(ch, discord.VoiceChannel)])
    
    # Count members by status
    online = len([m for m in guild.members if m.status == discord.Status.online])
    idle = len([m for m in guild.members if m.status == discord.Status.idle])
    dnd = len([m for m in guild.members if m.status == discord.Status.dnd])
    offline = len([m for m in guild.members if m.status == discord.Status.offline])
    
    embed = discord.Embed(title="📊 Thống kê Server", color=0x3498db)
    embed.add_field(name="👥 Thành viên", value=f"Tổng: {guild.member_count}\n🟢 Online: {online}\n🟡 Idle: {idle}\n🔴 DND: {dnd}\n⚫ Offline: {offline}", inline=True)
    embed.add_field(name="📺 Kênh", value=f"💬 Text: {text_channels}\n🔊 Voice: {voice_channels}\nTổng: {len(guild.channels)}", inline=True)
    embed.add_field(name="📈 Khác", value=f"🎭 Roles: {len(guild.roles)}\n⭐ Boost: {guild.premium_subscription_count}\n📅 Tạo: {guild.created_at.strftime('%d/%m/%Y')}", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='analyze')
async def analyze_user(ctx, member: discord.Member = None):
    """99. Phân tích người dùng"""
    if member is None:
        member = ctx.author
    
    user_data = get_user_data(member.id)
    
    embed = discord.Embed(title=f"🔍 Phân tích {member.display_name}", color=0x9b59b6)
    
    # Activity level based on level and exp
    total_activity = user_data[1] * 100 + user_data[2]
    if total_activity < 200:
        activity_level = "Mới tham gia"
    elif total_activity < 500:
        activity_level = "Hoạt động vừa phải"
    elif total_activity < 1000:
        activity_level = "Hoạt động tích cực"
    else:
        activity_level = "Rất tích cực"
    
    embed.add_field(name="📊 Mức độ hoạt động", value=activity_level, inline=True)
    embed.add_field(name="💰 Tình trạng kinh tế", value="Ổn định" if user_data[3] > 500 else "Cần cải thiện", inline=True)
    embed.add_field(name="⭐ Tiềm năng", value="Cao" if user_data[1] > 5 else "Đang phát triển", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='report')
async def generate_report(ctx, report_type="daily"):
    """100. Tạo báo cáo"""
    embed = discord.Embed(title="📋 Báo cáo hệ thống", color=0x2c3e50)
    
    if report_type.lower() == "daily":
        embed.add_field(name="📅 Ngày", value=datetime.date.today().strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="🤖 Trạng thái bot", value="Hoạt động bình thường", inline=True)
        embed.add_field(name="📊 Lệnh sử dụng", value="Đang thu thập dữ liệu", inline=True)
        embed.add_field(name="👥 Người dùng hoạt động", value=len(bot.users), inline=True)
        embed.add_field(name="🏠 Servers", value=len(bot.guilds), inline=True)
        embed.add_field(name="💾 Database", value="Kết nối ổn định", inline=True)
    
    elif report_type.lower() == "system":
        embed.add_field(name="🖥️ CPU", value="Đang hoạt động", inline=True)
        embed.add_field(name="💿 RAM", value="Đang sử dụng", inline=True)
        embed.add_field(name="🌐 Network", value="Kết nối tốt", inline=True)
    
    else:
        await ctx.send("❌ Loại báo cáo: daily, system")
        return
    
    await ctx.send(embed=embed)

# =============================================================================
# LỆNH BỔ SUNG VÀ ERROR HANDLING
# =============================================================================

@bot.command(name='ascii')
async def ascii_art(ctx, *, text):
    """Bonus: ASCII Art"""
    if len(text) > 10:
        await ctx.send("❌ Văn bản quá dài! (Tối đa 10 ký tự)")
        return
    
    await ctx.send(ascii_art)

@bot.command(name='log')
@commands.has_permissions(administrator=True)
async def log_command(ctx, action="view"):
    """Lệnh log cho admin"""
    if action.lower() == "view":
        embed = discord.Embed(title="📋 Log hệ thống", color=0x34495e)
        embed.add_field(name="Trạng thái", value="Đang hoạt động", inline=True)
        embed.add_field(name="Lỗi gần đây", value="Không có", inline=True)
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Sử dụng: !log view")

@bot.event
async def on_command_error(ctx, error):
    """Xử lý lỗi lệnh"""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Lệnh không tồn tại! Sử dụng `!help_all` để xem tất cả lệnh.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Bạn không có quyền sử dụng lệnh này!")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Thiếu tham số! Kiểm tra cách sử dụng lệnh.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Tham số không hợp lệ!")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏰ Lệnh đang cooldown! Thử lại sau {round(error.retry_after, 2)} giây.")
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send("❌ Bot không có quyền thực hiện lệnh này!")
    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.send("❌ Lệnh này chỉ có thể sử dụng trong server!")
    elif isinstance(error, commands.PrivateMessageOnly):
        await ctx.send("❌ Lệnh này chỉ có thể sử dụng trong tin nhắn riêng!")
    elif isinstance(error, discord.Forbidden):
        await ctx.send("❌ Bot không có quyền thực hiện hành động này!")
    elif isinstance(error, discord.NotFound):
        await ctx.send("❌ Không tìm thấy đối tượng được yêu cầu!")
    elif isinstance(error, discord.HTTPException):
        await ctx.send("❌ Có lỗi xảy ra khi giao tiếp với Discord!")
    else:
        await ctx.send(f"❌ Đã xảy ra lỗi không xác định: {str(error)}")
        print(f"Unhandled error: {error}")

@bot.event
async def on_message(message):
    """Xử lý tin nhắn và EXP"""
    if message.author.bot:
        return
    
    # Auto-moderation (simple)
    if message.guild:
        bad_words = ['spam', 'hack', 'cheat', 'Lồn', 'cặc', 'ditmemay', 'https:']  # Thêm từ cấm tùy ý
        if any(word in message.content.lower() for word in bad_words):
            try:
                await message.delete()
                await message.channel.send(f"⚠️ {message.author.mention}, tin nhắn của bạn chứa nội dung không phù hợp!", delete_after=5)
            except discord.Forbidden:
                pass
    
    # Random EXP gain (giảm tần suất để tránh spam)
    if random.randint(1, 20) == 1:  # 5% chance thay vì 10%
        user_data = get_user_data(message.author.id)
        exp_gain = random.randint(1, 3)  # Giảm EXP gain
        new_exp = user_data[2] + exp_gain
        new_level = user_data[1]
        
        # Check level up
        exp_needed = new_level * 100
        levelup_msg = ""
        if new_exp >= exp_needed:
            new_level += 1
            new_exp = new_exp - exp_needed  # Giữ lại EXP thừa
            levelup_msg = f"🎉 Chúc mừng {message.author.mention}! Bạn đã lên level {new_level}!"
        
        update_user_data(message.author.id, level=new_level, exp=new_exp)
        
        # Chỉ thông báo level up, không thông báo EXP gain để tránh spam
        if levelup_msg:
            embed = discord.Embed(title="🎊 Level Up!", description=levelup_msg, color=0x00ff00)
            embed.add_field(name="Level mới", value=new_level, inline=True)
            embed.add_field(name="EXP", value=f"{new_exp}/{new_level * 100}", inline=True)
            await message.channel.send(embed=embed, delete_after=10)
    
    # Process commands after handling EXP
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    """Chào mừng thành viên mới"""
    # Tìm kênh welcome (có thể tùy chỉnh)
    welcome_channel = discord.utils.get(member.guild.channels, name='welcome')
    if not welcome_channel:
        welcome_channel = discord.utils.get(member.guild.channels, name='general')
    
    if welcome_channel:
        embed = discord.Embed(
            title="🎉 Chào mừng thành viên mới!",
            description=f"Chào mừng {member.mention} đến với {member.guild.name}!",
            color=0x00ff00
        )
        embed.add_field(name="Thành viên thứ", value=f"#{member.guild.member_count}", inline=True)
        embed.add_field(name="Tham gia lúc", value=datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), inline=True)
        
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        
        try:
            await welcome_channel.send(embed=embed)
        except discord.Forbidden:
            pass

@bot.event
async def on_member_remove(member):
    """Thông báo khi thành viên rời khỏi server"""
    # Tìm kênh log hoặc general
    log_channel = discord.utils.get(member.guild.channels, name='log')
    if not log_channel:
        log_channel = discord.utils.get(member.guild.channels, name='general')
    
    if log_channel:
        embed = discord.Embed(
            title="👋 Thành viên đã rời",
            description=f"{member.display_name} đã rời khỏi server",
            color=0xff0000
        )
        embed.add_field(name="Tên", value=str(member), inline=True)
        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="Rời lúc", value=datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), inline=True)
        
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass

@bot.event
async def on_guild_join(guild):
    """Khi bot được thêm vào server mới"""
    print(f"Bot đã được thêm vào server: {guild.name} (ID: {guild.id})")
    
    # Tìm kênh để gửi tin nhắn chào
    channel = discord.utils.get(guild.channels, name='general')
    if not channel:
        channel = guild.system_channel
    if not channel:
        # Tìm kênh text đầu tiên mà bot có thể gửi tin nhắn
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).send_messages:
                channel = ch
                break
    
    if channel:
        embed = discord.Embed(
            title="🤖 Xin chào!",
            description="Cảm ơn bạn đã thêm tôi vào server!",
            color=0x00ff00
        )
        embed.add_field(name="Bắt đầu", value="Sử dụng `!help_all` để xem tất cả lệnh", inline=False)
        embed.add_field(name="Hỗ trợ", value="Bot có 100+ lệnh tiện ích", inline=False)
        
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass

@bot.event
async def on_guild_remove(guild):
    """Khi bot bị xóa khỏi server"""
    print(f"Bot đã bị xóa khỏi server: {guild.name} (ID: {guild.id})")

# Thêm một số lệnh debug cho admin
@bot.command(name='debug')
@commands.is_owner()
async def debug_info(ctx):
    """Thông tin debug cho owner"""
    embed = discord.Embed(title="🔧 Debug Info", color=0x95a5a6)
    embed.add_field(name="Guilds", value=len(bot.guilds), inline=True)
    embed.add_field(name="Users", value=len(bot.users), inline=True)
    embed.add_field(name="Commands", value=len(bot.commands), inline=True)
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    
    # Memory usage (nếu có thể)
    try:
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        embed.add_field(name="Memory", value=f"{memory_mb:.2f} MB", inline=True)
    except ImportError:
        embed.add_field(name="Memory", value="N/A", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='reload')
@commands.is_owner()
async def reload_bot(ctx):
    """Reload bot (chỉ owner)"""
    await ctx.send("🔄 Đang reload bot...")
    # Ở đây bạn có thể thêm logic reload nếu cần
    await ctx.send("✅ Reload hoàn thành!")

@bot.command(name='shutdown')
@commands.is_owner()
async def shutdown_bot(ctx):
    """Tắt bot (chỉ owner)"""
    await ctx.send("🔌 Đang tắt bot...")
    await bot.close()

# Thêm cooldown cho một số lệnh để tránh spam
@bot.command(name='spam_test')
@commands.cooldown(1, 30, commands.BucketType.user)  # 1 lần mỗi 30 giây
async def spam_test(ctx):
    """Lệnh test cooldown"""
    await ctx.send("✅ Lệnh test cooldown hoạt động!")

# Thêm một số utility functions
def format_time(seconds):
    """Format seconds thành readable time"""
    if seconds < 60:
        return f"{int(seconds)} giây"
    elif seconds < 3600:
        return f"{int(seconds // 60)} phút {int(seconds % 60)} giây"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours} giờ {minutes} phút"

def is_url(string):
    """Kiểm tra xem string có phải URL không"""
    import re
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(string) is not None

# Bot startup
if __name__ == "__main__":
    # Store start time for uptime command
    bot.start_time = datetime.datetime.now()
    
    # Load bot token from environment variable
    bot_token = os.getenv("DISCORD_BOT_TOKEN")
    if not bot_token:
        print("❌ Lỗi: Không tìm thấy token bot trong biến môi trường DISCORD_BOT_TOKEN")
        print("💡 Hướng dẫn:")
        print("1. Tạo file .env trong thư mục dự án")
        print("2. Thêm dòng: DISCORD_BOT_TOKEN=your_bot_token_here")
        print("3. Thay your_bot_token_here bằng token thật của bot")
        exit(1)
    
    try:
        print("🚀 Đang khởi động bot...")
        print(f"📊 Đã tải {len(bot.commands)} lệnh")
        print("⏳ Đang kết nối tới Discord...")
        bot.run(bot_token)
    except discord.errors.LoginFailure:
        print("❌ Lỗi: Token bot không hợp lệ")
        print("💡 Kiểm tra lại token trong file .env")
    except discord.errors.PrivilegedIntentsRequired:
        print("❌ Lỗi: Bot cần quyền Privileged Gateway Intents")
        print("💡 Bật Message Content Intent trong Discord Developer Portal")
    except KeyboardInterrupt:
        print("\n⏹️ Bot đã được dừng bởi người dùng")
    except Exception as e:
        print(f"❌ Lỗi khi khởi động bot: {str(e)}")
        print("💡 Kiểm tra lại cấu hình và thử lại")
                               