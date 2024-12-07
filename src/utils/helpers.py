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
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}ч {mins}мин"

def format_price(price: int) -> str:
    """Форматирование цены"""
    return f"{price:,}₽".replace(',', ' ')

def format_ticket_message(tickets_data: dict) -> str:
    """Форматирование сообщения с билетами"""
    if not tickets_data or not tickets_data.get('success') or not tickets_data.get('data'):
        return "К сожалению, билеты не найдены 😔"
    
    tickets = tickets_data['data']
    currency = tickets_data.get('currency', 'RUB').upper()
    message_parts = []
    
    for i, ticket in enumerate(tickets[:5], 1):
        try:
            # Форматируем даты
            departure_at = format_date(ticket['departure_at'])
            return_at = format_date(ticket['return_at']) if ticket.get('return_at') else None
            
            # Форматируем длительность
            duration_to = format_duration(ticket['duration_to'])
            duration_back = format_duration(ticket['duration_back']) if ticket.get('duration_back') else None
            
            # Формируем сообщение о пересадках
            transfers_to = format_transfers(ticket.get('transfers', 0))
            transfers_back = format_transfers(ticket.get('return_transfers', 0)) if ticket.get('return_transfers') is not None else None
            
            # Формируем ссылку на билет
            ticket_link = f"https://www.aviasales.ru{ticket['link']}"
            
            # Формируем сообщение для билета
            message = [
                f"{i}. *{ticket.get('airline', 'Авиакомпания')} {ticket.get('flight_number', '')}*",
                f"💰 Цена: *{format_price(ticket['price'])} {currency}*",
                f"🛫 Вылет: {departure_at}",
                f"⏱ Длительность: {duration_to} ({transfers_to})"
            ]
            
            # Добавляем информацию о обратном рейсе, если есть
            if return_at and duration_back and transfers_back:
                message.extend([
                    f"🛬 Возврат: {return_at}",
                    f"⏱ Длительность обратно: {duration_back} ({transfers_back})"
                ])
            
            message.append(f"🔗 [Купить билет]({ticket_link})")
            message_parts.append("\n".join(message))
            
        except Exception as e:
            logger.error(f"Ошибка при форматировании билета: {e}", exc_info=True)
            continue
    
    if not message_parts:
        return "Не удалось отформатировать информацию о билетах 😔"
    
    return "\n\n".join(message_parts)

def format_transfers(count: int) -> str:
    """Форматирование количества пересадок"""
    if count == 0:
        return "без пересадок"
    elif count == 1:
        return "1 пересадка"
    elif 2 <= count <= 4:
        return f"{count} пересадки"
    else:
        return f"{count} пересадок"
