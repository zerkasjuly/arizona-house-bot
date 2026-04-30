import os
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
records = []
job_refs = {}

SERVERS = {
    "01": "Phoenix", "02": "Tucson", "03": "Scottdale", "04": "Chandler",
    "05": "Brainburg", "06": "SaintRose", "07": "Mesa", "08": "Red-Rock",
    "09": "Yuma", "10": "Surprise", "11": "Prescott", "12": "Glendale",
    "13": "Kingman", "14": "Winslow", "15": "Payson", "16": "Gilbert",
    "17": "Show-Low", "18": "Casa-Grande", "19": "Page", "20": "Sun-City",
    "21": "Queen-Creek", "22": "Sedona", "23": "Holiday", "24": "Wednesday",
    "25": "Yava", "26": "Faraway", "27": "Bumble-Bee", "28": "Mirage"
}


def calc_drop(start_time, payday, insured):
    now = datetime.now()
    current = datetime.strptime(start_time, "%H:%M").replace(year=now.year, month=now.month, day=now.day)
    p = payday
    while True:
        current += timedelta(hours=1)
        p -= 1 if insured else 2
        if insured and p == 2:
            return current + timedelta(hours=1)
        if not insured and p <= 1:
            return current


async def notify(context):
    data = context.job.data
    await context.bot.send_message(context.job.chat_id,
        f"⚠️ Дом №{data['house']} на сервере {SERVERS.get(data['server'])} слетает через {data['mins']} минут")


async def cleanup(context):
    house = context.job.data
    global records
    records = [r for r in records if r['house'] != house]


def schedule_notifications(app, chat_id, house_id, server, drop):
    for mins in [10, 5]:
        when = (drop - timedelta(minutes=mins) - datetime.now()).total_seconds()
        if when > 0:
            app.job_queue.run_once(notify, when=when, chat_id=chat_id,
                data={'house': house_id, 'server': server, 'mins': mins})

    cleanup_time = (drop - datetime.now()).total_seconds()
    if cleanup_time > 0:
        app.job_queue.run_once(cleanup, when=cleanup_time, data=house_id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("/add, /list, /delete, /edit")


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace('/add', '').strip()
    lines = text.split('\n')
    result = []

    for line in lines:
        try:
            start_time, house_id, payday, insurance, server = line.split()
            payday = int(payday)
            insured = insurance.lower() == 'yes'
            drop = calc_drop(start_time, payday, insured)

            schedule_notifications(context.application, update.effective_chat.id, house_id, server, drop)

            records.append({
                'house': house_id,
                'payday': payday,
                'insured': insured,
                'server': server,
                'drop': drop
            })

            alt = f" или {(drop + timedelta(hours=1)).strftime('%H:%M')}" if insured else ""
            result.append(f"✅ {house_id} → {drop.strftime('%d.%m %H:%M')}{alt}")
        except:
            result.append(f"❌ Ошибка: {line}")

    await update.message.reply_text('\n'.join(result))


async def delete_record(update: Update, context: ContextTypes.DEFAULT_TYPE):
    house_id = context.args[0]
    global records
    records = [r for r in records if r['house'] != house_id]
    await update.message.reply_text(f"🗑 Удалён {house_id}")


async def edit_record(update: Update, context: ContextTypes.DEFAULT_TYPE):
    house_id, start_time, payday, insurance, server = context.args
    payday = int(payday)
    insured = insurance.lower() == 'yes'

    for r in records:
        if r['house'] == house_id:
            drop = calc_drop(start_time, payday, insured)
            schedule_notifications(context.application, update.effective_chat.id, house_id, server, drop)
            r.update({'payday': payday, 'insured': insured, 'server': server, 'drop': drop})
            await update.message.reply_text(f"✏️ Обновлён {house_id}")
            return


async def list_records(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not records:
        await update.message.reply_text("Список пуст")
        return

    grouped = {}
    for r in sorted(records, key=lambda x: x['drop']):
        grouped.setdefault(r['server'], []).append(r)

    msg = "🔥 Список слётов\n\n"
    for server, houses in grouped.items():
        msg += f"🌍 {SERVERS.get(server)} ({server})\n"
        for r in houses:
            alt = f" / {(r['drop'] + timedelta(hours=1)).strftime('%H:%M')}?" if r['insured'] else ""
            msg += f"⏰ {r['drop'].strftime('%d.%m %H:%M')}{alt} | 🏠 {r['house']}\n🛡 {'Страховка' if r['insured'] else 'Без страховки'}\n\n"

    await update.message.reply_text(msg)


def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('add', add))
    app.add_handler(CommandHandler('list', list_records))
    app.add_handler(CommandHandler('delete', delete_record))
    app.add_handler(CommandHandler('edit', edit_record))
    app.run_polling()


if __name__ == '__main__':
    main()
