import os
import logging
from fastapi import FastAPI, Request
import requests
import json

app = FastAPI()

# Используем OpenRouter API вместо прямого DeepSeek
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Модель DeepSeek через OpenRouter (полностью бесплатно!)
# Доступные бесплатные модели:
# - "deepseek/deepseek-chat-v3-0324:free" - последняя версия DeepSeek
# - "deepseek/deepseek-r1:free" - DeepSeek с рассуждениями
# - "deepseek/deepseek-v3-base:free" - базовая версия
DEEPSEEK_MODEL = "deepseek/deepseek-chat-v3-0324:free"

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.post("/")
async def main(request: Request):
    try:
        # Получаем данные от Алисы
        body = await request.json()
        logger.info(f"Получен запрос от Алисы")
        
        # Извлекаем текст пользователя
        if "request" in body and "original_utterance" in body["request"]:
            user_text = body["request"]["original_utterance"]
        else:
            user_text = ""
        
        logger.info(f"Текст пользователя: {user_text}")
        
        if not user_text:
            user_text = "Пустой запрос"
        
        # Проверяем, что ключ API есть
        if not OPENROUTER_API_KEY:
            logger.error("API ключ OpenRouter не найден")
            return error_response(body, "Ошибка: не настроен API ключ OpenRouter. Получите ключ на openrouter.ai")
        
        # Отправляем запрос к OpenRouter
        logger.info(f"Отправляю запрос к OpenRouter, модель: {DEEPSEEK_MODEL}")
        
        # Формируем запрос к OpenRouter
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://dialogs.yandex.ru",  # Откуда пришел запрос
            "X-Title": "Alisa DeepSeek Skill"  # Название вашего навыка
        }
        
        data = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": "Ты полезный ассистент. Отвечай кратко, но по существу. Твой ответ будет озвучен Алисой, поэтому используй разговорный стиль, избегай markdown и сложного форматирования."},
                {"role": "user", "content": user_text}
            ],
            "temperature": 0.7,
            "max_tokens": 500  # Ограничиваем длину ответа для голоса
        }
        
        # Отправляем запрос
        response = requests.post(
            OPENROUTER_API_URL,
            headers=headers,
            data=json.dumps(data),
            timeout=30
        )
        
        # Проверяем статус ответа
        if response.status_code != 200:
            logger.error(f"Ошибка от OpenRouter API: {response.status_code} - {response.text}")
            
            # Понятные сообщения об ошибках
            if response.status_code == 402:
                error_msg = "Бесплатный лимит OpenRouter исчерпан. Попробуйте другую бесплатную модель или зарегистрируйтесь снова."
            elif response.status_code == 401:
                error_msg = "Неверный API ключ OpenRouter. Проверьте ключ в настройках."
            elif response.status_code == 429:
                error_msg = "Слишком много запросов. Подождите немного и попробуйте снова."
            else:
                error_msg = f"Сервис временно недоступен. Код ошибки: {response.status_code}"
            
            return error_response(body, error_msg)
        
        # Получаем ответ от OpenRouter
        response_data = response.json()
        logger.info(f"Получен ответ от OpenRouter")
        
        # Безопасно извлекаем ответ
        answer = "Извините, не удалось получить ответ от нейросети."
        
        if "choices" in response_data and len(response_data["choices"]) > 0:
            if "message" in response_data["choices"][0] and "content" in response_data["choices"][0]["message"]:
                answer = response_data["choices"][0]["message"]["content"]
            elif "text" in response_data["choices"][0]:  # Некоторые модели возвращают text вместо message.content
                answer = response_data["choices"][0]["text"]
        elif "error" in response_data:
            logger.error(f"Ошибка в ответе: {response_data['error']}")
            answer = f"Ошибка: {response_data['error'].get('message', 'неизвестная ошибка')}"
        
        # Обрезаем слишком длинные ответы (Алиса не любит длинные тексты)
        if len(answer) > 1000:
            answer = answer[:1000] + "..."
        
        # Возвращаем ответ Алисе
        return {
            "version": body.get("version", "1.0"),
            "session": body.get("session", {}),
            "response": {
                "end_session": False,
                "text": answer
            }
        }
        
    except requests.exceptions.Timeout:
        logger.error("Таймаут при запросе к OpenRouter")
        return error_response(body, "Извините, сервер не отвечает. Попробуйте позже.")
        
    except requests.exceptions.ConnectionError:
        logger.error("Ошибка соединения с OpenRouter")
        return error_response(body, "Извините, проблемы с соединением. Попробуйте позже.")
        
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON: {e}")
        return error_response(body, "Извините, получен некорректный ответ от сервера.")
        
    except KeyError as e:
        logger.error(f"Ошибка в структуре запроса от Алисы: {e}")
        return error_response(body, "Извините, не могу обработать ваш запрос.")
        
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {str(e)}", exc_info=True)
        return error_response(body, "Произошла внутренняя ошибка. Мы уже работаем над этим.")

def error_response(body, text):
    """Функция для формирования ответа с ошибкой"""
    return {
        "version": body.get("version", "1.0"),
        "session": body.get("session", {}),
        "response": {
            "end_session": False,
            "text": text
        }
    }

@app.get("/")
async def root():
    """Корневой путь - информация о сервисе"""
    return {
        "status": "ok", 
        "message": "DeepSeek Alisa skill is running via OpenRouter",
        "models": [
            "deepseek/deepseek-chat-v3-0324:free",
            "deepseek/deepseek-r1:free",
            "deepseek/deepseek-v3-base:free"
        ]
    }

@app.get("/health")
async def health():
    """Проверка здоровья сервиса"""
    return {
        "status": "healthy",
        "api_key_configured": bool(OPENROUTER_API_KEY)
    }

@app.get("/test")
async def test():
    """Тестовый endpoint для проверки без Алисы"""
    return {
        "message": "Сервер работает! Для использования навыка перейдите в Яндекс.Диалоги."
    }
