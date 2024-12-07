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
                'duration': 4.0,   # Длительность полета
                'transfers': 2.0,  # Количество пересадок
            }
            
            scores = {}
            
            # Оценка цены (обратная зависимость - чем дешевле, тем лучше)
            base_price = float(ticket['price'])
            scores['price'] = 1.0 / (base_price / 10000)  # Нормализация относительно 10000
            
            # Оценка длительности (обратная зависимость)
            duration = float(ticket.get('duration', 0))
            scores['duration'] = 1.0 / (duration / 240)  # Нормализация относительно 4 часов
            
            # Оценка количества пересадок (обратная зависимость)
            transfers = int(ticket.get('transfers', 0))
            scores['transfers'] = 1.0 / (transfers + 1)  # +1 чтобы избежать деления на ноль
            
            # Базовая оценка
            total_score = sum(scores[key] * WEIGHTS[key] for key in WEIGHTS)
            
            return total_score
            
        except Exception as e:
            logger.error(f"Ошибка при расчете оценки билета: {e}", exc_info=True)
            return 0.0

    def _rank_tickets(self, tickets: list) -> list:
        """Ранжирование билетов по различным критериям"""
        try:
            if not tickets:
                return []

            # Сначала сортируем по цене для определения минимальной цены
            tickets.sort(key=lambda x: x.get('price', float('inf')))
            min_price = tickets[0]['price']

            # Группируем билеты по ценовым диапазонам (в пределах 10% разницы)
            price_groups = []
            current_group = []
            
            for ticket in tickets:
                price_diff_percent = ((ticket['price'] - min_price) / min_price) * 100
                if not current_group or price_diff_percent <= 10:
                    current_group.append(ticket)
                else:
                    if current_group:
                        price_groups.append(current_group)
                    current_group = [ticket]
            
            if current_group:
                price_groups.append(current_group)

            # Сортируем каждую группу с приоритетом длительности
            sorted_groups = []
            for group in price_groups:
                # Для билетов в пределах 10% разницы в цене увеличиваем вес длительности
                for ticket in group:
                    ticket['_score'] = self._calculate_ticket_score(ticket)
                    if len(group) > 1:  # Если в группе больше одного билета
                        # Увеличиваем влияние длительности для близких по цене билетов
                        duration_score = 1.0 / (float(ticket.get('duration', 0)) / 240)
                        ticket['_score'] += duration_score * 2  # Дополнительный бонус за длительность

                group.sort(key=lambda x: x['_score'], reverse=True)
                sorted_groups.extend(group)

            return sorted_groups

        except Exception as e:
            logger.error(f"Ошибка при ранжировании билетов: {e}", exc_info=True)
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
            if not self._validate_params(params):
                return {"success": False, "error": "Invalid parameters"}

            # Всегда используем поиск с гибкими датами
            if params.get('flexible_dates', True):
                logger.info("Используем поиск с гибкими датами")
                return await self.search_tickets_with_flexible_dates(params)
            
            logger.info("Начало поиска билетов. Параметры: " + json.dumps(params, ensure_ascii=False))
            
            async with aiohttp.ClientSession() as session:
                return await self._search_tickets_for_date(session, params)
                
        except Exception as e:
            logger.error(f"Ошибка при поиске билетов: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

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
            logger.info(f"Начинаем поиск с гибкими датами. Базовая дата: {base_date.strftime('%Y-%m-%d')}")
            
            search_dates = []
            if date_context.get('is_start_of_month'):
                # Ищем билеты на первые 5 дней месяца
                logger.info("Поиск на первые 5 дней месяца")
                for day in range(5):
                    search_date = base_date + timedelta(days=day)
                    search_dates.append(search_date)
                    logger.info(f"Добавлена дата поиска: {search_date.strftime('%Y-%m-%d')}")
            else:
                # Ищем билеты в диапазоне ±2 дня от указанной даты
                logger.info("Поиск в диапазоне ±2 дня")
                for day in range(-2, 3):
                    search_date = base_date + timedelta(days=day)
                    search_dates.append(search_date)
                    logger.info(f"Добавлена дата поиска: {search_date.strftime('%Y-%m-%d')}")

            all_tickets = []
            
            # Выполняем все запросы параллельно с помощью aiohttp.ClientSession
            async with aiohttp.ClientSession() as session:
                tasks = []
                
                # Создаем параметры поиска для каждой даты
                for search_date in search_dates:
                    search_params = params.copy()
                    search_params['departure_at'] = search_date.strftime('%Y-%m-%d')
                    
                    if date_context.get('duration_days'):
                        # Если указан диапазон длительности
                        duration_days = date_context['duration_days']
                        if isinstance(duration_days, list):
                            min_days, max_days = duration_days
                            logger.info(f"Поиск с диапазоном длительности {min_days}-{max_days} дней")
                            # Проверяем несколько вариантов длительности с шагом в 2-3 дня
                            step = max(2, (max_days - min_days) // 3)  # Адаптивный шаг
                            logger.info(f"Используем шаг {step} дней для поиска")
                            for duration in range(min_days, max_days + 1, step):
                                search_params_with_duration = search_params.copy()
                                return_date = search_date + timedelta(days=duration)
                                search_params_with_duration['return_at'] = return_date.strftime('%Y-%m-%d')
                                logger.info(f"Поиск билетов: вылет {search_params_with_duration['departure_at']}, возврат {search_params_with_duration['return_at']} (длительность {duration} дней)")
                                tasks.append(self._search_tickets_for_date(session, search_params_with_duration))
                        else:
                            # Если указана конкретная длительность
                            return_date = search_date + timedelta(days=duration_days)
                            search_params['return_at'] = return_date.strftime('%Y-%m-%d')
                            logger.info(f"Поиск билетов: вылет {search_params['departure_at']}, возврат {search_params['return_at']} (длительность {duration_days} дней)")
                            tasks.append(self._search_tickets_for_date(session, search_params))
                    else:
                        # Поиск билетов только в одну сторону
                        logger.info(f"Поиск билетов только в одну сторону на дату {search_params['departure_at']}")
                        tasks.append(self._search_tickets_for_date(session, search_params))

                logger.info(f"Всего создано {len(tasks)} поисковых запросов")
                
                # Выполняем все запросы параллельно
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Собираем все успешные результаты
                successful_results = 0
                for result in results:
                    if isinstance(result, dict) and result.get('success') and result.get('data'):
                        all_tickets.extend(result['data'])
                        successful_results += 1
                
                logger.info(f"Успешно выполнено {successful_results} из {len(tasks)} запросов")
                logger.info(f"Всего найдено {len(all_tickets)} билетов")

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
