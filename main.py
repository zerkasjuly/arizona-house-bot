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
    chat_id INTEGER
)
""")
conn.commit()

# ---------- TIME CALC ----------
def calc_time(payday, safe):
    base = now_msk()

    if safe:
        payday -= 1

    payday = max(payday, 1)

    t = base + timedelta(hours=payday)

    # округление до следующего часа
    if t.minute > 0 or t.second > 0:
        t = t.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:
        t = t.replace(minute=0, second=0, microsecond=0)

    return t

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

# ---------- RESTORE AFTER RESTART ----------
async def restore(app):
    await asyncio.sleep(2)

    cur.execute("SELECT * FROM houses")
    rows = cur.fetchall()

    for hid, payday, safe, server, chat_id in rows:
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

            cur.execute("""
                REPLACE INTO houses VALUES (?, ?, ?, ?, ?)
            """, (hid, payday, safe, server, chat_id))

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

# ---------- LIST (SORTED FIX) ----------
async def list_houses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    cur.execute("SELECT * FROM houses WHERE chat_id=?", (chat_id,))
    rows = cur.fetchall()

    if not rows:
        await update.message.reply_text("Пусто")
        return

    data = []

    for hid, payday, safe, server, _ in rows:
        drop = calc_time(payday, safe)
        data.append((drop, hid, safe, server))

    # 🔥 сортировка по ближайшему слёту
    data.sort(key=lambda x: x[0])

    text = "🏠 Дома (по ближайшему слёту):\n\n"
    keyboard = []

    for drop, hid, safe, server in data:
        text += f"{hid} | {server} | {'🛡' if safe else '❌'} | {drop.strftime('%H:%M')}\n"

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

        await query.edit_message_text(
            f"✏️ Дом {hid} удалён.\nОтправь его заново."
        )

# ---------- SERVER MENU ----------
async def server_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton(s, callback_data=f"srv_{s}") for s in SERVERS[i:i+3]]
          for i in range(0, len(SERVERS), 3)]

    await update.message.reply_text(
        "Выбери сервер:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏠 Бот домов\n\n"
        "Формат:\n"
        "258 17 со страховкой Mesa\n\n"
        "/list — список домов"
    )

# ---------- MAIN ----------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_houses))
    app.add_handler(CommandHandler("server", server_menu))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, parser))
    app.add_handler(CallbackQueryHandler(buttons))

    app.post_init = restore

    app.run_polling()

if __name__ == "__main__":
    main()
