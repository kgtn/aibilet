"""
Сервис для работы с Aviasales API.
"""
import logging
import json
from datetime import datetime
import aiohttp
from ..config import Config

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

    def _calculate_ticket_score(self, ticket: dict) -> float:
        """Вычисление оценки для билета на основе критериев"""
        try:
            # Веса для разных критериев
            WEIGHTS = {
                'price': 5.0,
                'duration': 4.0,
                'transfers': 2.0,
                'departure_time': 1.0
            }
            
            # Нормализация цены (меньше лучше)
            price_score = 1.0 / (float(ticket['price']) / 10000)  # Нормализуем относительно 10000 рублей
            
            # Нормализация длительности (меньше лучше)
            duration = float(ticket.get('duration_to', 0))
            if ticket.get('duration_back'):
                duration += float(ticket['duration_back'])
            duration_score = 1.0 / (duration / 120)  # Нормализуем относительно 2 часов
            
            # Нормализация количества пересадок (меньше лучше)
            transfers = int(ticket.get('transfers', 0))
            transfers_score = 1.0 / (transfers + 1)
            
            # Оценка времени вылета (лучше если в промежутке 6:00-23:00)
            departure_time = datetime.fromisoformat(ticket['departure_at']).hour
            departure_score = 1.0 if 6 <= departure_time <= 23 else 0.5
            
            # Вычисление общего счета
            total_score = (
                WEIGHTS['price'] * price_score +
                WEIGHTS['duration'] * duration_score +
                WEIGHTS['transfers'] * transfers_score +
                WEIGHTS['departure_time'] * departure_score
            )
            
            return total_score
            
        except Exception as e:
            logger.error(f"Ошибка вычисления оценки билета: {e}", exc_info=True)
            return 0.0

    def rank_tickets(self, tickets: list) -> dict:
        """Ранжирование билетов по заданным критериям"""
        try:
            if not tickets:
                return {
                    "ranked_tickets": [],
                    "summary": "Нет билетов для ранжирования"
                }

            # Вычисляем оценки для каждого билета
            scored_tickets = [(ticket, self._calculate_ticket_score(ticket)) for ticket in tickets]
            
            # Сортируем билеты по оценке (по убыванию) и берем топ-10
            scored_tickets.sort(key=lambda x: x[1], reverse=True)
            top_tickets = [ticket for ticket, _ in scored_tickets[:10]]
            
            # Создаем краткое описание ранжирования
            best_ticket = top_tickets[0]
            summary = (
                f"Лучший вариант: {best_ticket['origin']} → {best_ticket['destination']}, "
                f"цена: {best_ticket['price']} руб., "
                f"пересадок: {best_ticket.get('transfers', 0)}"
            )
            
            return {
                "ranked_tickets": top_tickets,
                "summary": summary
            }
            
        except Exception as e:
            logger.error(f"Ошибка ранжирования билетов: {e}", exc_info=True)
            return {
                "ranked_tickets": tickets[:10] if tickets else [],
                "summary": "Ошибка при ранжировании билетов"
            }

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
                    logger.info(f"API Response Status: {response.status}")
                    logger.info(f"API Response Headers: {response.headers}")
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"API Response Body: {json.dumps(data, ensure_ascii=False)}")
                        tickets = data.get("data", [])
                        
                        if not tickets:
                            logger.info("Билеты не найдены")
                            return None

                        # Обогащение билетов дополнительной информацией
                        enriched_tickets = []
                        for ticket in tickets:
                            try:
                                # Преобразуем относительную ссылку в абсолютную
                                link = ticket.get('link', '')
                                if link and link.startswith('/'):
                                    link = f"https://www.aviasales.ru{link}"
                                
                                ticket.update({
                                    'origin': params['origin'],
                                    'destination': params['destination'],
                                    'link': link
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
