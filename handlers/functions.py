from aiogram.types import Message


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
