# bot_webhook.py

import os
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

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
# Drawing Functions
# ----------------------
def draw_centered_text(draw, x_center, y, text, font, fill="black"):
    """
    Draw centered Arabic text using native RTL support.
    """
    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font,
        direction="rtl",
        language="ar"
    )

    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]

    draw.text(
        (x_center - w // 2, y - h // 2),
        text,
        font=font,
        fill=fill,
        direction="rtl",
        language="ar"
    )

    return h


def wrap_rtl_text(draw, text, font, max_width):
    """
    Wrap Arabic text correctly while measuring width in RTL mode.
    """
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()

        bbox = draw.textbbox(
            (0, 0),
            test_line,
            font=font,
            direction="rtl",
            language="ar"
        )

        width = bbox[2] - bbox[0]

        if width <= max_width:
            current_line = test_line
        else:
            if current_line:
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

    sample_bbox = draw.textbbox(
        (0, 0),
        "أ",
        font=font_body,
        direction="rtl",
        language="ar"
    )
    line_height = sample_bbox[3] - sample_bbox[1]

    for line in lines:
        draw_centered_text(draw, x_center_body, y_body, line, font_body, "black")
        y_body += line_height + 10

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
