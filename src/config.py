"""
Конфигурация и загрузка переменных окружения.
"""
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

class Config:
    """Конфигурационные параметры"""
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    AVIASALES_TOKEN = os.getenv('AVIASALES_API_KEY')
