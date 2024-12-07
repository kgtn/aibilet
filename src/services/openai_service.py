"""
Сервис для работы с OpenAI API.
"""
import json
import logging
from openai import AsyncOpenAI
from ..config import Config
from datetime import datetime, timedelta
from typing import Dict
import re

logger = logging.getLogger(__name__)

class OpenAIService:
    """Сервис для работы с OpenAI API"""
    def __init__(self):
        self.client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = "gpt-3.5-turbo"

    async def extract_flight_params(self, text: str, current_state: dict = None) -> dict:
        """Извлечение параметров полета из текста"""
        try:
            logger.info(f"Начало извлечения параметров. Текст: {text}, Текущее состояние: {json.dumps(current_state, ensure_ascii=False) if current_state else 'None'}")
            
            current_date = datetime.now()
            
            example_response = {
                "origin": "LED",
                "destination": "BKK",
                "origin_city": "Санкт-Петербург",
                "destination_city": "Бангкок",
                "departure_at": "2025-02-01",
                "return_at": "2025-02-15"
            }
            
            system_content = f"""Ты помощник по поиску авиабилетов. Извлеки параметры полета из текста. Текущая дата: {current_date.strftime('%Y-%m-%d')}.
            Верни JSON с полями:
            - origin (IATA код города отправления, например LED для Санкт-Петербурга)
            - destination (IATA код города назначения, например BKK для Бангкока)
            - origin_city (название города отправления)
            - destination_city (название города назначения)
            - departure_at (дата вылета в формате YYYY-MM-DD)
            - return_at (дата возвращения в формате YYYY-MM-DD, если указано)
            
            Примеры городов и их IATA кодов:
            Москва: MOW
            Санкт-Петербург: LED
            Новосибирск: OVB
            Екатеринбург: SVX
            Казань: KZN
            Бангкок: BKK
            Пхукет: HKT
            
            Правила обработки дат:
            1. Если указано "начало месяца" - установи дату на 1 число указанного месяца
            2. Если указана длительность поездки (например, "на 2 недели"), укажи соответствующую дату возврата
            3. Если год не указан и дата уже прошла в текущем году - используй следующий год
            
            Пример запроса: "из Санкт-Петербурга в Бангкок в начале февраля на 2 недели"
            Пример ответа: {json.dumps(example_response, ensure_ascii=False, indent=4)}
            """

            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": text}
            ]

            logger.debug(f"Отправка запроса к OpenAI. Сообщения: {json.dumps(messages, ensure_ascii=False)}")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            response_text = response.choices[0].message.content
            logger.info(f"Получен ответ от OpenAI: {response_text}")
            
            try:
                params = json.loads(response_text)
                
                # Валидация обязательных полей
                required_fields = ['origin', 'destination', 'origin_city', 'destination_city']
                missing_fields = [field for field in required_fields if not params.get(field)]
                if missing_fields:
                    logger.warning(f"Отсутствуют обязательные поля в ответе OpenAI: {', '.join(missing_fields)}")
                    return {}
                
                # Валидация IATA кодов
                for field in ['origin', 'destination']:
                    if iata_code := params.get(field):
                        if not (len(iata_code) == 3 and iata_code.isupper() and iata_code.isalpha()):
                            logger.error(f"Некорректный IATA код {field}: {iata_code}")
                            return {}
                
                # Обработка дат
                if "начал" in text.lower() and any(month in text.lower() for month in ["январ", "феврал", "март", "апрел", "май", "июн", "июл", "август", "сентябр", "октябр", "ноябр", "декабр"]):
                    logger.info("Обнаружен запрос на начало месяца")
                    current_year = datetime.now().year
                    month_names = {
                        "январ": 1, "феврал": 2, "март": 3, "апрел": 4,
                        "май": 5, "июн": 6, "июл": 7, "август": 8,
                        "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12
                    }
                    
                    for month_name, month_num in month_names.items():
                        if month_name in text.lower():
                            if month_num < datetime.now().month:
                                year = current_year + 1
                            else:
                                year = current_year
                            
                            departure_date = datetime(year, month_num, 1)
                            params['departure_at'] = departure_date.strftime('%Y-%m-%d')
                            
                            # Обработка длительности поездки
                            weeks_match = re.search(r'(\d+)\s*недел', text.lower())
                            if weeks_match:
                                weeks = int(weeks_match.group(1))
                                return_date = departure_date + timedelta(weeks=weeks)
                                params['return_at'] = return_date.strftime('%Y-%m-%d')
                                logger.info(f"Установлены даты: вылет {params['departure_at']}, возврат {params['return_at']}")
                            break
                
                # Проверяем корректность дат
                if params.get('departure_at') and params.get('return_at'):
                    departure_date = datetime.strptime(params['departure_at'], '%Y-%m-%d')
                    return_date = datetime.strptime(params['return_at'], '%Y-%m-%d')
                    days_diff = (return_date - departure_date).days
                    
                    # Если в тексте указаны недели, проверяем соответствие
                    weeks_match = re.search(r'(\d+)\s*недел', text.lower())
                    if weeks_match:
                        expected_weeks = int(weeks_match.group(1))
                        expected_days = expected_weeks * 7
                        if abs(days_diff - expected_days) > 2:  # Допускаем погрешность в 2 дня
                            logger.warning(f"Некорректная длительность поездки. Ожидалось {expected_days} дней, получено {days_diff} дней")
                            params['return_at'] = (departure_date + timedelta(days=expected_days)).strftime('%Y-%m-%d')
                            logger.info(f"Скорректирована дата возврата на {params['return_at']}")
                
                logger.info(f"Финальные извлеченные параметры: {json.dumps(params, ensure_ascii=False)}")
                return params
                
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга JSON из ответа OpenAI: {str(e)}\nОтвет: {response_text}")
                return {}
                
        except Exception as e:
            logger.error(f"Критическая ошибка при извлечении параметров полета: {str(e)}", exc_info=True)
            return {}

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
            "origin": "IATA код города отправления",
            "destination": "IATA код города назначения",
            "origin_city": "название города отправления",
            "destination_city": "название города назначения",
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
