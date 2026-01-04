import os
import re
import pandas as pd
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

user_files = {}

def extract_order_number(text):
    match = re.search(r"\b\d{8,}\b", text)
    return match.group(0) if match else None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📦 Пришли PDF с ярлыками, затем Excel со списком заказов"
    )

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    doc = update.message.document
    path = os.path.join(DATA_DIR, doc.file_name)

    tg_file = await doc.get_file()
    await tg_file.download_to_drive(path)

    user_files.setdefault(user_id, {})

    if doc.file_name.lower().endswith(".pdf"):
        user_files[user_id]["pdf"] = path
        await update.message.reply_text("✅ PDF получен, жду Excel")
    elif doc.file_name.lower().endswith((".xlsx", ".xls")):
        user_files[user_id]["excel"] = path
        await update.message.reply_text("⏳ Обрабатываю…")
        await process_files(update, context)

async def process_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    files = user_files.get(user_id)

    if not files or "pdf" not in files or "excel" not in files:
        return

    df = pd.read_excel(files["excel"])
    order_map = {}

    for _, row in df.iterrows():
        try:
            order = str(int(row["Номер заказа"]))
            product = str(row["Название товара"])
            order_map[order] = product
        except:
            continue

    reader = PdfReader(files["pdf"])
    writer = PdfWriter()
    grouped = {}

    with pdfplumber.open(files["pdf"]) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            order = extract_order_number(text)
            product = order_map.get(order, "НЕ НАЙДЕНО")
            grouped.setdefault(product, []).append(i)

    for product in sorted(grouped):
        for page_index in grouped[product]:
            writer.add_page(reader.pages[page_index])

    output = f"sorted_{user_id}.pdf"
    with open(output, "wb") as f:
        writer.write(f)

    await update.message.reply_document(
        document=open(output, "rb"),
        caption="✅ Ярлыки отсортированы по товарам"
    )

    user_files[user_id] = {}

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.run_polling()
