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
    raise ValueError("TELEGRAM_TOKEN not set in environment variables")

PORT = int(os.environ.get("PORT", 10000))
RENDER_NAME = os.environ.get("RENDER_SERVICE_NAME")
WEBHOOK_URL = f"https://{RENDER_NAME}.onrender.com/{TELEGRAM_TOKEN}"

TEMPLATE_PATH = "certificate_template.png"
FONT_PATH_BOLD = "NotoKufiArabic-Bold.ttf"

# Positions
POSITIONS = {
    "h1": (651, 470),
    "name": (650, 545),
    "role": (652, 615),
    "body": 665
}

X_LEFT, X_RIGHT = 28, 1241


# ----------------------
# Conversation states
# ----------------------
H1, NAME, ROLE, BODY = range(4)


# ----------------------
# RTL Helper
# ----------------------
def rtl(text: str) -> str:
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


# ----------------------
# Drawing Functions
# ----------------------
def draw_centered_text(draw, x_center, y, text, font, fill="black"):
    text_rtl = rtl(text)
    bbox = draw.textbbox((0, 0), text_rtl, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text((x_center - w // 2, y - h // 2), text_rtl, font=font, fill=fill)
    return h


def wrap_rtl_text(draw, text, font, max_width):
    """
    Proper RTL wrapping without flipping lines.
    """
    lines = []
    words = text.split()
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        test_line_rtl = rtl(test_line)

        bbox = draw.textbbox((0, 0), test_line_rtl, font=font)
        width = bbox[2] - bbox[0]

        if width <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines


def generate_certificate(h1_text, name_text, role_text, body_text):
    img = Image.open(TEMPLATE_PATH).convert("RGB")
    draw = ImageDraw.Draw(img)

    font_h1 = ImageFont.truetype(FONT_PATH_BOLD, 40)
    font_name = ImageFont.truetype(FONT_PATH_BOLD, 40)
    font_role = ImageFont.truetype(FONT_PATH_BOLD, 30)
    font_body = ImageFont.truetype(FONT_PATH_BOLD, 40)

    # Header
    draw_centered_text(draw, *POSITIONS["h1"], h1_text, font_h1, "black")
    draw_centered_text(draw, *POSITIONS["name"], name_text, font_name, "white")
    draw_centered_text(draw, *POSITIONS["role"], role_text, font_role, "green")

    # Body
    y_body = POSITIONS["body"]
    x_center_body = (X_LEFT + X_RIGHT) // 2
    max_width = X_RIGHT - X_LEFT

    lines = wrap_rtl_text(draw, body_text, font_body, max_width)

    sample_bbox = draw.textbbox((0, 0), rtl("أ"), font=font_body)
    line_height = sample_bbox[3] - sample_bbox[1]

    for line in lines:
        draw_centered_text(draw, x_center_body, y_body, line, font_body, "black")
        y_body += line_height + 8

    bio = BytesIO()
    bio.name = "certificate.png"
    img.save(bio, "PNG")
    bio.seek(0)

    return bio


# ----------------------
# Handlers
# ----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً! لنبدأ إنشاء الشهادة.\n\nأدخل نص H1:")
    return H1


async def h1_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["h1"] = update.message.text
    await update.message.reply_text("الآن أدخل الاسم:")
    return NAME


async def name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("أدخل الدور/الصفة:")
    return ROLE


async def role_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["role"] = update.message.text
    await update.message.reply_text("أخيراً، أدخل نص الجسم (body):")
    return BODY


async def body_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["body"] = update.message.text

    bio = generate_certificate(
        context.user_data["h1"],
        context.user_data["name"],
        context.user_data["role"],
        context.user_data["body"],
    )

    await update.message.reply_photo(photo=bio, caption="تم إنشاء الشهادة بنجاح!")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم إلغاء العملية.")
    return ConversationHandler.END


# ----------------------
# Main
# ----------------------
if __name__ == "__main__":

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            H1: [MessageHandler(filters.TEXT & ~filters.COMMAND, h1_input)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_input)],
            ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, role_input)],
            BODY: [MessageHandler(filters.TEXT & ~filters.COMMAND, body_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=WEBHOOK_URL,
    )
 Thread
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


