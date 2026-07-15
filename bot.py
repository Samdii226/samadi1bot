"""
Samadi Bot - A Multi-Purpose Telegram Bot
Features: URL Shortener, Word Counter, Image Generation, Image Converter, Image Resizer, QR Generator
Deployed on Railway with GitHub integration
"""

import os
import re
import logging
import asyncio
from io import BytesIO
from typing import Optional, Tuple
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
import pyshorteners

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
DEFAULT_IMAGE_SIZE = (512, 512)
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
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

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
    if format_type.lower() == "jpeg":
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
    
    output = BytesIO()
    img.save(output, format=format_type.upper())
    output.seek(0)
    return output

async def generate_ai_image(prompt: str) -> Optional[bytes]:
    """Generate image using Pollinations.ai API."""
    try:
        # Clean prompt for URL
        clean_prompt = prompt.replace(" ", "%20").replace("\n", " ")
        # Add style enhancements
        enhanced_prompt = f"{clean_prompt}, high quality, detailed"
        
        url = f"https://image.pollinations.ai/prompt/{enhanced_prompt}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=API_TIMEOUT) as response:
                if response.status == 200:
                    return await response.read()
                return None
    except Exception as e:
        logger.error(f"AI Image generation error: {e}")
        return None

async def shorten_url(url: str) -> str:
    """Shorten URL using multiple services with fallback."""
    services = [
        ("is.gd", f"https://is.gd/create.php?format=json&url={url}"),
        ("tinyurl", f"https://tinyurl.com/api-create.php?url={url}"),
    ]
    
    for service_name, api_url in services:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.text()
                        if data and "error" not in data.lower():
                            return data.strip()
        except Exception as e:
            logger.warning(f"{service_name} failed: {e}")
            continue
    
    return "❌ Error: Unable to shorten URL. Please try again."

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

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = """
📖 *Samadi Bot Help Guide*

🔗 *URL Shortener*
• Send any URL starting with http:// or https://
• Get a shortened link instantly

📊 *Word Counter*
• Send any text
• Get: Words, Characters, Sentences, Paragraphs, Lines

🎨 *AI Image Generation*
• Describe what you want to see
• Example: "A beautiful sunset over mountains"
• Powered by Pollinations.ai (free)

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

For support: @YourSupportUsername
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command."""
    context.user_data.clear()
    await update.message.reply_text(
        "✅ Operation cancelled. Use /start to begin again."
    )

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
            "Example: https://www.example.com/very/long/url"
        ),
        "count": (
            "📊 *Word Counter Mode*\n\n"
            "Send me any text to analyze.\n"
            "I'll count words, characters, sentences, and paragraphs."
        ),
        "image_gen": (
            "🎨 *AI Image Generation Mode*\n\n"
            "Describe the image you want to generate.\n"
            "Example: 'A cat wearing a hat, digital art style'\n\n"
            "⭐ Pro tip: Be specific for better results!"
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
            "Example: https://t.me/samadi1bot"
        ),
        "help": (
            "ℹ️ *Help & Information*\n\n"
            "Samadi Bot is a multi-purpose utility bot.\n\n"
            "Use /help for detailed instructions.\n"
            "Use /start to see the main menu."
        ),
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
    """Handle text messages based on current mode."""
    user = update.effective_user
    text = update.message.text
    mode = context.user_data.get("mode")
    
    if not mode:
        await update.message.reply_text(
            "⚠️ Please use /start to choose a tool first!"
        )
        return
    
    # ===== URL SHORTENER =====
    if mode == "shorten":
        if not is_valid_url(text):
            await update.message.reply_text(
                "❌ Invalid URL. Please send a valid URL starting with http:// or https://"
            )
            return
        
        await update.message.reply_text("⏳ Shortening your URL...")
        short_url = await shorten_url(text)
        
        response = f"""
🔗 *URL Shortened Successfully!*

📎 *Original URL:*
{text}

📌 *Shortened URL:*
{short_url}

🔢 *Original length:* {len(text)} characters
🔢 *Shortened length:* {len(short_url)} characters
💾 *Saved:* {len(text) - len(short_url)} characters
"""
        await update.message.reply_text(response, parse_mode="Markdown")
        context.user_data["mode"] = None
    
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

📋 *Text Preview:*
_{text[:200]}{'...' if len(text) > 200 else ''}_
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
        
        image_data = await generate_ai_image(text)
        if image_data:
            await update.message.reply_photo(
                photo=BytesIO(image_data),
                caption=f"🎨 *AI Generated Image*\n\nPrompt: {text}\n\nPowered by Pollinations.ai",
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
    
    # ===== IMAGE CONVERTER =====
    if mode == "image_convert":
        format_type = caption.lower().strip()
        
        # Remove common punctuation and clean up
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
            
            # Handle JPEG special case
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
        # Parse dimensions from caption
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
            "📸 Image received! Use /start to choose a tool first."
        )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document messages (for image files)."""
    # Check if it's an image file
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
                "⚠️ An error occurred. Please try again or use /start to restart."
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
