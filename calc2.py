import os
import logging
from io import BytesIO
from telegram import Update, File
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from google import genai
from google.genai import types
from PIL import Image

# =======================================================
# 1. إعدادات المفاتيح والنماذج
# =======================================================
# المفاتيح التي أدخلتها (يرجى التأكد من صلاحية مفتاح Gemini)
GEMINI_API_KEY = "AIzaSyBf7M4FJezWz41QPy7EG1vDaTLthS2S_k0" 
TELEGRAM_BOT_TOKEN = "8297911732:AAFf-M0vg-zdcKejeU9nOj9V1Wipk7tlCGo" 
MODEL_NAME = "gemini-2.5-flash" 

try:
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception:
    client = genai.Client(api_key=GEMINI_API_KEY)
    logging.warning("Gemini Client initialized. Please ensure the API Key is valid.")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# =======================================================
# 2. البرومبت القوي (Strong Prompt) لاستخراج الإجابة ورقم السؤال
# =======================================================
STRONG_PROMPT = """
Analyze the attached image, which contains a Calculus 2 mathematical problem. Your task is to solve the problem and ONLY output the final, simplified answer along with the question number.
Follow this **EXACT** three-part output format, separated by newlines:

1. **Question Number:** Extract the problem number (e.g., 5, 2a, 12.A, etc.). If no explicit number is found, output "N/A".
2. **Multiple Choice Option (If applicable):** If the problem is multiple choice, output the letter of the correct option (e.g., A, B, C, or D). If not multiple choice, output "N/A".
3. **Final Answer (LaTeX):** The final, simplified numerical or analytical answer, enclosed in double dollar signs ($$).

**CRITICAL RULE:** Do not include any explanations, steps, or introductory text. Provide only the final, clean output in the specified three-line format.
"""

SYSTEM_INSTRUCTION = "You are a highly specialized and accurate mathematical machine designed to solve Calculus 2 problems. Your sole output must be the Question Number, the Multiple Choice option (or N/A), and the Final Answer in the exact LaTeX format specified by the user's prompt. You must strictly adhere to the requested three-line output format and exclude all reasoning."


# =======================================================
# 3. دوال معالجة البوت (Handlers)
# =======================================================

async def start(update: Update, context) -> None:
    """Sends a greeting message."""
    await update.message.reply_text('مرحباً! أرسل لي صورة تحوي سؤال كالكولاس 2 وسأقوم بإعطائك رقم السؤال والإجابة النهائية فقط.')

async def handle_photo(update: Update, context) -> None:
    """Processes the received photo with the Gemini API."""
    

    try:
        # 1. الحصول على كائن الملف وتنزيله
        photo_file: File = await update.message.photo[-1].get_file()
        photo_bytes_io = BytesIO()
        await photo_file.download_to_memory(photo_bytes_io)
        photo_bytes = photo_bytes_io.getvalue()
        
        # 2. تحديد نوع MIME
        image_stream = BytesIO(photo_bytes)
        img = Image.open(image_stream)
        mime_type = Image.MIME.get(img.format, 'image/jpeg')

        # 3. تحويل الصورة إلى جزء (Part) لـ Gemini API
        image_part = types.Part.from_bytes(data=photo_bytes, mime_type=mime_type)

        # 4. استدعاء Gemini API
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[STRONG_PROMPT, image_part],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.1 
            )
        )

        # 5. تحليل وإرسال الإجابة النهائية المعزولة (حل مشكلة التنسيق)
        final_output = response.text.strip()
        
        parts = final_output.split('\n', 2)
        
        if len(parts) == 3:
            question_num = parts[0].strip()
            option = parts[1].strip()
            answer = parts[2].strip()
            
            # 5.1. إرسال العنوان باستخدام Markdown (آمن)
            await update.message.reply_text("★ **نتائج التحليل الدقيق للسؤال:**", parse_mode='Markdown')
            
            # 5.2. بناء رسالة النتيجة النهائية
            result_message = f"رقم السؤال: {question_num}\n"
            if option != 'N/A':
                 result_message += f"رمز الإجابة الصحيحة: {option}\n"
            result_message += f"الإجابة النهائية (LaTeX):\n{answer}"
            
            # 5.3. إرسال النتيجة كنص عادي (بدون parse_mode) لتجنب تعارض LaTeX
            await update.message.reply_text(result_message)
            
        else:
            output_message = f"**⚠️ الإخراج غير مطابق للتنسيق المطلوب. الإخراج الخام:**\n{final_output}"
            await update.message.reply_text(output_message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error processing photo: {e}")
        # إرسال رسالة الخطأ كنص عادي لتجنب أي مشاكل تنسيق أخرى
        await update.message.reply_text(f"عذراً، حدث خطأ أثناء معالجة طلبك. الخطأ: {e}", parse_mode=None)


# =======================================================
# 4. دالة main لتشغيل البوت
# =======================================================
def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_photo))

    logger.info("Bot started and polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
