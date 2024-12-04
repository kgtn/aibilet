"""
Обработчик сообщений от пользователя.
"""
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from services.openai_service import OpenAIService
from services.aviasales_service import AviasalesService
from utils.helpers import format_ticket_message

class MessageHandlers:
    """Класс обработчиков сообщений"""
    def __init__(self):
        self.openai_service = OpenAIService()
        self.aviasales_service = AviasalesService()

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка входящих сообщений"""
        try:
            # Получаем текст сообщения
            message_text = update.message.text
            
            # Отправляем сообщение о начале обработки
            await update.message.reply_text(" Ищу подходящие билеты...")

            # Извлекаем параметры полета с помощью OpenAI
            flight_params = await self.openai_service.extract_flight_params(message_text)
            
            if not flight_params:
                await update.message.reply_text(" Не удалось определить параметры полета из вашего сообщения. "
                                              "Пожалуйста, укажите город отправления, город прибытия и даты.")
                return

            # Ищем билеты через Aviasales API
            tickets = await self.aviasales_service.search_tickets(flight_params)
            
            if not tickets:
                await update.message.reply_text(" К сожалению, билетов по вашему запросу не найдено.")
                return

            # Ранжируем билеты с помощью OpenAI
            ranked_tickets = await self.openai_service.rank_tickets(tickets)
            
            # Форматируем и отправляем результаты
            response = format_ticket_message(ranked_tickets)
            await update.message.reply_text(response)

        except Exception as e:
            await update.message.reply_text(" Произошла ошибка при обработке запроса. Попробуйте позже.")
            print(f"Error in handle_message: {str(e)}")

    def get_handler(self):
        """Возвращает обработчик сообщений"""
        return MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
