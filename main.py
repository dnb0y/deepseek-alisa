import os
from fastapi import FastAPI, Request
import requests
import logging

app = FastAPI()

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Настраиваем логирование для отслеживания ошибок
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.post("/")
async def main(request: Request):
    try:
        # Получаем данные от Алисы
        body = await request.json()
        logger.info(f"Получен запрос: {body}")
        
        # Извлекаем текст пользователя
        user_text = body["request"]["original_utterance"]
        
        if not user_text:
            user_text = "Пустой запрос"
        
        # Проверяем, что ключ API есть
        if not DEEPSEEK_API_KEY:
            logger.error("API ключ DeepSeek не найден")
            return error_response(body, "Ошибка: не настроен API ключ")
        
        # Отправляем запрос к DeepSeek
        logger.info(f"Отправляю запрос к DeepSeek: {user_text}")
        
        response = requests.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "Ты полезный ассистент. Отвечай кратко, но по существу."},
                    {"role": "user", "content": user_text}
                ],
                "temperature": 0.7,
                "max_tokens": 1000
            },
            timeout=30  # Таймаут 30 секунд
        )
        
        # Проверяем статус ответа
        if response.status_code != 200:
            logger.error(f"Ошибка от DeepSeek API: {response.status_code} - {response.text}")
            return error_response(body, f"Извините, сервис временно недоступен. Код ошибки: {response.status_code}")
        
        # Получаем ответ от DeepSeek
        response_data = response.json()
        logger.info(f"Ответ от DeepSeek: {response_data}")
        
        # Безопасно извлекаем ответ с проверкой структуры
        if "choices" in response_data and len(response_data["choices"]) > 0:
            if "message" in response_data["choices"][0] and "content" in response_data["choices"][0]["message"]:
                answer = response_data["choices"][0]["message"]["content"]
            else:
                logger.error(f"Неожиданная структура message: {response_data['choices'][0]}")
                answer = "Извините, получил неожиданный формат ответа"
        else:
            logger.error(f"Нет поля choices в ответе: {response_data}")
            answer = "Извините, не могу обработать запрос"
        
        # Возвращаем ответ Алисе
        return {
            "version": body["version"],
            "session": body["session"],
            "response": {
                "end_session": False,
                "text": answer
            }
        }
        
    except requests.exceptions.Timeout:
        logger.error("Таймаут при запросе к DeepSeek")
        return error_response(body, "Извините, сервер не отвечает. Попробуйте позже.")
        
    except requests.exceptions.ConnectionError:
        logger.error("Ошибка соединения с DeepSeek")
        return error_response(body, "Извините, проблемы с соединением. Попробуйте позже.")
        
    except KeyError as e:
        logger.error(f"Ошибка в структуре запроса от Алисы: {e}")
        return error_response(body, "Извините, не могу обработать ваш запрос")
        
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
async def health_check():
    """Для проверки, что сервер работает"""
    return {"status": "ok", "message": "DeepSeek Alisa skill is running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
