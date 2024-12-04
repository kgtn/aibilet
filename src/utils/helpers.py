"""
Вспомогательные функции.
"""
from datetime import datetime

def format_ticket_message(tickets: list) -> str:
    """Форматирование сообщения с информацией о билетах"""
    if not tickets:
        return "Билеты не найдены"

    message_parts = [" Найденные билеты:\n"]

    for i, ticket in enumerate(tickets[:10], 1):
        # Форматируем информацию о рейсе туда
        departure_at = datetime.fromisoformat(ticket['departure_at'].replace('Z', '+00:00'))
        arrival_at = datetime.fromisoformat(ticket['arrival_at'].replace('Z', '+00:00'))
        duration = int(ticket.get('duration', 0))
        
        ticket_info = [
            f"\n{i}. {ticket['origin']} {ticket['destination']}",
            f" Цена: {ticket['price']} руб",
            f" Вылет: {departure_at.strftime('%d.%m.%Y %H:%M')}",
            f" Прилет: {arrival_at.strftime('%d.%m.%Y %H:%M')}",
            f" Время в пути: {duration//60}ч {duration%60}мин",
            f" Пересадок: {ticket.get('transfers', 0)}"
        ]

        # Добавляем информацию о обратном рейсе, если есть
        if ticket.get('return_at'):
            return_at = datetime.fromisoformat(ticket['return_at'].replace('Z', '+00:00'))
            ticket_info.extend([
                f"\nОбратный рейс:",
                f" Вылет: {return_at.strftime('%d.%m.%Y %H:%M')}"
            ])

        message_parts.append("\n".join(ticket_info))

    return "\n\n".join(message_parts)
