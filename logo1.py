import logging
import io
from PIL import Image, ImageEnhance
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- الإعدادات ---
TELEGRAM_BOT_TOKEN = '7571096468:AAFyUppNq2Mv9Z79Rrm_Xy7wjAX58_Kt6iw'
LOGO_FILE_PATH = 'logo1.png'
WATERMARK_OPACITY = 0.3  # القيمة الافتراضية
LOGO_WIDTH_RATIO = 1
JPEG_QUALITY = 95

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- تحميل الشعار ---
try:
    original_logo = Image.open(LOGO_FILE_PATH).convert("RGBA")
    logger.info(f"تم تحميل الشعار الأصلي '{LOGO_FILE_PATH}' بنجاح.")
    logo_to_use_in_function = original_logo
except FileNotFoundError:
    logger.error(f"خطأ: لم يتم العثور على ملف الشعار '{LOGO_FILE_PATH}'.")
    logo_to_use_in_function = None
except Exception as e:
    logger.error(f"خطأ أثناء تحميل الشعار: {e}")
    logo_to_use_in_function = None

try:
    Antialias = Image.Resampling.LANCZOS
except AttributeError:
    Antialias = Image.LANCZOS

# --- دالة إضافة العلامة المائية ---
def add_watermark(input_image_stream, original_logo_image):
    if not original_logo_image:
        logger.error("الشعار غير محمل.")
        return None
    try:
        base_image = Image.open(input_image_stream).convert("RGBA")
        img_width, img_height = base_image.size
        logo_width, logo_height = original_logo_image.size
        if logo_width == 0: return None

        new_logo_width = int(img_width * LOGO_WIDTH_RATIO)
        new_logo_height = int(logo_height * (new_logo_width / logo_width))
        resized_logo = original_logo_image.resize((new_logo_width, new_logo_height), Antialias)

        if resized_logo.mode != 'RGBA':
            resized_logo = resized_logo.convert('RGBA')

        alpha = resized_logo.split()[3]
        alpha = ImageEnhance.Brightness(alpha).enhance(WATERMARK_OPACITY)
        resized_logo.putalpha(alpha)

        position = ((img_width - resized_logo.width) // 2, (img_height - resized_logo.height) // 2)
        transparent_layer = Image.new('RGBA', base_image.size, (0, 0, 0, 0))
        transparent_layer.paste(resized_logo, position, resized_logo)
        watermarked_image = Image.alpha_composite(base_image, transparent_layer).convert("RGB")

        output_stream = io.BytesIO()
        watermarked_image.save(output_stream, format='JPEG', quality=JPEG_QUALITY)
        output_stream.seek(0)
        return output_stream
    except Exception as e:
        logger.error(f"خطأ داخل add_watermark: {e}", exc_info=True)
        return None

# --- معالج الصور ---
async def process_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if message.chat.type != 'private':
        return
    if not message.photo:
        return

    photo_file_id = message.photo[-1].file_id
    photo_stream = io.BytesIO()

    try:
        photo_file = await context.bot.get_file(photo_file_id)
        await photo_file.download_to_memory(photo_stream)
        photo_stream.seek(0)

        if logo_to_use_in_function is None:
            raise ValueError("الشعار غير محمل.")

        watermarked_stream = add_watermark(photo_stream, logo_to_use_in_function)
        if not watermarked_stream:
            raise ValueError("فشل في إضافة العلامة المائية.")

        await message.reply_photo(
            photo=InputFile(watermarked_stream, filename=f'watermarked_{photo_file_id}.jpg'),
            caption=f"✅ تم إضافة الشعار بنجاح!\n🔆 الشفافية الحالية: {WATERMARK_OPACITY}"
        )

    except Exception as e:
        logger.error(f"خطأ أثناء معالجة الصورة: {e}", exc_info=True)
        await message.reply_text("حدث خطأ أثناء معالجة الصورة.")
    finally:
        photo_stream.close()

# --- أمر /set_opacity ---
async def set_opacity_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global WATERMARK_OPACITY

    if update.message.chat.type != 'private':
        return

    if not context.args:
        await update.message.reply_text("❗استخدم الأمر بهذا الشكل:\n/set_opacity 0.5")
        return

    try:
        new_opacity = float(context.args[0])
        if not 0 <= new_opacity <= 1:
            raise ValueError

        WATERMARK_OPACITY = new_opacity
        await update.message.reply_text(f"✅ تم تعيين شفافية العلامة المائية إلى {WATERMARK_OPACITY}")
        logger.info(f"تم تغيير الشفافية إلى {WATERMARK_OPACITY}")

    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال رقم بين 0 و 1.\nمثال: /set_opacity 0.4")

# --- أمر /start ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != 'private':
        return
    user_name = update.effective_user.first_name
    await update.message.reply_text(
        f"👋 أهلاً يا {user_name}!\n"
        "أرسل لي أي صورة وسأضيف إليها الشعار وأعيدها إليك.\n\n"
        "🔧 يمكنك التحكم في شفافية الشعار عبر الأمر:\n"
        "/set_opacity 0.5 (بين 0 و 1)\n"
        f"القيمة الحالية: {WATERMARK_OPACITY}"
    )

# --- الدالة الرئيسية ---
def main() -> None:
    logger.info("تشغيل البوت...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("set_opacity", set_opacity_command))
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, process_photo))
    application.run_polling()

if __name__ == '__main__':
    main()
