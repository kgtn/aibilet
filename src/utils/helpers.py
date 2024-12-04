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
        return " Билеты не найдены"

    message_parts = [" Найденные билеты:\n"]

    for i, ticket in enumerate(tickets[:10], 1):
        try:
            # Базовая информация о рейсе
            ticket_info = [
                f"\n{i}. {ticket.get('origin', 'Город')} {ticket.get('destination', 'Город')}",
                f" Цена: {ticket.get('price', 'н/д')} руб",
                f" Вылет: {format_date(ticket.get('departure_at', 'н/д'))}",
                f" Прилет: {format_date(ticket.get('arrival_at', 'н/д'))}",
                f" Время в пути: {format_duration(ticket.get('duration', 0))}",
                f" Пересадок: {ticket.get('transfers', 0)}"
            ]

            # Информация о обратном рейсе
            if ticket.get('return_at'):
                ticket_info.extend([
                    f"\nОбратный рейс:",
                    f" Вылет: {format_date(ticket['return_at'])}"
                ])

            message_parts.append("\n".join(ticket_info))

        except KeyError as e:
            print(f"Missing key in ticket data: {e}")
            continue
        except Exception as e:
            print(f"Error formatting ticket: {e}")
            continue

    return "\n\n".join(message_parts)
