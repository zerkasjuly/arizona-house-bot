import sqlite3
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

def server_keyboard():
    kb = []
    row = []
    for i, s in enumerate(SERVERS, 1):
        row.append(InlineKeyboardButton(s, callback_data=f"srv_{s}"))
        if i % 3 == 0:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    return InlineKeyboardMarkup(kb)

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
    real = payday - 1 if safe else payday
    return now_msk() + timedelta(hours=max(real, 1))

# ---------- NOTIFY ----------
async def notify(context: ContextTypes.DEFAULT_TYPE):
    hid, text = context.job.data.split("|")
    await context.bot.send_message(context.job.chat_id, f"🏠 Дом {hid}\n{text}")

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
                data=f"{hid}|{text}"
            )

# ---------- RESTORE AFTER RESTART ----------
async def restore_jobs(app):
    cur.execute("SELECT * FROM houses")
    for hid, payday, safe, server, chat_id in cur.fetchall():
        schedule(app, chat_id, hid, payday, safe)

# ---------- ADD / PARSER ----------
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

            added.append((hid, server, safe))
        except:
            pass

    conn.commit()

    if added:
        msg = "✅ Добавлено:\n\n"
        for hid, server, safe in added:
            msg += f"🏠 {hid} | 🖥 {server} | {'🛡' if safe else '❌'}\n"
        await update.message.reply_text(msg)

# ---------- LIST ----------
async def list_houses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    cur.execute("SELECT * FROM houses WHERE chat_id=?", (chat_id,))
    rows = cur.fetchall()

    if not rows:
        await update.message.reply_text("Пусто")
        return

    text = "🏠 Дома:\n\n"
    keyboard = []

    for hid, payday, safe, server, _ in rows:
        drop = calc_time(payday, safe)
        text += f"{hid} | {server} | {'🛡' if safe else '❌'} | {drop.strftime('%H:%M')}\n"

        keyboard.append([
            InlineKeyboardButton(f"❌ {hid}", callback_data=f"del_{hid}")
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

    # ❌ delete
    if data.startswith("del_"):
        hid = int(data.split("_")[1])

        cur.execute("DELETE FROM houses WHERE id=? AND chat_id=?", (hid, chat_id))
        conn.commit()

        await query.edit_message_text(f"❌ Дом {hid} удалён")

    # 🖥 server select
    elif data.startswith("srv_"):
        server = data.split("_", 1)[1]
        await query.edit_message_text(f"🖥 Сервер выбран: {server}")

# ---------- SERVER MENU ----------
async def server_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выбери сервер:",
        reply_markup=server_keyboard()
    )

# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏠 Бот домов\n\n"
        "Пример:\n"
        "258 17 со страховкой Mesa\n\n"
        "/server — выбрать сервер\n"
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

    app.post_init = restore_jobs

    app.run_polling()

if __name__ == "__main__":
    main()
