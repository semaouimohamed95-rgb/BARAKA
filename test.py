# bot_flask.py

import os
from io import BytesIO
from threading import Thread
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ----------------------
# Config
# ----------------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")  # Set in Render environment variables

# Certificate template & fonts
TEMPLATE_PATH = "certificate_template.png"
FONT_PATH_BOLD = "NotoKufiArabic-Bold.ttf"

# Positions
POSITIONS = {
    "h1": (651, 470),
    "name": (650, 545),
    "role": (652, 615),
    "body": 665  # starting y-coordinate for body
}
X_LEFT, X_RIGHT = 28, 1241  # body text limits

# ----------------------
# Flask server (keeps Render free tier alive)
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
    # Load template
    img = Image.open(TEMPLATE_PATH).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Fonts
    font_h1 = ImageFont.truetype(FONT_PATH_BOLD, 40)
    font_name = ImageFont.truetype(FONT_PATH_BOLD, 40)
    font_role = ImageFont.truetype(FONT_PATH_BOLD, 30)
    font_body = ImageFont.truetype(FONT_PATH_BOLD, 40)

    # Draw h1, name, role
    draw_centered_text(draw, POSITIONS["h1"][0], POSITIONS["h1"][1], h1_text, font_h1, "black")
    draw_centered_text(draw, POSITIONS["name"][0], POSITIONS["name"][1], name_text, font_name, "white")
    draw_centered_text(draw, POSITIONS["role"][0], POSITIONS["role"][1], role_text, font_role, "green")

    # Body: wrap text within x_left/x_right
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

    # Draw body lines
    sample_h = draw.textbbox((0, 0), get_display(arabic_reshaper.reshape("أ")), font=font_body)[3]
    for line in lines:
        draw_centered_text(draw, x_center_body, y_body, line, font_body, "black")
        y_body += sample_h + 2

    # Save to BytesIO for Telegram
    bio = BytesIO()
    bio.name = "certificate.png"
    img.save(bio, "PNG")
    bio.seek(0)
    return bio

# ----------------------
# Telegram handlers
# ----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحباً! أرسل لي البيانات بهذا الشكل:\n"
        "/generate\nh1: ...\nname: ...\nrole: ...\nbody: ..."
    )

async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.split("\n")[1:]  # skip /generate line
        data = {}
        for line in text:
            if ":" in line:
                key, value = line.split(":", 1)
                data[key.strip().lower()] = value.strip()

        required_keys = ["h1", "name", "role", "body"]
        if not all(k in data for k in required_keys):
            await update.message.reply_text("يجب إرسال جميع الحقول: h1, name, role, body")
            return

        bio = generate_certificate(
            h1_text=data["h1"],
            name_text=data["name"],
            role_text=data["role"],
            body_text=data["body"]
        )
        await update.message.reply_photo(photo=bio)
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ: {e}")

# ----------------------
# Run bot + Flask
# ----------------------
if __name__ == "__main__":
    # Start Flask in a thread
    Thread(target=run_flask).start()

    # Start Telegram bot
    bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("generate", generate))
    bot_app.run_polling()
