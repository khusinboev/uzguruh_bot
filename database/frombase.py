import aiosqlite
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

DB_NAME = "mybot.db"


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS channel (
            group_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            PRIMARY KEY (group_id, channel_id)
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS add_members (
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            member INTEGER NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (group_id, member)
        )
        """)

        await db.execute("CREATE INDEX IF NOT EXISTS idx_add_members_user_id ON add_members (user_id)")
        await db.commit()


# -------------------- CHANNEL FUNKSIYALAR --------------------

async def add_channel(group_id: int, channel_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        try:
            await db.execute(
                "INSERT INTO channel (group_id, channel_id) VALUES (?, ?)",
                (group_id, channel_id)
            )
            await db.commit()
        except aiosqlite.IntegrityError:
            pass  # Allaqachon mavjud


async def remove_channel(group_id: int, channel_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "DELETE FROM channel WHERE group_id = ? AND channel_id = ?",
            (group_id, channel_id)
        )
        await db.commit()


async def get_required_channels(group_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT channel_id FROM channel WHERE group_id = ?", (group_id,)) as cursor:
            return [row[0] for row in await cursor.fetchall()]


# -------------------- ADD_MEMBER FUNKSIYALAR --------------------

async def add_member(group_id: int, user_id: int, member: int):
    async with aiosqlite.connect(DB_NAME) as db:
        try:
            await db.execute(
                "INSERT INTO add_members (group_id, user_id, member) VALUES (?, ?, ?)",
                (group_id, user_id, member)
            )
            await db.commit()
        except aiosqlite.IntegrityError:
            pass  # Allaqachon mavjud


async def remove_members_by_user(group_id: int, user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "DELETE FROM add_members WHERE group_id = ? AND user_id = ?",
            (group_id, user_id)
        )
        await db.commit()


async def remove_all_members(group_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "DELETE FROM add_members WHERE group_id = ?",
            (group_id,)
        )
        await db.commit()


# -------------------- STATISTIKA FUNKSIYALAR --------------------

async def get_top_adders(group_id: int, limit: int = 20):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            """
            SELECT user_id, COUNT(*) as total
            FROM add_members
            WHERE group_id = ?
            GROUP BY user_id
            ORDER BY total DESC
            LIMIT ?
            """,
            (group_id, limit)
        ) as cursor:
            return await cursor.fetchall()


async def get_total_by_user(group_id: int, user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            """
            SELECT COUNT(*) FROM add_members
            WHERE group_id = ? AND user_id = ?
            """,
            (group_id, user_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


# -------------------- IS FOLLOW --------------------

async def notify_admins_about_bot_rights(bot: Bot, group_id: int, channel_id: int):
    try:
        admins = await bot.get_chat_administrators(group_id)
        channel = await bot.get_chat(channel_id)

        for admin in admins:
            if admin.user.is_bot:
                continue  # O'zini yubormasin
            try:
                await bot.send_message(
                    admin.user.id,
                    f"⚠️ Bot <b>{channel.title}</b> kanaliga admin emas.\n\n"
                    f"Iltimos, <a href='https://t.me/{channel.username}'>@{channel.username}</a> kanalga botni admin qilib qo‘shing.",
                    parse_mode="HTML"
                )
            except Exception as ex:
                print(ex)
                continue  # Adminning shaxsiyiga yozib bo'lmasa o'tkazib yubor
    except Exception:
        pass


async def is_user_subscribed(bot: Bot, channel_id: int, user_id: int, chat_id: int) -> bool:
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        return member.status in ["member", "administrator", "creator"]
    except TelegramBadRequest:
        # Bot kanalga kira olmayapti -> admin emas
        await notify_admins_about_bot_rights(bot, chat_id, channel_id)
        return True  # Foydalanuvchini tekshira olmayapmiz, ammo spam bo‘lmasligi uchun True qaytaramiz
    except Exception:
        return False
