import discord
from discord.ui import View
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

def format_date(dt):
    return dt.strftime("%d.%m.%Y %H:%M") if dt else "Неизвестно"

class ProfileView(View):
    def __init__(self, ctx, guild_id, messages_log, target_user, reactions_given, reactions_received, nick_history_db):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.guild_id = guild_id
        self.messages_log = messages_log
        self.target_user = target_user
        self.avatar_img = None
        self.reactions_given = reactions_given
        self.reactions_received = reactions_received
        self.nick_history_db = nick_history_db
    
    async def send(self):
        await self.update_display()
    
    async def get_avatar(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(self.target_user.display_avatar.url) as resp:
                if resp.status == 200:
                    img_data = await resp.read()
                    avatar = Image.open(io.BytesIO(img_data))
                    return avatar.convert('RGBA')
        return None
    
    def create_circle_avatar(self, avatar_img, size=90):
        avatar = avatar_img.resize((size, size), Image.Resampling.LANCZOS)
        mask = Image.new('L', (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse([(0, 0), (size, size)], fill=255)
        result = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        result.paste(avatar, (0, 0), mask)
        border = Image.new('RGBA', (size+8, size+8), (0, 0, 0, 0))
        border_draw = ImageDraw.Draw(border)
        border_draw.ellipse([(4, 4), (size+4, size+4)], outline=(200,200,200), width=3)
        border.paste(result, (4, 4), result)
        return border
    
    async def update_display(self, interaction=None):
        CARD_WIDTH, CARD_HEIGHT = 1000, 700
        bg = load_background()
        img = bg.copy()
        draw = ImageDraw.Draw(img)
        
        try:
            font_title = ImageFont.truetype("segoeui.ttf", 26)
            font_large = ImageFont.truetype("segoeuib.ttf", 34)
            font_normal = ImageFont.truetype("segoeui.ttf", 18)
            font_small = ImageFont.truetype("segoeui.ttf", 14)
            font_bold = ImageFont.truetype("segoeuib.ttf", 19)
        except:
            font_title = font_large = font_normal = font_small = font_bold = ImageFont.load_default()
        
        margin, radius = 20, 25
        now = datetime.now(timezone.utc)
        guild_msgs = self.messages_log[self.guild_id]
        user = self.target_user
        member = self.ctx.guild.get_member(user.id)
        
        user_msgs = [m for m in guild_msgs if m["user_name"] == user.name]
        total_msgs = len(user_msgs)
        msgs_1d = len([m for m in user_msgs if m["time"].replace(tzinfo=timezone.utc) > now - timedelta(days=1)])
        msgs_7d = len([m for m in user_msgs if m["time"].replace(tzinfo=timezone.utc) > now - timedelta(days=7)])
        msgs_30d = len([m for m in user_msgs if m["time"].replace(tzinfo=timezone.utc) > now - timedelta(days=30)])
        
        channel_counts = defaultdict(int)
        for m in user_msgs:
            channel_counts[m["channel_name"]] += 1
        favorite_channel = max(channel_counts.items(), key=lambda x: x[1])[0] if channel_counts else "Нет"
        favorite_channel_count = channel_counts.get(favorite_channel, 0)
        
        total_guild_msgs = len(guild_msgs)
        activity_percent = (total_msgs / total_guild_msgs * 100) if total_guild_msgs > 0 else 0
        
        all_users = defaultdict(int)
        for m in guild_msgs:
            all_users[m["user_name"]] += 1
        sorted_users = sorted(all_users.items(), key=lambda x: x[1], reverse=True)
        rank = 1
        for i, (u, _) in enumerate(sorted_users):
            if u == user.name:
                rank = i + 1
                break
        
        achievements = []
        if total_msgs >= 100:
            achievements.append("100 сообщений")
        if total_msgs >= 1000:
            achievements.append("1000 сообщений")
        if total_msgs >= 5000:
            achievements.append("5000 сообщений")
        if total_msgs >= 10000:
            achievements.append("10000 сообщений")
        if msgs_30d >= 300:
            achievements.append("300 за месяц")
        if rank == 1:
            achievements.append("Лидер сервера")
        
        nick_history_list = []
        for row in self.nick_history_db:
            nick_history_list.append(f"{row['old_nick']} -> {row['new_nick']}")
        nick_history_str = ", ".join(nick_history_list[-3:]) if nick_history_list else "Нет истории"
        
        if member:
            status = member.status
            if status == discord.Status.online:
                status_text, status_color = "В сети", (87,242,135)
            elif status == discord.Status.idle:
                status_text, status_color = "Не активен", (251,211,141)
            elif status == discord.Status.dnd:
                status_text, status_color = "Не беспокоить", (237,66,69)
            else:
                status_text, status_color = "Не в сети", (116,127,141)
        else:
            status_text, status_color = "Не в сети", (116,127,141)
        
        roles_text = ""
        if member and len(member.roles) > 1:
            roles_list = [role.name for role in member.roles if role.name != "@everyone"][:4]
            roles_text = ", ".join(roles_list)
            if len(member.roles) > 5:
                roles_text += f" +{len(member.roles)-5}"
        else:
            roles_text = "Нет ролей"
        
        dark_color = (40, 44, 52, 180)
        card_layer = Image.new('RGBA', (CARD_WIDTH, CARD_HEIGHT), (0, 0, 0, 0))
        card_draw = ImageDraw.Draw(card_layer)
        draw_rounded_rect(card_draw, [margin, margin, CARD_WIDTH-margin, CARD_HEIGHT-margin], radius, fill=dark_color)
        img = Image.alpha_composite(img.convert('RGBA'), card_layer)
        draw = ImageDraw.Draw(img)
        
        x, y, padding = margin, margin, 22
        
        draw.text((x+padding, y+12), "Профиль пользователя", fill=(255,255,255), font=font_title)
        
        if self.avatar_img is None:
            self.avatar_img = await self.get_avatar()
        if self.avatar_img:
            avatar = self.create_circle_avatar(self.avatar_img, 85)
            img.paste(avatar, (x+padding, y+50), avatar)
        else:
            draw.ellipse([x+padding, y+50, x+padding+85, y+135], fill=(80,80,80), outline=(200,200,200), width=3)
        
        draw.text((x+padding+105, y+55), user.display_name, fill=(255,255,255), font=font_bold)
        draw.text((x+padding+105, y+80), f"@{user.name}", fill=(200,200,200), font=font_small)
        draw.text((x+padding+105, y+100), f"Глобальное имя: {user.global_name or 'Нет'}", fill=(180,180,180), font=font_small)
        draw.ellipse([x+padding+105, y+123, x+padding+118, y+136], fill=status_color)
        draw.text((x+padding+128, y+123), status_text, fill=(200,200,200), font=font_small)
        draw.text((x+padding+105, y+148), f"ID: {user.id}", fill=(150,150,150), font=font_small)
        
        stats_y = y + 185
        draw.text((x+padding, stats_y), "Статистика сообщений", fill=(255,255,255), font=font_normal)
        draw.text((x+padding, stats_y+25), "Всего", fill=(180,180,180), font=font_small)
        draw.text((x+padding, stats_y+45), str(total_msgs), fill=(255,255,255), font=font_bold)
        draw.text((x+padding+95, stats_y+25), "1 день", fill=(180,180,180), font=font_small)
        draw.text((x+padding+95, stats_y+45), str(msgs_1d), fill=(255,255,255), font=font_small)
        draw.text((x+padding+175, stats_y+25), "7 дней", fill=(180,180,180), font=font_small)
        draw.text((x+padding+175, stats_y+45), str(msgs_7d), fill=(255,255,255), font=font_small)
        draw.text((x+padding+255, stats_y+25), "30 дней", fill=(180,180,180), font=font_small)
        draw.text((x+padding+255, stats_y+45), str(msgs_30d), fill=(255,255,255), font=font_small)
        draw.text((x+padding+350, stats_y+25), "Ранг", fill=(180,180,180), font=font_small)
        draw.text((x+padding+350, stats_y+45), f"#{rank}", fill=(255,255,255), font=font_small)
        
        draw.text((x+padding, stats_y+80), f"Любимый канал: #{favorite_channel} ({favorite_channel_count} сообщ.)", fill=(200,200,200), font=font_small)
        draw.text((x+padding, stats_y+103), f"Процент активности: {activity_percent:.2f}% от всех сообщений", fill=(200,200,200), font=font_small)
        draw.text((x+padding+380, stats_y+80), f"Реакций получено: {self.reactions_received}", fill=(200,200,200), font=font_small)
        draw.text((x+padding+380, stats_y+103), f"Реакций поставлено: {self.reactions_given}", fill=(200,200,200), font=font_small)
        
        acc_y = stats_y + 145
        draw.text((x+padding, acc_y), "Информация об аккаунте", fill=(255,255,255), font=font_normal)
        draw.text((x+padding, acc_y+28), "Аккаунт создан", fill=(180,180,180), font=font_small)
        draw.text((x+padding, acc_y+50), format_date(user.created_at), fill=(220,220,220), font=font_small)
        draw.text((x+padding, acc_y+75), "Присоединился", fill=(180,180,180), font=font_small)
        draw.text((x+padding, acc_y+97), format_date(member.joined_at) if member else "Неизвестно", fill=(220,220,220), font=font_small)
        draw.text((x+padding+280, acc_y+28), "Буст сервера", fill=(180,180,180), font=font_small)
        boost_text = f"С {format_date(member.premium_since)}" if (member and member.premium_since) else "Нет"
        draw.text((x+padding+280, acc_y+50), boost_text, fill=(220,220,220), font=font_small)
        draw.text((x+padding+280, acc_y+75), "Роли", fill=(180,180,180), font=font_small)
        draw.text((x+padding+280, acc_y+97), roles_text[:35], fill=(220,220,220), font=font_small)
        
        ach_y = acc_y + 135
        draw.text((x+padding, ach_y), "Достижения", fill=(255,255,255), font=font_normal)
        ach_text = "  ".join(achievements[:5]) if achievements else "Пока нет достижений"
        draw.text((x+padding, ach_y+28), ach_text[:80], fill=(255,215,0) if achievements else (180,180,180), font=font_small)
        
        nick_y = ach_y + 65
        draw.text((x+padding, nick_y), "История ников", fill=(255,255,255), font=font_normal)
        draw.text((x+padding, nick_y+28), nick_history_str[:80], fill=(200,200,200), font=font_small)
        
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        file = discord.File(buf, filename="profile.png")
        embed = discord.Embed(color=0xFFFFFF)
        embed.set_image(url="attachment://profile.png")
        
        if interaction:
            await interaction.response.edit_message(embed=embed, attachments=[file], view=self)
        else:
            await self.ctx.send(embed=embed, file=file, view=self)