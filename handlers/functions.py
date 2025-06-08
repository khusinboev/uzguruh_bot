from aiogram.types import Message

from config import cur, conn


async def classify_admin(msg: Message):
    if msg.sender_chat and msg.sender_chat.type == "channel" and msg.is_automatic_forward:
        return True

    elif msg.sender_chat and msg.sender_chat.type in ["group", "supergroup"]:
        return True

    elif msg.from_user and msg.from_user.is_bot:
        member = await msg.bot.get_chat_member(msg.chat.id, msg.from_user.id)
        if member.status in ["administrator", "creator"]:
            return True

    elif msg.from_user:
        member = await msg.bot.get_chat_member(msg.chat.id, msg.from_user.id)
        if member.status in ["administrator", "creator"]:
            return True
    return False


async def increment_user_comment(group_id: int, user_id: int, message_id: int, message_text: str = "") -> None:
    """Insert or update comment count and total length for user"""
    text_length = len(message_text.strip()) if message_text else 0

    try:
        cur.execute("""
            INSERT INTO user_comments (group_id, user_id, count, lengths)
            VALUES (%s, %s, 1, %s)
            ON CONFLICT (group_id, user_id)
            DO UPDATE SET 
                count = user_comments.count + 1,
                lengths = user_comments.lengths + EXCLUDED.lengths
        """, (group_id, user_id, text_length))
        conn.commit()

        cur.execute("""
            INSERT INTO comment_messages (group_id, user_id, message_id, length)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (group_id, user_id) DO NOTHING
            """, (group_id, user_id, message_id, text_length))
        conn.commit()
    except Exception as err:
        print(f"increment_user_comment error: {err}")
        conn.rollback()
        raise


async def delete_group_comments(group_id: int) -> None:
    """Delete all comment counts for a specific group"""
    try:
        cur.execute(
            "DELETE FROM user_comments WHERE group_id = %s",
            (group_id,)
        )
        conn.commit()

        cur.execute(
            "DELETE FROM comment_messages WHERE group_id = %s",
            (group_id,)
        )
        conn.commit()
    except Exception as err:
        print(f"delete_group_comments error: {err}")
        conn.rollback()
        raise


async def get_top_commenters(group_id: int, limit: int = 20):
    """
    Get top commenters with their comment count and average length
    Returns: List of tuples (user_id, count, average_length)
    """
    try:
        cur.execute("""
            SELECT user_id, count, 
                   CASE WHEN count > 0 THEN ROUND(lengths::decimal / count, 1) ELSE 0 END as avg_length
            FROM user_comments
            WHERE group_id = %s
            ORDER BY count DESC
            LIMIT %s
        """, (group_id, limit))
        return cur.fetchall()
    except Exception as err:
        print(f"get_top_commenters error: {err}")
        return []