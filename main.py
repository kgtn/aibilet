"""
Основной файл Telegram бота для поиска авиабилетов.
"""
import os
import asyncio
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart, Command

from src.config import Config
from src.services.openai_service import OpenAIService
from src.services.aviasales_service import AviasalesService
from src.utils.helpers import format_ticket_message

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация сервисов
openai_service = OpenAIService()
aviasales_service = AviasalesService()

# Инициализация бота и диспетчера
bot = Bot(token=Config.TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    await message.answer(
        "Привет! Я бот для поиска авиабилетов. 🛫\n"
        "Просто напиши мне, куда и когда хочешь полететь, например:\n"
        "- Найди билеты из Москвы в Париж на начало июня\n"
        "- Хочу слетать в Барселону из Питера в июле"
    )

@dp.message()
async def handle_message(message: Message):
    """Обработка входящих сообщений"""
    try:
        # Логируем входящее сообщение
        logger.info(f"Получен запрос от {message.from_user.username}: {message.text}")
        
        # Отправляем сообщение о начале поиска
        status_message = await message.answer("🔍 Анализирую ваш запрос...")

        # Извлекаем параметры полета с помощью OpenAI
        flight_params = await openai_service.extract_flight_params(message.text)
        
        if not flight_params:
            await status_message.edit_text(
                "❌ Не удалось определить параметры полета.\n"
                "Пожалуйста, укажите:\n"
                "- город отправления\n"
                "- город прибытия\n"
                "- предпочтительные даты"
            )
            return

        # Логируем полученные параметры
        logger.info(f"Извлеченные параметры: {flight_params}")
        
        # Обновляем статус-сообщение
        await status_message.edit_text(
            f"🔍 Ищу билеты:\n"
            f"✈️ {flight_params['origin']} ({flight_params['origin_airport']}) → "
            f"{flight_params['destination']} ({flight_params['destination_airport']})\n"
            f"📅 Вылет: {flight_params['departure_at']}\n"
            f"🔄 Возвращение: {flight_params['return_at'] or 'билет в один конец'}"
        )

        # Ищем билеты через Aviasales API
        tickets = await aviasales_service.search_tickets(flight_params)
        
        if not tickets:
            await status_message.edit_text("😔 К сожалению, билетов по вашему запросу не найдено.")
            return

        # Ранжируем билеты с помощью OpenAI
        ranked_result = await openai_service.rank_tickets(tickets)
        
        if not ranked_result or 'ranked_tickets' not in ranked_result:
            await status_message.edit_text("😔 Произошла ошибка при обработке результатов.")
            return

        # Форматируем и отправляем результаты
        response = format_ticket_message(ranked_result['ranked_tickets'])
        await status_message.edit_text("🎫 Вот что я нашел:")
        await message.answer(response)

        # Отправляем краткое описание выбора
        if 'summary' in ranked_result:
            await message.answer(f"💡 {ranked_result['summary']}")

    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}", exc_info=True)
        await message.answer("😔 Произошла ошибка при обработке запроса. Попробуйте позже.")

async def main():
    """Запуск бота"""
    try:
        logger.info("Запуск бота...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Бот остановлен из-за ошибки: {e}")
