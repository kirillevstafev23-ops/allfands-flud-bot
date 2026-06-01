import os
import asyncio
import sqlite3
import logging
import time
from datetime import datetime
from contextlib import closing

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

# ---------------- CONFIG ----------------

TOKEN = os.getenv("TOKEN")

ADMINS = [1739947062, 5655991466]

INFO_CHANNEL = "https://t.me/+rFs7nnx639BmNzgy"
FLUD_LINK = "https://t.me/+zTukwrwrgxOGUy"

# ---------------- LOGGING ----------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher(storage=MemoryStorage())

# ---------------- ANTI-SPAM ----------------

user_last_time = {}
SPAM_DELAY = 15  # секунд между действиями

def anti_spam(user_id: int) -> bool:
    now = time.time()
    last = user_last_time.get(user_id, 0)

    if now - last < SPAM_DELAY:
        return True

    user_last_time[user_id] = now
    return False

# ---------------- DB ----------------

def db():
    return sqlite3.connect("bot.db", check_same_thread=False)

def init_db():
    with closing(db()) as conn:
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            role TEXT,
            fandom TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS applications(
            user_id INTEGER PRIMARY KEY,
            status TEXT DEFAULT 'pending'
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            admin_id INTEGER,
            action TEXT,
            created_at TEXT
        )
        """)

        conn.commit()

def now():
    return datetime.now().strftime("%d.%m.%Y %H:%M")

def save_user(user_id, username):
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute("""
        INSERT OR IGNORE INTO users(user_id, username, created_at)
        VALUES (?, ?, ?)
        """, (user_id, username, now()))
        conn.commit()

def update_profile(user_id, role, fandom):
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute("""
        UPDATE users SET role=?, fandom=?, status='pending'
        WHERE user_id=?
        """, (role, fandom, user_id))
        conn.commit()

def get_status(user_id):
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT status FROM users WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        return row[0] if row else None

def set_status(user_id, status):
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET status=? WHERE user_id=?", (status, user_id))
        conn.commit()

def log(user_id, admin_id, action):
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO logs(user_id, admin_id, action, created_at)
        VALUES (?, ?, ?, ?)
        """, (user_id, admin_id, action, now()))
        conn.commit()

# ---------------- FSM ----------------

class Form(StatesGroup):
    question = State()
    role = State()
    fandom = State()

# ---------------- UI ----------------

def start_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Инфо-канал", url=INFO_CHANNEL)],
        [InlineKeyboardButton(text="🚀 Начать анкету", callback_data="start_form")]
    ])

def admin_kb(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"accept:{user_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{user_id}")
        ],
        [InlineKeyboardButton(text="🚫 Бан", callback_data=f"ban:{user_id}")]
    ])

# ---------------- START ----------------

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):

    if anti_spam(message.from_user.id):
        await message.answer("⏳ Не спамь")
        return

    save_user(
        message.from_user.id,
        f"@{message.from_user.username}" if message.from_user.username else "no_username"
    )

    if get_status(message.from_user.id) == "banned":
        await message.answer("🚫 Вы заблокированы.")
        return

    await state.clear()

    text = (
        "✨ <b>Добро пожаловать</b>\n\n"
        "━━━━━━━━━━━━━━\n"
        "📌 Здесь ты можешь подать заявку\n"
        "━━━━━━━━━━━━━━"
    )

    await message.answer(text, reply_markup=start_kb())

# ---------------- FLOW ----------------

@dp.callback_query(F.data == "start_form")
async def start_form(call: CallbackQuery, state: FSMContext):

    if anti_spam(call.from_user.id):
        await call.answer("⏳ Подожди")
        return

    await state.set_state(Form.question)
    await call.message.answer("❓ Сколько длится рест?")
    await call.answer()


@dp.message(Form.question)
async def q(message: Message, state: FSMContext):

    if message.text.lower().strip() != "3 недели":
        await message.answer("🚫 Неверно")
        return

    await state.set_state(Form.role)
    await message.answer("🎭 Ваша роль?")


@dp.message(Form.role)
async def role(message: Message, state: FSMContext):
    await state.update_data(role=message.text)
    await state.set_state(Form.fandom)
    await message.answer("🌍 Ваш фандом?")


@dp.message(Form.fandom)
async def fandom(message: Message, state: FSMContext):

    if anti_spam(message.from_user.id):
        await message.answer("⏳ Подожди")
        return

    data = await state.get_data()

    role = data["role"]
    fandom = message.text

    if get_status(message.from_user.id) == "pending":
        await message.answer("⚠️ Заявка уже отправлена")
        return

    update_profile(message.from_user.id, role, fandom)
    set_status(message.from_user.id, "pending")

    username = f"@{message.from_user.username}" if message.from_user.username else "no_username"

    text = (
        "📨 <b>НОВАЯ ЗАЯВКА</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"👤 {username}\n"
        f"🆔 {message.from_user.id}\n"
        f"🎭 {role}\n"
        f"🌍 {fandom}\n"
        f"🕰 {now()}\n"
        "━━━━━━━━━━━━━━"
    )

    for admin in ADMINS:
        await bot.send_message(admin, text, reply_markup=admin_kb(message.from_user.id))

    await message.answer("✅ Заявка отправлена")
    await state.clear()

# ---------------- ADMIN ----------------

def is_admin(user_id: int):
    return user_id in ADMINS

@dp.callback_query(F.data.startswith("accept:"))
async def accept(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return

    user_id = int(call.data.split(":")[1])

    if get_status(user_id) != "pending":
        await call.answer("Уже обработано")
        return

    set_status(user_id, "accepted")
    log(user_id, call.from_user.id, "accept")

    await bot.send_message(
        user_id,
        f"✨ <b>Заявка одобрена</b>\n\n{FLUD_LINK}"
    )

    await call.message.edit_text("✅ ПРИНЯТО")
    await call.answer()


@dp.callback_query(F.data.startswith("reject:"))
async def reject(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return

    user_id = int(call.data.split(":")[1])

    set_status(user_id, "rejected")
    log(user_id, call.from_user.id, "reject")

    await bot.send_message(user_id, "❌ Заявка отклонена")

    await call.message.edit_text("❌ ОТКЛОНЕНО")
    await call.answer()


@dp.callback_query(F.data.startswith("ban:"))
async def ban(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return

    user_id = int(call.data.split(":")[1])

    set_status(user_id, "banned")
    log(user_id, call.from_user.id, "ban")

    await bot.send_message(user_id, "🚫 Вы забанены")

    await call.message.edit_text("🚫 БАН")
    await call.answer()

# ---------------- MAIN ----------------

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
