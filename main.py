import os
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

TOKEN = os.getenv("BOT_TOKEN")
TZ = ZoneInfo("Europe/Moscow")


# =========================
# TIME
# =========================
def parse_time(t: str):
    h, _ = map(int, t.split(":"))
    return datetime.now(TZ).replace(hour=h, minute=0, second=0, microsecond=0)


# =========================
# CORE LOGIC
# =========================
def calc_hours(payday: int, safe: int):
    if safe:
        return max(payday - 1, 0)
    else:
        return max((payday - 1 + 1) // 2, 0)


def get_drop(start, payday, safe):
    return start + timedelta(hours=calc_hours(payday, safe))


# =========================
# DB
# =========================
conn = sqlite3.connect("houses.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS houses (
    id INTEGER PRIMARY KEY,
    payday INTEGER,
    safe INTEGER,
    server TEXT,
    drop_time TEXT
)
""")
conn.commit()


# =========================
# PARSER
# =========================
async def parser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.lower()
        parts = [x.strip() for x in text.split("/")]

        if len(parts) < 5:
            return

        t = parse_time(parts[0])
        hid = int(parts[1])
        payday = int(parts[2])
        mode = parts[3]
        server = parts[4]

        safe = 1 if "со" in mode else 0

        drop = get_drop(t, payday, safe)

        cur.execute(
            "REPLACE INTO houses VALUES (?, ?, ?, ?, ?)",
            (hid, payday, safe, server, drop.isoformat())
        )
        conn.commit()

        await update.message.reply_text(
            f"✅ Добавлено:\n\n"
            f"🏠 {hid} | {server}\n"
            f"⏰ слёт: {drop.strftime('%H:%M')}"
        )

    except:
        await update.message.reply_text("❌ ошибка формата")


# =========================
# LIST
# =========================
async def list_houses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT * FROM houses")
    rows = cur.fetchall()

    if not rows:
        await update.message.reply_text("Пусто")
        return

    now = datetime.now(TZ).replace(minute=0, second=0, microsecond=0)

    data = []

    for hid, payday, safe, server, drop_str in rows:
        drop = datetime.fromisoformat(drop_str)
        hours_left = int((drop - now).total_seconds() // 3600)

        if hours_left <= 2:
            color = "🔴"
        elif hours_left <= 5:
            color = "🟡"
        else:
            color = "🟢"

        data.append((drop, f"{color} {hid} | {server} | {drop.strftime('%H:%M')} | ~{hours_left}ч"))

    data.sort(key=lambda x: x[0])

    text = "🏠 Дома (по ближайшему слёту):\n\n"

    for _, line in data:
        text += line + "\n"

    await update.message.reply_text(text)


# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏠 BOT READY\n\n"
        "Формат:\n"
        "05:00 / 1111 / 3 / без страховки / phoenix\n\n"
        "/list - список"
    )


# =========================
# MAIN
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_houses))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, parser))

    app.run_polling()


if __name__ == "__main__":
    main()
