import os
import asyncio
import speech_recognition as sr
from g4f.client import Client
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from pydub import AudioSegment
import edge_tts
from appLor import lore

initial_message = {"role": "system", "content": lore}
history = [initial_message]




from diffusers import StableDiffusionPipeline
import torch
client = Client()
recognizer = sr.Recognizer()



async def generate_image_response(message: str, user_name: str):
 return


async def generate_response(message: str, user_name: str) -> str:
    history.append({"role": "user", "content": f"{user_name} каже: {message}."})
    try:
        response = client.chat.completions.create(model="gpt-4o-mini", messages=history)
        response_message = response.choices[0].message.content
        history.append({"role": "assistant", "content": response_message})
        return response_message
    except Exception as e:
        print(f"Помилка при отриманні відповіді: {e}")
        return "Шо за хуйня, сервер глючить, йопта!"

async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    file_path = f"voice_messages/{update.message.message_id}.ogg"
    wav_file_path = f"voice_messages/{update.message.message_id}.wav"
    
    try:
        os.makedirs("voice_messages", exist_ok=True)
        file = await update.message.voice.get_file()
        await file.download_to_drive(file_path)
        
        AudioSegment.from_ogg(file_path).export(wav_file_path, format="wav")
        
        with sr.AudioFile(wav_file_path) as source:
            audio = recognizer.record(source)
            user_message = recognizer.recognize_google(audio, language="uk-UA")
            history.append({"role": "user", "content": f"{update.message.from_user.first_name} каже: {user_message}."})
            await update.message.reply_text(user_message)
        
    except Exception as e:
        print(f"An error occurred: {e}")
        await update.message.reply_text("Хуйню сказав.")
    finally:
        for path in [file_path, wav_file_path]:
            if os.path.exists(path):
                os.remove(path)

async def generate_voice_message(text: str) -> str:
    file_path = "voice_messages/response.mp3"
    try:
        os.makedirs("voice_messages", exist_ok=True)
        tts = edge_tts.Communicate(text=text, voice="uk-UA-OstapNeural")
        await tts.save(file_path)
        ogg_file_path = file_path.replace(".mp3", ".ogg")
        AudioSegment.from_mp3(file_path).export(ogg_file_path, format="ogg", codec="libopus")

        return ogg_file_path
    except Exception as e:
        print(f"An error occurred: {e}")
        return ''

async def process_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global history
    if len(history) > 10000:
        history = [initial_message]
    
    user_message = update.message.text.lower()
    user_name = update.message.from_user.first_name
    
    if "валера розкажи" in user_message or (update.message.reply_to_message and update.message.reply_to_message.voice and update.message.reply_to_message.from_user.id == context.bot.id):
        message = await generate_response(user_message, user_name)
        file_path = await asyncio.create_task(generate_voice_message(message))
        with open(file_path, "rb") as file:
            await update.message.reply_voice(file, duration=AudioSegment.from_ogg(file_path).duration_seconds)
    elif "валера покажи" in user_message:
        message = await generate_image_response(user_message, user_name)
        await update.message.reply_text(message)        
    elif "валера" in user_message or (update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id):
        message = await generate_response(user_message, user_name)
        await update.message.reply_text(message)
    else:
        history.append({"role": "user", "content": f"{user_name} каже: {user_message}. В: {update.message.date}"})

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = await generate_response("Привітайся з людьми блять", "Валера")
    await update.message.reply_text(message)

async def trigger_words(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update:
        if update.message.voice:
            await handle_voice_message(update, context)
        if update.message.text:
            await process_text_message(update, context)

def main() -> None:
    TOKEN = "7608860683:AAFq_3vq2WCaiIz3euz9OZCsU4CDD16Bf6Q"
    if not TOKEN:
        raise ValueError("Не знайдено токен! Задай змінну оточення TELEGRAM_BOT_TOKEN.")
    
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.ALL, trigger_words))
    print("Бот запущено!")
    application.run_polling()

if __name__ == '__main__':
    main()
