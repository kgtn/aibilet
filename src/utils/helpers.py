"""
Вспомогательные функции.
"""
from datetime import datetime

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

def format_ticket_message(tickets: list) -> str:
    """Форматирование сообщения с информацией о билетах"""
    if not tickets:
        return "✈️ Билеты не найдены"

    message_parts = ["🎫 Найденные билеты:"]

    for i, ticket in enumerate(tickets[:10], 1):
        try:
            # Форматируем цену как ссылку в формате Markdown
            price_link = f"[{ticket.get('price', 'н/д')}₽]({ticket.get('link', '')})"
            
            # Формируем информацию о маршруте
            route_info = (
                f"\n{i}. 🛫 {ticket.get('origin', '')} ✈️ {ticket.get('destination', '')}"
            )
            
            # Информация о вылете туда
            departure_info = (
                f"🛫 Вылет: {format_date(ticket.get('departure_at', 'н/д'))}\n"
                f"⏱ Длительность: {format_duration(ticket.get('duration_to', 0))}"
            )
            
            # Информация о возвращении
            return_info = ""
            if ticket.get('return_at'):
                return_info = (
                    f"\n🛬 Обратно: {format_date(ticket.get('return_at', 'н/д'))}\n"
                    f"⏱ Длительность: {format_duration(ticket.get('duration_back', 0))}"
                )
            
            # Информация о пересадках
            transfers = ticket.get('transfers', 0)
            transfer_emoji = "🔁" if transfers > 0 else "✈️"
            transfer_info = f"{transfer_emoji} Пересадок: {transfers}"
            
            # Собираем всю информацию о билете
            ticket_info = (
                f"{route_info}\n"
                f"{departure_info}\n"
                f"{return_info}\n"
                f"{transfer_info}\n"
                f"💰 Стоимость: {price_link}"
            )

            message_parts.append(ticket_info)

        except KeyError as e:
            print(f"Missing key in ticket data: {e}")
            continue
        except Exception as e:
            print(f"Error formatting ticket: {e}")
            continue

    return "\n".join(message_parts)
