"""
Сервис для работы с Aviasales API.
"""
import logging
import json
from datetime import datetime
import aiohttp
from config import Config

logger = logging.getLogger(__name__)

class AviasalesService:
    """Сервис для работы с Aviasales API"""
    AIRPORT_CODES = {
        'Москва': 'MOW',
        'Санкт-Петербург': 'LED',
        'Париж': 'PAR',
        'Барселона': 'BCN',
        'Рим': 'ROM'
    }

    def __init__(self):
        self.token = Config.AVIASALES_TOKEN
        self.base_url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"

    def _get_airport_code(self, city: str) -> str:
        """Получение IATA кода аэропорта"""
        return self.AIRPORT_CODES.get(city, city)

    def _validate_params(self, params: dict) -> bool:
        """Валидация параметров запроса"""
        required_fields = ['origin', 'destination', 'departure_at']
        return all(params.get(field) for field in required_fields)

    def _format_date(self, date_str: str) -> str:
        """Форматирование даты для API"""
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d')
            return date.strftime('%Y-%m-%d')
        except Exception as e:
            logger.error(f"Ошибка форматирования даты: {e}")
            return None

    async def search_tickets(self, params: dict) -> list:
        """Поиск билетов"""
        try:
            # Добавляем IATA коды если их нет
            params['origin_airport'] = params.get('origin_airport', 
                self._get_airport_code(params['origin']))
            params['destination_airport'] = params.get('destination_airport', 
                self._get_airport_code(params['destination']))

            if not self._validate_params(params):
                logger.error("Некорректные параметры запроса")
                return None

            # Подготовка параметров запроса
            query_params = {
                "currency": "rub",
                "origin": params['origin_airport'],
                "destination": params['destination_airport'],
                "departure_at": self._format_date(params['departure_at']),
                "return_at": self._format_date(params['return_at']) if params.get('return_at') else None,
                "sorting": "price",
                "direct": "false",
                "limit": "30",
                "token": self.token
            }

            # Удаляем None значения
            query_params = {k: v for k, v in query_params.items() if v is not None}

            logger.info(f"Параметры поиска билетов: {json.dumps(query_params, ensure_ascii=False)}")

            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=query_params) as response:
                    if response.status == 200:
                        data = await response.json()
                        tickets = data.get("data", [])
                        
                        if not tickets:
                            logger.info("Билеты не найдены")
                            return None

                        # Обогащение билетов дополнительной информацией
                        enriched_tickets = []
                        for ticket in tickets:
                            try:
                                ticket.update({
                                    'origin': params['origin'],
                                    'destination': params['destination'],
                                    'link': f"https://www.aviasales.ru/search/{ticket['origin']}{ticket['destination']}{datetime.now().strftime('%d%m')}"
                                })
                                enriched_tickets.append(ticket)
                            except Exception as e:
                                logger.warning(f"Ошибка обработки билета: {e}")

                        logger.info(f"Найдено билетов: {len(enriched_tickets)}")
                        return enriched_tickets

                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка API Aviasales: {response.status}, {error_text}")
                        return None

        except aiohttp.ClientError as e:
            logger.error(f"Сетевая ошибка: {e}")
            return None
        except Exception as e:
            logger.error(f"Неизвестная ошибка при поиске билетов: {e}", exc_info=True)
            return None
