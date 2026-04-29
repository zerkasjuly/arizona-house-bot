import asyncio
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import os

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN не найден")

def next_midnight():
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)

def calc_datetime(payday):
    return next_midnight() + timedelta(hours=payday - 2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команды:\n"
        "/watch ID payday — поставить слежение\n"
        "или отправь список строками: ID payday"
    )

async def notify(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    await context.bot.send_message(
        job.chat_id,
        f"⚠️ Через 3 минуты слёт дома ID {job.data}!"
    )

async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        house_id = int(context.args[0])
        payday = int(context.args[1])

        drop_time = calc_datetime(payday)
        notify_time = drop_time - timedelta(minutes=3)

        delay = (notify_time - datetime.now()).total_seconds()

        if delay <= 0:
            await update.message.reply_text("Это время уже прошло")
            return

        context.job_queue.run_once(
            notify,
            when=delay,
            chat_id=update.effective_chat.id,
            data=house_id
        )

        await update.message.reply_text(
            f"Слежение включено для ID {house_id}\n"
            f"Слёт: {drop_time.strftime('%H:%M')}\n"
            f"Напомню за 3 минуты"
        )

    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

async def calculate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = update.message.text.strip().split('\n')
    result = []

    for line in lines:
        try:
            house_id, payday = map(int, line.split())
            drop = calc_datetime(payday)
            result.append((drop, f"ID {house_id} — {drop.strftime('%H:%M')}"))
        except:
            result.append((datetime.max, f"Ошибка: {line}"))

    result.sort(key=lambda x: x[0])
    await update.message.reply_text('\n'.join(r[1] for r in result))

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("watch", watch))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, calculate))

    app.run_polling()

if __name__ == "__main__":
    main()
