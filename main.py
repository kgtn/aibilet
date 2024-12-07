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
from datetime import datetime

from src.config import Config
from src.services.openai_service import OpenAIService
from src.services.aviasales_service import AviasalesService
from src.utils.helpers import format_ticket_message
from src.services.dialog_state import DialogStateManager

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
dialog_manager = DialogStateManager()

# Инициализация бота и диспетчера
bot = Bot(token=Config.TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    # Очищаем состояние диалога при старте
    dialog_manager.clear_state(message.from_user.id)
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
        
        # Получаем состояние диалога
        state = dialog_manager.get_state(message.from_user.id)
        
        # Отправляем сообщение о начале поиска
        status_message = await message.answer("🔍 Анализирую ваш запрос...")

        # Извлекаем параметры полета с помощью OpenAI
        current_state = {
            'origin': state.origin,
            'destination': state.destination,
            'departure_at': state.departure_at
        }
        flight_params = await openai_service.extract_flight_params(message.text, current_state)
        
        if not flight_params:
            await status_message.edit_text(
                "❌ Не удалось определить параметры полета.\n"
                "Пожалуйста, попробуйте переформулировать запрос."
            )
            return

        # Обновляем состояние диалога
        state.update_from_params(flight_params)
        
        # Проверяем, все ли параметры заполнены
        if not state.is_complete:
            missing_params = state.get_missing_params()
            questions = []
            
            if "город отправления" in missing_params:
                questions.append("Из какого города вы хотите вылететь?")
            if "город прибытия" in missing_params:
                questions.append("В какой город вы хотите полететь?")
            if "дату вылета" in missing_params:
                questions.append("Когда вы планируете вылет?")
            
            await status_message.edit_text(
                "Мне нужно уточнить несколько деталей:\n" +
                "\n".join(f"❓ {q}" for q in questions)
            )
            return

        # Формируем сообщение о поиске
        search_message = (
            f"🔍 Ищу билеты:\n"
            f"✈️ {state.origin_city} ({state.origin}) → {state.destination_city} ({state.destination})\n"
        )

        # Проверяем, нужен ли гибкий поиск
        is_flexible = flight_params.get('flexible_dates', False)
        date_context = flight_params.get('date_context', {})
        
        if is_flexible:
            if date_context.get('is_start_of_month'):
                search_message += f"📅 Ищу варианты в начале месяца (1-5 число)\n"
            else:
                search_message += f"📅 Ищу варианты около {state.departure_at}\n"
        else:
            search_message += f"📅 Вылет: {state.departure_at}\n"
        
        if state.return_at:
            search_message += f"🔄 Возвращение: {state.return_at}\n"
        else:
            search_message += "🔄 Билет в один конец\n"
        
        await status_message.edit_text(search_message + "\n⏳ Идет поиск...")

        # Ищем билеты через Aviasales API
        search_params = state.to_search_params()
        search_params['date_context'] = date_context
        
        if is_flexible:
            tickets = await aviasales_service.search_tickets_with_flexible_dates(search_params)
        else:
            tickets = await aviasales_service.search_tickets(search_params)
        
        if not tickets.get('success') or not tickets.get('data'):
            await status_message.edit_text(
                "😔 К сожалению, билетов по вашему запросу не найдено.\n"
                "Попробуйте изменить даты или направление."
            )
            return

        # Форматируем и отправляем результаты
        total_found = tickets.get('total_found', len(tickets['data']))
        response = format_ticket_message(tickets['data'])
        
        result_message = (
            f"🎫 Найдено {total_found} вариантов. Вот лучшие из них:\n"
            f"✈️ {state.origin_city} ({state.origin}) → {state.destination_city} ({state.destination})\n"
            f"📅 {state.departure_at}"
        )
        
        if state.return_at:
            result_message += f" - {state.return_at}"
        
        if is_flexible:
            result_message += "\n💡 Показаны лучшие варианты с гибкими датами"
        
        await status_message.edit_text(
            result_message + "\n\n" + response,
            disable_web_page_preview=True,
            parse_mode="HTML"
        )
        
        # Очищаем состояние диалога после успешного поиска
        dialog_manager.clear_state(message.from_user.id)

    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}", exc_info=True)
        await message.answer("😔 Произошла ошибка при обработке запроса. Попробуйте еще раз.")
        # Очищаем состояние диалога при ошибке
        dialog_manager.clear_state(message.from_user.id)

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
