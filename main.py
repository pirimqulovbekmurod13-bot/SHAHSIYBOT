import asyncio
import logging
import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardMarkup, KeyboardButton, CallbackQuery
)

BOT_TOKEN = "8828504975:AAHBA8yMnuAHEA1XMsDBxYz1Vu6ptaZDDNE"
SUPER_ADMIN_ID = 8520817573  # Asosiy egasi ID'si

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- FSM (Shtatlar) ---
class AnimeSearch(StatesGroup):
    waiting_for_code = State()

class AnimeAdd(StatesGroup):
    title = State()
    genre = State()
    year = State()
    photo = State()
    episodes_count = State()

class EpisodeAdd(StatesGroup):
    anime_code = State()
    ep_num = State()
    video = State()

class SettingsEdit(StatesGroup):
    admin_link = State()
    channel_link = State()

class AdminManage(StatesGroup):
    add_admin = State()

class ChannelManage(StatesGroup):
    add_channel_id = State()
    add_channel_link = State()

class AnimeEdit(StatesGroup):
    select_code = State()
    choose_field = State()
    new_value = State()

# --- Ma'lumotlar Bazasi ---
async def init_db():
    async with aiosqlite.connect("anime_bot.db") as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
        await db.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS animes (
                code INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                genre TEXT,
                year TEXT,
                photo_id TEXT,
                total_episodes TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anime_code INTEGER,
                ep_num INTEGER,
                video_id TEXT
            )
        """)
        await db.execute("CREATE TABLE IF NOT EXISTS channels (channel_id TEXT PRIMARY KEY, invite_link TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        
        await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (SUPER_ADMIN_ID,))
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('admin_link', 'https://t.me/telegram')")
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('channel_link', 'https://t.me/telegram')")
        await db.commit()

async def is_admin(user_id: int) -> bool:
    async with aiosqlite.connect("anime_bot.db") as db:
        async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
            return bool(await cursor.fetchone())

# --- Majburiy Obuna Tekshiruvi ---
async def check_sub(user_id: int) -> tuple[bool, list]:
    async with aiosqlite.connect("anime_bot.db") as db:
        async with db.execute("SELECT channel_id, invite_link FROM channels") as cursor:
            channels = await cursor.fetchall()
            
    unsubbed = []
    for ch_id, invite_link in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status in ["left", "kicked"]:
                unsubbed.append((ch_id, invite_link))
        except Exception:
            unsubbed.append((ch_id, invite_link))
    
    return (len(unsubbed) == 0, unsubbed)

# --- Klaviaturalar ---
def main_kb(is_adm: bool):
    kb = [
        [KeyboardButton(text="🔍 Anime qidirish"), KeyboardButton(text="🎬 Barcha animelar")],
        [KeyboardButton(text="❓ Help"), KeyboardButton(text="📊 Statistika")]
    ]
    if is_adm:
        kb.append([KeyboardButton(text="⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yangi Anime qo'shish", callback_data="add_anime"),
         InlineKeyboardButton(text="📹 Qism qo'shish", callback_data="add_ep")],
        [InlineKeyboardButton(text="✏️ Animeni tahrirlash", callback_data="edit_anime"),
         InlineKeyboardButton(text="📢 Kanalga Post chiqarish", callback_data="post_channel")],
        [InlineKeyboardButton(text="👑 Adminlar boshqaruvi", callback_data="manage_admins"),
         InlineKeyboardButton(text="📢 Majburiy obuna", callback_data="manage_sub")],
        [InlineKeyboardButton(text="🔗 Help havolalarini o'zgartirish", callback_data="change_links")]
    ])

# --- Obunachilar Menyusi ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    async with aiosqlite.connect("anime_bot.db") as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
        await db.commit()
    
    adm = await is_admin(message.from_user.id)
    await message.answer("Xush kelibsiz! Anime ko'rish uchun menyudan foydalaning.", reply_markup=main_kb(adm))

@dp.message(F.text == "❓ Help")
async def help_cmd(message: types.Message):
    async with aiosqlite.connect("anime_bot.db") as db:
        async with db.execute("SELECT value FROM settings WHERE key='admin_link'") as c1:
            adm_l = (await c1.fetchone())[0]
        async with db.execute("SELECT value FROM settings WHERE key='channel_link'") as c2:
            ch_l = (await c2.fetchone())[0]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍💻 Asosiy Admin", url=adm_l)],
        [InlineKeyboardButton(text="📢 Rasmiy Kanal", url=ch_l)]
    ])
    await message.answer("Yordam va rasmiy sahifalarimiz:", reply_markup=kb)

@dp.message(F.text == "🎬 Barcha animelar")
async def all_animes(message: types.Message):
    async with aiosqlite.connect("anime_bot.db") as db:
        async with db.execute("SELECT code, title, year FROM animes") as cursor:
            animes = await cursor.fetchall()
            
    if not animes:
        return await message.answer("Hozircha animelar yo'q.")
        
    text = "📋 **Barcha animelar ro'yxati:**\n\n"
    for code, title, year in animes:
        text += f"🔑 **Kodi: `{code}`** | {title} ({year})\n"
    
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "📊 Statistika")
async def stats(message: types.Message):
    async with aiosqlite.connect("anime_bot.db") as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c1:
            u_cnt = (await c1.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM animes") as c2:
            a_cnt = (await c2.fetchone())[0]
            
    await message.answer(f"📊 **Bot Statistikasi:**\n\n👥 Foydalanuvchilar: {u_cnt}\n🎬 Animelar: {a_cnt}", parse_mode="Markdown")

# --- 1. QIDIRUV BO'LIMI ---
@dp.message(F.text == "🔍 Anime qidirish")
async def start_search(message: types.Message, state: FSMContext):
    is_sub, unsubbed = await check_sub(message.from_user.id)
    if not is_sub:
        btns = [[InlineKeyboardButton(text="📢 Kanalga o'tish", url=link)] for _, link in unsubbed]
        btns.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub_cb")])
        return await message.answer("❌ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

    await message.answer("🔑 Iltimos, anime kodini kiriting:")
    await state.set_state(AnimeSearch.waiting_for_code)

@dp.callback_query(F.data == "check_sub_cb")
async def check_sub_callback(call: CallbackQuery):
    is_sub, _ = await check_sub(call.from_user.id)
    if is_sub:
        await call.message.delete()
        await call.message.answer("✅ Obuna tekshirildi! Endi 🔍 Anime qidirish tugmasini bosishingiz mumkin.")
    else:
        await call.answer("❌ Hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)

@dp.message(AnimeSearch.waiting_for_code)
async def process_search_code(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Iltimos, faqat raqam ko'rinishidagi kodni kiriting.")
        return

    code = int(message.text)
    async with aiosqlite.connect("anime_bot.db") as db:
        async with db.execute("SELECT title, genre, year, photo_id, total_episodes FROM animes WHERE code=?", (code,)) as c:
            anime = await c.fetchone()
            
        if not anime:
            await message.answer("❌ Bu kod bo'yicha anime topilmadi.")
            await state.clear()
            return
            
        title, genre, year, photo_id, total_ep = anime
        async with db.execute("SELECT ep_num FROM episodes WHERE anime_code=?", (code,)) as c2:
            episodes = await c2.fetchall()

    caption = f"🎬 **{title}**\n\n🎭 Janri: {genre}\n📅 Yili: {year}\n🎞 Qismlar soni: {total_ep}\n🔑 Kodi: `{code}`"
    
    buttons = []
    row = []
    for (ep_num,) in episodes:
        row.append(InlineKeyboardButton(text=f"{ep_num}-qism", callback_data=f"get_ep_{code}_{ep_num}"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer_photo(photo=photo_id, caption=caption, reply_markup=kb, parse_mode="Markdown")
    await state.clear()

@dp.callback_query(F.data.startswith("get_ep_"))
async def send_episode(call: CallbackQuery):
    _, _, code, ep_num = call.data.split("_")
    async with aiosqlite.connect("anime_bot.db") as db:
        async with db.execute("SELECT video_id FROM episodes WHERE anime_code=? AND ep_num=?", (code, ep_num)) as c:
            ep = await c.fetchone()
            
    if ep:
        await call.message.answer_video(video=ep[0], caption=f"🎬 Anime kodi: {code} | {ep_num}-qism")
    else:
        await call.answer("Qism topilmadi!", show_alert=True)
    await call.answer()

# --- ADMIN PANEL ---
@dp.message(F.text == "⚙️ Admin Panel")
async def admin_panel(message: types.Message):
    if await is_admin(message.from_user.id):
        await message.answer("⚙️ Admin panel interfeysi:", reply_markup=admin_kb())

# --- 2. MAJBURIY OBUNA BOSHQARUVI ---
@dp.callback_query(F.data == "manage_sub")
async def manage_sub(call: CallbackQuery):
    async with aiosqlite.connect("anime_bot.db") as db:
        async with db.execute("SELECT channel_id, invite_link FROM channels") as c:
            channels = await c.fetchall()

    text = f"📢 **Majburiy obuna kanallari ({len(channels)} ta):**\n\n"
    btns = []
    for ch_id, link in channels:
        text += f"🔹 `{ch_id}` - [Kanal havolasi]({link})\n"
        btns.append([InlineKeyboardButton(text=f"❌ O'chirish: {ch_id}", callback_data=f"del_ch_{ch_id}")])

    btns.append([InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_channel")])
    await call.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns), parse_mode="Markdown", disable_web_page_preview=True)
    await call.answer()

@dp.callback_query(F.data == "add_channel")
async def add_channel_start(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Kanal ID'sini kiriting (masalan: `-100123456789`):\n*Eslatma: Bot kanalda administrator bo'lishi kerak!*")
    await state.set_state(ChannelManage.add_channel_id)
    await call.answer()

@dp.message(ChannelManage.add_channel_id)
async def process_ch_id(message: types.Message, state: FSMContext):
    await state.update_data(ch_id=message.text.strip())
    await message.answer("Kanalga kirish havolasini (link) kiriting:")
    await state.set_state(ChannelManage.add_channel_link)

@dp.message(ChannelManage.add_channel_link)
async def process_ch_link(message: types.Message, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect("anime_bot.db") as db:
        await db.execute("INSERT OR REPLACE INTO channels (channel_id, invite_link) VALUES (?, ?)", (data['ch_id'], message.text.strip()))
        await db.commit()
    await message.answer("✅ Kanal majburiy obunaga muvaffaqiyatli qo'shildi!")
    await state.clear()

@dp.callback_query(F.data.startswith("del_ch_"))
async def del_channel(call: CallbackQuery):
    ch_id = call.data.replace("del_ch_", "")
    async with aiosqlite.connect("anime_bot.db") as db:
        await db.execute("DELETE FROM channels WHERE channel_id=?", (ch_id,))
        await db.commit()
    await call.message.answer(f"✅ Kanal `{ch_id}` majburiy obunadan olib tashlandi!")
    await call.answer()

# --- 3. ANIME TAHRIRLASH BO'LIMI ---
@dp.callback_query(F.data == "edit_anime")
async def edit_anime_start(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Tahrirlamoqchi bo'lgan anime KODINI kiriting:")
    await state.set_state(AnimeEdit.select_code)
    await call.answer()

@dp.message(AnimeEdit.select_code)
async def edit_anime_select(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("⚠️ Iltimos, faqat raqamli kod kiriting.")

    code = int(message.text)
    async with aiosqlite.connect("anime_bot.db") as db:
        async with db.execute("SELECT title, genre, year, total_episodes FROM animes WHERE code=?", (code,)) as c:
            anime = await c.fetchone()

    if not anime:
        await message.answer("❌ Bu kod bo'yicha anime topilmadi.")
        return await state.clear()

    await state.update_data(edit_code=code)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Nomi", callback_data="field_title"), InlineKeyboardButton(text="Janri", callback_data="field_genre")],
        [InlineKeyboardButton(text="Yili", callback_data="field_year"), InlineKeyboardButton(text="Qismlar soni", callback_data="field_total_episodes")]
    ])
    await message.answer(f"🎬 **{anime[0]}**\nQaysi ma'lumotni o'zgartirmoqchisiz?", reply_markup=kb, parse_mode="Markdown")
    await state.set_state(AnimeEdit.choose_field)

@dp.callback_query(AnimeEdit.choose_field, F.data.startswith("field_"))
async def edit_choose_field(call: CallbackQuery, state: FSMContext):
    field = call.data.replace("field_", "")
    await state.update_data(field=field)
    await call.message.answer(f"Yangi qiymatni kiriting ({field}):")
    await state.set_state(AnimeEdit.new_value)
    await call.answer()

@dp.message(AnimeEdit.new_value)
async def edit_save_value(message: types.Message, state: FSMContext):
    data = await state.get_data()
    code = data['edit_code']
    field = data['field']
    new_val = message.text

    async with aiosqlite.connect("anime_bot.db") as db:
        await db.execute(f"UPDATE animes SET {field}=? WHERE code=?", (new_val, code))
        await db.commit()

    await message.answer(f"✅ Anime kodi `{code}` uchun `{field}` muvaffaqiyatli o'zgartirildi!", parse_mode="Markdown")
    await state.clear()

# --- BOSHQA ADMIN BO'LIMLARI ---
@dp.callback_query(F.data == "add_anime")
async def start_add_anime(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Anime nomini kiriting:")
    await state.set_state(AnimeAdd.title)
    await call.answer()

@dp.message(AnimeAdd.title)
async def process_a_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("Animening janrlarini kiriting:")
    await state.set_state(AnimeAdd.genre)

@dp.message(AnimeAdd.genre)
async def process_a_genre(message: types.Message, state: FSMContext):
    await state.update_data(genre=message.text)
    await message.answer("Chiqarilgan yilini kiriting (masalan: 2024):")
    await state.set_state(AnimeAdd.year)

@dp.message(AnimeAdd.year)
async def process_a_year(message: types.Message, state: FSMContext):
    await state.update_data(year=message.text)
    await message.answer("Jami nechta qismdan iboratligini kiriting:")
    await state.set_state(AnimeAdd.episodes_count)

@dp.message(AnimeAdd.episodes_count)
async def process_a_ep_count(message: types.Message, state: FSMContext):
    await state.update_data(total_episodes=message.text)
    await message.answer("Anime rasmini yuboring:")
    await state.set_state(AnimeAdd.photo)

@dp.message(AnimeAdd.photo, F.photo)
async def process_a_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photo_id = message.photo[-1].file_id
    
    async with aiosqlite.connect("anime_bot.db") as db:
        cursor = await db.execute(
            "INSERT INTO animes (title, genre, year, photo_id, total_episodes) VALUES (?, ?, ?, ?, ?)",
            (data['title'], data['genre'], data['year'], photo_id, data['total_episodes'])
        )
        anime_code = cursor.lastrowid
        await db.commit()
        
    await message.answer(f"✅ Anime saqlandi!\n🔑 Tayinlangan kod: `{anime_code}`", parse_mode="Markdown")
    await state.clear()

@dp.callback_query(F.data == "add_ep")
async def start_add_ep(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Qism qo'shmoqchi bo'lgan anime kodini kiriting:")
    await state.set_state(EpisodeAdd.anime_code)
    await call.answer()

@dp.message(EpisodeAdd.anime_code)
async def process_ep_code(message: types.Message, state: FSMContext):
    await state.update_data(anime_code=int(message.text))
    await message.answer("Nechanchi qismligini raqamda kiriting:")
    await state.set_state(EpisodeAdd.ep_num)

@dp.message(EpisodeAdd.ep_num)
async def process_ep_num(message: types.Message, state: FSMContext):
    await state.update_data(ep_num=int(message.text))
    await message.answer("Qism videosini yuboring:")
    await state.set_state(EpisodeAdd.video)

@dp.message(EpisodeAdd.video, F.video)
async def process_ep_video(message: types.Message, state: FSMContext):
    data = await state.get_data()
    video_id = message.video.file_id
    
    async with aiosqlite.connect("anime_bot.db") as db:
        await db.execute(
            "INSERT INTO episodes (anime_code, ep_num, video_id) VALUES (?, ?, ?)",
            (data['anime_code'], data['ep_num'], video_id)
        )
        await db.commit()
        
    await message.answer(f"✅ Anime kodi `{data['anime_code']}` uchun {data['ep_num']}-qism saqlandi!")
    await state.clear()

@dp.callback_query(F.data == "change_links")
async def change_links(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Yangi Admin Telegram linkini kiriting:")
    await state.set_state(SettingsEdit.admin_link)
    await call.answer()

@dp.message(SettingsEdit.admin_link)
async def set_adm_link(message: types.Message, state: FSMContext):
    await state.update_data(admin_link=message.text)
    await message.answer("Yangi Rasmiy Kanal linkini kiriting:")
    await state.set_state(SettingsEdit.channel_link)

@dp.message(SettingsEdit.channel_link)
async def set_ch_link(message: types.Message, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect("anime_bot.db") as db:
        await db.execute("UPDATE settings SET value=? WHERE key='admin_link'", (data['admin_link'],))
        await db.execute("UPDATE settings SET value=? WHERE key='channel_link'", (message.text,))
        await db.commit()
    await message.answer("✅ Help havolalari muvaffaqiyatli o'zgartirildi!")
    await state.clear()

@dp.callback_query(F.data == "manage_admins")
async def manage_admins(call: CallbackQuery):
    async with aiosqlite.connect("anime_bot.db") as db:
        async with db.execute("SELECT user_id FROM admins") as c:
            adms = await c.fetchall()
            
    text = "👑 **Adminlar ro'yxati:**\n" + "\n".join([f"- `{a[0]}`" for a in adms])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Admin qo'shish ID orqali", callback_data="add_admin_id")]
    ])
    await call.message.answer(text, reply_markup=kb, parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data == "add_admin_id")
async def add_admin_cmd(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Yangi admin Telegram Numeric ID'sini yuboring:")
    await state.set_state(AdminManage.add_admin)
    await call.answer()

@dp.message(AdminManage.add_admin)
async def process_add_admin(message: types.Message, state: FSMContext):
    new_id = int(message.text)
    async with aiosqlite.connect("anime_bot.db") as db:
        await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (new_id,))
        await db.commit()
    await message.answer(f"✅ User ID `{new_id}` admin qilib belgilandi!")
    await state.clear()

async def main():
    logging.basicConfig(level=logging.INFO)
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())