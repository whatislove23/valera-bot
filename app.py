import os
import asyncio
import speech_recognition as sr
from g4f.client import Client
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from pydub import AudioSegment
import edge_tts
from appLor import lore
from dotenv import load_dotenv
import uvicorn
from fastapi import FastAPI

# Initialize FastAPI
app = FastAPI()

# Global Variables
history = [{"role": "system", "content": lore}]
client = Client()
recognizer = sr.Recognizer()


@app.get("/")
def get_history():
    """Returns conversation history."""
    return history


async def generate_response(message: str, user_name: str) -> str:
    """Generates a text response based on chat history."""
    history.append({"role": "user", "content": f"{user_name} каже: {message}."})
    try:
        response = client.chat.completions.create(model="gpt-4o-mini", messages=history)
        response_message = response.choices[0].message.content
        history.append({"role": "assistant", "content": response_message})
        return response_message
    except Exception as e:
        print(f"Помилка при отриманні відповіді: {e}")
        return "Шо за хуйня, сервер глючить, йопта!"


async def generate_voice_message(text: str) -> str:
    """Converts text to a voice message."""
    file_path = "voice_messages/response.mp3"
    os.makedirs("voice_messages", exist_ok=True)
    
    try:
        tts = edge_tts.Communicate(text=text, voice="uk-UA-OstapNeural")
        await tts.save(file_path)
        ogg_file_path = file_path.replace(".mp3", ".ogg")
        AudioSegment.from_mp3(file_path).export(ogg_file_path, format="ogg", codec="libopus")
        return ogg_file_path
    except Exception as e:
        print(f"Помилка в генерації голосового повідомлення: {e}")
        return ''


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processes voice messages from users."""
    file_path = f"voice_messages/{update.message.message_id}.ogg"
    wav_file_path = f"voice_messages/{update.message.message_id}.wav"

    os.makedirs("voice_messages", exist_ok=True)

    try:
        file = await update.message.voice.get_file()
        await file.download_to_drive(file_path)
        AudioSegment.from_ogg(file_path).export(wav_file_path, format="wav")

        with sr.AudioFile(wav_file_path) as source:
            audio = recognizer.record(source)
            user_message = recognizer.recognize_google(audio, language="uk-UA")

        history.append({"role": "user", "content": f"{update.message.from_user.first_name} каже: {user_message}."})
        await update.message.reply_text(user_message)

    except Exception as e:
        print(f"Помилка обробки голосового повідомлення: {e}")
        await update.message.reply_text("Хуйню сказав.")
    finally:
        for path in [file_path, wav_file_path]:
            if os.path.exists(path):
                os.remove(path)


async def process_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processes text messages from users."""
    global history
    if len(history) > 1000:
        history = [{"role": "system", "content": lore}]

    user_message = update.message.text.lower()
    user_name = update.message.from_user.first_name

    if "валера розкажи" in user_message or (update.message.reply_to_message and update.message.reply_to_message.voice and update.message.reply_to_message.from_user.id == context.bot.id):
        message = await generate_response(user_message, user_name)
        file_path = await generate_voice_message(message)
        if file_path:
            with open(file_path, "rb") as file:
                await update.message.reply_voice(file, duration=AudioSegment.from_ogg(file_path).duration_seconds)

    elif "валера покажи" in user_message:
        await update.message.reply_text("Сам знайди")  # Stub for image response

    elif "валера" in user_message or (update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id):
        message = await generate_response(user_message, user_name)
        await update.message.reply_text(message)

    else:
        history.append({"role": "user", "content": f"{user_name} каже: {user_message}. В: {update.message.date}"})


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command."""
    message = await generate_response("Привітайся з людьми блять", "Валера")
    await update.message.reply_text(message)


async def trigger_words(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles all text and voice messages."""
    if update.message:
        if update.message.text:
            await process_text_message(update, context)
        elif update.message.voice:
            await handle_voice_message(update, context)


async def start_telegram_bot() -> None:
    """Initializes and starts the Telegram bot."""
    load_dotenv()
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise ValueError("Не знайдено токен! Задай змінну оточення TELEGRAM_BOT_TOKEN.")

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.ALL, trigger_words))

    print("Бот запущено!")
    await application.run_polling()


async def start_fastapi() -> None:
    """Runs FastAPI inside the asyncio event loop."""
    config = uvicorn.Config(app, host="0.0.0.0", port=int(os.getenv("PORT", 4000)))
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    """Runs both FastAPI and Telegram bot concurrently."""
    await asyncio.gather(start_fastapi(), start_telegram_bot())


if __name__ == "__main__":
    asyncio.run(main())