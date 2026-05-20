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

class LogsView(View):
    def __init__(self, ctx, guild_id, logs_list):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.guild_id = guild_id
        self.logs_list = logs_list
        self.current_page = 0
        self.items_per_page = 10
    
    async def send(self):
        await self.update_display()
    
    async def update_display(self, interaction=None):
        CARD_WIDTH, CARD_HEIGHT = 1000, 700
        bg = load_background()
        img = bg.copy()
        draw = ImageDraw.Draw(img)
        
        try:
            font_title = ImageFont.truetype("segoeui.ttf", 30)
            font_normal = ImageFont.truetype("segoeui.ttf", 18)
            font_small = ImageFont.truetype("segoeui.ttf", 14)
        except:
            font_title = font_normal = font_small = ImageFont.load_default()
        
        margin, radius = 25, 25
        logs = self.logs_list[self.guild_id].copy()
        logs.reverse()
        total_pages = max(1, (len(logs) + self.items_per_page - 1) // self.items_per_page)
        self.current_page = max(0, min(self.current_page, total_pages - 1))
        start = self.current_page * self.items_per_page
        current_logs = logs[start:start+self.items_per_page]
        
        dark_color = (40, 44, 52, 180)
        card_layer = Image.new('RGBA', (CARD_WIDTH, CARD_HEIGHT), (0, 0, 0, 0))
        card_draw = ImageDraw.Draw(card_layer)
        draw_rounded_rect(card_draw, [margin, margin, CARD_WIDTH-margin, CARD_HEIGHT-margin], radius, fill=dark_color)
        img = Image.alpha_composite(img.convert('RGBA'), card_layer)
        draw = ImageDraw.Draw(img)
        
        x, y, padding = margin, margin, 25
        draw.text((x+padding, y+20), "Логи сервера", fill=(255,255,255), font=font_title)
        draw.text((x+padding, y+55), f"Страница {self.current_page+1} из {total_pages}", fill=(200,200,200), font=font_small)
        
        if not logs:
            draw.text((x+padding, y+100), "Логов пока нет", fill=(150,150,150), font=font_normal)
        else:
            y_header = y + 95
            draw.text((x+padding+5, y_header), "Тип", fill=(200,200,200), font=font_small)
            draw.text((x+padding+140, y_header), "Пользователь", fill=(200,200,200), font=font_small)
            draw.text((x+padding+280, y_header), "Канал", fill=(200,200,200), font=font_small)
            draw.text((x+padding+400, y_header), "Действие", fill=(200,200,200), font=font_small)
            draw.text((x+padding+680, y_header), "Время", fill=(200,200,200), font=font_small)
            
            y_log = y_header + 25
            row_height = 52
            for i, log in enumerate(current_logs):
                y_pos = y_log + i * row_height
                draw.text((x+padding+5, y_pos), log["type"][:18], fill=(220,220,220), font=font_small)
                draw.text((x+padding+140, y_pos), log["user_name"][:20], fill=(255,255,255), font=font_small)
                draw.text((x+padding+280, y_pos), log["channel"][:15], fill=(220,220,220), font=font_small)
                draw.text((x+padding+400, y_pos), log["content"][:35], fill=(200,200,200), font=font_small)
                draw.text((x+padding+680, y_pos), log["time"], fill=(180,180,180), font=font_small)
        
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        file = discord.File(buf, filename="logs.png")
        embed = discord.Embed(color=0xFFFFFF)
        embed.set_image(url="attachment://logs.png")
        
        self.clear_items()
        btn_prev = Button(label="◀ Назад", style=discord.ButtonStyle.secondary)
        btn_next = Button(label="Вперёд ▶", style=discord.ButtonStyle.secondary)
        btn_refresh = Button(label="Обновить", style=discord.ButtonStyle.primary)
        
        async def prev_callback(i):
            if self.current_page > 0:
                self.current_page -= 1
                await self.update_display(i)
        
        async def next_callback(i):
            if self.current_page < total_pages - 1:
                self.current_page += 1
                await self.update_display(i)
        
        async def refresh_callback(i):
            await self.update_display(i)
        
        btn_prev.callback = prev_callback
        btn_next.callback = next_callback
        btn_refresh.callback = refresh_callback
        
        self.add_item(btn_prev)
        self.add_item(btn_next)
        self.add_item(btn_refresh)
        
        if interaction:
            await interaction.response.edit_message(embed=embed, attachments=[file], view=self)
        else:
            await self.ctx.send(embed=embed, file=file, view=self)