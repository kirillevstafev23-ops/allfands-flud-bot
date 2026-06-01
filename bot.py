import os
import asyncio
import random
import sqlite3
import threading
import logging
from datetime import datetime
from contextlib import closing

from flask import Flask
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

TOKEN = os.getenv("TOKEN")

ADMINS = [1739947062, 5655991466]

INFO_CHANNEL = "https://t.me/+rFs7nnx639BmNzgy"
FLUD_LINK = "https://t.me/+zTukwrwrqlgxOGUy"
FLUD_CHAT_ID = int(os.getenv("FLUD_CHAT_ID", "-1000000000000"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

app = Flask(__name__)

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher(storage=MemoryStorage())

QUOTES = [
    f"✨ Цитата №{i}. Каждая история начинается с первого сообщения."
    for i in range(1, 101)
]

ATMOSPHERES = [
    f"🌙 Атмосфера №{i}. За каждым сообщением скрывается новая история."
    for i in range(1, 51)
]

RULES_TEXT = """
<b>📖 Правила</b>

━━━━━━━━━━━━━━

✨ Уважайте участников.
✨ Не провоцируйте конфликты.
✨ Соблюдайте атмосферу общения.
✨ Следуйте указаниям администрации.

━━━━━━━━━━━━━━
"""

FAQ_TEXT = """
<b>❓ FAQ</b>

━━━━━━━━━━━━━━

• Как попасть во флуд?
— Заполнить анкету.

• Когда рассмотрят заявку?
— После проверки администрацией.

• Можно ли подать заново?
— Да, если нет бана.

━━━━━━━━━━━━━━
"""

ABOUT_TEXT = """
<b>🎭 О флуде</b>

━━━━━━━━━━━━━━

Место для общения,
сюжетов,
знакомств,
идей
и вдохновения.

━━━━━━━━━━━━━━
"""

FANDOMS_TEXT = """
<b>🌍 Фандомы</b>

━━━━━━━━━━━━━━

Приветствуются любые фандомы,
каноны,
авторские миры
и кроссоверы.

━━━━━━━━━━━━━━
"""

WELCOME = """
<b>✨ Добро пожаловать ✨</b>

━━━━━━━━━━━━━━

<i>Каждая история начинается с первого сообщения.</i>

━━━━━━━━━━━━━━
"""

# ---------------- DATABASE ----------------

def db():
    return sqlite3.connect("flud.db", check_same_thread=False)


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
        CREATE TABLE IF NOT EXISTS logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            admin_id INTEGER,
            action TEXT,
            created_at TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS bans(
            user_id INTEGER PRIMARY KEY,
            admin_id INTEGER,
            created_at TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS applications(
            user_id INTEGER PRIMARY KEY,
            msg_admin_1 INTEGER,
            msg_admin_2 INTEGER
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS applications_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            role TEXT,
            fandom TEXT,
            status TEXT,
            admin_id INTEGER,
            created_at TEXT
        )
        """)

        conn.commit()


def now():
    return datetime.now().strftime("%d.%m.%Y %H:%M")


def user_status(user_id):
    try:
        with closing(db()) as conn:
            cur = conn.cursor()
            cur.execute("SELECT status FROM users WHERE user_id=?", (user_id,))
            row = cur.fetchone()
            return row[0] if row else None
    except Exception as e:
        logger.exception(e)
        return None


def save_user(user_id, username):
    try:
        with closing(db()) as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT OR IGNORE INTO users
            (user_id,username,created_at)
            VALUES(?,?,?)
            """, (user_id, username, now()))
            conn.commit()
    except Exception as e:
        logger.exception(e)


def update_profile(user_id, role, fandom):
    try:
        with closing(db()) as conn:
            cur = conn.cursor()
            cur.execute("""
            UPDATE users
            SET role=?, fandom=?, status='pending'
            WHERE user_id=?
            """, (role, fandom, user_id))
            conn.commit()
    except Exception as e:
        logger.exception(e)


def update_status(user_id, status, admin_id=None):
    try:
        with closing(db()) as conn:
            cur = conn.cursor()

            cur.execute("""
            UPDATE users
            SET status=?
            WHERE user_id=?
            """, (status, user_id))

            cur.execute("""
            INSERT INTO applications_history
            (user_id, username, role, fandom, status, admin_id, created_at)
            SELECT user_id, username, role, fandom, ?, ?, ?
            FROM users WHERE user_id=?
            """, (status, admin_id, now(), user_id))

            conn.commit()
    except Exception as e:
        logger.exception(e)


def add_log(user_id, admin_id, action):
    try:
        with closing(db()) as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO logs(user_id,admin_id,action,created_at)
            VALUES(?,?,?,?)
            """, (user_id, admin_id, action, now()))
            conn.commit()
    except Exception as e:
        logger.exception(e)


def save_application(user_id, m1, m2):
    try:
        with closing(db()) as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT OR REPLACE INTO applications
            (user_id,msg_admin_1,msg_admin_2)
            VALUES(?,?,?)
            """, (user_id, m1, m2))
            conn.commit()
    except Exception as e:
        logger.exception(e)


def get_application(user_id):
    try:
        with closing(db()) as conn:
            cur = conn.cursor()
            cur.execute("""
            SELECT msg_admin_1,msg_admin_2
            FROM applications
            WHERE user_id=?
            """, (user_id,))
            return cur.fetchone()
    except Exception as e:
        logger.exception(e)
        return None


# ---------------- FSM ----------------

class Register(StatesGroup):
    question = State()
    role = State()
    fandom = State()


class Broadcast(StatesGroup):
    text = State()


# ---------------- KEYBOARDS ----------------

def info_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Инфо-канал", url=INFO_CHANNEL)],
            [InlineKeyboardButton(text="✅ Ознакомился", callback_data="read_info")]
        ]
    )


def pending_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📖 Правила", callback_data="rules")],
            [InlineKeyboardButton(text="❓ FAQ", callback_data="faq")],
            [InlineKeyboardButton(text="🎭 О флуде", callback_data="about")],
            [InlineKeyboardButton(text="🌍 Фандомы", callback_data="fandoms")],
            [InlineKeyboardButton(text="✨ Атмосфера", callback_data="atmosphere")],
            [InlineKeyboardButton(text="🎲 Случайная цитата", callback_data="quote")]
        ]
    )


def admin_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton(text="👥 Пользователи", callback_data="users")],
            [InlineKeyboardButton(text="📨 Заявки", callback_data="apps")],
            [InlineKeyboardButton(text="📜 История", callback_data="history")],
            [InlineKeyboardButton(text="📢 Рассылка", callback_data="broadcast")],
            [InlineKeyboardButton(text="🚫 Бан-лист", callback_data="banlist")],
            [InlineKeyboardButton(text="👥 Участников во флуде", callback_data="members")]
        ]
    )


# ---------------- FLASK ----------------

@app.route("/")
def home():
    return "BOT ONLINE"


def run_flask():
    try:
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
    except Exception as e:
        logger.exception(e)


# ---------------- SAFE SEND ----------------

async def safe_send(admin, text, kb):
    try:
        return await bot.send_message(admin, text, reply_markup=kb)
    except Exception as e:
        logger.exception(e)
        return None


# ---------------- START ----------------

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    try:
        username = f"@{message.from_user.username}" if message.from_user.username else "Не указан"

        save_user(message.from_user.id, username)

        if user_status(message.from_user.id) == "banned":
            await message.answer("🚫 Вы заблокированы.")
            return

        await state.clear()

        await message.answer(
            WELCOME + "\n\n" + random.choice(QUOTES),
            reply_markup=info_kb()
        )
    except Exception as e:
        logger.exception(e)


@dp.callback_query(F.data == "read_info")
async def read_info(call: CallbackQuery, state: FSMContext):
    try:
        await state.set_state(Register.question)

        await call.message.answer(
            "<b>❓ Проверочный вопрос</b>\n\nМаксимальный срок реста?"
        )

        await call.answer()
    except Exception as e:
        logger.exception(e)


@dp.message(Register.question)
async def q_step(message: Message, state: FSMContext):
    try:
        if message.text.lower().strip() != "3 недели":
            await message.answer("🚫 Неверно.\n\nПопробуйте ещё раз.")
            return

        await state.set_state(Register.role)
        await message.answer("🎭 Укажите вашу роль:")
    except Exception as e:
        logger.exception(e)


@dp.message(Register.role)
async def role_step(message: Message, state: FSMContext):
    try:
        await state.update_data(role=message.text)
        await state.set_state(Register.fandom)
        await message.answer("🌍 Укажите фандом:")
    except Exception as e:
        logger.exception(e)


@dp.message(Register.fandom)
async def fandom_step(message: Message, state: FSMContext):
    try:
        data = await state.get_data()

        role = data["role"]
        fandom = message.text

        update_profile(message.from_user.id, role, fandom)

        username = f"@{message.from_user.username}" if message.from_user.username else "Не указан"

        text = f"""
📨 Новая анкета

━━━━━━━━━━━━━━

👤 Пользователь
{username}

🆔 ID
{message.from_user.id}

🎭 Роль
{role}

🌍 Фандом
{fandom}

🕰 Подана
{now()}

━━━━━━━━━━━━━━
"""

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Принять", callback_data=f"accept:{message.from_user.id}")
                ],
                [
                    InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{message.from_user.id}")
                ],
                [
                    InlineKeyboardButton(text="🚫 Забанить", callback_data=f"ban:{message.from_user.id}")
                ]
            ]
        )

        ids = []

        for admin in ADMINS:
            msg = await safe_send(admin, text, kb)
            if msg:
                ids.append(msg.message_id)
            else:
                ids.append(0)

        if len(ids) >= 2:
            save_application(message.from_user.id, ids[0], ids[1])

        await message.answer(
            "<b>📨 Заявка отправлена администрации.</b>",
            reply_markup=pending_menu()
        )

        await state.clear()

    except Exception as e:
        logger.exception(e)


# ---------------- USER MENU ----------------

@dp.callback_query(F.data == "rules")
async def rules(call: CallbackQuery):
    try:
        await call.message.answer(RULES_TEXT)
        await call.answer()
    except Exception as e:
        logger.exception(e)


@dp.callback_query(F.data == "faq")
async def faq(call: CallbackQuery):
    try:
        await call.message.answer(FAQ_TEXT)
        await call.answer()
    except Exception as e:
        logger.exception(e)


@dp.callback_query(F.data == "about")
async def about(call: CallbackQuery):
    try:
        await call.message.answer(ABOUT_TEXT)
        await call.answer()
    except Exception as e:
        logger.exception(e)


@dp.callback_query(F.data == "fandoms")
async def fandoms(call: CallbackQuery):
    try:
        await call.message.answer(FANDOMS_TEXT)
        await call.answer()
    except Exception as e:
        logger.exception(e)


@dp.callback_query(F.data == "atmosphere")
async def atmosphere(call: CallbackQuery):
    try:
        await call.message.answer(random.choice(ATMOSPHERES))
        await call.answer()
    except Exception as e:
        logger.exception(e)


@dp.callback_query(F.data == "quote")
async def quote(call: CallbackQuery):
    try:
        await call.message.answer(random.choice(QUOTES))
        await call.answer()
    except Exception as e:
        logger.exception(e)


# ---------------- ADMIN SAFE CHECK ----------------

def is_admin(user_id: int):
    return user_id in ADMINS


# ---------------- APPLICATION PROCESS ----------------

async def edit_admin_messages(user_id, text):
    try:
        row = get_application(user_id)
        if not row:
            return

        for admin_id, msg_id in zip(ADMINS, row):
            try:
                await bot.edit_message_text(
                    text=text,
                    chat_id=admin_id,
                    message_id=msg_id
                )
            except Exception as e:
                logger.exception(e)
    except Exception as e:
        logger.exception(e)


@dp.callback_query(F.data.startswith("accept:"))
async def accept(call: CallbackQuery):
    try:
        if not is_admin(call.from_user.id):
            return

        user_id = int(call.data.split(":")[1])

        if user_status(user_id) != "pending":
            await call.answer("Уже обработано")
            return

        update_status(user_id, "accepted", call.from_user.id)

        add_log(user_id, call.from_user.id, "accepted")

        try:
            await bot.send_message(
                user_id,
                f"""
✨ Ваша анкета одобрена

Совет флуда рассмотрел заявку
и открыл для вас доступ.

🌙 Добро пожаловать.

🔗 Ссылка:
{FLUD_LINK}

━━━━━━━━━━━━━━
{random.choice(QUOTES)}
"""
            )
        except Exception as e:
            logger.exception(e)

        admin_name = f"@{call.from_user.username}" if call.from_user.username else str(call.from_user.id)

        await edit_admin_messages(
            user_id,
            f"✅ Пользователь принят\n\nАдминистратор: {admin_name}"
        )

        await call.answer("Принято")

    except Exception as e:
        logger.exception(e)


@dp.callback_query(F.data.startswith("reject:"))
async def reject(call: CallbackQuery):
    try:
        if not is_admin(call.from_user.id):
            return

        user_id = int(call.data.split(":")[1])

        if user_status(user_id) != "pending":
            await call.answer("Уже обработано")
            return

        update_status(user_id, "rejected", call.from_user.id)

        add_log(user_id, call.from_user.id, "rejected")

        try:
            await bot.send_message(
                user_id,
                """
📩 Анкета рассмотрена

К сожалению, сейчас она не была одобрена.

Вы можете подать новую заявку позже.
"""
            )
        except Exception as e:
            logger.exception(e)

        admin_name = f"@{call.from_user.username}" if call.from_user.username else str(call.from_user.id)

        await edit_admin_messages(
            user_id,
            f"❌ Пользователь отклонён\n\nАдминистратор: {admin_name}"
        )

        await call.answer("Отклонено")

    except Exception as e:
        logger.exception(e)


@dp.callback_query(F.data.startswith("ban:"))
async def ban(call: CallbackQuery):
    try:
        if not is_admin(call.from_user.id):
            return

        user_id = int(call.data.split(":")[1])

        if user_status(user_id) == "banned":
            await call.answer("Уже забанен")
            return

        update_status(user_id, "banned", call.from_user.id)

        with closing(db()) as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT OR REPLACE INTO bans
            VALUES(?,?,?)
            """, (user_id, call.from_user.id, now()))
            conn.commit()

        add_log(user_id, call.from_user.id, "banned")

        try:
            await bot.send_message(user_id, "🚫 Вы заблокированы.")
        except Exception as e:
            logger.exception(e)

        admin_name = f"@{call.from_user.username}" if call.from_user.username else str(call.from_user.id)

        await edit_admin_messages(
            user_id,
            f"🚫 Пользователь забанен\n\nАдминистратор: {admin_name}"
        )

        await call.answer("Забанен")

    except Exception as e:
        logger.exception(e)


# ---------------- ADMIN PANEL ----------------

@dp.message(Command("admin"))
async def admin(message: Message):
    try:
        if not is_admin(message.from_user.id):
            return

        await message.answer("<b>⚙️ Админ-панель</b>", reply_markup=admin_kb())
    except Exception as e:
        logger.exception(e)


@dp.callback_query(F.data == "stats")
async def stats(call: CallbackQuery):
    try:
        with closing(db()) as conn:
            cur = conn.cursor()

            total = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            accepted = cur.execute("SELECT COUNT(*) FROM users WHERE status='accepted'").fetchone()[0]
            rejected = cur.execute("SELECT COUNT(*) FROM users WHERE status='rejected'").fetchone()[0]
            banned = cur.execute("SELECT COUNT(*) FROM users WHERE status='banned'").fetchone()[0]
            pending = cur.execute("SELECT COUNT(*) FROM users WHERE status='pending'").fetchone()[0]

        await call.message.answer(f"""
📊 Статистика

━━━━━━━━━━━━━━

👥 Всего: {total}
✅ Принято: {accepted}
❌ Отклонено: {rejected}
🚫 Забанено: {banned}
📨 Ожидают: {pending}
""")

        await call.answer()

    except Exception as e:
        logger.exception(e)


@dp.callback_query(F.data == "users")
async def users(call: CallbackQuery):
    try:
        with closing(db()) as conn:
            cur = conn.cursor()
            rows = cur.execute("""
            SELECT username,user_id,status
            FROM users
            ORDER BY user_id DESC
            LIMIT 20
            """).fetchall()

        text = "<b>👥 Последние пользователи</b>\n\n"

        for r in rows:
            text += f"{r[0]}\nID: {r[1]}\nСтатус: {r[2]}\n\n"

        await call.message.answer(text)
        await call.answer()

    except Exception as e:
        logger.exception(e)


@dp.callback_query(F.data == "apps")
async def apps(call: CallbackQuery):
    try:
        with closing(db()) as conn:
            cur = conn.cursor()
            rows = cur.execute("""
            SELECT username,user_id,role,fandom
            FROM users
            WHERE status='pending'
            """).fetchall()

        if not rows:
            await call.message.answer("📭 Нет заявок.")
            await call.answer()
            return

        text = "<b>📨 Заявки</b>\n\n"

        for r in rows:
            text += f"{r[0]}\nID: {r[1]}\nРоль: {r[2]}\nФандом: {r[3]}\n\n"

        await call.message.answer(text)
        await call.answer()

    except Exception as e:
        logger.exception(e)


@dp.callback_query(F.data == "history")
async def history(call: CallbackQuery):
    try:
        with closing(db()) as conn:
            cur = conn.cursor()
            rows = cur.execute("""
            SELECT user_id, admin_id, status, created_at
            FROM applications_history
            ORDER BY id DESC
            LIMIT 20
            """).fetchall()

        text = "<b>📜 История действий</b>\n\n"

        for r in rows:
            text += f"ID:{r[0]} | Admin:{r[1]} | {r[2]} | {r[3]}\n"

        await call.message.answer(text)
        await call.answer()

    except Exception as e:
        logger.exception(e)


@dp.callback_query(F.data == "banlist")
async def banlist(call: CallbackQuery):
    try:
        with closing(db()) as conn:
            cur = conn.cursor()
            rows = cur.execute("SELECT user_id FROM bans").fetchall()

        text = "<b>🚫 Бан-лист</b>\n\n" + ("\n".join(str(r[0]) for r in rows) if rows else "Пусто.")

        await call.message.answer(text)
        await call.answer()

    except Exception as e:
        logger.exception(e)


@dp.callback_query(F.data == "broadcast")
async def broadcast(call: CallbackQuery, state: FSMContext):
    try:
        await state.set_state(Broadcast.text)
        await call.message.answer("📢 Отправьте текст рассылки.")
        await call.answer()
    except Exception as e:
        logger.exception(e)


@dp.message(Broadcast.text)
async def broadcast_send(message: Message, state: FSMContext):
    try:
        if not is_admin(message.from_user.id):
            return

        with closing(db()) as conn:
            cur = conn.cursor()
            users = cur.execute("""
            SELECT user_id FROM users WHERE status='accepted'
            """).fetchall()

        success = 0
        errors = 0

        for u in users:
            try:
                await bot.send_message(u[0], message.text)
                success += 1
            except Exception as e:
                logger.exception(e)
                errors += 1

        await message.answer(f"""
📢 Рассылка завершена

━━━━━━━━━━━━━━

✅ Успешно: {success}
❌ Ошибки: {errors}
👥 Всего: {len(users)}
""")

        await state.clear()

    except Exception as e:
        logger.exception(e)


@dp.callback_query(F.data == "members")
async def members(call: CallbackQuery):
    try:
        count = await bot.get_chat_member_count(FLUD_CHAT_ID)
        await call.message.answer(f"👥 Участников во флуде: {count}")
        await call.answer()
    except Exception as e:
        logger.exception(e)
        await call.message.answer("⚠️ Ошибка получения участников.")


# ---------------- MAIN ----------------

async def main():
    init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(main())
