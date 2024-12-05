"""
Сервис для работы с OpenAI API.
"""
import json
import logging
from openai import AsyncOpenAI
from ..config import Config

logger = logging.getLogger(__name__)

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
                    Извлеки из текста пользователя параметры для поиска билетов.
                    
                    Формат ответа JSON:
                    {
                        "origin": "Название города отправления",
                        "destination": "Название города прибытия",
                        "origin_airport": "IATA код аэропорта отправления",
                        "destination_airport": "IATA код аэропорта прибытия",
                        "departure_at": "YYYY-MM-DD",
                        "return_at": "YYYY-MM-DD или null"
                    }
                    
                    Правила:
                    1. Даты в формате YYYY-MM-DD
                    2. Первая дата из диапазона
                    3. Null если возврат не указан
                    4. IATA коды в верхнем регистре
                    5. Города с большой буквы"""},
                    {"role": "user", "content": text}
                ],
                response_format={"type": "json_object"}
            )
            
            # Получаем и парсим JSON из ответа
            result = json.loads(response.choices[0].message.content)
            logger.info(f"Извлеченные параметры: {result}")
            return result

        except Exception as e:
            logger.error(f"Ошибка извлечения параметров: {e}", exc_info=True)
            return None

    async def rank_tickets(self, tickets: list) -> dict:
        """Ранжирование билетов"""
        try:
            logger.info("Входные данные для ранжирования:")
            for ticket in tickets:
                logger.info(f"Билет до ранжирования: {json.dumps(ticket, ensure_ascii=False)}")

            system_content = """Ранжируй билеты по следующим критериям (в порядке приоритета):
1. Минимальная цена (price) — главный критерий.
2. Минимальное время в пути (duration_to, duration_back) — важнее, если разница в цене меньше 20%.
3. Наименьшее число пересадок (transfers) — в случае одинаковой цены и времени в пути.
4. Удобное время вылета (6:00-23:00) — применяй, если остальные критерии равны.

ВАЖНО: Сохраняй ВСЕ поля билета без изменений:
- Точные значения длительности полета (duration_to, duration_back)
- Все временные метки и цены
- Все остальные поля, включая link

Для ранжирования используй весовые коэффициенты:
- Цена: вес 5
- Время в пути: вес 4
- Количество пересадок: вес 2
- Время вылета: вес 1

Формат ответа JSON:
{
    "ranked_tickets": [
        {
            "price": число,
            "origin": "город",
            "destination": "город",
            "departure_at": "YYYY-MM-DDTHH:mm:ss",
            "arrival_at": "YYYY-MM-DDTHH:mm:ss",
            "duration_to": число,
            "duration_back": число,
            "transfers": число,
            "return_at": "YYYY-MM-DDTHH:mm:ss или null",
            "link": "оригинальная ссылка без изменений"
        }
    ],
    "summary": "Краткое описание ранжирования"
}"""

            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": json.dumps(tickets, ensure_ascii=False)}
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            logger.info(f"Ранжированные билеты: {len(result.get('ranked_tickets', []))}")
            for ticket in result.get('ranked_tickets', []):
                logger.info(f"Билет после ранжирования: {json.dumps(ticket, ensure_ascii=False)}")
            
            return result

        except Exception as e:
            logger.error(f"Ошибка ранжирования билетов: {e}", exc_info=True)
            return None
