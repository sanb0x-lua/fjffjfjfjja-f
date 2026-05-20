import discord
from discord.ui import View, Button
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

class HelpView(View):
    def __init__(self):
        super().__init__(timeout=120)
    
    async def send(self, ctx):
        await self.update_display(ctx)
    
    async def update_display(self, ctx, interaction=None):
        CARD_WIDTH, CARD_HEIGHT = 1000, 700
        bg = load_background()
        img = bg.copy()
        draw = ImageDraw.Draw(img)
        
        try:
            font_title = ImageFont.truetype("segoeui.ttf", 36)
            font_normal = ImageFont.truetype("segoeui.ttf", 24)
            font_small = ImageFont.truetype("segoeui.ttf", 20)
            font_bold = ImageFont.truetype("segoeuib.ttf", 26)
        except:
            font_title = font_normal = font_small = font_bold = ImageFont.load_default()
        
        margin, radius = 25, 25
        dark_color = (40, 44, 52, 180)
        card_layer = Image.new('RGBA', (CARD_WIDTH, CARD_HEIGHT), (0, 0, 0, 0))
        card_draw = ImageDraw.Draw(card_layer)
        draw_rounded_rect(card_draw, [margin, margin, CARD_WIDTH-margin, CARD_HEIGHT-margin], radius, fill=dark_color)
        img = Image.alpha_composite(img.convert('RGBA'), card_layer)
        draw = ImageDraw.Draw(img)
        
        x, y, padding = margin, margin, 30
        draw.text((x+padding, y+30), "Помощь", fill=(255,255,255), font=font_title)
        draw.text((x+padding, y+80), "Список доступных команд", fill=(200,200,200), font=font_small)
        
        commands_y = y + 150
        commands = [
            ("S!S", "Статистика сервера"),
            ("S!LB", "Лидерборд"),
            ("S!P", "Профиль (S!P @user)"),
            ("S!L", "Логи сервера"),
            ("S!setL", "Установить канал для логов"),
            ("S!H", "Помощь")
        ]
        
        for i, (cmd, desc) in enumerate(commands):
            draw.text((x+padding, commands_y + i*60), cmd, fill=(255,255,255), font=font_bold)
            draw.text((x+padding+200, commands_y + i*60 + 5), desc, fill=(200,200,200), font=font_normal)
        
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        file = discord.File(buf, filename="help.png")
        embed = discord.Embed(color=0xFFFFFF)
        embed.set_image(url="attachment://help.png")
        
        self.clear_items()
        btn_stats = Button(label="S!S", style=discord.ButtonStyle.primary)
        btn_lb = Button(label="S!LB", style=discord.ButtonStyle.primary)
        btn_profile = Button(label="S!P", style=discord.ButtonStyle.primary)
        btn_logs = Button(label="S!L", style=discord.ButtonStyle.primary)
        
        async def stats_callback(i):
            await ctx.invoke(ctx.bot.get_command('S'))
        async def lb_callback(i):
            await ctx.invoke(ctx.bot.get_command('LB'))
        async def profile_callback(i):
            await ctx.invoke(ctx.bot.get_command('P'))
        async def logs_callback(i):
            await ctx.invoke(ctx.bot.get_command('L'))
        
        btn_stats.callback = stats_callback
        btn_lb.callback = lb_callback
        btn_profile.callback = profile_callback
        btn_logs.callback = logs_callback
        
        self.add_item(btn_stats)
        self.add_item(btn_lb)
        self.add_item(btn_profile)
        self.add_item(btn_logs)
        
        if interaction:
            await interaction.response.edit_message(embed=embed, attachments=[file], view=self)
        else:
            await ctx.send(embed=embed, file=file, view=self)