import os
import logging
from fastapi import FastAPI, Request
import requests
import json

app = FastAPI()

# Используем OpenRouter API
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# АКТУАЛЬНЫЕ БЕСПЛАТНЫЕ МОДЕЛИ OPENROUTER (проверено работают)
# Полный список: https://openrouter.ai/models?q=free
AVAILABLE_MODELS = {
    "deepseek-v3": "deepseek/deepseek-chat-v3-0324:free",  # DeepSeek V3
    "deepseek-r1": "deepseek/deepseek-r1:free",           # DeepSeek R1 с рассуждениями
    "gemma-3": "google/gemma-3-27b-it:free",              # Google Gemma 3 (отличная альтернатива)
    "llama-3.3": "meta-llama/llama-3.3-70b-instruct:free", # Llama 3.3 70B
    "qwen-2.5": "qwen/qwen2.5-72b-instruct:free"          # Qwen 2.5 72B
}

# Выбираем модель (можно менять по желанию)
SELECTED_MODEL = AVAILABLE_MODELS["deepseek-v3"]  # Используем DeepSeek V3

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
        logger.info(f"Отправляю запрос к OpenRouter, модель: {SELECTED_MODEL}")
        
        # Важно! Правильные заголовки для OpenRouter
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://dialogs.yandex.ru",  # Обязательно для бесплатных моделей
            "X-Title": "Alisa DeepSeek Skill"  # Название вашего навыка
        }
        
        # Формируем запрос
        data = {
            "model": SELECTED_MODEL,
            "messages": [
                {"role": "system", "content": "Ты полезный ассистент. Отвечай кратко, но по существу. Твой ответ будет озвучен Алисой, поэтому используй разговорный стиль, избегай markdown и сложного форматирования."},
                {"role": "user", "content": user_text}
            ],
            "temperature": 0.7,
            "max_tokens": 500,
            "top_p": 0.9
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
            
            # Понятные сообщения об ошибках на основе документации OpenRouter [citation:1]
            error_msg = "Сервис временно недоступен. "
            
            try:
                error_data = response.json()
                if "error" in error_data and "message" in error_data["error"]:
                    error_msg = error_data["error"]["message"]
            except:
                pass
            
            # Специфичные ошибки
            if response.status_code == 404:
                if "data policy" in error_msg.lower():
                    error_msg = "Ошибка приватности. Отключите 'ZDR Endpoints Only' в настройках OpenRouter: https://openrouter.ai/settings/privacy [citation:3]"
                elif "no endpoints found" in error_msg.lower():
                    error_msg = "Модель временно недоступна. Пробуем другую модель..."
                    # Пробуем другую модель при ошибке
                    return await try_alternative_model(body, user_text)
                else:
                    error_msg = f"Модель не найдена. Возможно, она была переименована. Текущая ошибка: {error_msg} [citation:1][citation:7]"
            elif response.status_code == 402:
                error_msg = "Бесплатный лимит исчерпан. Попробуйте другую бесплатную модель или зарегистрируйтесь снова."
            elif response.status_code == 429:
                error_msg = "Слишком много запросов. Бесплатные модели имеют лимит 50 запросов в день. Подождите до 22:00 МСК [citation:1]"
            
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

async def try_alternative_model(body, user_text):
    """Пробует использовать альтернативную модель при ошибке"""
    alternative_models = [
        AVAILABLE_MODELS["gemma-3"],      # Google Gemma 3
        AVAILABLE_MODELS["llama-3.3"],    # Llama 3.3
        AVAILABLE_MODELS["qwen-2.5"],     # Qwen 2.5
    ]
    
    for model in alternative_models:
        try:
            logger.info(f"Пробуем альтернативную модель: {model}")
            
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://dialogs.yandex.ru",
                "X-Title": "Alisa DeepSeek Skill"
            }
            
            data = {
                "model": model,
                "messages": [{"role": "user", "content": user_text}],
                "max_tokens": 500
            }
            
            response = requests.post(
                OPENROUTER_API_URL,
                headers=headers,
                data=json.dumps(data),
                timeout=15
            )
            
            if response.status_code == 200:
                response_data = response.json()
                answer = response_data["choices"][0]["message"]["content"]
                
                return {
                    "version": body.get("version", "1.0"),
                    "session": body.get("session", {}),
                    "response": {
                        "end_session": False,
                        "text": f"[Использую резервную модель] {answer}"
                    }
                }
        except:
            continue
    
    return error_response(body, "Все модели временно недоступны. Попробуйте позже.")

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
        "message": "Alisa DeepSeek Skill is running",
        "current_model": SELECTED_MODEL,
        "available_models": AVAILABLE_MODELS,
        "note": "Если модель не работает, проверьте настройки приватности OpenRouter: https://openrouter.ai/settings/privacy [citation:3]"
    }

@app.get("/health")
async def health():
    """Проверка здоровья"""
    return {
        "status": "healthy",
        "api_key_configured": bool(OPENROUTER_API_KEY),
        "model": SELECTED_MODEL
    }
