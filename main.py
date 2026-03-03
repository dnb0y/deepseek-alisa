import os
import logging
from fastapi import FastAPI, Request
import requests
import json

app = FastAPI()

# Используем OpenRouter API
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ✅ Только DeepSeek R1 с рассуждениями (полностью бесплатно!)
DEEPSEEK_MODEL = "deepseek/deepseek-r1-distill-llama-70b:free"

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
        
        # Правильные заголовки для OpenRouter
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://dialogs.yandex.ru",
            "X-Title": "Alisa DeepSeek Skill"
        }
        
        # Формируем запрос
        data = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": "Ты полезный ассистент с возможностью рассуждений. Отвечай кратко, но по существу. Твой ответ будет озвучен Алисой, поэтому используй разговорный стиль, избегай markdown и сложного форматирования."},
                {"role": "user", "content": user_text}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        # Отправляем запрос
        response = requests.post(
            OPENROUTER_API_URL,
            headers=headers,
            data=json.dumps(data),
            timeout=30
        )
        
        # Логируем статус для отладки
        logger.info(f"Статус ответа от OpenRouter: {response.status_code}")
        
        # Проверяем статус ответа
        if response.status_code != 200:
            logger.error(f"Ошибка от OpenRouter API: {response.status_code} - {response.text}")
            
            # Понятные сообщения об ошибках
            error_msg = "Сервис временно недоступен. "
            
            try:
                error_data = response.json()
                if "error" in error_data and "message" in error_data["error"]:
                    error_msg = error_data["error"]["message"]
            except:
                pass
            
            # Специфичные ошибки
            if response.status_code == 404:
                error_msg = "Модель DeepSeek R1 временно недоступна. Проверьте: 1) Отключите 'ZDR Endpoints Only' в настройках OpenRouter (https://openrouter.ai/settings/privacy) 2) Модель может быть переименована"
            elif response.status_code == 402:
                error_msg = "Бесплатный лимит DeepSeek R1 исчерпан. Попробуйте позже или используйте другой аккаунт."
            elif response.status_code == 429:
                error_msg = "Слишком много запросов. Бесплатные модели имеют лимит запросов в день. Подождите немного."
            
            return error_response(body, error_msg)
        
        # Получаем ответ от OpenRouter
        response_data = response.json()
        logger.info(f"Получен ответ от OpenRouter")
        
        # Безопасно извлекаем ответ
        answer = "Извините, не удалось получить ответ от нейросети."
        
        if "choices" in response_data and len(response_data["choices"]) > 0:
            if "message" in response_data["choices"][0] and "content" in response_data["choices"][0]["message"]:
                answer = response_data["choices"][0]["message"]["content"]
            elif "text" in response_data["choices"][0]:
                answer = response_data["choices"][0]["text"]
        
        # Обрезаем слишком длинные ответы
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
    """Информация о сервисе"""
    return {
        "status": "ok", 
        "message": "Alisa DeepSeek R1 Skill is running",
        "model": DEEPSEEK_MODEL,
        "note": "Используется только DeepSeek R1 с рассуждениями. Если модель не работает, проверьте настройки приватности OpenRouter: https://openrouter.ai/settings/privacy"
    }

@app.get("/health")
async def health():
    """Проверка здоровья"""
    return {
        "status": "healthy",
        "api_key_configured": bool(OPENROUTER_API_KEY),
        "model": DEEPSEEK_MODEL
    }
