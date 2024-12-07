"""
Вспомогательные функции.
"""
from datetime import datetime
import logging
logger = logging.getLogger(__name__)

def format_date(date_str: str) -> str:
    """Форматирование даты и времени"""
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%d.%m.%Y %H:%M')
    except Exception:
        return date_str

def format_duration(minutes: int) -> str:
    """Форматирование длительности полета"""
    if not minutes:
        return "?"
    
    hours = minutes // 60
    mins = minutes % 60
    
    if hours == 0:
        return f"{mins}мин"
    elif mins == 0:
        return f"{hours}ч"
    else:
        return f"{hours}ч {mins}мин"

def format_price(price: int) -> str:
    """Форматирование цены"""
    return f"{price:,}₽".replace(',', ' ')

def format_ticket_message(tickets_data: list | dict) -> str:
    """Форматирование сообщения с билетами"""
    if isinstance(tickets_data, dict):
        if not tickets_data or not tickets_data.get('success') or not tickets_data.get('data'):
            return "К сожалению, билеты не найдены 😔"
        tickets = tickets_data['data']
        currency = tickets_data.get('currency', 'RUB').upper()
    else:
        if not tickets_data:
            return "К сожалению, билеты не найдены 😔"
        tickets = tickets_data
        currency = 'RUB'

    message_parts = []
    
    for i, ticket in enumerate(tickets[:5], 1):
        try:
            # Форматируем даты
            departure_at = format_date(ticket['departure_at'])
            return_at = format_date(ticket['return_at']) if ticket.get('return_at') else None
            
            # Форматируем длительность
            duration_to = format_duration(ticket.get('duration_to', 0))
            duration_back = format_duration(ticket.get('duration_back', 0)) if ticket.get('return_at') else None
            
            # Определяем наличие пересадок
            transfers = int(ticket.get('transfers', 0))
            return_transfers = int(ticket.get('return_transfers', 0)) if ticket.get('return_transfers') is not None else None
            
            # Формируем ссылку на билет
            price = format_price(ticket['price'])
            ticket_url = f"https://www.aviasales.ru{ticket['link']}"
            
            # Формируем сообщение для одного билета
            ticket_message = [
                f"\n🎫 Вариант {i}:",
                f"💰 <a href='{ticket_url}'>{price}</a> {currency}",
                f"✈️ Туда: {departure_at}"
            ]
            
            # Добавляем информацию о пересадках для полета туда
            if transfers == 0:
                ticket_message.append(f"⭐️ Прямой рейс ({duration_to})")
            else:
                transfer_text = "1 пересадка" if transfers == 1 else f"{transfers} пересадки" if 2 <= transfers <= 4 else f"{transfers} пересадок"
                ticket_message.append(f"🛑 {transfer_text} ({duration_to})")
            
            # Добавляем информацию о обратном рейсе, если есть
            if return_at and duration_back:
                ticket_message.append(f"🔄 Обратно: {return_at}")
                if return_transfers == 0:
                    ticket_message.append(f"⭐️ Прямой рейс ({duration_back})")
                else:
                    return_transfer_text = "1 пересадка" if return_transfers == 1 else f"{return_transfers} пересадки" if 2 <= return_transfers <= 4 else f"{return_transfers} пересадок"
                    ticket_message.append(f"🛑 {return_transfer_text} ({duration_back})")
            
            message_parts.append("\n".join(ticket_message))
            
        except Exception as e:
            logger.error(f"Ошибка форматирования билета: {str(e)}")
            continue
    
    if not message_parts:
        return "К сожалению, не удалось отформатировать информацию о билетах 😔"
    
    return "\n\n".join(message_parts)

def format_transfers(count: int) -> str:
    """Форматирование количества пересадок"""
    if count == 0:
        return "Прямой рейс"
    elif count == 1:
        return "1 пересадка"
    else:
        return f"{count} пересадки" if 2 <= count <= 4 else f"{count} пересадок"
