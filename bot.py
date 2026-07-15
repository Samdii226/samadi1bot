"""
Samadi Bot - A Multi-Purpose Telegram Bot
Features: URL Shortener, Word Counter, Image Generation, Image Converter, Image Resizer, QR Generator
"""

import os
import re
import logging
from io import BytesIO
from typing import Optional
from urllib.parse import urlparse

# Third-party imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import requests
from PIL import Image
import qrcode

# ============================================================================
# CONFIGURATION
# ============================================================================

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required!")

MAX_IMAGE_DIMENSION = 4000
SUPPORTED_FORMATS = ["jpeg", "png", "webp", "jpg"]
API_TIMEOUT = 30

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def is_valid_url(url: str) -> bool:
    """Check if the string is a valid URL."""
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def clean_url(url: str) -> str:
    """Clean and format URL."""
    url = url.strip()
    url = re.sub(r'[.,;!?]+$', '', url)
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url

def count_text_stats(text: str) -> dict:
    """Analyze text and return statistics."""
    return {
        "words": len(text.split()),
        "characters": len(text),
        "characters_no_spaces": len(text.replace(" ", "")),
        "sentences": len(re.findall(r'[.!?]+', text)),
        "paragraphs": len(text.split('\n\n')),
        "lines": len(text.split('\n')),
    }

def generate_qr_code(data: str) -> BytesIO:
    """Generate QR code image from data."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output

def resize_image(image_data: bytes, width: int, height: int) -> BytesIO:
    """Resize image to specified dimensions."""
    img = Image.open(BytesIO(image_data))
    img = img.resize((width, height), Image.Resampling.LANCZOS)
    
    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output

def convert_image_format(image_data: bytes, format_type: str) -> BytesIO:
    """Convert image to different format."""
    img = Image.open(BytesIO(image_data))
    
    if format_type.lower() in ["jpeg", "jpg"]:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
    
    output = BytesIO()
    img.save(output, format=format_type.upper())
    output.seek(0)
    return output

def generate_ai_image(prompt: str) -> Optional[bytes]:
    """Generate image using Pollinations.ai API."""
    try:
        clean_prompt = prompt.replace(" ", "%20").replace("\n", " ")
        url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=512&height=512&nologo=true"
        
        response = requests.get(url, timeout=API_TIMEOUT)
        if response.status_code == 200:
            return response.content
        return None
    except Exception as e:
        logger.error(f"AI Image generation error: {e}")
        return None

# ===== SIMPLIFIED URL SHORTENER - Using TinyURL (Most Reliable) =====
def shorten_url(url: str) -> tuple:
    """
    Shorten URL using TinyURL (most reliable, no API key needed).
    Returns: (shortened_url, error_message)
    """
    url = clean_url(url)
    
    # Try TinyURL first (most reliable)
    try:
        response = requests.get(
            "https://tinyurl.com/api-create.php",
            params={"url": url},
            timeout=15
        )
        if response.status_code == 200:
            short_url = response.text.strip()
            if short_url and "error" not in short_url.lower():
                logger.info(f"TinyURL success: {short_url}")
                return (short_url, None)
    except Exception as e:
        logger.warning(f"TinyURL failed: {e}")
    
    # Try is.gd as fallback
    try:
        response = requests.get(
            "https://is.gd/create.php",
            params={"format": "json", "url": url},
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            if "shorturl" in data:
                logger.info(f"is.gd success: {data['shorturl']}")
                return (data["shorturl"], None)
    except Exception as e:
        logger.warning(f"is.gd failed: {e}")
    
    # Try v.gd as second fallback
    try:
        response = requests.get(
            "https://v.gd/create.php",
            params={"format": "json", "url": url},
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            if "shorturl" in data:
                logger.info(f"v.gd success: {data['shorturl']}")
                return (data["shorturl"], None)
    except Exception as e:
        logger.warning(f"v.gd failed: {e}")
    
    return (None, "All URL shortening services are currently unavailable. Please try again later.")

# ============================================================================
# BOT HANDLERS
# ============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    
    welcome_text = f"""
🤖 *Welcome to Samadi Bot, {user.first_name}!*

I'm your all-in-one utility bot with powerful features:

🎯 *Available Tools:*
🔗 URL Shortener - Shorten long links instantly
📊 Word Counter - Analyze any text
🎨 Image Generation - Create AI images
🔄 Image Converter - Convert between formats
📐 Image Resizer - Resize images
📱 QR Generator - Create QR codes

*How to use:*
Just click a button below or use commands!
"""
    
    keyboard = [
        [InlineKeyboardButton("🔗 URL Shortener", callback_data="shorten")],
        [InlineKeyboardButton("📊 Word Counter", callback_data="count")],
        [InlineKeyboardButton("🎨 AI Image Generation", callback_data="image_gen")],
        [InlineKeyboardButton("🔄 Image Converter", callback_data="image_convert")],
        [InlineKeyboardButton("📐 Image Resizer", callback_data="image_resize")],
        [InlineKeyboardButton("📱 QR Code Generator", callback_data="qr")],
        [InlineKeyboardButton("ℹ️ Help / About", callback_data="help")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )
    
    logger.info(f"User {user.username} started the bot")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = """
📖 *Samadi Bot Help Guide*

🔗 *URL Shortener*
• Send any URL or use: `/shorten url`
• Example: `/shorten https://t.me/Trading_Forex_Quotex_Signals`

📊 *Word Counter*
• Send any text or use: `/count text`

🎨 *AI Image Generation*
• Describe what you want or use: `/image prompt`
• Example: `/image a beautiful sunset`

🔄 *Image Converter*
• Send an image with format in caption
• Formats: JPEG, PNG, WEBP

📐 *Image Resizer*
• Send an image with dimensions in caption
• Example: caption "800x600"

📱 *QR Code Generator*
• Send text/URL or use: `/qr text`

*Commands:*
/start - Show main menu
/help - Show this help
/cancel - Cancel current operation
/image prompt - Generate AI image
/shorten url - Shorten a URL
/count text - Count words
/qr text - Generate QR code
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command."""
    context.user_data.clear()
    await update.message.reply_text("✅ Operation cancelled. Use /start to begin again.")

# ===== COMMAND: /shorten =====
async def shorten_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /shorten command."""
    url = " ".join(context.args)
    
    if not url:
        await update.message.reply_text(
            "🔗 *URL Shortener*\n\n"
            "Usage: `/shorten your_url_here`\n"
            "Example: `/shorten https://t.me/Trading_Forex_Quotex_Signals`",
            parse_mode="Markdown"
        )
        return
    
    # Show typing indicator
    await update.message.reply_text("⏳ Shortening your URL...")
    
    # Clean and validate URL
    url = clean_url(url)
    if not is_valid_url(url):
        await update.message.reply_text(
            "❌ Invalid URL. Please send a valid URL starting with http:// or https://"
        )
        return
    
    # Shorten the URL
    short_url, error = shorten_url(url)
    
    if short_url:
        response = f"""
🔗 *URL Shortened Successfully!*

📎 *Original URL:*
{url}

📌 *Shortened URL:*
{short_url}

💾 *Saved:* {len(url) - len(short_url)} characters
"""
        await update.message.reply_text(response, parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"❌ {error}\n\n"
            "Please try:\n"
            "1. Using the menu button\n"
            "2. Or try again in a few minutes"
        )

# ===== COMMAND: /image =====
async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /image command."""
    prompt = " ".join(context.args)
    
    if not prompt:
        await update.message.reply_text(
            "🎨 *AI Image Generation*\n\n"
            "Usage: `/image your prompt here`\n"
            "Example: `/image a beautiful sunset over mountains`",
            parse_mode="Markdown"
        )
        return
    
    await update.message.reply_text("🎨 Generating your image... This may take a moment.")
    
    image_data = generate_ai_image(prompt)
    if image_data:
        await update.message.reply_photo(
            photo=BytesIO(image_data),
            caption=f"🎨 *AI Generated Image*\n\nPrompt: {prompt}",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "❌ Failed to generate image. Please try again with a different prompt."
        )

# ===== COMMAND: /count =====
async def count_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /count command."""
    text = " ".join(context.args)
    
    if not text:
        await update.message.reply_text(
            "📊 *Word Counter*\n\n"
            "Usage: `/count your text here`\n"
            "Example: `/count This is a sample text`",
            parse_mode="Markdown"
        )
        return
    
    stats = count_text_stats(text)
    
    response = f"""
📊 *Text Analysis Results*

📝 *Words:* {stats['words']}
🔤 *Characters:* {stats['characters']}
🔡 *Characters (no spaces):* {stats['characters_no_spaces']}
📖 *Sentences:* {stats['sentences']}
📄 *Paragraphs:* {stats['paragraphs']}
📏 *Lines:* {stats['lines']}
"""
    await update.message.reply_text(response, parse_mode="Markdown")

# ===== COMMAND: /qr =====
async def qr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /qr command."""
    data = " ".join(context.args)
    
    if not data:
        await update.message.reply_text(
            "📱 *QR Code Generator*\n\n"
            "Usage: `/qr your text or URL here`\n"
            "Example: `/qr https://t.me/Trading_Forex_Quotex_Signals`",
            parse_mode="Markdown"
        )
        return
    
    try:
        qr_image = generate_qr_code(data)
        await update.message.reply_photo(
            photo=qr_image,
            caption=f"📱 *QR Code Generated*\n\nContent: {data[:100]}{'...' if len(data) > 100 else ''}",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"QR generation error: {e}")
        await update.message.reply_text("❌ Error generating QR code. Please try again.")

# ============================================================================
# CALLBACK HANDLERS
# ============================================================================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    messages = {
        "shorten": "🔗 *URL Shortener Mode*\n\nSend me a URL to shorten.\nExample: https://www.example.com/very/long/url",
        "count": "📊 *Word Counter Mode*\n\nSend me any text to analyze.",
        "image_gen": "🎨 *AI Image Generation Mode*\n\nDescribe the image you want to generate.\nExample: 'A cat wearing a hat, digital art style'",
        "image_convert": "🔄 *Image Converter Mode*\n\nSend an image with format in caption.\nFormats: JPEG, PNG, WEBP",
        "image_resize": "📐 *Image Resizer Mode*\n\nSend an image with dimensions in caption.\nExample: '800x600'",
        "qr": "📱 *QR Code Generator Mode*\n\nSend me text or a URL to generate a QR code.",
        "help": "ℹ️ *Help & Information*\n\nUse /help for detailed instructions.\nUse /start to see the main menu.",
    }
    
    if data in messages:
        await query.edit_message_text(
            messages[data],
            parse_mode="Markdown",
        )
        context.user_data["mode"] = data

# ============================================================================
# MESSAGE HANDLERS
# ============================================================================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages."""
    user = update.effective_user
    text = update.message.text
    mode = context.user_data.get("mode")
    
    logger.info(f"Text from {user.username}: {text[:50]}... Mode: {mode}")
    
    if not mode:
        await update.message.reply_text(
            "⚠️ Please use /start to choose a tool first!\n\n"
            "📌 *Quick commands:*\n"
            "/image prompt - Generate AI image\n"
            "/shorten url - Shorten a URL\n"
            "/count text - Count words\n"
            "/qr text - Generate QR code",
            parse_mode="Markdown"
        )
        return
    
    # ===== URL SHORTENER =====
    if mode == "shorten":
        url = clean_url(text)
        if not is_valid_url(url):
            await update.message.reply_text(
                "❌ Invalid URL. Please send a valid URL starting with http:// or https://"
            )
            return
        
        await update.message.reply_text("⏳ Shortening your URL...")
        short_url, error = shorten_url(url)
        
        if short_url:
            await update.message.reply_text(
                f"🔗 *Shortened URL:*\n{short_url}",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(f"❌ {error}")
        
        context.user_data["mode"] = None
    
    # ===== WORD COUNTER =====
    elif mode == "count":
        stats = count_text_stats(text)
        response = f"""
📊 *Results:*
📝 Words: {stats['words']}
🔤 Characters: {stats['characters']}
📖 Sentences: {stats['sentences']}
📄 Paragraphs: {stats['paragraphs']}
"""
        await update.message.reply_text(response, parse_mode="Markdown")
        context.user_data["mode"] = None
    
    # ===== AI IMAGE GENERATION =====
    elif mode == "image_gen":
        if len(text) > 200:
            await update.message.reply_text("❌ Prompt too long. Max 200 characters.")
            return
        
        await update.message.reply_text("🎨 Generating image...")
        image_data = generate_ai_image(text)
        if image_data:
            await update.message.reply_photo(
                photo=BytesIO(image_data),
                caption=f"🎨 {text}",
            )
        else:
            await update.message.reply_text("❌ Failed to generate image.")
        context.user_data["mode"] = None
    
    # ===== QR CODE =====
    elif mode == "qr":
        try:
            qr_image = generate_qr_code(text)
            await update.message.reply_photo(photo=qr_image)
        except Exception as e:
            await update.message.reply_text("❌ Error generating QR code.")
        context.user_data["mode"] = None
    
    else:
        await update.message.reply_text("⚠️ Unknown mode. Use /start to restart.")
        context.user_data.clear()

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo messages."""
    mode = context.user_data.get("mode")
    caption = update.message.caption or ""
    
    if mode == "image_convert":
        format_type = re.sub(r'[^a-zA-Z]', '', caption.lower())
        if format_type not in SUPPORTED_FORMATS:
            await update.message.reply_text(f"❌ Invalid format. Supported: {', '.join(SUPPORTED_FORMATS)}")
            return
        
        try:
            await update.message.reply_text("🔄 Converting image...")
            photo_file = await update.message.photo[-1].get_file()
            image_data = await photo_file.download_as_bytearray()
            
            output_format = "jpeg" if format_type == "jpg" else format_type
            converted = convert_image_format(image_data, output_format)
            
            await update.message.reply_document(
                document=converted,
                filename=f"converted.{output_format}",
            )
            context.user_data["mode"] = None
        except Exception as e:
            await update.message.reply_text("❌ Error converting image.")
    
    elif mode == "image_resize":
        dimensions = re.search(r'(\d+)\s*[xX]\s*(\d+)', caption)
        if not dimensions:
            await update.message.reply_text("❌ Please specify dimensions: width x height")
            return
        
        width, height = int(dimensions.group(1)), int(dimensions.group(2))
        if width > 4000 or height > 4000:
            await update.message.reply_text("❌ Dimensions too large. Max 4000x4000")
            return
        
        try:
            await update.message.reply_text("📐 Resizing image...")
            photo_file = await update.message.photo[-1].get_file()
            image_data = await photo_file.download_as_bytearray()
            resized = resize_image(image_data, width, height)
            
            await update.message.reply_document(
                document=resized,
                filename=f"resized_{width}x{height}.png",
            )
            context.user_data["mode"] = None
        except Exception as e:
            await update.message.reply_text("❌ Error resizing image.")
    
    else:
        await update.message.reply_text("📸 Use /start to choose a tool first.")

# ============================================================================
# ERROR HANDLER
# ============================================================================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Update {update} caused error: {context.error}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ Error occurred. Try:\n"
                "1. Use /shorten command directly\n"
                "2. Use /start to restart\n"
                "3. Try again in a few minutes"
            )
    except:
        pass

# ============================================================================
# MAIN
# ============================================================================

def main():
    """Start the bot."""
    logger.info("🤖 Starting Samadi Bot...")
    
    application = Application.builder().token(TOKEN).build()
    
    # Commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("image", image_command))
    application.add_handler(CommandHandler("shorten", shorten_command))
    application.add_handler(CommandHandler("count", count_command))
    application.add_handler(CommandHandler("qr", qr_command))
    
    # Callbacks
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    logger.info("✅ Bot is running!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
