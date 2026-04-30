import os
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
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
    p = payday

    while True:
        current += timedelta(hours=1)
        p -= 1 if insured else 2

        if insured:
            if p == 2:
                current += timedelta(hours=1)
                return current.strftime("%H:%M")
        else:
            if p <= 1:
                return current.strftime("%H:%M")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Используй:\n"
        "/add 05:00 321 5 yes 07\n\n"
        "формат:\nвремя id payday yes/no сервер"
    )


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        start_time, house_id, payday, insurance, server = context.args
        payday = int(payday)
        insured = insurance.lower() == "yes"

        drop = calc_drop(start_time, payday, insured)

        record = {
            "drop": drop,
            "house": house_id,
            "payday": payday,
            "insured": insured,
            "server": server
        }
        records.append(record)

        await update.message.reply_text(
            f"✅ Дом {house_id} добавлен\n"
            f"🌍 {SERVERS.get(server, server)}\n"
            f"⏰ Слёт: {drop}"
        )
    except Exception as e:
        await update.message.reply_text("Пример: /add 05:00 321 5 yes 07")


async def list_records(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not records:
        await update.message.reply_text("Список пуст")
        return

    sorted_records = sorted(records, key=lambda x: x['drop'])
    msg = "🔥 Список слётов\n\n"

    for r in sorted_records:
        msg += (
            f"⏰ {r['drop']} | 🏠 {r['house']}\n"
            f"🌍 {SERVERS.get(r['server'], r['server'])}\n"
            f"🛡 {'Страховка' if r['insured'] else 'Без страховки'}\n\n"
        )

    await update.message.reply_text(msg)


def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("list", list_records))
    app.run_polling()


if __name__ == "__main__":
    main()
