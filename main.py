import sqlite3
from datetime import datetime, timedelta
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

TOKEN = os.getenv("BOT_TOKEN")

# ---------- TIME ----------
def now():
    return datetime.utcnow() + timedelta(hours=3)

# ---------- DB ----------
conn = sqlite3.connect("houses.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS houses (
    id INTEGER,
    payday INTEGER,
    safe INTEGER,
    server TEXT,
    chat_id INTEGER,
    created_at TEXT
)
""")
conn.commit()

# ---------- BASE SLOTS ----------
SAFE_BASE = 6   # слёт safe
NOSAFE_BASE = 20  # слёт no safe

# ---------- CORE LOGIC (NO LIMITS, NO TABLES) ----------
def calc_time(payday: int, safe: int):
    base = SAFE_BASE if safe else NOSAFE_BASE

    # просто сдвиг назад
    hour = (base - payday) % 24

    return f"{hour:02d}:00"

# ---------- REAL TIME LEFT (for /list) ----------
def time_left(payday: int, safe: int):
    base = SAFE_BASE if safe else NOSAFE_BASE

    target_hour = (base - payday) % 24

    n = now()
    candidate = n.replace(hour=target_hour, minute=0, second=0, microsecond=0)

    if candidate < n:
        candidate += timedelta(days=1)

    return candidate

# ---------- PARSER ----------
async def parser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_id = update.effective_chat.id

    added = []

    for line in text.split("\n"):
        try:
            parts = line.split()

            hid = int(parts[0])
            payday = int(parts[1])

            safe = 1 if "со страховкой" in line else 0
            server = parts[-1].capitalize()

            created = now().strftime("%d.%m %H:%M")

            cur.execute("""
                REPLACE INTO houses VALUES (?, ?, ?, ?, ?, ?)
            """, (hid, payday, safe, server, chat_id, created))

            conn.commit()

            t = calc_time(payday, safe)

            added.append(f"🏠 {hid} | {server} | {t}")

        except:
            pass

    if added:
        await update.message.reply_text("✅ Добавлено:\n\n" + "\n".join(added))

# ---------- LIST ----------
async def list_houses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    cur.execute("SELECT * FROM houses WHERE chat_id=?", (chat_id,))
    rows = cur.fetchall()

    if not rows:
        await update.message.reply_text("Пусто")
        return

    result = []

    for hid, payday, safe, server, _, created in rows:
        drop_time = time_left(payday, safe)

        hours_left = (drop_time - now()).total_seconds() / 3600

        if hours_left < 1:
            color = "🔴"
        elif hours_left < 3:
            color = "🟡"
        else:
            color = "🟢"

        result.append(
            (
                drop_time,
                f"{color} {hid} | {server} | {'🛡' if safe else '❌'} | "
                f"{drop_time.strftime('%H:%M')} | {hours_left:.1f}ч\n"
                f"🕒 {created}"
            )
        )

    result.sort(key=lambda x: x[0])

    text = "🏠 Дома:\n\n" + "\n\n".join(r[1] for r in result)

    await update.message.reply_text(text)

# ---------- DELETE ----------
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data.startswith("del_"):
        hid = int(q.data.split("_")[1])

        cur.execute("DELETE FROM houses WHERE id=?", (hid,))
        conn.commit()

        await q.edit_message_text(f"❌ Удалён дом {hid}")

# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏠 Arizona RP Tracker (FINAL V4)\n\n"
        "Формат:\n"
        "1234 20 со страховкой winslow\n"
        "1660 2 без страховки mesa\n\n"
        "/list"
    )

# ---------- MAIN ----------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_houses))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, parser))
    app.add_handler(CallbackQueryHandler(buttons))

    app.run_polling()

if __name__ == "__main__":
    main()
