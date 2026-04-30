import sqlite3
import os

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

TOKEN = os.getenv("BOT_TOKEN")

# ---------- DB ----------
conn = sqlite3.connect("houses.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS houses (
    id INTEGER,
    payday INTEGER,
    safe INTEGER,
    server TEXT,
    chat_id INTEGER
)
""")
conn.commit()

# ---------- CORE LOGIC ----------
def calc_slot(payday: int, safe: int):
    base = 6 if safe else 20
    return f"{(base - payday) % 24:02d}:00"

# ---------- TIME LEFT (для /list) ----------
def fake_hours_left(payday: int, safe: int):
    # чисто визуал, без datetime багов
    base = 6 if safe else 20
    return abs(base - payday)

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

            cur.execute(
                "REPLACE INTO houses VALUES (?, ?, ?, ?, ?)",
                (hid, payday, safe, server, chat_id)
            )
            conn.commit()

            slot = calc_slot(payday, safe)

            added.append(f"🏠 {hid} | {server} | {slot}")

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

    items = []

    for hid, payday, safe, server, _ in rows:
        slot = calc_slot(payday, safe)
        hours = fake_hours_left(payday, safe)

        # цвет
        if hours <= 2:
            color = "🔴"
        elif hours <= 6:
            color = "🟡"
        else:
            color = "🟢"

        items.append(
            (hours,
             f"{color} {hid} | {server} | {'🛡' if safe else '❌'} | {slot} | ~{hours}h")
        )

    items.sort(key=lambda x: x[0])

    text = "🏠 Дома:\n\n" + "\n".join(i[1] for i in items)

    await update.message.reply_text(text)

# ---------- DELETE ----------
async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        hid = int(context.args[0])

        cur.execute("DELETE FROM houses WHERE id=?", (hid,))
        conn.commit()

        await update.message.reply_text(f"❌ Удалён дом {hid}")

    except:
        await update.message.reply_text("Используй: /del 123")

# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏠 FINAL ARIZONA BOT\n\n"
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
    app.add_handler(CommandHandler("del", delete))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, parser))

    app.run_polling()

if __name__ == "__main__":
    main()
