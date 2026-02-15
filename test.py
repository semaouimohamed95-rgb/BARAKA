# bot_conversation.py
import os
from io import BytesIO
from threading import Thread
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
from flask import Flask
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
TEMPLATE_PATH = "certificate_template.png"
FONT_PATH_BOLD = "NotoKufiArabic-Bold.ttf"

POSITIONS = {
    "h1": (651, 470),
    "name": (650, 545),
    "role": (652, 615),
    "body": 665,
}
X_LEFT, X_RIGHT = 28, 1241

# ----------------------
# Flask to keep Render alive
# ----------------------
app = Flask(__name__)
@app.route("/")
def home():
    return "Certificate Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ----------------------
# Helper functions
# ----------------------
def draw_centered_text(draw, x_center, y, text, font, fill="black"):
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    bbox = draw.textbbox((0, 0), bidi_text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text((x_center - w // 2, y - h // 2), bidi_text, font=font, fill=fill)
    return h

def generate_certificate(h1_text, name_text, role_text, body_text):
    img = Image.open(TEMPLATE_PATH).convert("RGB")
    draw = ImageDraw.Draw(img)

    font_h1 = ImageFont.truetype(FONT_PATH_BOLD, 40)
    font_name = ImageFont.truetype(FONT_PATH_BOLD, 40)
    font_role = ImageFont.truetype(FONT_PATH_BOLD, 30)
    font_body = ImageFont.truetype(FONT_PATH_BOLD, 40)

    draw_centered_text(draw, POSITIONS["h1"][0], POSITIONS["h1"][1], h1_text, font_h1, "black")
    draw_centered_text(draw, POSITIONS["name"][0], POSITIONS["name"][1], name_text, font_name, "white")
    draw_centered_text(draw, POSITIONS["role"][0], POSITIONS["role"][1], role_text, font_role, "green")

    y_body = POSITIONS["body"]
    x_center_body = (X_LEFT + X_RIGHT) // 2
    words = body_text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip()
        reshaped_test_line = get_display(arabic_reshaper.reshape(test_line))
        bbox = draw.textbbox((0, 0), reshaped_test_line, font=font_body)
        w = bbox[2] - bbox[0]
        if w <= (X_RIGHT - X_LEFT):
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)

    sample_h = draw.textbbox((0, 0), get_display(arabic_reshaper.reshape("أ")), font=font_body)[3]
    for line in lines:
        draw_centered_text(draw, x_center_body, y_body, line, font_body, "black")
        y_body += sample_h + 2

    bio = BytesIO()
    bio.name = "certificate.png"
    img.save(bio, "PNG")
    bio.seek(0)
    return bio

# ----------------------
# Conversation states
# ----------------------
H1, NAME, ROLE, BODY = range(4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً! من فضلك أدخل نص H1:")
    return H1

async def h1_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["h1"] = update.message.text
    await update.message.reply_text("الآن أدخل الاسم:")
    return NAME

async def name_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("الآن أدخل الدور (role):")
    return ROLE

async def role_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["role"] = update.message.text
    await update.message.reply_text("وأخيراً، أدخل نص body:")
    return BODY

async def body_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["body"] = update.message.text

    bio = generate_certificate(
        h1_text=context.user_data["h1"],
        name_text=context.user_data["name"],
        role_text=context.user_data["role"],
        body_text=context.user_data["body"],
    )

    await update.message.reply_photo(photo=bio)
    await update.message.reply_text("تم إنشاء الشهادة بنجاح ✅")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم إلغاء العملية.")
    return ConversationHandler.END

# ----------------------
# Run bot + Flask
# ----------------------
if __name__ == "__main__":
    Thread(target=run_flask).start()

    bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            H1: [MessageHandler(filters.TEXT & ~filters.COMMAND, h1_step)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_step)],
            ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, role_step)],
            BODY: [MessageHandler(filters.TEXT & ~filters.COMMAND, body_step)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    bot_app.add_handler(conv_handler)
    bot_app.run_polling()
