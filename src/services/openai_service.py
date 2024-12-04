"""
Сервис для работы с OpenAI API.
"""
from openai import AsyncOpenAI
from config import Config

class OpenAIService:
    """Сервис для работы с OpenAI API"""
    def __init__(self):
        self.client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)

    async def extract_flight_params(self, text: str) -> dict:
        """Извлечение параметров полета из текста"""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": """Ты помощник по поиску авиабилетов. 
                    Извлеки из текста пользователя следующие параметры:
                    - Город отправления и его IATA код
                    - Город прибытия и его IATA код
                    - Дата вылета (или диапазон дат)
                    - Дата возвращения (или диапазон дат, если есть)
                    Верни результат в формате JSON."""},
                    {"role": "user", "content": text}
                ]
            )
            
            # Извлекаем и парсим JSON из ответа
            result = response.choices[0].message.content
            return result  # TODO: добавить парсинг JSON

        except Exception as e:
            print(f"Error in extract_flight_params: {str(e)}")
            return None

    async def rank_tickets(self, tickets: list) -> list:
        """Ранжирование билетов"""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": """Ранжируй билеты по следующим приоритетам:
                    1. Минимальная цена
                    2. Минимальное время в пути
                    3. Наименьшее число пересадок
                    4. Комфортное время вылета/прилета
                    Верни top-10 вариантов в формате JSON."""},
                    {"role": "user", "content": str(tickets)}
                ]
            )
            
            # Извлекаем и парсим JSON из ответа
            result = response.choices[0].message.content
            return result  # TODO: добавить парсинг JSON

        except Exception as e:
            print(f"Error in rank_tickets: {str(e)}")
            return None
