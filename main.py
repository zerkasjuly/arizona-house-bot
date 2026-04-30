import os
import sqlite3
from datetime import datetime, timedelta
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

TOKEN = os.getenv("BOT_TOKEN")

# ---------------- DB ----------------
conn = sqlite3.connect("houses.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS houses (
    id INTEGER PRIMARY KEY,
    payday INTEGER,
    safe INTEGER,
    server TEXT
)
""")
conn.commit()


# ---------------- TIME ----------------
def now():
    return datetime.now()


# ---------------- SIMULATION ----------------
def simulate_hours(payday: int, safe: int) -> int:
    hours = 0
    p = payday

    if safe:
        while p > 1:
            p -= 1
            hours += 1
        hours += 1
    else:
        while p > 0:
            p -= 2
            hours += 1

    return hours


def drop_time(payday, safe):
    return now() + timedelta(hours=simulate_hours(payday, safe))


def color(hours):
    if hours <= 2:
        return "🔴"
    if hours <= 5:
        return "🟡"
    return "🟢"


# ---------------- PARSER ----------------
async def parser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower().split()

    if len(text) >= 4:
        try:
            hid = int(text[0])
            payday = int(text[1])
            server = text[-1]
            safe = 1 if "со" in " ".join(text[2:-1]) else 0

            cur.execute(
                "REPLACE INTO houses VALUES (?, ?, ?, ?)",
                (hid, payday, safe, server)
            )
            conn.commit()

            dt = drop_time(payday, safe)

            await update.message.reply_text(
                f"🏠 {hid} | {server}\n⏰ слёт: {dt.strftime('%H:%M')}"
            )
        except:
            pass


# ---------------- BUTTONS ----------------
def keyboard(hid):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕", callback_data=f"add_{hid}"),
            InlineKeyboardButton("➖", callback_data=f"sub_{hid}"),
            InlineKeyboardButton("🗑", callback_data=f"del_{hid}")
        ]
    ])


async def list_houses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT * FROM houses")
    rows = cur.fetchall()

    if not rows:
        await update.message.reply_text("Пусто")
        return

    text = "🏠 Дома:\n\n"

    for hid, payday, safe, server in rows:
        dt = drop_time(payday, safe)
        hours_left = (dt - now()).total_seconds() / 3600

        text += (
            f"{color(hours_left)} {hid} | {server} → {dt.strftime('%H:%M')}\n"
            f"/"
        )

        await update.message.reply_text(text, reply_markup=keyboard(hid))


# ---------------- CALLBACKS ----------------
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    action, hid = q.data.split("_")
    hid = int(hid)

    cur.execute("SELECT payday, safe FROM houses WHERE id=?", (hid,))
    row = cur.fetchone()

    if not row:
        return

    payday, safe = row

    if action == "add":
        payday += 1
    elif action == "sub":
        payday -= 1
    elif action == "del":
        cur.execute("DELETE FROM houses WHERE id=?", (hid,))
        conn.commit()
        await q.edit_message_text("Удалено")
        return

    cur.execute(
        "UPDATE houses SET payday=? WHERE id=?",
        (payday, hid)
    )
    conn.commit()

    dt = drop_time(payday, safe)

    await q.edit_message_text(
        f"🏠 {hid}\n⏰ {dt.strftime('%H:%M')}",
        reply_markup=keyboard(hid)
    )


# ---------------- START ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏠 V2 BOT\n\n"
        "формат:\n"
        "1234 10 со страховкой mesa\n\n"
        "/list"
    )


# ---------------- MAIN ----------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_houses))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, parser))

    app.run_polling()


if __name__ == "__main__":
    main()
