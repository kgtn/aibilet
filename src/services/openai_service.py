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
            next_year = current_date.year + 1
            
            example_response = {
                "origin": "LED",
                "destination": "BKK",
                "origin_city": "Санкт-Петербург",
                "destination_city": "Бангкок",
                "departure_at": "2024-02-01",
                "return_at": "2024-02-15",
                "flexible_dates": True,
                "date_context": {
                    "is_start_of_month": True,
                    "month_number": 2,
                    "duration_days": [15, 20]  # Теперь поддерживаем диапазон
                }
            }
            
            system_content = f"""Ты помощник по поиску авиабилетов. Извлеки параметры полета из текста. 
            Текущая дата: {current_date.strftime('%Y-%m-%d')}.
            
            Правила обработки дат:
            1. Если месяц не указан явно, используй ближайший подходящий месяц в будущем
            2. Для определения года:
               - Если указанный месяц раньше или равен текущему → используй {next_year} год
               - Если указанный месяц позже текущего → используй {current_date.year} год
            3. При указании "начало месяца" используй первое число месяца
            4. Если указан диапазон дней (например, "15-20 дней"), верни его как массив [15, 20]
            
            Примеры (если текущий месяц декабрь {current_date.year}):
            - "в феврале" → {next_year}-02 (так как февраль уже в следующем году)
            - "в январе" → {next_year}-01 (так как январь уже в следующем году)
            - "в декабре" → {next_year}-12 (так как текущий декабрь уже идет, ищем следующий)
            
            Верни JSON с полями:
            - origin (IATA код города отправления, например LED для Санкт-Петербурга)
            - destination (IATA код города назначения, например BKK для Бангкока)
            - origin_city (название города отправления)
            - destination_city (название города назначения)
            - departure_at (дата вылета в формате YYYY-MM-DD)
            - return_at (дата возвращения в формате YYYY-MM-DD, если указано)
            - flexible_dates (true/false - если пользователю не важны точные даты)
            - date_context (объект с дополнительной информацией о датах):
              - is_start_of_month (true/false - если указано "начало месяца")
              - is_mid_month (true/false - если указана середина месяца)
              - is_end_month (true/false - если указан конец месяца)
              - month_number (номер месяца, если указан)
              - relative_days (количество дней относительно текущей даты, если указано "через N дней")
              - season (лето/осень/зима/весна, если указан сезон)
              - duration_days (число или массив [мин, макс] для диапазона длительности поездки в днях)

            Примеры запросов и их обработки:
            1. "из Москвы в Париж на 7 дней" -> duration_days: 7
            2. "из Питера в Бангкок на 15-20 дней" -> duration_days: [15, 20]
            3. "из Москвы в Рим на неделю" -> duration_days: 7
            4. "из Питера в Париж на 10-14 дней" -> duration_days: [10, 14]
            
            Правила обработки дат:
            1. Если указаны неточные даты ("в начале месяца", "где-то в июне") - установи flexible_dates в true
            2. Если указана длительность поездки - укажи в duration_days
            3. Если год не указан и дата уже прошла в текущем году - используй следующий год
            4. Для относительных дат ("через неделю", "через 5 дней") - укажи relative_days
            5. При указании сезона - установи соответствующий месяц (лето: июнь-август, осень: сентябрь-ноябрь и т.д.)

            Пример запроса: "{text}"
            Пример ответа: {json.dumps(example_response, ensure_ascii=False, indent=2)}"""

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
                
                # Обработка дат и контекста
                if params.get('flexible_dates'):
                    date_context = params.get('date_context', {})
                    
                    # Обработка начала месяца
                    if date_context.get('is_start_of_month'):
                        month_number = date_context.get('month_number')
                        if month_number:
                            current_year = datetime.now().year
                            # Если указанный месяц меньше или равен текущему, значит это следующий год
                            # Если указанный месяц позже текущего, оставляем текущий год
                            if month_number <= datetime.now().month:
                                current_year += 1
                            params['departure_at'] = f"{current_year}-{month_number:02d}-01"
                            
                            # Если указана длительность, рассчитываем дату возврата
                            if duration_days := date_context.get('duration_days'):
                                if isinstance(duration_days, list):
                                    min_duration, max_duration = duration_days
                                    return_date = datetime.strptime(params['departure_at'], '%Y-%m-%d') + timedelta(days=max_duration)
                                    params['return_at'] = return_date.strftime('%Y-%m-%d')
                                else:
                                    return_date = datetime.strptime(params['departure_at'], '%Y-%m-%d') + timedelta(days=duration_days)
                                    params['return_at'] = return_date.strftime('%Y-%m-%d')
                
                logger.info(f"Финальные извлеченные параметры: {json.dumps(params, ensure_ascii=False)}")
                return params
                
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка декодирования JSON: {str(e)}")
                return {}
            except Exception as e:
                logger.error(f"Ошибка обработки ответа OpenAI: {str(e)}")
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
