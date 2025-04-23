import asyncio
import asyncpg
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Chat, Message

from config import USERNAME, PASSWORD, DATABASE

DATABASE_URL = f"postgresql://{USERNAME}:{PASSWORD}@localhost:5432/{DATABASE}"

async def create_pool():
    return await asyncpg.create_pool(DATABASE_URL)


# database.py

async def init_db(pool):
    async with pool.acquire() as conn:
        # Kanal ro‘yxati uchun jadval
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS channel (
            group_id BIGINT NOT NULL,
            channel_id BIGINT NOT NULL,
            PRIMARY KEY (group_id, channel_id)
        )
        """)

        # Foydalanuvchi tomonidan qo‘shilgan odamlar
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS add_members (
            group_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            member BIGINT NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (group_id, member)
        )
        """)

        # Har bir guruh uchun majburiy qo‘shish talabi
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS group_requirement (
            group_id BIGINT PRIMARY KEY,
            required_count INTEGER NOT NULL
        )
        """)

        # Foydalanuvchining statusi: talab bajarilganmi yoki yo‘q
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS user_requirement (
            group_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            status BOOLEAN NOT NULL DEFAULT FALSE,
            PRIMARY KEY (group_id, user_id)
        )
        """)

        # YANGI groups jadvali: vaqt bilan
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            group_id BIGINT PRIMARY KEY,
            bot_status BOOLEAN NOT NULL DEFAULT TRUE,
            number INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Foydalanuvchilar jadvali
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status BOOLEAN NOT NULL DEFAULT TRUE
        )
        """)



# -------------------- CHANNEL FUNKSIYALAR --------------------

async def add_channel(pool: asyncpg.Pool, group_id: int, channel_id: int):
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                "INSERT INTO channel (group_id, channel_id) VALUES ($1, $2)",
                group_id, channel_id
            )
        except asyncpg.UniqueViolationError:
            pass  # Allaqachon mavjud (primary key buzilishi)

async def remove_channel(pool: asyncpg.Pool, group_id: int, channel_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM channel WHERE group_id = $1 AND channel_id = $2",
            group_id, channel_id
        )

async def get_required_channels(pool: asyncpg.Pool, group_id: int) -> list[int]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT channel_id FROM channel WHERE group_id = $1",
            group_id
        )
        return [row["channel_id"] for row in rows]


# -------------------- ADD_MEMBER FUNKSIYALAR --------------------

async def add_member(pool: asyncpg.Pool, message: Message, member_id: int):
    group_id = message.chat.id
    user_id = message.from_user.id

    async with pool.acquire() as conn:
        # Oldin bu kombinatsiya mavjudligini tekshiramiz
        exists = await conn.fetchval("""
            SELECT 1 FROM add_members 
            WHERE group_id = $1 AND user_id = $2 AND member = $3
        """, group_id, user_id, member_id)

        if not exists:
            # Yangi qo‘shilgan a’zoni bazaga qo‘shamiz
            await conn.execute("""
                INSERT INTO add_members (group_id, user_id, member)
                VALUES ($1, $2, $3)
            """, group_id, user_id, member_id)

            # Endi necha kishini qo‘shganini hisoblaymiz
            added_count = await conn.fetchval("""
                SELECT COUNT(*) FROM add_members 
                WHERE group_id = $1 AND user_id = $2
            """, group_id, user_id)

            # Talab sonini olib kelamiz
            required_row = await conn.fetchrow("""
                SELECT required_count FROM group_requirement 
                WHERE group_id = $1
            """, group_id)

            required_count = required_row["required_count"] if required_row else 0

            # Agar talab bajarilgan bo‘lsa, user_requirement ni yangilaymiz
            if added_count >= required_count:
                await conn.execute("""
                    INSERT INTO user_requirement (group_id, user_id, status)
                    VALUES ($1, $2, TRUE)
                    ON CONFLICT (group_id, user_id)
                    DO UPDATE SET status = EXCLUDED.status
                """, group_id, user_id)



# Faqat bitta userning qo‘shganlarini o‘chirish
async def remove_members_by_user(pool: asyncpg.Pool, group_id: int, user_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM add_members WHERE group_id = $1 AND user_id = $2",
            group_id, user_id
        )

        await conn.execute("""
            INSERT INTO user_requirement (group_id, user_id, status)
            VALUES ($1, $2, FALSE)
            ON CONFLICT (group_id, user_id) DO UPDATE SET status = EXCLUDED.status
        """, group_id, user_id)


# Butun guruhdagi barcha userlarning qo‘shganlarini o‘chirish
async def remove_all_members(pool: asyncpg.Pool, group_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM add_members WHERE group_id = $1",
            group_id
        )

        await conn.execute(
            "UPDATE user_requirement SET status = FALSE WHERE group_id = $1",
            group_id
        )


# Statusni olish
async def get_user_status(pool: asyncpg.Pool, message: Message) -> bool:
    group_id = message.chat.id
    user_id = message.from_user.id

    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT status FROM user_requirement 
            WHERE group_id = $1 AND user_id = $2
        """, group_id, user_id)

        return bool(row['status']) if row else False


# update data
async def update_user_status(pool: asyncpg.Pool, message: Message):
    group_id = message.chat.id

    async with pool.acquire() as conn:
        # Guruh uchun talab qilingan odam sonini olish
        row = await conn.fetchrow("""
            SELECT required_count FROM group_requirement WHERE group_id = $1
        """, group_id)
        if not row:
            return
        required_count = row['required_count']

        # Har bir userning nechta odam qo‘shganini olish
        user_member_counts = await conn.fetch("""
            SELECT user_id, COUNT(member) as member_count
            FROM add_members
            WHERE group_id = $1
            GROUP BY user_id
        """, group_id)

        # Statusni yangilash
        for record in user_member_counts:
            user_id = record['user_id']
            member_count = record['member_count']
            status = member_count >= required_count

            await conn.execute("""
                INSERT INTO user_requirement (group_id, user_id, status)
                VALUES ($1, $2, $3)
                ON CONFLICT (group_id, user_id) DO UPDATE SET status = EXCLUDED.status
            """, group_id, user_id, status)


# -------------------- STATISTIKA FUNKSIYALAR --------------------

async def get_top_adders(pool, group_id: int, limit: int = 20):
    async with pool.acquire() as conn:
        result = await conn.fetch(
            """
            SELECT user_id, COUNT(*) as total
            FROM add_members
            WHERE group_id = $1
            GROUP BY user_id
            ORDER BY total DESC
            LIMIT $2
            """, group_id, limit
        )
        return result


async def get_total_by_user(pool, group_id: int, user_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT COUNT(*) FROM add_members
            WHERE group_id = $1 AND user_id = $2
            """, group_id, user_id
        )
        return row[0] if row else 0


# -------------------- IS FOLLOW --------------------

async def notify_admins_about_bot_rights(bot: Bot, group_id: int, channel_id: int):
    try:
        admins = await bot.get_chat_administrators(group_id)
        channel: Chat = await bot.get_chat(channel_id)

        for admin in admins:
            user = admin.user
            if user.is_bot:
                continue  # Bot o'ziga yozmasin

            try:
                await bot.send_message(
                    user.id,
                    f"⚠️ Bot <b>{channel.title}</b> kanaliga admin emas.\n\n"
                    f"Iltimos, <a href='https://t.me/{channel.username}'>@{channel.username}</a> kanalga botni admin qilib qo‘shing.",
                    parse_mode="HTML"
                )
            except Exception as ex:
                print(f"[Xatolik] {user.id} ga yuborib bo‘lmadi: {ex}")
    except Exception as e:
        print(f"[Adminlarni olishda xatolik]: {e}")


async def is_user_subscribed_all_channels(message: Message, pool) -> tuple[bool, list[str]]:
    bot = message.bot
    user_id = message.from_user.id
    group_id = message.chat.id

    unsubscribed_channels = []

    try:
        async with pool.acquire() as conn:
            channels = await conn.fetch(
                "SELECT channel_id FROM channel WHERE group_id = $1", group_id
            )
    except Exception as e:
        print(f"[DB xatolik]: {e}")
        return True, []

    if not channels:
        return True, []  # Guruhga kanal biriktirilmagan

    for (channel_id,) in channels:
        try:
            member = await bot.get_chat_member(channel_id, user_id)
            if member.status not in {"member", "administrator", "creator"}:
                channel = await bot.get_chat(channel_id)
                unsubscribed_channels.append(f"@{channel.username}" if channel.username else channel.title)
        except TelegramBadRequest as e:
            if "user not found" in str(e):
                # Balki user kanalga tashrif buyurmagan yoki owner
                continue
            else:
                # Bot kanalga kira olmayapti
                await notify_admins_about_bot_rights(bot, group_id, channel_id)
        except Exception as e:
            print(f"[Tekshiruv xatosi]: {e}")

    return (len(unsubscribed_channels) == 0), unsubscribed_channels



# ==== user check =====
async def check_user_requirement(message: Message, pool) -> tuple[bool, int | None]:
    group_id = message.chat.id
    user_id = message.from_user.id

    async with pool.acquire() as conn:
        # Guruhda majburiy odam qo‘shish bor-yo‘qligini tekshiramiz
        row = await conn.fetchrow(
            "SELECT required_count FROM group_requirement WHERE group_id = $1", group_id
        )
        if not row:
            return True, None  # Majburiy qo‘shish yo‘q

        required_count = row[0]

    # Foydalanuvchi statusini tekshiramiz
    row = await conn.fetchrow(
        "SELECT status FROM user_requirement WHERE group_id = $1 AND user_id = $2", group_id, user_id
    )
    if row and row[0]:
        return True, None  # Allaqachon kerakli odamlarni qo‘shgan

    # Foydalanuvchi qo‘shgan odamlar sonini hisoblaymiz
    added_count = await conn.fetchval(
        "SELECT COUNT(*) FROM add_members WHERE group_id = $1 AND user_id = $2", group_id, user_id
    )

    if added_count >= required_count:
        # Statusni yangilaymiz
        await conn.execute("""
            INSERT INTO user_requirement (group_id, user_id, status)
            VALUES ($1, $2, 1)
            ON CONFLICT(group_id, user_id) DO UPDATE SET status=1
        """, group_id, user_id)
        return True, None
    else:
        # Yana qancha odam qo‘shishi kerakligini qaytaramiz
        need_number = required_count - added_count
        return False, need_number
