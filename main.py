import os
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TOKEN")
records = []

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
    current = datetime.strptime(start_time, "%H:%M")
    now = datetime.now()
    current = current.replace(year=now.year, month=now.month, day=now.day)
    p = payday

    while True:
        current += timedelta(hours=1)
        p -= 1 if insured else 2

        if insured and p == 2:
            current += timedelta(hours=1)
            return current
        elif not insured and p <= 1:
            return current


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/add 05:00 321 5 yes 14\n"
        "/list\n"
        "/delete 321\n"
        "/edit 321 06:00 7 no 14"
    )


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        start_time, house_id, payday, insurance, server = context.args
        payday = int(payday)
        insured = insurance.lower() == "yes"
        drop_dt = calc_drop(start_time, payday, insured)

        records.append({
            "house": house_id,
            "payday": payday,
            "insured": insured,
            "server": server,
            "drop": drop_dt
        })

        await update.message.reply_text(
            f"✅ {house_id}\n"
            f"🌍 {SERVERS.get(server)}\n"
            f"⏰ {drop_dt.strftime('%d.%m %H:%M')}"
        )
    except:
        await update.message.reply_text("Ошибка. Пример: /add 05:00 321 5 yes 14")


async def delete_record(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        house_id = context.args[0]
        global records
        records = [r for r in records if r['house'] != house_id]
        await update.message.reply_text(f"🗑 Удалён {house_id}")
    except:
        await update.message.reply_text("/delete 321")


async def edit_record(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        house_id, start_time, payday, insurance, server = context.args
        payday = int(payday)
        insured = insurance.lower() == "yes"

        for r in records:
            if r['house'] == house_id:
                r['payday'] = payday
                r['insured'] = insured
                r['server'] = server
                r['drop'] = calc_drop(start_time, payday, insured)
                await update.message.reply_text(f"✏️ Обновлён {house_id}")
                return

        await update.message.reply_text("Дом не найден")
    except:
        await update.message.reply_text("/edit 321 05:00 5 yes 14")


async def list_records(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not records:
        await update.message.reply_text("Пусто")
        return

    grouped = {}
    for r in records:
        grouped.setdefault(r['server'], []).append(r)

    msg = "🔥 СЛЁТЫ\n\n"

    for server in sorted(grouped.keys()):
        msg += f"🌍 {server}: {SERVERS.get(server)}\n"
        for r in sorted(grouped[server], key=lambda x: x['drop']):
            msg += (
                f"⏰ {r['drop'].strftime('%d.%m %H:%M')} | 🏠 {r['house']}\n"
                f"🛡 {'Страховка' if r['insured'] else 'Без'}\n"
            )
        msg += "\n"

    await update.message.reply_text(msg)


def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("list", list_records))
    app.add_handler(CommandHandler("delete", delete_record))
    app.add_handler(CommandHandler("edit", edit_record))
    app.run_polling()


if __name__ == "__main__":
    main()
