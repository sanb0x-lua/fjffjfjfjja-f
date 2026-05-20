import discord
from discord.ui import View, Button
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont
import io
import aiohttp
import os

def draw_rounded_rect(draw, xy, radius, fill=None):
    x1, y1, x2, y2 = xy
    draw.rectangle([x1+radius, y1, x2-radius, y2], fill=fill)
    draw.rectangle([x1, y1+radius, x2, y2-radius], fill=fill)
    draw.pieslice([x1, y1, x1+radius*2, y1+radius*2], 180, 270, fill=fill)
    draw.pieslice([x2-radius*2, y1, x2, y1+radius*2], 270, 360, fill=fill)
    draw.pieslice([x1, y2-radius*2, x1+radius*2, y2], 90, 180, fill=fill)
    draw.pieslice([x2-radius*2, y2-radius*2, x2, y2], 0, 90, fill=fill)

def load_background():
    bg_path = "assets/bg.png"
    if os.path.exists(bg_path):
        bg = Image.open(bg_path)
        bg = bg.resize((1000, 700))
        return bg.convert('RGB')
    else:
        return Image.new('RGB', (1000, 700), (30, 35, 60))

async def get_avatar_image(user):
    async with aiohttp.ClientSession() as session:
        async with session.get(user.display_avatar.url) as resp:
            if resp.status == 200:
                img_data = await resp.read()
                avatar = Image.open(io.BytesIO(img_data))
                return avatar.convert('RGBA')
    return None

def create_circle_avatar(avatar_img, size=35):
    avatar = avatar_img.resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new('L', (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse([(0, 0), (size, size)], fill=255)
    result = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    result.paste(avatar, (0, 0), mask)
    return result

class LeaderBoardView(View):
    def __init__(self, ctx, guild_id, messages_log):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.guild_id = guild_id
        self.messages_log = messages_log
        self.current_days = 1
        self.current_page = 0
        self.avatar_cache = {}
    
    async def send(self):
        await self.update_display()
    
    async def update_display(self, interaction=None):
        CARD_WIDTH, CARD_HEIGHT = 1000, 700
        bg = load_background()
        img = bg.copy()
        draw = ImageDraw.Draw(img)
        
        try:
            font_title = ImageFont.truetype("segoeui.ttf", 30)
            font_normal = ImageFont.truetype("segoeui.ttf", 20)
            font_small = ImageFont.truetype("segoeui.ttf", 17)
            font_bold = ImageFont.truetype("segoeuib.ttf", 20)
        except:
            font_title = font_normal = font_small = font_bold = ImageFont.load_default()
        
        margin, radius = 25, 25
        now = datetime.now(timezone.utc)
        guild_msgs = self.messages_log[self.guild_id]
        
        cutoff = now - timedelta(days=self.current_days)
        filtered = [m for m in guild_msgs if m["time"].replace(tzinfo=timezone.utc) > cutoff]
        user_counts = defaultdict(int)
        for m in filtered:
            user_counts[m["user_name"]] += 1
        top_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)
        
        items_per_page = 14
        total_pages = max(1, (len(top_users) + items_per_page - 1) // items_per_page)
        self.current_page = max(0, min(self.current_page, total_pages - 1))
        start = self.current_page * items_per_page
        current_users = top_users[start:start+items_per_page]
        
        dark_color = (40, 44, 52, 180)
        card_layer = Image.new('RGBA', (CARD_WIDTH, CARD_HEIGHT), (0, 0, 0, 0))
        card_draw = ImageDraw.Draw(card_layer)
        draw_rounded_rect(card_draw, [margin, margin, CARD_WIDTH-margin, CARD_HEIGHT-margin], radius, fill=dark_color)
        img = Image.alpha_composite(img.convert('RGBA'), card_layer)
        draw = ImageDraw.Draw(img)
        
        x, y, padding = margin, margin, 30
        period_name = {1: "1 день", 7: "7 дней", 30: "30 дней"}
        draw.text((x+padding, y+20), f"Лидерборд - {period_name.get(self.current_days, 'все время')}", fill=(255,255,255), font=font_title)
        draw.text((x+padding, y+60), f"Всего участников: {len(user_counts)}", fill=(200,200,200), font=font_small)
        draw.text((x+padding, y+90), f"Страница {self.current_page+1} из {total_pages}", fill=(200,200,200), font=font_small)
        
        y_header = y + 135
        draw.text((x+padding+45, y_header), "Пользователь", fill=(200,200,200), font=font_normal)
        draw.text((x+padding+320, y_header), "Сообщений", fill=(200,200,200), font=font_normal)
        
        y_user = y + 175
        row_height = 38
        for i, (user, count) in enumerate(current_users):
            rank = start + i + 1
            color = (255,255,255) if rank == 1 else (220,220,220) if rank == 2 else (200,200,200) if rank == 3 else (180,180,180)
            draw.text((x+padding+10, y_user + i*row_height), str(rank), fill=color, font=font_bold)
            
            member = discord.utils.get(self.ctx.guild.members, name=user)
            if member and member.id not in self.avatar_cache:
                avatar_img = await get_avatar_image(member)
                if avatar_img:
                    self.avatar_cache[member.id] = avatar_img
            if member and member.id in self.avatar_cache:
                avatar = create_circle_avatar(self.avatar_cache[member.id], 32)
                img.paste(avatar, (x+padding+38, y_user + i*row_height + 2), avatar)
            
            draw.text((x+padding+80, y_user + i*row_height + 5), user[:25], fill=(255,255,255), font=font_small)
            draw.text((x+padding+320, y_user + i*row_height + 5), str(count), fill=color, font=font_bold)
        
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        file = discord.File(buf, filename="leaderboard.png")
        embed = discord.Embed(color=0xFFFFFF)
        embed.set_image(url="attachment://leaderboard.png")
        
        self.clear_items()
        btn1 = Button(label="1 день", style=discord.ButtonStyle.secondary)
        btn7 = Button(label="7 дней", style=discord.ButtonStyle.secondary)
        btn30 = Button(label="30 дней", style=discord.ButtonStyle.secondary)
        btn_prev = Button(label="◀ Назад", style=discord.ButtonStyle.secondary)
        btn_next = Button(label="Вперёд ▶", style=discord.ButtonStyle.secondary)
        
        async def day_callback(d):
            async def callback(i):
                self.current_days = d
                self.current_page = 0
                await self.update_display(i)
            return callback
        
        async def prev_callback(i):
            if self.current_page > 0:
                self.current_page -= 1
                await self.update_display(i)
        
        async def next_callback(i):
            if self.current_page < total_pages - 1:
                self.current_page += 1
                await self.update_display(i)
        
        btn1.callback = await day_callback(1)
        btn7.callback = await day_callback(7)
        btn30.callback = await day_callback(30)
        btn_prev.callback = prev_callback
        btn_next.callback = next_callback
        
        self.add_item(btn1)
        self.add_item(btn7)
        self.add_item(btn30)
        self.add_item(btn_prev)
        self.add_item(btn_next)
        
        if interaction:
            await interaction.response.edit_message(embed=embed, attachments=[file], view=self)
        else:
            await self.ctx.send(embed=embed, file=file, view=self)