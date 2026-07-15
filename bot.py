"""
Samadi Bot - A Multi-Purpose Telegram Bot
Features: URL Shortener, Word Counter, Image Generation, Image Converter, Image Resizer, QR Generator
Deployed on Railway with GitHub integration
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

# Environment variables
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required!")

# Constants
MAX_IMAGE_DIMENSION = 4000
SUPPORTED_FORMATS = ["jpeg", "png", "webp", "jpg"]
API_TIMEOUT = 30

# Logging setup
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
        # Add http:// if no scheme is present
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def clean_url(url: str) -> str:
    """Clean and format URL."""
    url = url.strip()
    # Remove any trailing punctuation
    url = re.sub(r'[.,;!?]+$', '', url)
    # Add https:// if no scheme
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
    
    # Handle JPEG special case (no alpha channel)
    if format_type.lower() == "jpeg" or format_type.lower() == "jpg":
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
    
    output = BytesIO()
    img.save(output, format=format_type.upper())
    output.seek(0)
    return output

def generate_ai_image(prompt: str) -> Optional[bytes]:
    """Generate image using Pollinations.ai API."""
    try:
        # Clean prompt for URL
        clean_prompt = prompt.replace(" ", "%20").replace("\n", " ")
        # Add style enhancements
        enhanced_prompt = f"{clean_prompt}, high quality, detailed"
        
        url = f"https://image.pollinations.ai/prompt/{enhanced_prompt}?width=512&height=512&nologo=true"
        
        response = requests.get(url, timeout=API_TIMEOUT)
        if response.status_code == 200:
            return response.content
        return None
    except Exception as e:
        logger.error(f"AI Image generation error: {e}")
        return None

def shorten_url(url: str) -> tuple:
    """
    Shorten URL using multiple services with fallback.
    Returns: (shortened_url, service_name, error_message)
    """
    url = clean_url(url)
    
    # Service 1: is.gd (Primary)
    try:
        response = requests.get(
            "https://is.gd/create.php",
            params={
                "format": "json",
                "url": url
            },
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if "shorturl" in data:
                return (data["shorturl"], "is.gd", None)
            elif "errormessage" in data:
                logger.warning(f"is.gd error: {data['errormessage']}")
        else:
            logger.warning(f"is.gd status: {response.status_code}")
    except Exception as e:
        logger.warning(f"is.gd failed: {e}")
    
    # Service 2: TinyURL (Fallback 1)
    try:
        response = requests.get(
            "https://tinyurl.com/api-create.php",
            params={"url": url},
            timeout=10
        )
        if response.status_code == 200:
            short_url = response.text.strip()
            if short_url and "error" not in short_url.lower():
                return (short_url, "tinyurl.com", None)
        else:
            logger.warning(f"TinyURL status: {response.status_code}")
    except Exception as e:
        logger.warning(f"TinyURL failed: {e}")
    
    # Service 3: Shrtcode (Fallback 2)
    try:
        response = requests.get(
            f"https://api.shrtco.de/v2/shorten",
            params={"url": url},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("ok") and "result" in data:
                return (data["result"]["short_link"], "shrtco.de", None)
    except Exception as e:
        logger.warning(f"Shrtcode failed: {e}")
    
    # All services failed
    return (None, None, "All URL shortening services are currently unavailable. Please try again later.")

# ============================================================================
# BOT HANDLERS
# ============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - Show main menu."""
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
Just click a button below and follow the instructions!

Made with ❤️ for your daily tasks
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
• Send any URL starting with http:// or https://
• Get a shortened link instantly
• Example: `/shorten https://t.me/Trading_Forex_Quotex_Signals`

📊 *Word Counter*
• Send any text
• Get: Words, Characters, Sentences, Paragraphs, Lines

🎨 *AI Image Generation*
• Describe what you want to see
• Example: "/image A beautiful sunset over mountains"

🔄 *Image Converter*
• Send an image with format in caption
• Formats: JPEG, PNG, WEBP
• Example: caption "png"

📐 *Image Resizer*
• Send an image with dimensions in caption
• Format: width x height
• Example: caption "800x600"

📱 *QR Code Generator*
• Send any text or URL
• Get a QR code image

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
    await update.message.reply_text(
        "✅ Operation cancelled. Use /start to begin again."
    )

# ===== COMMAND: /image for direct image generation =====
async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /image command - Generate image from prompt."""
    prompt = " ".join(context.args)
    
    if not prompt:
        await update.message.reply_text(
            "🎨 *AI Image Generation*\n\n"
            "Usage: `/image your prompt here`\n"
            "Example: `/image a beautiful sunset over mountains`\n\n"
            "Or use the menu button for more options!",
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

# ===== COMMAND: /shorten for direct URL shortening =====
async def shorten_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /shorten command - Shorten URL directly."""
    url = " ".join(context.args)
    
    if not url:
        await update.message.reply_text(
            "🔗 *URL Shortener*\n\n"
            "Usage: `/shorten your_url_here`\n"
            "Example: `/shorten https://t.me/Trading_Forex_Quotex_Signals`",
            parse_mode="Markdown"
        )
        return
    
    await update.message.reply_text("⏳ Shortening your URL...")
    
    # Clean and validate URL
    url = clean_url(url)
    if not is_valid_url(url):
        await update.message.reply_text(
            "❌ Invalid URL. Please send a valid URL starting with http:// or https://"
        )
        return
    
    # Shorten the URL
    short_url, service, error = shorten_url(url)
    
    if short_url:
        response = f"""
🔗 *URL Shortened Successfully!*

📎 *Original URL:*
{url}

📌 *Shortened URL:*
{short_url}

🔢 *Original length:* {len(url)} characters
🔢 *Shortened length:* {len(short_url)} characters
💾 *Saved:* {len(url) - len(short_url)} characters
🏷️ *Service:* {service}
"""
        await update.message.reply_text(response, parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"❌ {error}\n\n"
            "Please try:\n"
            "1. Sending the URL directly\n"
            "2. Using the button menu\n"
            "3. Or try again in a few minutes"
        )

# ===== COMMAND: /count for direct word counting =====
async def count_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /count command - Count words directly."""
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

# ===== COMMAND: /qr for direct QR generation =====
async def qr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /qr command - Generate QR code directly."""
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
    """Handle button clicks from inline keyboard."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    messages = {
        "shorten": (
            "🔗 *URL Shortener Mode*\n\n"
            "Please send me a URL to shorten.\n"
            "Example: https://www.example.com/very/long/url\n\n"
            "Or use: `/shorten your_url`"
        ),
        "count": (
            "📊 *Word Counter Mode*\n\n"
            "Send me any text to analyze.\n"
            "I'll count words, characters, sentences, and paragraphs.\n\n"
            "Or use: `/count your text here`"
        ),
        "image_gen": (
            "🎨 *AI Image Generation Mode*\n\n"
            "Describe the image you want to generate.\n"
            "Example: 'A cat wearing a hat, digital art style'\n\n"
            "⭐ Pro tip: Be specific for better results!\n"
            "Or use: `/image your prompt here`"
        ),
        "image_convert": (
            "🔄 *Image Converter Mode*\n\n"
            "Send me an image with format in caption.\n"
            "Supported formats: JPEG, PNG, WEBP\n\n"
            "Example: Send a photo with caption 'png'"
        ),
        "image_resize": (
            "📐 *Image Resizer Mode*\n\n"
            "Send me an image with dimensions in caption.\n"
            "Format: width x height\n\n"
            "Example: Send a photo with caption '500x500'"
        ),
        "qr": (
            "📱 *QR Code Generator Mode*\n\n"
            "Send me text or a URL to generate a QR code.\n"
            "Example: https://t.me/Trading_Forex_Quotex_Signals\n\n"
            "Or use: `/qr your text here`"
        ),
        "help": (
            "ℹ️ *Help & Information*\n\n"
            "Samadi Bot is a multi-purpose utility bot.\n\n"
            "Use /help for detailed instructions.\n"
            "Use /start to see the main menu.\n\n"
            "📌 *Quick Commands:*\n"
            "/image prompt - Generate AI image\n"
            "/shorten url - Shorten a URL\n"
            "/count text - Count words\n"
            "/qr text - Generate QR code"
        ),
    }
    
    if data in messages:
        await query.edit_message_text(
            messages[data],
            parse_mode="Markdown",
        )
        context.user_data["mode"] = data
        logger.info(f"User {update.effective_user.username} selected mode: {data}")

# ============================================================================
# MESSAGE HANDLERS
# ============================================================================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages based on current mode."""
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
        # Clean and validate URL
        url = clean_url(text)
        if not is_valid_url(url):
            await update.message.reply_text(
                "❌ Invalid URL. Please send a valid URL starting with http:// or https://\n"
                "Example: https://www.example.com"
            )
            return
        
        await update.message.reply_text("⏳ Shortening your URL...")
        short_url, service, error = shorten_url(url)
        
        if short_url:
            response = f"""
🔗 *URL Shortened Successfully!*

📎 *Original URL:*
{url}

📌 *Shortened URL:*
{short_url}

🏷️ *Service:* {service}
"""
            await update.message.reply_text(response, parse_mode="Markdown")
            context.user_data["mode"] = None
        else:
            await update.message.reply_text(
                f"❌ {error}\n\n"
                "Please try:\n"
                "1. Using the /shorten command\n"
                "2. Or try again in a few minutes"
            )
    
    # ===== WORD COUNTER =====
    elif mode == "count":
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
        context.user_data["mode"] = None
    
    # ===== AI IMAGE GENERATION =====
    elif mode == "image_gen":
        if len(text) > 200:
            await update.message.reply_text(
                "❌ Prompt too long. Please keep it under 200 characters."
            )
            return
        
        await update.message.reply_text("🎨 Generating your image... This may take a moment.")
        
        image_data = generate_ai_image(text)
        if image_data:
            await update.message.reply_photo(
                photo=BytesIO(image_data),
                caption=f"🎨 *AI Generated Image*\n\nPrompt: {text}",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                "❌ Failed to generate image. Please try again with a different prompt."
            )
        context.user_data["mode"] = None
    
    # ===== QR CODE GENERATOR =====
    elif mode == "qr":
        if len(text) > 2000:
            await update.message.reply_text("❌ Text too long for QR code. Max 2000 characters.")
            return
        
        try:
            qr_image = generate_qr_code(text)
            await update.message.reply_photo(
                photo=qr_image,
                caption=f"📱 *QR Code Generated*\n\nContent: {text[:100]}{'...' if len(text) > 100 else ''}",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"QR generation error: {e}")
            await update.message.reply_text("❌ Error generating QR code. Please try again.")
        
        context.user_data["mode"] = None
    
    # ===== IMAGE CONVERTER (text handler) =====
    elif mode == "image_convert":
        await update.message.reply_text(
            "📸 Please send an image with the format in the caption.\n"
            "Example: Send a photo with caption 'png'"
        )
    
    # ===== IMAGE RESIZER (text handler) =====
    elif mode == "image_resize":
        await update.message.reply_text(
            "📸 Please send an image with dimensions in the caption.\n"
            "Example: Send a photo with caption '800x600'"
        )
    
    else:
        await update.message.reply_text(
            "⚠️ Unknown mode. Please use /start to choose a tool."
        )
        context.user_data.clear()

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo messages for conversion and resizing."""
    mode = context.user_data.get("mode")
    caption = update.message.caption or ""
    
    logger.info(f"Photo received. Mode: {mode}, Caption: {caption}")
    
    # ===== IMAGE CONVERTER =====
    if mode == "image_convert":
        format_type = caption.lower().strip()
        format_type = re.sub(r'[^a-zA-Z]', '', format_type)
        
        if format_type not in SUPPORTED_FORMATS:
            await update.message.reply_text(
                f"❌ Invalid format. Supported: {', '.join(SUPPORTED_FORMATS)}\n"
                "Example caption: png, jpeg, webp"
            )
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
                caption=f"✅ *Image converted to {output_format.upper()}*",
                parse_mode="Markdown",
            )
            context.user_data["mode"] = None
            
        except Exception as e:
            logger.error(f"Image conversion error: {e}")
            await update.message.reply_text("❌ Error converting image. Please try again.")
    
    # ===== IMAGE RESIZER =====
    elif mode == "image_resize":
        dimensions = re.search(r'(\d+)\s*[xX]\s*(\d+)', caption)
        
        if not dimensions:
            await update.message.reply_text(
                "❌ Please specify dimensions in caption: width x height\n"
                "Example: 800x600"
            )
            return
        
        width = int(dimensions.group(1))
        height = int(dimensions.group(2))
        
        if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
            await update.message.reply_text(
                f"❌ Dimensions too large. Maximum: {MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION}"
            )
            return
        
        if width < 10 or height < 10:
            await update.message.reply_text("❌ Dimensions too small. Minimum: 10x10")
            return
        
        try:
            await update.message.reply_text("📐 Resizing image...")
            
            photo_file = await update.message.photo[-1].get_file()
            image_data = await photo_file.download_as_bytearray()
            
            resized = resize_image(image_data, width, height)
            
            await update.message.reply_document(
                document=resized,
                filename=f"resized_{width}x{height}.png",
                caption=f"✅ *Image resized to {width}x{height}*",
                parse_mode="Markdown",
            )
            context.user_data["mode"] = None
            
        except Exception as e:
            logger.error(f"Image resize error: {e}")
            await update.message.reply_text("❌ Error resizing image. Please try again.")
    
    else:
        await update.message.reply_text(
            "📸 Image received! Use /start to choose a tool first.\n\n"
            "📌 *Quick commands:*\n"
            "/image prompt - Generate AI image\n"
            "/shorten url - Shorten a URL\n"
            "/count text - Count words\n"
            "/qr text - Generate QR code",
            parse_mode="Markdown"
        )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document messages (for image files)."""
    file = update.message.document
    mime_type = file.mime_type or ""
    
    if mime_type.startswith("image/"):
        await update.message.reply_text(
            "📸 Image document received! Please use /start to choose a tool.\n"
            "Note: For best results, send photos directly (not as files)."
        )
    else:
        await update.message.reply_text(
            "📄 Document received. I only process images. Use /start to see available tools."
        )

# ============================================================================
# ERROR HANDLER
# ============================================================================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}")
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ An error occurred. Please try again or use /start to restart.\n\n"
                "If the problem persists, try using the /shorten command directly."
            )
    except:
        pass

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Start the bot."""
    logger.info("🤖 Starting Samadi Bot...")
    logger.info(f"Bot token: {TOKEN[:10]}... (hidden for security)")
    
    # Build application
    application = Application.builder().token(TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    
    # Direct command handlers
    application.add_handler(CommandHandler("image", image_command))
    application.add_handler(CommandHandler("shorten", shorten_command))
    application.add_handler(CommandHandler("count", count_command))
    application.add_handler(CommandHandler("qr", qr_command))
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Add message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start the bot with long polling
    logger.info("✅ Bot is running! Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
