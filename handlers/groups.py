import asyncio
import logging
from datetime import timedelta

from aiogram import Router, Bot
from aiogram.enums import ChatType, MessageEntityType
from aiogram.filters import BaseFilter, Command, CommandObject
from aiogram.types import Message, ChatPermissions

from database.cache import get_admins
from database.frombase import add_member, add_channel, remove_channel, \
    remove_members_by_user, remove_all_members, get_total_by_user, get_top_adders, \
    get_required_channels, is_user_subscribed_all_channels, check_user_requirement # bazaga yozuvchi funksiya
from handlers.functions import classify_admin

logger = logging.getLogger(__name__)
group_router = Router()


# === FILTERS ===
class IsGroupMessage(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.chat.type in {ChatType.GROUP, ChatType.SUPERGROUP}


class HasLink(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        if not message.entities:
            return False

        for entity in message.entities:
            if entity.type in [MessageEntityType.URL, MessageEntityType.TEXT_LINK]:
                return True
        return False


class IsJoinOrLeft(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return bool(message.new_chat_members or message.left_chat_member)


# === KIRDI CHIQDI TOZALASH === 90%
@group_router.message(IsGroupMessage(), IsJoinOrLeft())
async def handle_group_join_left(message: Message, bot: Bot):
    if message.new_chat_members:
        for new_member in message.new_chat_members:
            # Agar user o‘zini o‘zi qo‘shmagan bo‘lsa, ya'ni birov qo‘shgan bo‘lsa
            if message.from_user.id != new_member.id:
                await add_member(
                    group_id=message.chat.id,
                    user_id=message.from_user.id,
                    member=new_member.id
                )

    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Xabarni o'chirishda xatolik: {e}")


# === HAVOLALARNI O'CHRISH  ===  100%
@group_router.message(IsGroupMessage(), HasLink())
async def handle_links(message: Message):
    if await classify_admin(message):
        return

    # O'chirish va ogohlantirish
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Xabarni o'chirishda xatolik: {e}")

    user_id = message.from_user.id
    name = message.from_user.full_name 
    await message.answer(
        f'<a href="tg://user?id={user_id}">{name}</a> - siz reklama yubordingiz.',
        parse_mode="HTML"
    )


@group_router.message(Command("start"), IsGroupMessage())
async def handle_get_channel(message: Message, bot: Bot):
            try:
                await message.delete()
            except Exception:
                pass
            

# === info === 89%
@group_router.message(Command("info"), IsGroupMessage())
async def handle_get_channel(message: Message, bot: Bot):
    if await classify_admin(message):
        pass
    else:
        all_ok, missing = await is_user_subscribed_all_channels(message)
        if all_ok:
            pass
        else:
            try:
                await message.delete()
            except Exception:
                pass
            kanal_list = '\n'.join(missing)
            await message.answer(f'<a href="tg://user?id={message.from_user.id}">{message.from_user.full_name}</a> '
                                 f'❗Iltimos, quyidagi kanallarga obuna bo‘ling:\n{kanal_list}',
                                 parse_mode="HTML")
            return
    await message.answer("""🫂Hamma uchun
/top
/replycount
/count

👨‍💻Adminlar uchun
/kanallar
/kanal
/kanald
/cleanuser
/cleangroup""")


# === majburiylar uchun ===

@group_router.message(IsGroupMessage(), F.text.startswith("/majbur"))
async def set_required_add_count(message: Message):
    # Faqat adminlar
    member = await message.chat.get_member(message.from_user.id)
    if not member.is_chat_admin():
        return await message.reply("❌ Bu buyruq faqat administratorlar uchun.")

    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        return await message.reply("❗ Iltimos, to‘g‘ri formatda yuboring: /majbur 3")

    required_count = int(args[1])
    group_id = message.chat.id

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO required_adds (group_id, required_count, active)
            VALUES (?, ?, 1)
            ON CONFLICT(group_id) DO UPDATE SET required_count = ?, active = 1
        """, (group_id, required_count, required_count))
        await db.commit()

    await message.reply(f"✅ Endi foydalanuvchilar {required_count} ta odam qo‘shmaguncha yozolmaydi.")

@group_router.message(IsGroupMessage(), F.text == "/majburoff")
async def disable_required_add_count(message: Message):
    member = await message.chat.get_member(message.from_user.id)
    if not member.is_chat_admin():
        return await message.reply("❌ Bu buyruq faqat administratorlar uchun.")

    group_id = message.chat.id

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO required_adds (group_id, required_count, active)
            VALUES (?, 0, 0)
            ON CONFLICT(group_id) DO UPDATE SET active = 0
        """, (group_id,))
        await db.commit()

    await message.reply("❎ Majburiy odam qo‘shish talabi o‘chirildi.")


# === kanal ro'yxat === 100%
@group_router.message(Command("kanallar"), IsGroupMessage())
async def handle_get_channel(message: Message, command: CommandObject, bot: Bot):
    if not await classify_admin(message):
        try:
            await message.delete()
        except Exception:
            pass
        return
    channels = await get_required_channels(message.chat.id)
    usernames = []
    for i in channels:
        chat = await message.bot.get_chat(i)
        if chat.username:
            usernames.append(f"@{chat.username}")
    if not usernames:
        await message.answer("Hech qanday kanal topilmadi!")
    else:
        await message.answer("Ulangan kanallar:\n"+'\n'.join(usernames))

# === kanal qo'shish === 100%
@group_router.message(Command("kanal"), IsGroupMessage())
async def handle_add_channel(message: Message, command: CommandObject, bot: Bot):
    if not await classify_admin(message):
        try:
            await message.delete()
        except Exception:
            pass
        return

    if not command.args:
        await message.reply("❗ Kanal username-ni kiriting: /kanal @username")
        return

    channel_username = command.args.strip()
    if not channel_username.startswith("@"):
        await message.reply("❗ To‘g‘ri formatda yuboring: @username")
        return

    try:
        channel = await message.bot.get_chat(channel_username)
        await add_channel(message.chat.id, channel.id)
        await message.reply(f"✅ {channel_username} bazaga qo‘shildi.")
    except Exception as e:
        logger.warning(f"Kanalni olishda xatolik: {e}")
        await message.reply("❌ Kanal topilmadi yoki bot kanal admini emas.")

# === kanal ayirish === 100%
@group_router.message(Command("kanald"), IsGroupMessage())
async def handle_remove_channel(message: Message, command: CommandObject, bot: Bot):
    if not await classify_admin(message):
        try:
            await message.delete()
        except Exception:
            pass
        return

    if not command.args:
        await message.reply("❗ Kanal username-ni kiriting: /kanald @username")
        return

    channel_username = command.args.strip()
    if not channel_username.startswith("@"):
        await message.reply("❗ To‘g‘ri formatda yuboring: @username")
        return

    try:
        channel = await message.bot.get_chat(channel_username)
        await remove_channel(message.chat.id, channel.id)
        await message.reply(f"🗑️ {channel_username} ushbu guruhdan o‘chirildi.")
    except Exception as e:
        logger.warning(f"Kanalni olishda xatolik: {e}")
        await message.reply("❌ Kanal topilmadi yoki bot kanalga kira olmayapti.")

# === clean by user === 100%
@group_router.message(Command("cleanuser"), IsGroupMessage())
async def handle_clean_user(message: Message, bot: Bot):
    if not await classify_admin(message):
        try:
            await message.delete()
        except Exception:
            pass
        return

    if not message.reply_to_message:
        await message.reply("❗ Bu komanda reply shaklida yuborilishi kerak.")
        return

    target_user = message.reply_to_message.from_user
    await remove_members_by_user(message.chat.id, target_user.id)
    await message.reply(f"🧹 {target_user.full_name} (ID: <code>{target_user.id}</code>) tomonidan qo‘shilganlar o‘chirildi.", parse_mode="HTML")

# === clean all === 100%
@group_router.message(Command("cleangroup"), IsGroupMessage())
async def handle_clean_group(message: Message):
    if not await classify_admin(message):
        try:
            await message.delete()
        except Exception:
            pass
        return

    await remove_all_members(message.chat.id)
    await message.reply("🧨 Guruhdagi barcha foydalanuvchilarning qo‘shganlari o‘chirildi.")

# === count by user === 89%
@group_router.message(Command("count"), IsGroupMessage())
async def handle_my_count(message: Message, bot: Bot):
    if await classify_admin(message):
        pass
    else:
        all_ok, missing = await is_user_subscribed_all_channels(message)
        if all_ok:
            pass
        else:
            try:
                await message.delete()
            except Exception:
                pass
            kanal_list = '\n'.join(missing)
            await message.answer(f'<a href="tg://user?id={message.from_user.id}">{message.from_user.full_name}</a> '
                                 f'❗Iltimos, quyidagi kanallarga obuna bo‘ling:\n{kanal_list}',
                                 parse_mode="HTML")
            return
    total = await get_total_by_user(message.chat.id, message.from_user.id)
    await message.reply(
        f"📊 Siz ushbu guruhga {total} ta foydalanuvchini qo‘shgansiz."
    )

# === count by other user === 89%
@group_router.message(Command("replycount"), IsGroupMessage())
async def handle_reply_count(message: Message, bot: Bot):
    if await classify_admin(message):
        pass
    else:
        all_ok, missing = await is_user_subscribed_all_channels(message)
        if all_ok:
            pass
        else:
            try:
                await message.delete()
            except Exception:
                pass
            kanal_list = '\n'.join(missing)
            await message.answer(f'<a href="tg://user?id={message.from_user.id}">{message.from_user.full_name}</a> '
                                 f'❗Iltimos, quyidagi kanallarga obuna bo‘ling:\n{kanal_list}',
                                 parse_mode="HTML")
            return

    if not message.reply_to_message:
        try: await message.reply("❗ Bu komanda faqat reply shaklida ishlaydi.")
        except: await message.answer("❗ Bu komanda faqat reply shaklida ishlaydi.")
        return

    replied_user = message.reply_to_message.from_user
    total = await get_total_by_user(message.chat.id, replied_user.id)

    await message.reply(
        f"👤 {replied_user.full_name} (ID: <code>{replied_user.id}</code>) ushbu guruhga {total} ta foydalanuvchini qo‘shgan.",
        parse_mode="HTML"
    )

# === top === 89%
@group_router.message(Command("top"), IsGroupMessage())
async def handle_top(message: Message, bot: Bot):
    if await classify_admin(message):
        pass
    else:
        all_ok, missing = await is_user_subscribed_all_channels(message)
        if all_ok:
            pass
        else:
            try:
                await message.delete()
            except Exception:
                pass
            kanal_list = '\n'.join(missing)
            await message.answer(f'<a href="tg://user?id={message.from_user.id}">{message.from_user.full_name}</a> '
                                 f'❗Iltimos, quyidagi kanallarga obuna bo‘ling:\n{kanal_list}',
                                 parse_mode="HTML")
            return

    top_users = await get_top_adders(message.chat.id, limit=20)

    if not top_users:
        await message.reply("📉 Hali hech kim foydalanuvchi qo‘shmagan.")
        return

    text = "🏆 <b>Eng ko‘p foydalanuvchi qo‘shganlar:</b>\n\n"
    for i, (user_id, count) in enumerate(top_users, start=1):
        name = message.from_user.full_name
        mention = f'<a href="tg://user?id={user_id}">{name}</a>'
        text += f"{i}. {mention} — {count} ta\n"

    await message.reply(text, parse_mode="HTML")


# === check channel subscription === 78%


@group_router.message(IsGroupMessage()) async def check_user_access(message: Message, bot: Bot): user = message.from_user chat_id = message.chat.id user_id = user.id

# Adminlar tekshirilmaydi
if await classify_admin(message):
    return

# Kanalga obuna tekshiruvi
all_ok, missing_channels = await is_user_subscribed_all_channels(message)

# Odam qo'shish tekshiruvi
is_ok, need_number = await check_user_requirement(message)

if all_ok and is_ok:
    return

try:
    await message.delete()
except Exception:
    pass

# Ogohlantirish matnini shakllantirish
warn_text = f'<a href="tg://user?id={user_id}">{user.full_name}</a>❗'
if not all_ok:
    kanal_list = '\n'.join(missing_channels)
    warn_text += f'Quyidagi kanallarga obuna bo‘ling:\n{kanal_list}\n'
if not is_ok:
    warn_text += f'Guruhda yozish uchun yana {need_number} ta odamni qo‘shishingiz kerak!'

# Ogohlantirish xabari
warn_msg = await message.answer(warn_text, parse_mode="HTML")

# Yozishni 10 soniyaga cheklash
try:
    until_timestamp = int((message.date + timedelta(seconds=10)).timestamp())
    await bot.restrict_chat_member(
        chat_id,
        user_id,
        permissions=ChatPermissions(can_send_messages=False),
        until_date=until_timestamp
    )
except Exception:
    pass

# 10 soniyadan so‘ng tiklash
await asyncio.sleep(10)

try:
    if warn_msg:
        await bot.delete_message(chat_id, warn_msg.message_id)
except Exception:
    pass

try:
    await bot.restrict_chat_member(
        chat_id,
        user_id,
        permissions=ChatPermissions(can_send_messages=True)
    )
except Exception:
    pass

