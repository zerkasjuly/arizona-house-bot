import sqlite3
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler
)
import os

TOKEN = os.getenv("BOT_TOKEN")

# ---------- TIME ----------
def now_msk():
    return datetime.utcnow() + timedelta(hours=3)

# ---------- SERVERS ----------
SERVERS = [
    "Mesa", "Phoenix", "Tucson", "Scottdale", "Chandler",
    "BrainBurg", "Saint Rose", "Red-Rock", "Yuma", "Surprise",
    "Prescott", "Glendale", "Kingman", "Winslow", "Payson",
    "Gilbert", "Show-Low", "Casa-Grande", "Page", "Sun-City",
    "Queen-Creek", "Sedona", "Holiday", "Wednesday", "Yava",
    "Faraway", "Bumble Bee", "Christmas", "Mirage", "Love",
    "Drake", "Space"
]

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

# ---------- SAFE SYSTEM (FIXED LOGIC MAP) ----------
# каждый диапазон payday = свой стабильный слёт
SAFE_RANGES = [
    (16, 15),
    (15, 16),
    (14, 17),
    (13, 18),
    (12, 19),
    (11, 20),
    (10, 21),
    (9, 22),
    (8, 23),
    (7, 0),
    (6, 1),
    (5, 2),
    (4, 3),
    (3, 4),
    (2, 5),
]

NO_SAFE_RANGES = [
    (10, 15),
    (8, 16),
    (6, 17),
    (4, 18),
    (2, 19),
]

# ---------- CALC (FIXED + STABLE) ----------
def calc_time(payday, safe):
    now = now_msk()
    base = now.replace(minute=0, second=0, microsecond=0)

    rules = SAFE_RANGES if safe else NO_SAFE_RANGES

    selected_hour = None

    # 1. ищем подходящий диапазон payday
    for limit, hour in rules:
        if payday >= limit:
            selected_hour = hour
            break

    # fallback (никогда не должен срабатывать, но на всякий)
    if selected_hour is None:
        selected_hour = rules[-1][1]

    # 2. строим ближайший слёт
    candidate = base.replace(hour=selected_hour)

    if candidate <= now:
        candidate += timedelta(days=1)

    return candidate

# ---------- COLORS ----------
def get_color(hours_left):
    if hours_left < 1:
        return "🔴"
    elif hours_left < 3:
        return "🟡"
    return "🟢"

# ---------- NOTIFY ----------
async def notify(context: ContextTypes.DEFAULT_TYPE):
    hid, text, chat_id = context.job.data.split("|")

    await context.bot.send_message(
        int(chat_id),
        f"🏠 Дом {hid}\n{text}"
    )

# ---------- SCHEDULE ----------
def schedule(app, chat_id, hid, payday, safe):
    drop = calc_time(payday, safe)
    seconds = (drop - now_msk()).total_seconds()

    if seconds <= 0:
        return

    alerts = [
        (seconds - 600, "⏰ 10 минут до слёта"),
        (seconds - 300, "⏰ 5 минут до слёта"),
    ]

    for delay, text in alerts:
        if delay > 0:
            app.job_queue.run_once(
                notify,
                delay,
                chat_id=chat_id,
                data=f"{hid}|{text}|{chat_id}"
            )

# ---------- RESTORE ----------
async def restore(app):
    await asyncio.sleep(2)

    cur.execute("SELECT * FROM houses")
    rows = cur.fetchall()

    for hid, payday, safe, server, chat_id, created_at in rows:
        schedule(app, chat_id, hid, payday, safe)

# ---------- PARSER ----------
async def parser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower().strip()
    chat_id = update.effective_chat.id

    lines = text.split("\n")
    added = []

    for line in lines:
        parts = line.split()
        if len(parts) < 4:
            continue

        try:
            hid = int(parts[0])
            payday = int(parts[1])
            safe = 1 if "со страховкой" in line else 0
            server = parts[-1].capitalize()

            created_at = now_msk().strftime("%d.%m %H:%M")

            cur.execute("""
                REPLACE INTO houses VALUES (?, ?, ?, ?, ?, ?)
            """, (hid, payday, safe, server, chat_id, created_at))

            schedule(context.application, chat_id, hid, payday, safe)

            drop = calc_time(payday, safe).strftime("%H:%M")

            added.append(f"{hid} | {server} | {drop}")

        except:
            pass

    conn.commit()

    if added:
        await update.message.reply_text(
            "✅ Добавлено:\n\n" + "\n".join(f"🏠 {a}" for a in added)
        )

# ---------- LIST ----------
async def list_houses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    cur.execute("SELECT * FROM houses WHERE chat_id=?", (chat_id,))
    rows = cur.fetchall()

    if not rows:
        await update.message.reply_text("Пусто")
        return

    data = []

    for hid, payday, safe, server, _, created_at in rows:
        drop = calc_time(payday, safe)

        now = now_msk()
        hours_left = (drop - now).total_seconds() / 3600

        data.append((drop, hid, safe, server, hours_left, created_at))

    data.sort(key=lambda x: x[0])

    text = "🏠 Дома (по ближайшему слёту):\n\n"
    keyboard = []

    for drop, hid, safe, server, hours_left, created_at in data:

        color = get_color(hours_left)

        if hours_left >= 1:
            time_info = f"До слёта {hours_left:.1f} ч"
        else:
            time_info = f"До слёта {int(hours_left * 60)} мин"

        text += (
            f"{color} {hid} | {server} | "
            f"{'🛡' if safe else '❌'} | "
            f"{drop.strftime('%H:%M')} | {time_info}\n"
            f"🕒 Дата записи: {created_at}\n\n"
        )

        keyboard.append([
            InlineKeyboardButton(f"❌ {hid}", callback_data=f"del_{hid}"),
            InlineKeyboardButton(f"✏️ {hid}", callback_data=f"edit_{hid}")
        ])

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- BUTTONS ----------
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat.id
    data = query.data

    if data.startswith("del_"):
        hid = int(data.split("_")[1])

        cur.execute("DELETE FROM houses WHERE id=? AND chat_id=?", (hid, chat_id))
        conn.commit()

        await query.edit_message_text(f"❌ Дом {hid} удалён")

    elif data.startswith("edit_"):
        hid = int(data.split("_")[1])

        cur.execute("DELETE FROM houses WHERE id=? AND chat_id=?", (hid, chat_id))
        conn.commit()

        await query.edit_message_text("✏️ Удалён. Отправь заново.")

# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏠 Arizona RP Bot\n\n"
        "Формат:\n"
        "123 16 со страховкой Mesa\n\n"
        "/list — список"
    )

# ---------- MAIN ----------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_houses))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, parser))
    app.add_handler(CallbackQueryHandler(buttons))

    app.post_init = restore

    app.run_polling()

if __name__ == "__main__":
    main()
