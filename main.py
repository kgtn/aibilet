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

        # Проверяем, есть ли указание на начало месяца
        is_start_of_month = flight_params.get('date_context', {}).get('is_start_of_month', False)
        
        # Обновляем статус-сообщение с полными параметрами
        search_message = (
            f"🔍 Ищу билеты:\n"
            f"✈️ {state.origin_city} ({state.origin}) → {state.destination_city} ({state.destination})\n"
        )
        
        if is_start_of_month:
            search_message += f"📅 Ищу варианты с 1 по 5 число\n"
            if state.return_at:
                search_message += f"🔄 С возвращением через {(datetime.strptime(state.return_at, '%Y-%m-%d') - datetime.strptime(state.departure_at, '%Y-%m-%d')).days} дней"
        else:
            search_message += f"📅 Вылет: {state.departure_at}\n"
            search_message += f"🔄 Возвращение: {state.return_at or 'билет в один конец'}"
        
        await status_message.edit_text(search_message)

        # Ищем билеты через Aviasales API
        search_params = state.to_search_params()
        if is_start_of_month:
            search_params['date_context'] = {'is_start_of_month': True}
            if state.return_at:
                search_params['date_context']['return_days'] = (
                    datetime.strptime(state.return_at, '%Y-%m-%d') - 
                    datetime.strptime(state.departure_at, '%Y-%m-%d')
                ).days
            tickets = await aviasales_service.search_tickets_in_range(search_params)
        else:
            tickets = await aviasales_service.search_tickets(search_params)
        
        if not tickets.get('success') or not tickets.get('data'):
            await status_message.edit_text(
                "😔 К сожалению, билетов по вашему запросу не найдено.\n"
                "Попробуйте изменить даты или направление."
            )
            # Очищаем состояние диалога
            dialog_manager.clear_state(message.from_user.id)
            return

        # Форматируем и отправляем результаты
        response = format_ticket_message(tickets)
        await status_message.edit_text(
            f"🎫 Вот что я нашел:\n"
            f"✈️ {state.origin_city} ({state.origin}) → {state.destination_city} ({state.destination})\n"
            f"📅 {state.departure_at} - {state.return_at or 'без обратного билета'}\n"
            f"💰 Цены указаны в {tickets.get('currency', 'RUB').upper()}\n"
        )
        await message.answer(response, parse_mode="Markdown", disable_web_page_preview=True)
        
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
