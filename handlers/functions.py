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


async def increment_user_comment(group_id: int, user_id: int) -> None:
    """Insert or increment user comment count in group"""
    try:
        cur.execute("""
            INSERT INTO user_comments (group_id, user_id, count)
            VALUES (%s, %s, 1)
            ON CONFLICT (group_id, user_id)
            DO UPDATE SET count = user_comments.count + 1
        """, (group_id, user_id))
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
    except Exception as err:
        print(f"delete_group_comments error: {err}")
        conn.rollback()
        raise


async def get_top_commenters(group_id: int, limit: int = 20) -> List[Tuple[int, int]]:
    """Get top 20 users with the most comments in a group"""
    try:
        cur.execute("""
            SELECT user_id, count
            FROM user_comments
            WHERE group_id = %s
            ORDER BY count DESC
            LIMIT %s
        """, (group_id, limit))
        return cur.fetchall()
    except Exception as err:
        print(f"get_top_commenters error: {err}")
        return []
