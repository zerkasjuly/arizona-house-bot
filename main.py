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
SAFE_SLOUT = 6
NOSAFE_SLOUT = 20

# ---------- CORE FIX (NO BUG VERSION) ----------
def calc_time(payday: int, safe: int):
    n = now()

    base_hour = SAFE_SLOUT if safe else NOSAFE_SLOUT

    # смещение payday (ключевая логика)
    target_hour = (base_hour - payday) % 24

    # текущий день
    candidate = n.replace(hour=target_hour, minute=0, second=0, microsecond=0)

    # если это уже прошло — переносим ТОЛЬКО на +1 цикл слёта (а не просто "завтра")
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

            t = calc_time(payday, safe).strftime("%H:%M")

            added.append(f"{hid} | {server} | {t}")

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
        drop = calc_time(payday, safe)

        hours_left = (drop - now()).total_seconds() / 3600

        color = "🔴" if hours_left < 1 else "🟡" if hours_left < 3 else "🟢"

        result.append(
            (
                drop,
                f"{color} {hid} | {server} | {'🛡' if safe else '❌'} | "
                f"{drop.strftime('%H:%M')} | {hours_left:.1f}ч\n"
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

        await q.edit_message_text(f"❌ Удалён {hid}")

# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏠 Arizona RP Bot (FINAL)\n\n"
        "Формат:\n"
        "1234 14 со страховкой winslow\n\n"
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
