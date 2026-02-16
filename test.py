# bot_webhook.py

import os
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# ----------------------
# Config
# ----------------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set")

PORT = int(os.environ.get("PORT", 10000))
RENDER_NAME = os.environ.get("RENDER_SERVICE_NAME")
WEBHOOK_URL = f"https://{RENDER_NAME}.onrender.com/{TELEGRAM_TOKEN}"

TEMPLATE_PATH = "certificate_template.png"
FONT_PATH = "NotoKufiArabic-Bold.ttf"

POSITIONS = {
    "h1": (651, 470),
    "name": (650, 545),
    "role": (652, 615),
    "body": 665
}

X_LEFT, X_RIGHT = 28, 1241

H1, NAME, ROLE, BODY = range(4)

# ----------------------
# Arabic Conversion
# ----------------------
def convert_arabic(text: str) -> str:
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)

# ----------------------
# Drawing
# ----------------------
def draw_centered(draw, x, y, text, font, fill="black"):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text((x - w // 2, y - h // 2), text, font=font, fill=fill)

def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test_line = f"{current} {word}".strip()
        visual = convert_arabic(test_line)

        bbox = draw.textbbox((0, 0), visual, font=font)
        width = bbox[2] - bbox[0]

        if width <= max_width:
            current = test_line
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines

def generate_certificate(h1, name, role, body):
    img = Image.open(TEMPLATE_PATH).convert("RGB")
    draw = ImageDraw.Draw(img)

    font_h1 = ImageFont.truetype(FONT_PATH, 40)
    font_name = ImageFont.truetype(FONT_PATH, 40)
    font_role = ImageFont.truetype(FONT_PATH, 30)
    font_body = ImageFont.truetype(FONT_PATH, 40)

    # Convert once
    h1_v = convert_arabic(h1)
    name_v = convert_arabic(name)
    role_v = convert_arabic(role)

    draw_centered(draw, *POSITIONS["h1"], h1_v, font_h1)
    draw_centered(draw, *POSITIONS["name"], name_v, font_name, "white")
    draw_centered(draw, *POSITIONS["role"], role_v, font_role, "green")

    y = POSITIONS["body"]
    center_x = (X_LEFT + X_RIGHT) // 2
    max_width = X_RIGHT - X_LEFT

    lines = wrap_text(draw, body, font_body, max_width)

    sample_bbox = draw.textbbox((0, 0), convert_arabic("أ"), font=font_body)
    line_height = sample_bbox[3] - sample_bbox[1]

    for line in lines:
        visual_line = convert_arabic(line)
        draw_centered(draw, center_x, y, visual_line, font_body)
        y += line_height + 10

    bio = BytesIO()
    bio.name = "certificate.png"
    img.save(bio, "PNG")
    bio.seek(0)
    return bio

# ----------------------
# Handlers
# ----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أدخل نص العنوان (H1):")
    return H1

async def h1_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["h1"] = update.message.text
    await update.message.reply_text("أدخل الاسم:")
    return NAME

async def name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("أدخل الصفة:")
    return ROLE

async def role_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["role"] = update.message.text
    await update.message.reply_text("أدخل نص الجسم:")
    return BODY

async def body_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["body"] = update.message.text

    bio = generate_certificate(
        context.user_data["h1"],
        context.user_data["name"],
        context.user_data["role"],
        context.user_data["body"]
    )

    await update.message.reply_photo(photo=bio, caption="تم إنشاء الشهادة ✅")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم الإلغاء.")
    return ConversationHandler.END

# ----------------------
# Main
# ----------------------
if __name__ == "__main__":

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            H1: [MessageHandler(filters.TEXT & ~filters.COMMAND, h1_input)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_input)],
            ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, role_input)],
            BODY: [MessageHandler(filters.TEXT & ~filters.COMMAND, body_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=WEBHOOK_URL,
    )
