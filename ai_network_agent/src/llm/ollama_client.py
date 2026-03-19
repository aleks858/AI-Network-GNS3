# src/llm/ollama_client.py
# 🤖 Клиент для локальной Ollama - С SYSTEM PROMPT КАК В GITHUB (одной строкой)

import requests
import json
import time
from typing import Optional, Dict, Any, List


class OllamaClient:
    """
    🤖 Клиент для локальной Ollama
    - System prompt одной строкой (как в GitHub клиенте)
    - Не требует внешних вызовов
    """
    
    # 👇 ОДНО ПРЕДЛОЖЕНИЕ - ТОЧНО КАК В GITHUB
    SYSTEM_PROMPT = "Ты - главный эксперт по сетям Cisco. Отвечай на русском языке. Для команд используй формат: оркестратору: [команда] стоп оркестратор"
    
    def __init__(self, model: str = "qwen2.5:7b", host: str = "http://localhost:11434"):
        """
        Инициализация клиента
        """
        self.model = model
        self.host = host
        self.url = f"{host}/api/chat"
        self.timeout = 120
        
        print(f"\n{'='*60}")
        print(f"✅ Ollama клиент инициализирован")
        print(f"   • Модель: {model}")
        print(f"   • Сервер: {host}")
        print(f"   • Системный промпт: как в GitHub (одной строкой)")
        print(f"{'='*60}\n")
        
        self._check_connection()
    
    def _check_connection(self) -> bool:
        """Проверяет доступность Ollama сервера"""
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                print(f"   • Доступные модели: {[m['name'] for m in models]}")
                return True
            return False
        except Exception as e:
            print(f"   ❌ Ollama не доступен: {e}")
            return False
    
    def ask(self, prompt: str, temperature: float = 0.7) -> str:
        """
        Отправляет запрос к модели с system prompt одной строкой
        
        Args:
            prompt: текст запроса
            temperature: температура (0.0 - 1.0)
            
        Returns:
            ответ модели
        """
        print(f"   🤔 Отправляю запрос к {self.model}...")
        
        # Формируем сообщения - system одной строкой + текущий вопрос
        messages = [
            {
                "role": "system",
                "content": self.SYSTEM_PROMPT  # 👇 одно предложение
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        
        try:
            start_time = time.time()
            
            response = requests.post(
                self.url,
                json=payload,
                timeout=self.timeout
            )
            
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                answer = result.get("message", {}).get("content", "")
                print(f"   ✅ Ответ получен за {elapsed:.2f} сек")
                return answer
            else:
                print(f"   ❌ Ошибка {response.status_code}")
                return f"Ошибка: {response.status_code}"
                
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            return f"Ошибка: {e}"
    
    def get_info(self) -> Dict[str, Any]:
        """Возвращает информацию о клиенте"""
        return {
            "model": self.model,
            "provider": "Ollama (local)",
            "system_prompt": self.SYSTEM_PROMPT,
            "mode": "github_compatible"
        }


# ==================== ТЕСТ ====================
def test_ollama():
    """Тестирует работу Ollama с system prompt одной строкой"""
    print("=" * 80)
    print("🧪 ТЕСТ OLLAMA (SYSTEM PROMPT ONE LINE)".center(80))
    print("=" * 80)
    
    client = OllamaClient()
    
    # Тест
    result = client.ask("Привет! Кто ты?")
    print(f"\n📊 Ответ:\n{result}")
    
    print("\n" + "=" * 80)
    print("✅ ТЕСТ ЗАВЕРШЁН".center(80))
    print("=" * 80)


if __name__ == "__main__":
    test_ollama()