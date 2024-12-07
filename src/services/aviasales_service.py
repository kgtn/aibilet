"""
Сервис для работы с Aviasales API.
"""
import logging
import json
from datetime import datetime, timedelta
import aiohttp
import asyncio
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
        self.api_token = Config.AVIASALES_TOKEN
        self.base_url = "https://api.travelpayouts.com/aviasales/v3"  # Убрал /prices_for_dates из базового URL

    def _get_airport_code(self, city: str) -> str:
        """Получение IATA кода аэропорта"""
        return self.AIRPORT_CODES.get(city, city)

    def _validate_params(self, params: dict) -> bool:
        """Проверяет корректность параметров поиска"""
        if not isinstance(params, dict):
            logger.error(f"Параметры должны быть словарем, получено: {type(params)}")
            return False

        required_fields = ['origin', 'departure_at']
        
        # Проверка наличия обязательных полей
        missing_fields = [field for field in required_fields if not params.get(field)]
        if missing_fields:
            logger.error(f"Отсутствуют обязательные параметры: {', '.join(missing_fields)}")
            logger.debug(f"Текущие параметры: {json.dumps(params, ensure_ascii=False)}")
            return False
        
        # Проверка формата IATA кодов
        for field in ['origin', 'destination']:
            iata_code = params.get(field)
            if iata_code and not (len(iata_code) == 3 and iata_code.isupper() and iata_code.isalpha()):
                logger.error(f"Некорректный формат IATA кода {field}: {iata_code}")
                return False
        
        # Проверка формата дат
        try:
            departure_date = datetime.strptime(params['departure_at'], '%Y-%m-%d')
            if params.get('return_at'):
                return_date = datetime.strptime(params['return_at'], '%Y-%m-%d')
                if return_date <= departure_date:
                    logger.error(f"Дата возврата {params['return_at']} должна быть после даты вылета {params['departure_at']}")
                    return False
        except ValueError as e:
            logger.error(f"Некорректный формат даты: {str(e)}")
            return False
        
        logger.info(f"Параметры поиска прошли валидацию: {json.dumps(params, ensure_ascii=False)}")
        return True

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
                'price': 5.0,      # Цена (самый важный фактор)
                'duration': 3.0,   # Длительность полета
                'transfers': 2.0,  # Количество пересадок
                'time': 1.0,      # Время вылета
                'airline': 0.5     # Рейтинг авиакомпании
            }
            
            scores = {}
            
            # Оценка цены (обратная зависимость - чем дешевле, тем лучше)
            base_price = float(ticket['price'])
            scores['price'] = 1.0 / (base_price / 10000)  # Нормализация относительно 10000
            
            # Оценка длительности (обратная зависимость)
            duration = float(ticket.get('duration', 0))
            scores['duration'] = 1.0 / (duration / 240)  # Нормализация относительно 4 часов
            
            # Оценка пересадок (обратная зависимость)
            transfers = int(ticket.get('transfers', 0))
            scores['transfers'] = 1.0 / (transfers + 1)
            
            # Оценка времени вылета (предпочтительно дневное время)
            departure_hour = datetime.strptime(ticket['departure_at'], '%Y-%m-%dT%H:%M:%S%z').hour
            if 8 <= departure_hour <= 22:
                time_score = 1.0
            elif 6 <= departure_hour < 8 or 22 < departure_hour <= 23:
                time_score = 0.7
            else:
                time_score = 0.3
            scores['time'] = time_score
            
            # Оценка авиакомпании (можно расширить списком предпочтительных авиакомпаний)
            scores['airline'] = 1.0  # Базовая оценка для всех авиакомпаний
            
            # Вычисление итоговой оценки
            final_score = sum(WEIGHTS[criterion] * score for criterion, score in scores.items())
            
            return final_score
            
        except Exception as e:
            logger.error(f"Error calculating ticket score: {str(e)}")
            return 0.0

    def _rank_tickets(self, tickets: list) -> list:
        """Ранжирование билетов по различным критериям"""
        try:
            scored_tickets = []
            for ticket in tickets:
                score = self._calculate_ticket_score(ticket)
                scored_tickets.append((score, ticket))
            
            # Сортируем по убыванию оценки
            scored_tickets.sort(reverse=True, key=lambda x: x[0])
            
            # Возвращаем только билеты без оценок
            return [ticket for score, ticket in scored_tickets]
            
        except Exception as e:
            logger.error(f"Error in _rank_tickets: {str(e)}")
            return tickets

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

    async def search_tickets(self, params: dict) -> dict:
        """Поиск билетов через API Aviasales"""
        try:
            logger.info(f"Начало поиска билетов. Параметры: {json.dumps(params, ensure_ascii=False)}")
            
            # Проверяем наличие обязательных параметров
            required_params = ['origin', 'departure_at']
            if not all(param in params for param in required_params):
                logger.error(f"Отсутствуют обязательные параметры: {[param for param in required_params if param not in params]}")
                return {}

            # Проверяем корректность IATA кодов
            for field in ['origin', 'destination']:
                iata_code = params.get(field)
                if iata_code and not (len(iata_code) == 3 and iata_code.isupper() and iata_code.isalpha()):
                    logger.error(f"Некорректный IATA код {field}: {iata_code}")
                    return {}

            # Создаем словарь параметров для API
            api_params = {
                'origin': params['origin'],
                'destination': params.get('destination'),
                'departure_at': params['departure_at'],
                'return_at': params.get('return_at'),
                'sorting': 'price',
                'direct': 'false',
                'currency': 'rub',
                'limit': '30',
            }
            
            # Удаляем None значения
            api_params = {k: v for k, v in api_params.items() if v is not None}
            
            logger.info(f"Параметры запроса к API: {json.dumps(api_params, ensure_ascii=False)}")
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/prices_for_dates"
                logger.info(f"URL запроса: {url}")
                
                async with session.get(
                    url,
                    params=api_params,
                    headers={'X-Access-Token': self.api_token}
                ) as response:
                    response_text = await response.text()
                    logger.info(f"Статус ответа: {response.status}")
                    logger.info(f"Тело ответа: {response_text}")
                    
                    if response.status != 200:
                        logger.error(f"Ошибка API: {response.status} - {response_text}")
                        return {}
                    
                    try:
                        data = await response.json()
                        logger.info(f"Получен ответ от API: {json.dumps(data, ensure_ascii=False)}")
                        
                        if not data.get('success'):
                            logger.error(f"Ошибка в ответе API: {data.get('error')}")
                            return {}
                        
                        return self._process_response(data, params)
                    except json.JSONDecodeError as e:
                        logger.error(f"Ошибка декодирования JSON: {str(e)}")
                        return {}
                    
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка при запросе к API: {str(e)}", exc_info=True)
            return {}
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при поиске билетов: {str(e)}", exc_info=True)
            return {}

    async def search_tickets_in_range(self, params: dict) -> dict:
        """Поиск билетов в диапазоне дат"""
        try:
            if not self._validate_params(params):
                logger.error("Параметры поиска не прошли валидацию")
                return {'success': False, 'error': 'Некорректные параметры поиска'}

            # Если указано начало месяца, ищем билеты на первые 5 дней
            if params.get('date_context', {}).get('is_start_of_month'):
                base_date = datetime.strptime(params['departure_at'], '%Y-%m-%d')
                return_days = params.get('date_context', {}).get('return_days')
                
                all_tickets = []
                async with aiohttp.ClientSession() as session:
                    tasks = []
                    for day_offset in range(5):  # Ищем на первые 5 дней месяца
                        search_date = base_date + timedelta(days=day_offset)
                        search_params = params.copy()
                        search_params['departure_at'] = search_date.strftime('%Y-%m-%d')
                        
                        if return_days is not None:
                            return_date = search_date + timedelta(days=return_days)
                            search_params['return_at'] = return_date.strftime('%Y-%m-%d')
                        
                        tasks.append(self._search_tickets_for_date(session, search_params))
                    
                    results = await asyncio.gather(*tasks)
                    for result in results:
                        if result and result.get('success') and result.get('data'):
                            all_tickets.extend(result['data'])
                
                if not all_tickets:
                    return {'success': False, 'error': 'Билеты не найдены'}
                
                # Сортируем билеты по цене
                all_tickets.sort(key=lambda x: x.get('price', float('inf')))
                
                return {
                    'success': True,
                    'data': all_tickets[:10],  # Возвращаем топ-10 самых дешевых билетов
                    'currency': 'RUB'
                }
            
            # Если нет указания на начало месяца, делаем обычный поиск
            return await self.search_tickets(params)
                    
        except Exception as e:
            logger.error(f"Ошибка при поиске билетов в диапазоне: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    async def _search_tickets_for_date(self, session: aiohttp.ClientSession, params: dict) -> dict:
        """Поиск билетов на конкретную дату"""
        try:
            url = f"{self.base_url}/prices_for_dates"
            
            query_params = {
                'origin': params['origin'],
                'destination': params.get('destination'),
                'departure_at': params['departure_at'],
                'return_at': params.get('return_at'),
                'unique': 'false',
                'sorting': 'price',
                'direct': 'false',
                'currency': 'rub',
                'limit': '30',
                'page': '1',
                'one_way': 'true' if not params.get('return_at') else 'false'
            }

            logger.info(f"Отправка запроса к Aviasales API: {url}")
            logger.debug(f"Параметры запроса: {json.dumps(query_params, ensure_ascii=False)}")
            
            async with session.get(
                url,
                params=query_params,
                headers={'X-Access-Token': self.api_token}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Ошибка API Aviasales ({response.status}): {error_text}")
                    return {'success': False, 'error': f'API error: {response.status}'}
                
                data = await response.json()
                logger.info(f"Получено {len(data.get('data', []))} билетов от API")
                
                if not data.get('success'):
                    logger.error(f"Ошибка в ответе API: {data.get('error')}")
                    return {'success': False, 'error': data.get('error')}
                
                return self._process_response(data, params)
                
        except Exception as e:
            logger.error(f"Ошибка при поиске билетов на дату: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def _process_response(self, data: dict, params: dict) -> dict:
        """Обработка ответа от API"""
        try:
            tickets = data.get('data', [])
            logger.info(f"Получено {len(tickets)} билетов от API")
            
            # Сортируем билеты по цене
            tickets.sort(key=lambda x: x.get('price', float('inf')))
            
            return {
                'success': True,
                'data': tickets,
                'currency': data.get('currency', 'rub')
            }
        
        except Exception as e:
            logger.error(f"Ошибка обработки ответа от API: {e}", exc_info=True)
            return {
                'success': False,
                'data': [],
                'error': str(e)
            }

    async def search_tickets_with_flexible_dates(self, params: dict) -> dict:
        """Поиск билетов с гибкими датами"""
        try:
            if not self._validate_params(params):
                return {"success": False, "error": "Invalid parameters"}

            date_context = params.get('date_context', {})
            base_date = datetime.strptime(params['departure_at'], '%Y-%m-%d')
            
            search_dates = []
            if date_context.get('is_start_of_month'):
                # Ищем билеты на первые 5 дней месяца
                for day in range(5):
                    search_date = base_date + timedelta(days=day)
                    search_dates.append(search_date)
            else:
                # Ищем билеты в диапазоне ±2 дня от указанной даты
                for day in range(-2, 3):
                    search_date = base_date + timedelta(days=day)
                    search_dates.append(search_date)

            all_tickets = []
            tasks = []
            
            # Создаем параметры поиска для каждой даты
            for search_date in search_dates:
                search_params = params.copy()
                search_params['departure_at'] = search_date.strftime('%Y-%m-%d')
                if params.get('return_at'):
                    # Сохраняем ту же длительность поездки
                    duration = (datetime.strptime(params['return_at'], '%Y-%m-%d') - 
                              datetime.strptime(params['departure_at'], '%Y-%m-%d')).days
                    search_params['return_at'] = (search_date + timedelta(days=duration)).strftime('%Y-%m-%d')
                
                tasks.append(self.search_tickets(search_params))
            
            # Выполняем все запросы параллельно
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Собираем все успешные результаты
            for result in results:
                if isinstance(result, dict) and result.get('success') and result.get('data'):
                    all_tickets.extend(result['data'])
            
            if not all_tickets:
                return {"success": False, "error": "No tickets found"}
            
            # Ранжируем все найденные билеты
            ranked_tickets = self._rank_tickets(all_tickets)
            
            return {
                "success": True,
                "data": ranked_tickets[:10],  # Возвращаем топ-10 лучших вариантов
                "total_found": len(all_tickets)
            }
            
        except Exception as e:
            logger.error(f"Error in search_tickets_with_flexible_dates: {str(e)}")
            return {"success": False, "error": str(e)}
