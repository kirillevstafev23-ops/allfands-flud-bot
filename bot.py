import os
import asyncio
import sqlite3
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
FLUD_LINK = "https://t.me/+zTukwrwrqlgxOGUy"

# ---------------- BOT ----------------

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher(storage=MemoryStorage())

# ---------------- ANTI SPAM (light) ----------------

last_action = {}
SPAM_DELAY = 8

def is_spam(user_id: int):
    now = time.time()
    if now - last_action.get(user_id, 0) < SPAM_DELAY:
        return True
    last_action[user_id] = now
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
            status TEXT DEFAULT 'new',
            created_at TEXT
        )
        """)

        conn.commit()

def now():
    return datetime.now().strftime("%d.%m.%Y %H:%M")

def save_user(uid, username):
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute("""
        INSERT OR IGNORE INTO users(user_id, username, created_at)
        VALUES (?, ?, ?)
        """, (uid, username, now()))
        conn.commit()

def get_status(uid):
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT status FROM users WHERE user_id=?", (uid,))
        row = cur.fetchone()
        return row[0] if row else None

def set_status(uid, status):
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET status=? WHERE user_id=?", (status, uid))
        conn.commit()

def update_profile(uid, role, fandom):
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute("""
        UPDATE users
        SET role=?, fandom=?, status='pending'
        WHERE user_id=?
        """, (role, fandom, uid))
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
        [InlineKeyboardButton(text="🚀 Начать", callback_data="start_form")]
    ])

def admin_kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("✅ Принять", callback_data=f"accept:{uid}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject:{uid}")
        ],
        [InlineKeyboardButton("🚫 Бан", callback_data=f"ban:{uid}")]
    ])

# ---------------- START ----------------

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):

    if is_spam(message.from_user.id):
        await message.answer("⏳ Слишком часто. Подождите.")
        return

    save_user(
        message.from_user.id,
        f"@{message.from_user.username}" if message.from_user.username else "no_username"
    )

    if get_status(message.from_user.id) == "banned":
        await message.answer("🚫 Доступ запрещён.")
        return

    await state.clear()

    text = (
        "🌙 <b>Добро пожаловать</b>\n\n"
        "━━━━━━━━━━━━━━\n"
        "✨ Это анкета для вступления во флуд-сообщество\n"
        "📌 Перед началом ознакомься с информацией\n"
        "━━━━━━━━━━━━━━\n\n"
        "👇 Нажми кнопку ниже"
    )

    await message.answer(text, reply_markup=start_kb())

# ---------------- STEP 1 ----------------

@dp.callback_query(F.data == "start_form")
async def start_form(call: CallbackQuery, state: FSMContext):

    if is_spam(call.from_user.id):
        await call.answer("⏳ Подождите")
        return

    await state.set_state(Form.question)

    await call.message.answer(
        "🧠 <b>Проверка</b>\n\n"
        "Сколько длится рест?\n\n"
        "✍️ Ответ одним сообщением"
    )

    await call.answer()

# ---------------- STEP 2 ----------------

@dp.message(Form.question)
async def question(message: Message, state: FSMContext):

    if message.text.lower().strip() != "3 недели":
        await message.answer("❌ Неверно. Попробуйте ещё раз.")
        return

    await state.set_state(Form.role)
    await message.answer("🎭 Укажите вашу роль")

# ---------------- STEP 3 ----------------

@dp.message(Form.role)
async def role(message: Message, state: FSMContext):

    await state.update_data(role=message.text)
    await state.set_state(Form.fandom)

    await message.answer("🌍 Укажите ваш фандом")

# ---------------- STEP 4 ----------------

@dp.message(Form.fandom)
async def fandom(message: Message, state: FSMContext):

    if is_spam(message.from_user.id):
        await message.answer("⏳ Подождите")
        return

    if get_status(message.from_user.id) == "pending":
        await message.answer("⚠️ Вы уже отправляли заявку")
        return

    data = await state.get_data()

    role = data["role"]
    fandom = message.text

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

    await message.answer(
        "✅ <b>Заявка отправлена</b>\n"
        "⏳ Ожидайте решения администрации"
    )

    await state.clear()

# ---------------- ADMIN ----------------

def is_admin(uid):
    return uid in ADMINS

@dp.callback_query(F.data.startswith("accept:"))
async def accept(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return

    uid = int(call.data.split(":")[1])

    set_status(uid, "accepted")

    await bot.send_message(
        uid,
        f"🎉 <b>Заявка одобрена</b>\n\n👉 {FLUD_LINK}"
    )

    await call.message.edit_text("✅ ПРИНЯТО")
    await call.answer()


@dp.callback_query(F.data.startswith("reject:"))
async def reject(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return

    uid = int(call.data.split(":")[1])

    set_status(uid, "rejected")

    await bot.send_message(uid, "❌ Заявка отклонена")

    await call.message.edit_text("❌ ОТКЛОНЕНО")
    await call.answer()


@dp.callback_query(F.data.startswith("ban:"))
async def ban(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return

    uid = int(call.data.split(":")[1])

    set_status(uid, "banned")

    await bot.send_message(uid, "🚫 Вы заблокированы")

    await call.message.edit_text("🚫 БАН")
    await call.answer()

# ---------------- MAIN ----------------

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
