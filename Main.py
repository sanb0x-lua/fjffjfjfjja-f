import discord
from discord.ext import commands
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont
import io
import os
import asyncpg
import asyncio
from aiohttp import web

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
intents.guilds = True
intents.moderation = True
intents.bans = True
intents.webhooks = True
intents.reactions = True

bot = commands.Bot(command_prefix="S!", intents=intents)

DATABASE_URL = os.getenv("DATABASE_URL")

messages_cache = defaultdict(list)
logs_cache = defaultdict(list)

class Database:
    def __init__(self):
        self.pool = None
    
    async def connect(self):
        self.pool = await asyncpg.create_pool(DATABASE_URL)
        await self.create_tables()
    
    async def create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT,
                    user_name TEXT,
                    channel_name TEXT,
                    time TIMESTAMP
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS logs (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT,
                    type TEXT,
                    user_name TEXT,
                    channel TEXT,
                    content TEXT,
                    time TEXT
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS log_channels (
                    guild_id BIGINT PRIMARY KEY,
                    channel_id BIGINT
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS nick_history (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT,
                    user_id BIGINT,
                    user_name TEXT,
                    old_nick TEXT,
                    new_nick TEXT,
                    time TEXT
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS reactions (
                    user_id BIGINT PRIMARY KEY,
                    given INT DEFAULT 0,
                    received INT DEFAULT 0
                )
            ''')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_guild ON messages(guild_id)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_name)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_logs_guild ON logs(guild_id)')
    
    async def save_message(self, guild_id, user_name, channel_name, time):
        async with self.pool.acquire() as conn:
            await conn.execute('INSERT INTO messages (guild_id, user_name, channel_name, time) VALUES ($1, $2, $3, $4)', guild_id, user_name, channel_name, time)
    
    async def get_messages(self, guild_id, days=None):
        async with self.pool.acquire() as conn:
            if days:
                cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                return await conn.fetch('SELECT * FROM messages WHERE guild_id = $1 AND time > $2', guild_id, cutoff)
            else:
                return await conn.fetch('SELECT * FROM messages WHERE guild_id = $1', guild_id)
    
    async def save_log(self, guild_id, log_type, user_name, channel, content, time):
        async with self.pool.acquire() as conn:
            await conn.execute('INSERT INTO logs (guild_id, type, user_name, channel, content, time) VALUES ($1, $2, $3, $4, $5, $6)', guild_id, log_type, user_name, channel, content, time)
    
    async def get_logs(self, guild_id, limit=1000):
        async with self.pool.acquire() as conn:
            return await conn.fetch('SELECT * FROM logs WHERE guild_id = $1 ORDER BY id DESC LIMIT $2', guild_id, limit)
    
    async def set_log_channel(self, guild_id, channel_id):
        async with self.pool.acquire() as conn:
            await conn.execute('INSERT INTO log_channels (guild_id, channel_id) VALUES ($1, $2) ON CONFLICT (guild_id) DO UPDATE SET channel_id = $2', guild_id, channel_id)
    
    async def get_log_channel(self, guild_id):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow('SELECT channel_id FROM log_channels WHERE guild_id = $1', guild_id)
            return row["channel_id"] if row else None
    
    async def save_nick_history(self, guild_id, user_id, user_name, old_nick, new_nick, time):
        async with self.pool.acquire() as conn:
            await conn.execute('INSERT INTO nick_history (guild_id, user_id, user_name, old_nick, new_nick, time) VALUES ($1, $2, $3, $4, $5, $6)', guild_id, user_id, user_name, old_nick, new_nick, time)
    
    async def get_nick_history(self, guild_id, user_id, limit=5):
        async with self.pool.acquire() as conn:
            return await conn.fetch('SELECT * FROM nick_history WHERE guild_id = $1 AND user_id = $2 ORDER BY id DESC LIMIT $3', guild_id, user_id, limit)
    
    async def update_reactions(self, user_id, given_delta=0, received_delta=0):
        async with self.pool.acquire() as conn:
            await conn.execute('INSERT INTO reactions (user_id, given, received) VALUES ($1, $2, $3) ON CONFLICT (user_id) DO UPDATE SET given = reactions.given + $2, received = reactions.received + $3', user_id, given_delta, received_delta)
    
    async def get_reactions(self, user_id):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow('SELECT given, received FROM reactions WHERE user_id = $1', user_id)
            return (row["given"], row["received"]) if row else (0, 0)

db = Database()

async def load_cache():
    global messages_cache, logs_cache
    for guild in bot.guilds:
        msgs = await db.get_messages(guild.id, 30)
        messages_cache[guild.id] = [dict(m) for m in msgs]
        logs = await db.get_logs(guild.id, 500)
        logs_cache[guild.id] = [dict(m) for m in logs]

@bot.event
async def on_ready():
    await db.connect()
    await load_cache()
    print(f'Bot ready: {bot.user}')
    if not os.path.exists("assets"):
        os.makedirs("assets")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.guild:
        now = datetime.now(timezone.utc)
        await db.save_message(message.guild.id, message.author.name, message.channel.name, now)
        messages_cache[message.guild.id].append({"guild_id": message.guild.id, "user_name": message.author.name, "channel_name": message.channel.name, "time": now})
        if len(messages_cache[message.guild.id]) > 5000:
            messages_cache[message.guild.id] = messages_cache[message.guild.id][-4000:]
    await bot.process_commands(message)

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    await db.update_reactions(user.id, given_delta=1, received_delta=0)
    if reaction.message.author and not reaction.message.author.bot:
        await db.update_reactions(reaction.message.author.id, given_delta=0, received_delta=1)

@bot.event
async def on_reaction_remove(reaction, user):
    if user.bot:
        return
    await db.update_reactions(user.id, given_delta=-1, received_delta=0)
    if reaction.message.author and not reaction.message.author.bot:
        await db.update_reactions(reaction.message.author.id, given_delta=0, received_delta=-1)

@bot.event
async def on_member_update(before, after):
    if before.nick != after.nick:
        old = before.nick if before.nick else before.name
        new = after.nick if after.nick else after.name
        time_str = datetime.now(timezone.utc).strftime("%d.%m %H:%M")
        await db.save_nick_history(before.guild.id, after.id, after.name, old, new, time_str)
        await db.save_log(before.guild.id, "Смена ника", after.name, "-", f"{old} -> {new}", time_str)

@bot.event
async def on_message_delete(message):
    if message.guild and message.author and not message.author.bot:
        time_str = datetime.now(timezone.utc).strftime("%d.%m %H:%M")
        await db.save_log(message.guild.id, "Удаление сообщ", message.author.name, message.channel.name, message.content[:55] if message.content else "(нет текста)", time_str)

@bot.event
async def on_message_edit(before, after):
    if before.guild and before.author and not before.author.bot:
        if before.content != after.content:
            time_str = datetime.now(timezone.utc).strftime("%d.%m %H:%M")
            await db.save_log(before.guild.id, "Редакт сообщ", before.author.name, before.channel.name, f"{before.content[:30]} -> {after.content[:30]}", time_str)

@bot.event
async def on_guild_channel_create(channel):
    time_str = datetime.now(timezone.utc).strftime("%d.%m %H:%M")
    await db.save_log(channel.guild.id, "Создан канал", "Система", channel.name, f"#{channel.name}", time_str)

@bot.event
async def on_guild_channel_delete(channel):
    time_str = datetime.now(timezone.utc).strftime("%d.%m %H:%M")
    await db.save_log(channel.guild.id, "Удалён канал", "Система", channel.name, f"#{channel.name} удалён", time_str)

@bot.event
async def on_guild_channel_update(before, after):
    if before.name != after.name:
        time_str = datetime.now(timezone.utc).strftime("%d.%m %H:%M")
        await db.save_log(before.guild.id, "Переимен канал", "Система", after.name, f"#{before.name} -> #{after.name}", time_str)

@bot.event
async def on_member_join(member):
    time_str = datetime.now(timezone.utc).strftime("%d.%m %H:%M")
    await db.save_log(member.guild.id, "Присоединился", member.name, "-", "Новый участник", time_str)

@bot.event
async def on_member_remove(member):
    time_str = datetime.now(timezone.utc).strftime("%d.%m %H:%M")
    await db.save_log(member.guild.id, "Покинул/Кик", member.name, "-", "Участник покинул", time_str)

@bot.event
async def on_member_ban(guild, user):
    time_str = datetime.now(timezone.utc).strftime("%d.%m %H:%M")
    await db.save_log(guild.id, "Бан", user.name, "-", "Забанен", time_str)

@bot.event
async def on_member_unban(guild, user):
    time_str = datetime.now(timezone.utc).strftime("%d.%m %H:%M")
    await db.save_log(guild.id, "Разбан", user.name, "-", "Разбанен", time_str)

@bot.event
async def on_guild_role_create(role):
    time_str = datetime.now(timezone.utc).strftime("%d.%m %H:%M")
    await db.save_log(role.guild.id, "Создана роль", "Система", role.name, "Новая роль", time_str)

@bot.event
async def on_guild_role_delete(role):
    time_str = datetime.now(timezone.utc).strftime("%d.%m %H:%M")
    await db.save_log(role.guild.id, "Удалена роль", "Система", role.name, "Роль удалена", time_str)

@bot.event
async def on_guild_role_update(before, after):
    if before.name != after.name:
        time_str = datetime.now(timezone.utc).strftime("%d.%m %H:%M")
        await db.save_log(before.guild.id, "Переимен роль", "Система", after.name, f"{before.name} -> {after.name}", time_str)
    elif before.color != after.color:
        time_str = datetime.now(timezone.utc).strftime("%d.%m %H:%M")
        await db.save_log(before.guild.id, "Цвет роли", "Система", after.name, "Изменён цвет", time_str)

@bot.event
async def on_user_update(before, after):
    if before.avatar != after.avatar:
        for guild in bot.guilds:
            member = guild.get_member(after.id)
            if member:
                time_str = datetime.now(timezone.utc).strftime("%d.%m %H:%M")
                await db.save_log(guild.id, "Смена аватара", after.name, "-", "Аватар изменён", time_str)
                break

@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel != after.channel:
        time_str = datetime.now(timezone.utc).strftime("%d.%m %H:%M")
        if after.channel:
            await db.save_log(member.guild.id, "Зайшёл в войс", member.name, after.channel.name, f"Вошёл в {after.channel.name}", time_str)
        else:
            await db.save_log(member.guild.id, "Вышел из войс", member.name, before.channel.name, f"Вышел из {before.channel.name}", time_str)

@bot.command()
async def setL(ctx, channel: discord.TextChannel = None):
    if channel is None:
        channel = ctx.channel
    await db.set_log_channel(ctx.guild.id, channel.id)
    await ctx.send(f"Лог канал: {channel.mention}")

@bot.command()
async def L(ctx):
    log_channel_id = await db.get_log_channel(ctx.guild.id)
    if not log_channel_id or ctx.channel.id != log_channel_id:
        await ctx.send("Code: 1")
        return
    from Logs import LogsView
    view = LogsView(ctx, ctx.guild.id, logs_cache)
    await view.send()

from Stats import StatsView
from LeaderBoard import LeaderBoardView
from Profile import ProfileView
from Help import HelpView

@bot.command()
async def S(ctx):
    if not ctx.guild:
        return
    view = StatsView(ctx, ctx.guild.id, messages_cache)
    await view.send()

@bot.command()
async def LB(ctx):
    if not ctx.guild:
        return
    view = LeaderBoardView(ctx, ctx.guild.id, messages_cache)
    await view.send()

@bot.command()
async def P(ctx, member: discord.Member = None):
    if not ctx.guild:
        return
    target = member or ctx.author
    given, received = await db.get_reactions(target.id)
    nick_history_db = await db.get_nick_history(ctx.guild.id, target.id, 5)
    view = ProfileView(ctx, ctx.guild.id, messages_cache, target, given, received, nick_history_db)
    await view.send()

@bot.command()
async def H(ctx):
    view = HelpView()
    await view.send(ctx)

# ========== ВЕБ-СЕРВЕР ДЛЯ RENDER (НЕ ДАЁТ ЗАСНУТЬ) ==========

async def health_check(request):
    return web.Response(text="Bot is alive!")

app = web.Application()
app.router.add_get('/', health_check)

async def run_web():
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")

async def main():
    await asyncio.gather(run_web(), bot.start(os.getenv("DISCORD_TOKEN")))

if __name__ == "__main__":
    asyncio.run(main())