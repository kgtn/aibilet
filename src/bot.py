"""
Основной файл Telegram бота для поиска авиабилетов.
"""
import asyncio
import logging
from telegram import Update
from telegram.ext import Application

from config import Config
from handlers.message_handler import MessageHandlers

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main():
    """Запуск бота"""
    try:
        # Проверка наличия токена
        if not Config.TELEGRAM_TOKEN:
            raise ValueError("Telegram token not found in environment variables")

        # Инициализация бота
        application = Application.builder().token(Config.TELEGRAM_TOKEN).build()
        
        # Инициализация обработчиков
        handlers = MessageHandlers()
        
        # Добавление обработчиков
        application.add_handler(handlers.get_handler())
        
        # Запуск бота
        logger.info("Starting bot...")
        await application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Error starting bot: {str(e)}")
        raise

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot stopped due to error: {str(e)}")
