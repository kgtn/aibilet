# AIBilet Telegram Bot

Телеграм бот для интеллектуального поиска авиабилетов с использованием OpenAI GPT и Aviasales API.

## Описание
Бот обрабатывает текстовые запросы пользователей на естественном языке, извлекает необходимые параметры для поиска авиабилетов и возвращает оптимальные варианты перелетов.

## Технологический стек
- Python 3.8+
- python-telegram-bot
- OpenAI API
- Aviasales API
- python-dotenv
- aiohttp

## Конфигурация
Создайте файл `.env` со следующими переменными:
```
TELEGRAM_TOKEN=your_telegram_token
OPENAI_API_KEY=your_openai_api_key
AVIASALES_TOKEN=your_aviasales_token
```

## План реализации

### 1. Базовая структура проекта
```
aibilet/
├── .env                    # Конфигурационные переменные
├── README.md              # Документация проекта
├── requirements.txt       # Зависимости проекта
├── src/
│   ├── __init__.py
│   ├── bot.py            # Основной файл бота
│   ├── config.py         # Конфигурация и загрузка переменных окружения
│   ├── handlers/         # Обработчики сообщений
│   │   ├── __init__.py
│   │   └── message_handler.py
│   ├── services/        # Бизнес-логика
│   │   ├── __init__.py
│   │   ├── openai_service.py    # Работа с OpenAI API
│   │   └── aviasales_service.py # Работа с Aviasales API
│   └── utils/           # Вспомогательные функции
│       ├── __init__.py
│       └── helpers.py
└── tests/              # Тесты
    └── __init__.py
```

## Прогресс реализации проекта

### 2.1 Настройка окружения 
- [x] Создание структуры проекта
- [x] Настройка виртуального окружения
- [x] Установка зависимостей
- [x] Настройка конфигурации

### 2.2 Разработка базовой функциональности бота 
- [x] Создание основного файла бота с обработкой ошибок и логированием
- [x] Реализация обработчика сообщений
- [x] Базовая структура для работы с OpenAI API
- [x] Базовая структура для работы с Aviasales API
- [x] Форматирование сообщений для пользователя

## Следующие этапы
- [ ] 2.3 Интеграция с OpenAI
- [ ] 2.4 Интеграция с Aviasales
- [ ] 2.5 Оптимизация результатов
- [ ] 2.6 Тестирование и отладка

## Примеры запросов
- "Найди билеты из Москвы в Париж на начало июня"
- "Хочу слетать в Барселону из Питера в середине июля на неделю"
- "Билеты в Рим из Москвы на выходные в мае"

## Запуск проекта
```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск бота
python src/bot.py
```