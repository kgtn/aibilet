import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from src.services.openai_service import OpenAIService

@pytest.fixture
def openai_service():
    with patch('src.services.openai_service.AsyncOpenAI') as mock_openai:
        service = OpenAIService()
        # Мокаем клиент OpenAI
        service.client = MagicMock()
        service.client.chat.completions.create = AsyncMock()
        yield service

@pytest.mark.asyncio
async def test_extract_flight_params_success(openai_service):
    """Тест успешного извлечения параметров полета"""
    # Подготовка тестовых данных
    test_text = "Найди билеты из Москвы в Париж на 15 июня"
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='''{
                    "origin": "MOW",
                    "destination": "PAR",
                    "origin_city": "Москва",
                    "destination_city": "Париж",
                    "departure_at": "2024-06-15"
                }'''
            )
        )
    ]
    
    # Настройка мока
    openai_service.client.chat.completions.create.return_value = mock_response
    
    # Выполнение теста
    result = await openai_service.extract_flight_params(test_text)
    
    # Проверки
    assert result is not None
    assert result["origin"] == "MOW"
    assert result["destination"] == "PAR"
    assert result["origin_city"] == "Москва"
    assert result["destination_city"] == "Париж"
    assert result["departure_at"] == "2024-06-15"

@pytest.mark.asyncio
async def test_extract_flight_params_with_return(openai_service):
    """Тест извлечения параметров для полета туда и обратно"""
    test_text = "Москва-Париж 15 июня на неделю"
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='''{
                    "origin": "MOW",
                    "destination": "PAR",
                    "origin_city": "Москва",
                    "destination_city": "Париж",
                    "departure_at": "2024-06-15",
                    "return_at": "2024-06-22"
                }'''
            )
        )
    ]
    
    openai_service.client.chat.completions.create.return_value = mock_response
    result = await openai_service.extract_flight_params(test_text)
    
    assert result["return_at"] == "2024-06-22"
    assert (datetime.strptime(result["return_at"], "%Y-%m-%d") - 
            datetime.strptime(result["departure_at"], "%Y-%m-%d")).days == 7

@pytest.mark.asyncio
async def test_extract_flight_params_invalid_response(openai_service):
    """Тест обработки некорректного ответа от OpenAI"""
    test_text = "невалидный запрос"
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"invalid": "response"}'
            )
        )
    ]
    
    openai_service.client.chat.completions.create.return_value = mock_response
    result = await openai_service.extract_flight_params(test_text)
    
    assert result == {}

@pytest.mark.asyncio
async def test_extract_flight_params_with_current_state(openai_service):
    """Тест извлечения параметров с учетом текущего состояния"""
    test_text = "давай на неделю позже"
    current_state = {
        "origin": "MOW",
        "destination": "PAR",
        "departure_at": "2024-06-15"
    }
    
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='''{
                    "origin": "MOW",
                    "destination": "PAR",
                    "origin_city": "Москва",
                    "destination_city": "Париж",
                    "departure_at": "2024-06-22"
                }'''
            )
        )
    ]
    
    openai_service.client.chat.completions.create.return_value = mock_response
    result = await openai_service.extract_flight_params(test_text, current_state)
    
    assert result["departure_at"] == "2024-06-22"
    assert result["origin"] == current_state["origin"]
    assert result["destination"] == current_state["destination"]

@pytest.mark.asyncio
async def test_extract_flight_params_api_error(openai_service):
    """Тест обработки ошибки API OpenAI"""
    test_text = "Москва-Париж завтра"
    
    # Имитируем ошибку API
    openai_service.client.chat.completions.create.side_effect = Exception("API Error")
    
    result = await openai_service.extract_flight_params(test_text)
    assert result == {}
