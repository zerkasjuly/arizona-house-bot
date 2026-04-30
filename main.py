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
    id INTEGER PRIMARY KEY,
    payday INTEGER,
    safe INTEGER,
    server TEXT,
    chat_id INTEGER
)
""")
conn.commit()

# ---------- МОДЕЛЬ СЛЁТА ----------
# чем больше target — тем дольше до слёта
SAFE_TARGET = 30
NOSAFE_TARGET = 18

# ---------- CORE ----------
def progress(payday: int, safe: int):
    target = SAFE_TARGET if safe else NOSAFE_TARGET

    # нормализуем от 0 до 1 (ВАЖНО)
    return min(payday / target, 1.0), target - payday


def status_bar(p):
    if p >= 0.8:
        return "🔴"
    elif p >= 0.5:
        return "🟡"
    return "🟢"

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

            cur.execute("""
                REPLACE INTO houses VALUES (?, ?, ?, ?, ?)
            """, (hid, payday, safe, server, chat_id))
            conn.commit()

            prog, left = progress(payday, safe)

            added.append(
                f"🏠 {hid} | {server} | {status_bar(prog)} | "
                f"{left} до слёта"
            )

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
        prog, left = progress(payday, safe)

        color = status_bar(prog)

        items.append(
            f"{color} {hid} | {server} | "
            f"{'🛡' if safe else '❌'} | "
            f"{left} payday до слёта"
        )

    await update.message.reply_text("🏠 Дома:\n\n" + "\n".join(items))

# ---------- DELETE ----------
async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        hid = int(context.args[0])

        cur.execute("DELETE FROM houses WHERE id=?", (hid,))
        conn.commit()

        await update.message.reply_text(f"❌ Удалён {hid}")

    except:
        await update.message.reply_text("Используй: /del 123")

# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏠 FINAL STATE MODEL V2\n\n"
        "Формат:\n"
        "1234 13 со страховкой winslow\n\n"
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
