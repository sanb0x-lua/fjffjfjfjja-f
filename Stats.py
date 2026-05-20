import discord
from discord.ui import View, Button
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont
import io
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

class StatsView(View):
    def __init__(self, ctx, guild_id, messages_log):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.guild_id = guild_id
        self.messages_log = messages_log
        self.current_days = 1
    
    async def send(self):
        await self.update_display()
    
    async def update_display(self, interaction=None):
        CARD_WIDTH, CARD_HEIGHT = 1000, 700
        bg = load_background()
        img = bg.copy()
        draw = ImageDraw.Draw(img)
        
        try:
            font_title = ImageFont.truetype("segoeui.ttf", 30)
            font_large = ImageFont.truetype("segoeuib.ttf", 52)
            font_normal = ImageFont.truetype("segoeui.ttf", 22)
            font_small = ImageFont.truetype("segoeui.ttf", 18)
            font_bold = ImageFont.truetype("segoeuib.ttf", 22)
        except:
            font_title = font_large = font_normal = font_small = font_bold = ImageFont.load_default()
        
        margin, radius = 25, 25
        now = datetime.now(timezone.utc)
        guild_msgs = self.messages_log[self.guild_id]
        
        def msg_count(d):
            cutoff = now - timedelta(days=d)
            return len([m for m in guild_msgs if m["time"].replace(tzinfo=timezone.utc) > cutoff])
        
        dark_color = (40, 44, 52, 180)
        card_layer = Image.new('RGBA', (CARD_WIDTH, CARD_HEIGHT), (0, 0, 0, 0))
        card_draw = ImageDraw.Draw(card_layer)
        draw_rounded_rect(card_draw, [margin, margin, CARD_WIDTH-margin, CARD_HEIGHT-margin], radius, fill=dark_color)
        img = Image.alpha_composite(img.convert('RGBA'), card_layer)
        draw = ImageDraw.Draw(img)
        
        x, y, padding = margin, margin, 30
        draw.text((x+padding, y+20), "Статистика сервера", fill=(255,255,255), font=font_title)
        draw.text((x+padding, y+60), self.ctx.guild.name, fill=(200,200,200), font=font_small)
        draw.text((x+padding, y+110), str(len(guild_msgs)), fill=(255,255,255), font=font_large)
        draw.text((x+padding, y+165), "всего сообщений", fill=(180,180,180), font=font_small)
        
        period_y = y + 220
        periods = [(1, "1 день"), (7, "7 дней"), (30, "30 дней")]
        for i, (d, name) in enumerate(periods):
            x_pos = x+padding + i*150
            draw.text((x_pos, period_y), name, fill=(180,180,180), font=font_small)
            draw.text((x_pos, period_y+32), str(msg_count(d)), fill=(255,255,255), font=font_bold)
        
        cutoff = now - timedelta(days=self.current_days)
        filtered = [m for m in guild_msgs if m["time"].replace(tzinfo=timezone.utc) > cutoff]
        user_counts = defaultdict(int)
        for m in filtered:
            user_counts[m["user_name"]] += 1
        top_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        draw.text((x+padding, y+310), "Топ пользователи", fill=(255,255,255), font=font_normal)
        y_user = y + 355
        for i, (user, count) in enumerate(top_users):
            color = (255,255,255) if i == 0 else (220,220,220) if i == 1 else (200,200,200) if i == 2 else (180,180,180)
            draw.text((x+padding+5, y_user + i*40), f"{i+1}. {user}", fill=color, font=font_small)
            draw.text((x+CARD_WIDTH-padding-70, y_user + i*40), str(count), fill=color, font=font_small)
        
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        file = discord.File(buf, filename="stats.png")
        embed = discord.Embed(color=0xFFFFFF)
        embed.set_image(url="attachment://stats.png")
        
        self.clear_items()
        btn1 = Button(label="1 день", style=discord.ButtonStyle.secondary)
        btn7 = Button(label="7 дней", style=discord.ButtonStyle.secondary)
        btn30 = Button(label="30 дней", style=discord.ButtonStyle.secondary)
        
        async def day_callback(d):
            async def callback(i):
                self.current_days = d
                await self.update_display(i)
            return callback
        
        btn1.callback = await day_callback(1)
        btn7.callback = await day_callback(7)
        btn30.callback = await day_callback(30)
        
        self.add_item(btn1)
        self.add_item(btn7)
        self.add_item(btn30)
        
        if interaction:
            await interaction.response.edit_message(embed=embed, attachments=[file], view=self)
        else:
            await self.ctx.send(embed=embed, file=file, view=self)