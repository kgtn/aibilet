"""
Сервис для работы с Aviasales API.
"""
import aiohttp
from config import Config

class AviasalesService:
    """Сервис для работы с Aviasales API"""
    def __init__(self):
        self.token = Config.AVIASALES_TOKEN
        self.base_url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"

    async def search_tickets(self, params: dict) -> list:
        """Поиск билетов"""
        try:
            # Формируем параметры запроса
            query_params = {
                "currency": "rub",
                "origin": params.get("origin_iata"),
                "destination": params.get("destination_iata"),
                "departure_at": params.get("departure_date"),
                "return_at": params.get("return_date"),
                "sorting": "price",
                "direct": "false",
                "limit": "30",
                "token": self.token
            }

            # Удаляем None значения
            query_params = {k: v for k, v in query_params.items() if v is not None}

            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=query_params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("data", [])
                    else:
                        print(f"Error from Aviasales API: {response.status}")
                        return None

        except Exception as e:
            print(f"Error in search_tickets: {str(e)}")
            return None
