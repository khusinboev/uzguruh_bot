import asyncio
from typing import List, Tuple, Optional
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Chat, Message
from config import cur, conn


# database
async def init_db():
    """Initialize database tables"""
    try:
        # Kanal ro'yxati uchun jadval
        cur.execute("""
        CREATE TABLE IF NOT EXISTS channel (
            group_id BIGINT NOT NULL,
            channel_id BIGINT NOT NULL,
            PRIMARY KEY (group_id, channel_id)
        )""")

        # Foydalanuvchi tomonidan qo'shilgan odamlar
        cur.execute("""
        CREATE TABLE IF NOT EXISTS add_members (
            group_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            member BIGINT NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (group_id, member))
            """)

        # Har bir guruh uchun majburiy qo'shish talabi
        cur.execute("""
        CREATE TABLE IF NOT EXISTS group_requirement (
            group_id BIGINT PRIMARY KEY,
            required_count INTEGER NOT NULL)
            """)

        # Foydalanuvchining statusi: talab bajarilganmi yoki yo'q
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_requirement (
            group_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            status BOOLEAN NOT NULL DEFAULT FALSE,
            PRIMARY KEY (group_id, user_id))
            """)

        # Guruhlar jadvali
        cur.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            group_id BIGINT PRIMARY KEY,
            bot_status BOOLEAN NOT NULL DEFAULT TRUE,
            number INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
            """)

        # Foydalanuvchilar jadvali
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status BOOLEAN NOT NULL DEFAULT TRUE)
            """)
        conn.commit()
    except Exception as err:
        print(f"Database initialization error: {err}")
        conn.rollback()
        raise


# -------------------- CHANNEL FUNCTIONS --------------------
async def add_channel(group_id: int, channel_id: int) -> None:
    """Add channel to group's required channels"""
    try:
        cur.execute(
            "INSERT INTO channel (group_id, channel_id) VALUES (%s, %s)",
            (group_id, channel_id)
        )
        conn.commit()
    except Exception as err:
        print(f"add_channel error: {err}")
        conn.rollback()
        raise


async def remove_channel(group_id: int, channel_id: int) -> None:
    """Remove channel from group's required channels"""
    try:
        cur.execute(
            "DELETE FROM channel WHERE group_id = %s AND channel_id = %s",
            (group_id, channel_id)
        )
        conn.commit()
    except Exception as err:
        print(f"remove_channel error: {err}")
        conn.rollback()
        raise


async def get_required_channels(group_id: int) -> List[int]:
    """Get list of required channels for group"""
    try:
        cur.execute(
            "SELECT channel_id FROM channel WHERE group_id = %s",
            (group_id,)
        )
        rows = cur.fetchall()
        return [row[0] for row in rows] if rows else []
    except Exception as err:
        print(f"get_required_channels error: {err}")
        return []


# -------------------- MEMBER FUNCTIONS --------------------
async def add_member(message: Message, member_id: int) -> None:
    """Add member brought by user to database"""
    group_id = message.chat.id
    user_id = message.from_user.id

    try:
        # Check if this combination already exists
        cur.execute("""
            SELECT 1 FROM add_members 
            WHERE group_id = %s AND user_id = %s AND member = %s
        """, (group_id, user_id, member_id))
        exists = cur.fetchone()

        if not exists:
            # Add new member
            cur.execute("""
                INSERT INTO add_members (group_id, user_id, member)
                VALUES (%s, %s, %s)
            """, (group_id, user_id, member_id))

            # Get count of members added by this user
            cur.execute("""
                SELECT COUNT(*) FROM add_members 
                WHERE group_id = %s AND user_id = %s
            """, (group_id, user_id))
            added_count = cur.fetchone()[0]

            # Get required count for group
            cur.execute("""
                SELECT required_count FROM group_requirement 
                WHERE group_id = %s
            """, (group_id,))
            required_row = cur.fetchone()
            required_count = required_row[0] if required_row else 0

            # Update user status if requirement met
            if added_count >= required_count:
                cur.execute("""
                    INSERT INTO user_requirement (group_id, user_id, status)
                    VALUES (%s, %s, TRUE)
                    ON CONFLICT (group_id, user_id)
                    DO UPDATE SET status = EXCLUDED.status
                """, (group_id, user_id))
        conn.commit()
    except Exception as err:
        print(f"add_member error: {err}")
        conn.rollback()
        raise


async def remove_members_by_user(group_id: int, user_id: int) -> None:
    """Remove all members added by specific user"""
    try:
        cur.execute(
            "DELETE FROM add_members WHERE group_id = %s AND user_id = %s",
            (group_id, user_id)
        )
        cur.execute("""
            INSERT INTO user_requirement (group_id, user_id, status)
            VALUES (%s, %s, FALSE)
            ON CONFLICT (group_id, user_id) 
            DO UPDATE SET status = EXCLUDED.status
        """, (group_id, user_id))
        conn.commit()
    except Exception as err:
        print(f"remove_members_by_user error: {err}")
        conn.rollback()
        raise


async def remove_all_members(group_id: int) -> None:
    """Remove all members from group"""
    try:
        cur.execute(
            "DELETE FROM add_members WHERE group_id = %s",
            (group_id,)
        )
        cur.execute(
            "UPDATE user_requirement SET status = FALSE WHERE group_id = %s",
            (group_id,)
        )
        conn.commit()
    except Exception as err:
        print(f"remove_all_members error: {err}")
        conn.rollback()
        raise


async def get_user_status(message: Message) -> bool:
    """Get user requirement status"""
    group_id = message.chat.id
    user_id = message.from_user.id

    try:
        cur.execute("""
            SELECT status FROM user_requirement 
            WHERE group_id = %s AND user_id = %s
        """, (group_id, user_id))
        row = cur.fetchone()
        return bool(row[0]) if row else False
    except Exception as err:
        print(f"get_user_status error: {err}")
        return False


async def update_user_status(message: Message) -> None:
    """Update all users' statuses in group"""
    group_id = message.chat.id

    try:
        # Get required count for group
        cur.execute("""
            SELECT required_count FROM group_requirement WHERE group_id = %s
        """, (group_id,))
        required_row = cur.fetchone()
        if not required_row:
            return
        required_count = required_row[0]

        # Get member counts for all users
        cur.execute("""
            SELECT user_id, COUNT(member) as member_count
            FROM add_members
            WHERE group_id = %s
            GROUP BY user_id
        """, (group_id,))
        user_member_counts = cur.fetchall()

        # Update statuses
        for user_id, member_count in user_member_counts:
            status = member_count >= required_count
            cur.execute("""
                INSERT INTO user_requirement (group_id, user_id, status)
                VALUES (%s, %s, %s)
                ON CONFLICT (group_id, user_id) 
                DO UPDATE SET status = EXCLUDED.status
            """, (group_id, user_id, status))
        conn.commit()
    except Exception as err:
        print(f"update_user_status error: {err}")
        conn.rollback()
        raise


# -------------------- STATISTICS FUNCTIONS --------------------
async def get_top_adders(group_id: int, limit: int = 20) -> List[Tuple[int, int]]:
    """Get top members who added most users"""
    try:
        cur.execute("""
            SELECT user_id, COUNT(*) as total
            FROM add_members
            WHERE group_id = %s
            GROUP BY user_id
            ORDER BY total DESC
            LIMIT %s
        """, (group_id, limit))
        return cur.fetchall()
    except Exception as err:
        print(f"get_top_adders error: {err}")
        return []


async def get_total_by_user(group_id: int, user_id: int) -> int:
    """Get total members added by user"""
    try:
        cur.execute("""
            SELECT COUNT(*) FROM add_members
            WHERE group_id = %s AND user_id = %s
        """, (group_id, user_id))
        row = cur.fetchone()
        return row[0] if row else 0
    except Exception as err:
        print(f"get_total_by_user error: {err}")
        return 0


# -------------------- SUBSCRIPTION CHECK --------------------
async def notify_admins_about_bot_rights(bot: Bot, group_id: int, channel_id: int) -> None:
    """Notify group admins about missing bot admin rights in channel"""
    try:
        admins = await bot.get_chat_administrators(group_id)
        channel: Chat = await bot.get_chat(channel_id)

        for admin in admins:
            user = admin.user
            if user.is_bot:
                continue

            try:
                await bot.send_message(
                    user.id,
                    f"⚠️ Bot <b>{channel.title}</b> kanaliga admin emas.\n\n"
                    f"Iltimos, <a href='https://t.me/{channel.username}'>@{channel.username}</a> "
                    "kanalga botni admin qilib qo'shing.",
                    parse_mode="HTML"
                )
            except Exception as ex:
                print(f"[Error] Couldn't send to {user.id}: {ex}")
    except Exception as e:
        print(f"[Admin fetch error]: {e}")


async def is_user_subscribed_all_channels(message: Message) -> Tuple[bool, List[str]]:
    """Check if user is subscribed to all required channels"""
    bot = message.bot
    user_id = message.from_user.id
    group_id = message.chat.id
    unsubscribed_channels = []

    try:
        channels = await get_required_channels(group_id)
        if not channels:
            return True, []  # No channels required for this group

        for channel_id in channels:
            try:
                member = await bot.get_chat_member(channel_id, user_id)
                if member.status not in {"member", "administrator", "creator"}:
                    channel = await bot.get_chat(channel_id)
                    unsubscribed_channels.append(
                        f"@{channel.username}" if channel.username
                        else channel.title
                    )
            except TelegramBadRequest as e:
                if "user not found" in str(e):
                    continue
                else:
                    await notify_admins_about_bot_rights(bot, group_id, channel_id)
            except Exception as e:
                print(f"[Subscription check error]: {e}")

        return (not unsubscribed_channels), unsubscribed_channels
    except Exception as e:
        print(f"[Channel check error]: {e}")
        return True, []


async def check_user_requirement(message: Message) -> Tuple[bool, Optional[int]]:
    """Check if user meets group requirements"""
    group_id = message.chat.id
    user_id = message.from_user.id

    try:
        # Check if group has requirements
        cur.execute("""
            SELECT required_count FROM group_requirement 
            WHERE group_id = %s
        """, (group_id,))
        required_row = cur.fetchone()
        if not required_row:
            return True, None  # No requirements for this group

        required_count = required_row[0]

        # Check user status
        cur.execute("""
            SELECT status FROM user_requirement 
            WHERE group_id = %s AND user_id = %s
        """, (group_id, user_id))
        status_row = cur.fetchone()
        if status_row and status_row[0]:
            return True, None  # Already met requirements

        # Count members added by user
        cur.execute("""
            SELECT COUNT(*) FROM add_members 
            WHERE group_id = %s AND user_id = %s
        """, (group_id, user_id))
        added_count = cur.fetchone()[0]

        if added_count >= required_count:
            # Update status
            cur.execute("""
                INSERT INTO user_requirement (group_id, user_id, status)
                VALUES (%s, %s, TRUE)
                ON CONFLICT(group_id, user_id) 
                DO UPDATE SET status = TRUE
            """, (group_id, user_id))
            conn.commit()
            return True, None
        else:
            return False, (required_count - added_count)
    except Exception as err:
        print(f"check_user_requirement error: {err}")
        return True, None