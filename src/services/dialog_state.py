"""
Управление состоянием диалога с пользователем.
"""
from dataclasses import dataclass
from typing import Optional, Dict
from datetime import datetime, timedelta
import logging
import json

logger = logging.getLogger(__name__)

class DialogState:
    """Состояние диалога с пользователем"""
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.origin = None  # IATA код города отправления
        self.destination = None  # IATA код города назначения
        self.origin_city = None  # Название города отправления
        self.destination_city = None  # Название города назначения
        self.departure_at = None  # Дата вылета
        self.return_at = None  # Дата возврата
        self.date_context = None  # Контекст дат (гибкие даты, начало месяца и т.д.)

    @property
    def is_complete(self) -> bool:
        """Проверяет, заполнены ли все обязательные параметры"""
        return all([self.origin, self.destination, self.departure_at, self.origin_city, self.destination_city])
    
    def get_missing_params(self) -> list[str]:
        """Возвращает список недостающих параметров"""
        missing = []
        if not self.origin or not self.origin_city:
            missing.append("город отправления")
        if not self.destination or not self.destination_city:
            missing.append("город прибытия")
        if not self.departure_at:
            missing.append("дату вылета")
        return missing

    def update_from_params(self, params: Dict) -> None:
        """Обновление состояния из параметров"""
        try:
            logger.info(f"Обновление состояния из параметров: {json.dumps(params, ensure_ascii=False)}")
            
            # Обновляем все поля, которые есть в параметрах
            for field in ['origin', 'destination', 'origin_city', 'destination_city', 
                         'departure_at', 'return_at', 'date_context']:
                if field in params:
                    setattr(self, field, params[field])
            
            logger.info(f"Состояние после обновления: origin={self.origin}, destination={self.destination}, "
                       f"origin_city={self.origin_city}, destination_city={self.destination_city}, "
                       f"departure_at={self.departure_at}, return_at={self.return_at}, "
                       f"date_context={json.dumps(self.date_context, ensure_ascii=False) if self.date_context else None}")
        except Exception as e:
            logger.error(f"Ошибка при обновлении состояния: {str(e)}", exc_info=True)

    def to_search_params(self) -> Dict:
        """Преобразование состояния в параметры для поиска"""
        try:
            # Проверяем наличие обязательных полей
            required_fields = ['origin', 'destination', 'departure_at']
            for field in required_fields:
                if not getattr(self, field):
                    logger.warning(f"Отсутствует обязательное поле {field}")
                    return {}

            # Создаем словарь параметров только с непустыми значениями
            params = {
                'origin': self.origin,
                'destination': self.destination,
                'departure_at': self.departure_at,
                'flexible_dates': True  # Всегда включаем поиск с гибкими датами
            }

            if self.return_at:
                params['return_at'] = self.return_at
            
            if self.date_context:
                params['date_context'] = self.date_context

            logger.info(f"Параметры поиска: {json.dumps(params, ensure_ascii=False)}")
            return params

        except Exception as e:
            logger.error(f"Ошибка при создании параметров поиска: {str(e)}", exc_info=True)
            return {}

class DialogStateManager:
    """Менеджер состояний диалогов"""
    def __init__(self):
        self.states: Dict[int, DialogState] = {}
    
    def get_state(self, user_id: int) -> DialogState:
        """Получает или создает состояние диалога для пользователя"""
        if user_id not in self.states:
            self.states[user_id] = DialogState(user_id)
        return self.states[user_id]
    
    def clear_state(self, user_id: int) -> None:
        """Очищает состояние диалога пользователя"""
        if user_id in self.states:
            del self.states[user_id]
