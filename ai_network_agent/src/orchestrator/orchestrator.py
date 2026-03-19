# src/orchestrator/orchestrator.py
# 🎼 ОРКЕСТРАТОР v5.3 - С РАСШИРЕННЫМ ПРОМПТОМ И МАКСИМАЛЬНЫМ ЛОГИРОВАНИЕМ
# - 6 частей промпта для гарантированного понимания
# - Детальное логирование каждого шага
# - Полная видимость работы оркестратора и исполнителя

import asyncio
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import json
import time
import threading
import traceback
from collections import deque
from enum import Enum
import sys
from pathlib import Path
import signal
import atexit
import socket
import gc

# Добавляем путь к проекту
sys.path.append(str(Path(__file__).parent.parent.parent))

# Импорт клиента GitHub (или запасной Qwen)
try:
    #from src.llm.github_client import GitHubModelsClient
    #LLM_CLIENT = GitHubModelsClient
    #LLM_NAME = "GitHub Models (GPT-4o mini)"
    #NEEDS_API_KEY = True
    raise Exception ("Используем Qwen")
except:
    from src.llm.ollama_client import OllamaClient
    LLM_CLIENT = OllamaClient
    LLM_NAME = "Ollama (Qwen)"
    NEEDS_API_KEY = False

class ComponentStatus(Enum):
    """Статусы здоровья компонентов"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    NOT_INITIALIZED = "not_initialized"


class Orchestrator:
    """
    🎼 ОРКЕСТРАТОР v5.3 - С РАСШИРЕННЫМ ПРОМПТОМ
    """
    
    # Константы
    MAX_HISTORY = 1000
    MAX_LOG_ENTRIES = 500
    MEMORY_SYNC_INTERVAL = 300  # 5 минут
    HEALTH_CHECK_INTERVAL = 60  # 60 секунд
    EXECUTOR_TIMEOUT = 15
    LLM_TIMEOUT = 300
    RETRY_DELAY = 3
    MAX_RETRIES = 2
    OLLAMA_PORT = 11434
    GNS3_API_PORT = 3080
    GITHUB_API_KEY = "YOUR_GITHUB_TOKEN_HERE"  # Твой ключ
    
    # Текущее выбранное устройство
    _current_device = None
    
    def __init__(self, websocket_callback=None):
        """
        Инициализация оркестратора
        """
        print("\n" + "="*100)
        print("🚀 ЗАПУСК ОРКЕСТРАТОРА v5.3".center(100))
        print("="*100)
        
        # Компоненты
        self.llm = None
        self.executor = None
        self.memory = None
        
        # Флаг завершения
        self.shutdown_flag = False
        self.shutdown_complete = threading.Event()
        
        # Флаг занятости LLM
        self.llm_busy = False
        self.llm_busy_lock = threading.RLock()
        
        # Статусы компонентов
        self.component_status = {
            'llm': {'available': False, 'last_check': None, 'failures': 0},
            'executor': {'available': False, 'last_check': None, 'failures': 0},
            'memory': {'available': False, 'last_check': None, 'failures': 0}
        }
        
        # Здоровье компонентов
        self.component_health = {
            'llm': {
                'status': ComponentStatus.NOT_INITIALIZED,
                'last_ok': None,
                'failures': 0,
                'response_time': None,
                'last_error': None,
                'last_error_time': None
            },
            'executor': {
                'status': ComponentStatus.NOT_INITIALIZED,
                'last_ok': None,
                'failures': 0,
                'response_time': None,
                'last_error': None,
                'last_error_time': None
            },
            'memory': {
                'status': ComponentStatus.NOT_INITIALIZED,
                'last_ok': None,
                'failures': 0,
                'response_time': None,
                'last_error': None,
                'last_error_time': None
            }
        }
        
        # Блокировки
        self.history_lock = threading.RLock()
        self.stats_lock = threading.RLock()
        self.status_lock = threading.RLock()
        self.health_lock = threading.RLock()
        self.cache_lock = threading.RLock()
        self.device_lock = threading.RLock()
        
        # Логирование
        self.ws_callback = websocket_callback
        self.event_log = deque(maxlen=self.MAX_LOG_ENTRIES)
        
        # История диалога
        self.conversation_history = deque(maxlen=self.MAX_HISTORY)
        
        # 6 частей промпта (расширенные)
        self.prompt_parts = [
            "Привет! Я оркестратор. Начинаем диалог.",
            
            "ТЫ - ГЛАВНЫЙ ЭКСПЕРТ ПО СЕТЯМ CISCO. Твоя задача - помогать с настройкой оборудования через оркестратор.",
            
            "ТВОЙ ИНСТРУМЕНТ - ОРКЕСТРАТОР. Он подключен к устройствам Cisco в GNS3. Ты общаешься с ним через специальные команды.",
            
            "ПРАВИЛО 1: Сначала ВСЕГДА выбирай устройство отдельной командой. Формат: оркестратору: ИМЯ_УСТРОЙСТВА стоп оркестратор. Пример: оркестратору: CORE1 стоп оркестратор",
            
            "ПРАВИЛО 2: После выбора устройства отправляй команды по одной. Формат: оркестратору: КОМАНДА_CISCO стоп оркестратор. Пример: оркестратору: show version стоп оркестратор",
            
            "ПРАВИЛО 3: Команды ТОЛЬКО на английском языке. Кавычки используй только если они часть команды. Не отправляй несколько команд в одном сообщении. Запомнил? Ответь кратко."
        ]
        
        self.system_prompt_sent = False
        self.system_prompt_acknowledged = False
        
        # Синхронизация с памятью
        self.last_memory_sync = datetime.now()
        self.last_synced_index = 0
        self.memory_sync_failures = 0
        
        # Статистика
        self.stats = {
            'messages_processed': 0,
            'commands_executed': 0,
            'commands_failed': 0,
            'memory_syncs': 0,
            'memory_sync_failures': 0,
            'retries_performed': 0,
            'health_checks_performed': 0,
            'device_switches': 0,
            'llm_calls': 0,
            'errors': deque(maxlen=50)
        }
        
        # Кэш
        self.response_cache = {}
        self.cache_ttl = 300
        
        # Фоновые потоки
        self.background_threads = []
        
        # Регистрируем обработчики
        atexit.register(self._graceful_shutdown)
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        except:
            pass
        
        # ===== ЗАПУСК =====
        self._check_environment()
        self._init_components()
        self._start_background_tasks()
        
        if self._is_component_available('llm'):
            self._send_prompt_parts()  # Отправляем 6 частей
        else:
            self._log("⚠️ LLM недоступна", "WARNING")
        
        self._print_status()
        self._log("🎼 Оркестратор готов к работе", "SUCCESS")
    
    # ==================== ОТПРАВКА 6 ЧАСТЕЙ ====================
    
    def _send_prompt_parts(self):
        """
        🚀 Отправка 6 частей промпта по очереди
        Каждая часть отправляется после получения ответа на предыдущую
        """
        if not self._is_component_available('llm') or self.llm is None:
            self._log("⚠️ LLM недоступна", "WARNING")
            return False
        
        self._log("📤 ЗАПУСК ОТПРАВКИ 6 ЧАСТЕЙ ПРОМПТА...", "INFO")
        self._log("📋 ДЕТАЛЬНЫЕ ИНСТРУКЦИИ ДЛЯ LLM:", "INFO")
        
        for i, part in enumerate(self.prompt_parts):
            self._log(f"📄 ЧАСТЬ {i+1}/6: {part[:100]}...", "INFO")
            
            try:
                response = self.llm.ask(part)
                self._log(f"💬 ОТВЕТ НА ЧАСТЬ {i+1}: {response[:200]}...", "INFO")
                
                # Сохраняем в историю
                self._add_to_history('system', f"Prompt part {i+1}", {'part': i+1})
                self._add_to_history('assistant', response, {'part': i+1})
                
                # Пауза между частями
                time.sleep(1)
                
            except Exception as e:
                self._log(f"❌ ОШИБКА ПРИ ОТПРАВКЕ ЧАСТИ {i+1}: {e}", "ERROR")
        
        self.system_prompt_sent = True
        self._log("✅ ВСЕ 6 ЧАСТЕЙ ПРОМПТА УСПЕШНО ОТПРАВЛЕНЫ", "SUCCESS")
        return True
    
    # ==================== ИЗВЛЕЧЕНИЕ КОМАНД С МАКСИМАЛЬНЫМ ЛОГИРОВАНИЕМ ====================
    
    def _extract_commands_from_llm(self, text: str) -> List[Tuple[Optional[str], str]]:
        """
        Извлекает команды из ответа LLM с МАКСИМАЛЬНЫМ ЛОГИРОВАНИЕМ
        """
        self._log(f"{'='*60}", "INFO")
        self._log(f"🔍 АНАЛИЗ ОТВЕТА LLM НАЛИЧИЕ КОМАНД", "INFO")
        self._log(f"{'='*60}", "INFO")
        
        self._log(f"📨 ДЛИНА ТЕКСТА: {len(text)} символов", "INFO")
        self._log(f"📨 ПЕРВЫЕ 200 СИМВОЛОВ:", "INFO")
        self._log(f"{text[:200]}", "INFO")
        self._log(f"📨 REPR ПРЕДСТАВЛЕНИЕ (видно спецсимволы):", "INFO")
        self._log(f"{repr(text[:200])}", "INFO")
        
        # Паттерн для поиска команд
        pattern = r'оркестратору:(.*?)(?:стоп оркестратор|$)'
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
        
        self._log(f"🔍 REGEX НАШЕЛ {len(matches)} СОВПАДЕНИЙ", "INFO")
        
        commands = []
        current_device = None
        
        for i, full_command in enumerate(matches):
            full_command = full_command.strip()
            self._log(f"{'─'*40}", "INFO")
            self._log(f"🔍 СОВПАДЕНИЕ {i+1}: '{full_command[:100]}...'", "INFO")
            
            if not full_command:
                self._log(f"⚠️ ПУСТОЕ СОВПАДЕНИЕ - ПРОПУСК", "WARNING")
                continue
            
            # Проверка на запрос к памяти
            if full_command.lower().startswith('memory_search'):
                self._log(f"📚 ОБНАРУЖЕН ЗАПРОС К ПАМЯТИ: {full_command[:50]}...", "INFO")
                continue
            
            # Проверка на выбор устройства (одно слово, только буквы/цифры)
            if re.match(r'^[A-Z0-9]+$', full_command, re.IGNORECASE):
                with self.device_lock:
                    self._current_device = full_command.upper()
                    current_device = full_command.upper()
                self._log(f"🎯 ВЫБРАНО УСТРОЙСТВО: {current_device}", "SUCCESS")
                with self.stats_lock:
                    self.stats['device_switches'] += 1
                continue
            
            # Если это команда - используем текущее устройство
            with self.device_lock:
                device = self._current_device
            
            if device is None:
                self._log(f"⚠️ КОМАНДА БЕЗ УСТРОЙСТВА: {full_command[:50]}...", "WARNING")
                self._log(f"   Будет отправлена на устройство по умолчанию", "WARNING")
                commands.append((None, full_command))
            else:
                self._log(f"✅ КОМАНДА ДЛЯ УСТРОЙСТВА {device}: {full_command[:50]}...", "INFO")
                commands.append((device, full_command))
        
        self._log(f"{'─'*40}", "INFO")
        self._log(f"📊 ИТОГО КОМАНД К ВЫПОЛНЕНИЮ: {len(commands)}", "INFO")
        
        if commands:
            for i, (dev, cmd) in enumerate(commands):
                self._log(f"   Команда {i+1}: устройство={dev or 'default'}, команда={cmd[:50]}...", "INFO")
        
        self._log(f"{'='*60}", "INFO")
        return commands
    
    # ==================== ОСНОВНОЙ МЕТОД PROCESS_REQUEST ====================
    
    async def process_request(self, user_input: str, from_web: bool = True) -> str:
        """Обработка запроса с МАКСИМАЛЬНЫМ ЛОГИРОВАНИЕМ"""
        
        self._log(f"{'='*60}", "INFO")
        self._log(f"📨 PROCESS_REQUEST ВЫЗВАН", "INFO")
        self._log(f"📨 from_web = {from_web}", "INFO")
        self._log(f"📨 ДЛИНА ВХОДНЫХ ДАННЫХ: {len(user_input)}", "INFO")
        self._log(f"📨 ПЕРВЫЕ 200 СИМВОЛОВ: {user_input[:200]}", "INFO")
        self._log(f"{'='*60}", "INFO")
        
        if self.shutdown_flag:
            self._log("🛑 ОРКЕСТРАТОР ЗАВЕРШАЕТ РАБОТУ", "WARNING")
            return "Оркестратор завершает работу"
        
        with self.stats_lock:
            self.stats['messages_processed'] += 1
        
        # ===== ОТ LLM (содержит команды) =====
        if not from_web:
            self._log("📥 ОБРАБОТКА ОТВЕТА ОТ LLM", "INFO")
            self._add_to_history('assistant', user_input, {'source': 'llm'})
            
            commands = self._extract_commands_from_llm(user_input)
            
            if commands:
                self._log(f"🚀 НАЙДЕНО {len(commands)} КОМАНД ДЛЯ ВЫПОЛНЕНИЯ", "SUCCESS")
                
                results = []
                for i, (device, command) in enumerate(commands):
                    self._log(f"{'─'*40}", "INFO")
                    self._log(f"🎯 ВЫПОЛНЕНИЕ КОМАНДЫ {i+1}/{len(commands)}", "INFO")
                    self._log(f"   Устройство: {device or 'default'}", "INFO")
                    self._log(f"   Команда: {command}", "INFO")
                    
                    result = await self._execute_command_with_retry(device, command)
                    results.append(result)
                    
                    self._log(f"   РЕЗУЛЬТАТ: {result[:100]}...", "INFO")
                
                # Формируем результат
                if len(results) == 1:
                    combined_result = results[0]
                else:
                    combined_result = "\n\n---\n\n".join([
                        f"📟 Результат команды {i+1}:\n{r}" 
                        for i, r in enumerate(results)
                    ])
                
                self._add_to_history('system', combined_result, {'type': 'batch_command'})
                self._log(f"✅ ВСЕ КОМАНДЫ ВЫПОЛНЕНЫ", "SUCCESS")
                return combined_result
            else:
                self._log(f"❌ КОМАНД НЕ НАЙДЕНО В ОТВЕТЕ LLM", "ERROR")
                self._log(f"   Ответ LLM будет передан как обычный текст", "INFO")
                return user_input
        
        # ===== ОТ ПОЛЬЗОВАТЕЛЯ =====
        else:
            self._log("👤 ОБРАБОТКА ЗАПРОСА ОТ ПОЛЬЗОВАТЕЛЯ", "INFO")
            self._add_to_history('user', user_input)
            
            if not self._is_component_available('llm') or self.llm is None:
                self._log("❌ LLM НЕДОСТУПНА", "ERROR")
                return "❌ LLM недоступна"
            
            with self.stats_lock:
                self.stats['llm_calls'] += 1
            
            self._log("🔄 ОТПРАВКА ЗАПРОСА В LLM...", "INFO")
            response = await self._get_llm_response(user_input, self._get_context_for_llm())
            self._log("✅ ОТВЕТ ПОЛУЧЕН ОТ LLM", "SUCCESS")
            
            self._add_to_history('assistant', response, {'source': 'llm'})
            return response
    
    # ==================== ВЫПОЛНЕНИЕ КОМАНД ====================
    
    async def _execute_command_with_retry(self, device: Optional[str], command: str) -> str:
        """Выполнение команды с повторными попытками"""
        self._log(f"🔄 _execute_command_with_retry: устройство={device}, команда={command[:50]}...", "INFO")
        
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                if self.shutdown_flag:
                    return "оркестратор отчитался об ошибке: Оркестратор завершает работу"
                
                if attempt > 0:
                    self._log(f"🔄 ПОВТОРНАЯ ПОПЫТКА {attempt + 1}/{self.MAX_RETRIES}", "INFO")
                    with self.stats_lock:
                        self.stats['retries_performed'] += 1
                    await asyncio.sleep(self.RETRY_DELAY * attempt)
                
                result = await self._execute_command_single(device, command)
                
                if not result.startswith("оркестратор отчитался об ошибке: Нет соединения"):
                    return result
                
                last_error = result
                
            except Exception as e:
                last_error = str(e)
                self._log(f"❌ ОШИБКА ПРИ ВЫПОЛНЕНИИ: {e}", "ERROR")
        
        with self.stats_lock:
            self.stats['commands_failed'] += 1
        
        return f"оркестратор отчитался об ошибке: Не удалось выполнить после {self.MAX_RETRIES} попыток"
    
    async def _execute_command_single(self, device: Optional[str], command: str) -> str:
        """Однократное выполнение команды"""
        self._log(f"⚙️ _execute_command_single: устройство={device}, команда={command[:50]}...", "INFO")
        
        if self.executor is None:
            self._log("❌ ИСПОЛНИТЕЛЬ НЕ ИНИЦИАЛИЗИРОВАН", "ERROR")
            return "оркестратор отчитался об ошибке: Исполнитель не инициализирован"
        
        device_name = device if device is not None else ""
        self._log(f"📤 ОТПРАВКА В EXECUTOR: устройство='{device_name}', команда='{command}'", "INFO")
        
        try:
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, self.executor.send, device_name, command),
                timeout=self.EXECUTOR_TIMEOUT
            )
            
            if result.success:
                with self.stats_lock:
                    self.stats['commands_executed'] += 1
                self._log(f"✅ КОМАНДА УСПЕШНО ВЫПОЛНЕНА", "SUCCESS")
                self._log(f"   РЕЗУЛЬТАТ: {result.response[:200]}...", "INFO")
                return f"оркестратор отчитался: {result.response}"
            else:
                with self.stats_lock:
                    self.stats['commands_failed'] += 1
                self._log(f"⚠️ КОМАНДА ВЕРНУЛА ОШИБКУ: {result.error}", "WARNING")
                return f"оркестратор отчитался об ошибке: {result.error}"
                
        except asyncio.TimeoutError:
            with self.stats_lock:
                self.stats['commands_failed'] += 1
            self._log(f"⏰ ТАЙМАУТ ВЫПОЛНЕНИЯ {self.EXECUTOR_TIMEOUT} СЕК", "ERROR")
            return f"оркестратор отчитался об ошибке: Таймаут ({self.EXECUTOR_TIMEOUT} сек)"
            
        except ConnectionRefusedError:
            self._update_component_status('executor', False)
            self._update_component_health('executor', False, error="Connection refused")
            with self.stats_lock:
                self.stats['commands_failed'] += 1
            self._log("🔌 НЕТ СОЕДИНЕНИЯ С GNS3", "ERROR")
            return "оркестратор отчитался об ошибке: Нет соединения с GNS3"
            
        except Exception as e:
            self._log(f"❌ НЕОЖИДАННАЯ ОШИБКА: {e}", "ERROR")
            with self.stats_lock:
                self.stats['commands_failed'] += 1
            return f"оркестратор отчитался об ошибке: {str(e)}"
    
    # ==================== LLM ====================
    
    async def _get_llm_response(self, user_input: str, context: List = None) -> str:
        """Получение ответа от LLM"""
        self._log(f"🔄 _get_llm_response: запрос пользователя: {user_input[:100]}...", "INFO")
        
        if self.llm is None:
            self._log("❌ LLM НЕ ИНИЦИАЛИЗИРОВАН", "ERROR")
            return "Ошибка: LLM не инициализирован"
        
        with self.llm_busy_lock:
            if self.llm_busy:
                self._log("⚠️ LLM ЗАНЯТА, ОЖИДАНИЕ...", "WARNING")
                await asyncio.sleep(1)
        
        with self._llm_busy_context():
            # Проверка кэша
            cache_key = user_input.strip().lower()
            if len(cache_key) < 50:
                with self.cache_lock:
                    cached = self.response_cache.get(cache_key)
                    if cached and time.time() - cached[1] < self.cache_ttl:
                        self._log("📦 ИСПОЛЬЗУЮ КЭШИРОВАННЫЙ ОТВЕТ", "INFO")
                        return cached[0]
            
            try:
                # Формируем контекст
                full_context = ""
                if context:
                    full_context = "Контекст:\n" + "\n".join(context[-3:])
                
                prompt = f"{full_context}\n\nПользователь: {user_input}" if full_context else user_input
                
                self._log("📤 ОТПРАВКА ЗАПРОСА В LLM...", "INFO")
                loop = asyncio.get_event_loop()
                response = await asyncio.wait_for(
                    loop.run_in_executor(None, self.llm.ask, prompt),
                    timeout=self.LLM_TIMEOUT
                )
                self._log("📥 ПОЛУЧЕН ОТВЕТ ОТ LLM", "SUCCESS")
                
                # Кэшируем
                if len(cache_key) < 50:
                    with self.cache_lock:
                        self.response_cache[cache_key] = (response, time.time())
                
                return response
                
            except asyncio.TimeoutError:
                self._update_component_health('llm', False, error="Timeout")
                self._log(f"⏰ ТАЙМАУТ LLM {self.LLM_TIMEOUT} СЕК", "ERROR")
                return f"Ошибка: Таймаут {self.LLM_TIMEOUT} сек"
            except Exception as e:
                self._update_component_health('llm', False, error=str(e))
                self._log(f"❌ ОШИБКА LLM: {e}", "ERROR")
                return f"Ошибка: {str(e)}"
    
    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================
    
    def _llm_busy_context(self):
        class _LLMBusyContext:
            def __init__(self, outer):
                self.outer = outer
            def __enter__(self):
                with self.outer.llm_busy_lock:
                    self.outer.llm_busy = True
                    self.outer._log("🔴 LLM ЗАНЯТА", "DEBUG")
            def __exit__(self, exc_type, exc_val, exc_tb):
                with self.outer.llm_busy_lock:
                    self.outer.llm_busy = False
                    self.outer._log("🟢 LLM СВОБОДНА", "DEBUG")
        return _LLMBusyContext(self)
    
    def _check_environment(self):
        """Проверка окружения"""
        self._log("🔍 ПРОВЕРКА ОКРУЖЕНИЯ...", "INFO")
        
        dirs = [
            "knowledge_base/raw/history", "knowledge_base/raw/chat",
            "knowledge_base/raw/docs", "knowledge_base/raw/errors",
            "knowledge_base/raw/scripts", "knowledge_base/chromadb",
            "knowledge_base/processed/chunks", "logs"
        ]
        for d in dirs:
            try:
                Path(d).mkdir(parents=True, exist_ok=True)
                self._log(f"   📁 {d} - создана/существует", "DEBUG")
            except:
                pass
        
        # Проверка портов
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('localhost', self.OLLAMA_PORT))
            self._log("✅ Ollama порт 11434 - доступен" if result == 0 else "⚠️ Ollama порт 11434 - не отвечает", 
                     "SUCCESS" if result == 0 else "WARNING")
            sock.close()
        except:
            self._log("⚠️ Не удалось проверить Ollama порт", "WARNING")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('localhost', self.GNS3_API_PORT))
            self._log("✅ GNS3 порт 3080 - доступен" if result == 0 else "⚠️ GNS3 порт 3080 - не отвечает", 
                     "SUCCESS" if result == 0 else "WARNING")
            sock.close()
        except:
            self._log("⚠️ Не удалось проверить GNS3 порт", "WARNING")
    
    def _init_components(self):
        """Инициализация компонентов"""
        self._log("🔧 ИНИЦИАЛИЗАЦИЯ КОМПОНЕНТОВ...", "INFO")
        
        # LLM
        try:
            if NEEDS_API_KEY:
                self.llm = LLM_CLIENT(api_key=self.GITHUB_API_KEY)
            else:
                self.llm = LLM_CLIENT()
            
            self._update_component_status('llm', True)
            self._update_component_health('llm', True, 0)
            self._log(f"✅ {LLM_NAME} - УСПЕШНО", "SUCCESS")
        except Exception as e:
            self.llm = None
            self._update_component_status('llm', False)
            self._update_component_health('llm', False, error=str(e))
            self._log(f"❌ LLM - ОШИБКА: {e}", "ERROR")
        
        # Executor
        try:
            from src.executor.executor import SocketExecutor
            self.executor = SocketExecutor()
            self._update_component_status('executor', True)
            self._update_component_health('executor', True)
            self._log("✅ Executor - УСПЕШНО", "SUCCESS")
            devices = list(self.executor.DEVICE_PORTS.keys())
            self._log(f"📋 Доступные устройства: {', '.join(devices)}", "INFO")
        except Exception as e:
            self.executor = None
            self._update_component_status('executor', False)
            self._update_component_health('executor', False, error=str(e))
            self._log(f"❌ Executor - ОШИБКА: {e}", "ERROR")
        
        # Memory
        try:
            from src.memory.manager import MemoryManager
            self.memory = MemoryManager()
            self._update_component_status('memory', True)
            self._update_component_health('memory', True)
            self._log("✅ Memory Manager - УСПЕШНО", "SUCCESS")
        except Exception as e:
            self.memory = None
            self._update_component_status('memory', False)
            self._update_component_health('memory', False, error=str(e))
            self._log(f"⚠️ Memory Manager - ОШИБКА: {e}", "WARNING")
    
    def _is_component_available(self, component: str) -> bool:
        with self.status_lock:
            return self.component_status.get(component, {}).get('available', False)
    
    def _update_component_status(self, component: str, available: bool):
        with self.status_lock:
            if component in self.component_status:
                self.component_status[component]['available'] = available
                self.component_status[component]['last_check'] = datetime.now()
                self.component_status[component]['failures'] = 0 if available else \
                    self.component_status[component]['failures'] + 1
    
    def _update_component_health(self, component: str, healthy: bool, 
                                response_time: float = None, error: str = None):
        with self.health_lock:
            if component not in self.component_health:
                return
            
            health = self.component_health[component]
            
            if healthy:
                health['status'] = ComponentStatus.HEALTHY
                health['last_ok'] = datetime.now()
                health['failures'] = 0
                if response_time is not None:
                    health['response_time'] = response_time
                health['last_error'] = None
                health['last_error_time'] = None
                self._update_component_status(component, True)
            else:
                health['failures'] += 1
                if health['failures'] >= 3:
                    health['status'] = ComponentStatus.UNHEALTHY
                    self._update_component_status(component, False)
                else:
                    health['status'] = ComponentStatus.DEGRADED
                
                if error:
                    health['last_error'] = error
                    health['last_error_time'] = datetime.now()
    
    def _log(self, message: str, level: str = "INFO", details: Dict = None):
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = {
            'timestamp': timestamp,
            'level': level,
            'message': message,
            'details': details or {}
        }
        
        self.event_log.append(log_entry)
        print(f"[{timestamp}] [{level}] {message}")
        
        if self.ws_callback and not self.shutdown_flag:
            try:
                self.ws_callback(log_entry)
            except:
                pass
        
        return log_entry
    
    def _print_status(self):
        print("\n" + "-"*80)
        print("📊 СТАТУС КОМПОНЕНТОВ:")
        
        with self.health_lock:
            for component, health in self.component_health.items():
                status = health['status']
                icon = {
                    ComponentStatus.HEALTHY: '🟢',
                    ComponentStatus.DEGRADED: '🟡',
                    ComponentStatus.UNHEALTHY: '🔴',
                    ComponentStatus.UNKNOWN: '⚪',
                    ComponentStatus.NOT_INITIALIZED: '⚫'
                }.get(status, '❓')
                
                failures = f" (сбоев: {health['failures']})" if health['failures'] > 0 else ""
                response_time = f" {health['response_time']:.2f}с" if health.get('response_time') else ""
                
                print(f"   {icon} {component.upper()}: {status.value}{response_time}{failures}")
        
        print("-"*80)
    
    def _add_to_history(self, role: str, content: str, metadata: Dict = None):
        if self.shutdown_flag:
            return
        
        with self.history_lock:
            self.conversation_history.append({
                'timestamp': datetime.now().isoformat(),
                'role': role,
                'content': content,
                'metadata': metadata or {}
            })
    
    def _get_context_for_llm(self) -> List[str]:
        with self.history_lock:
            if len(self.conversation_history) > 0:
                return [msg['content'] for msg in list(self.conversation_history)[-5:]]
        return []
    
    def _start_background_tasks(self):
        """Запуск фоновых задач"""
        self._log("🔄 ЗАПУСК ФОНОВЫХ ЗАДАЧ...", "INFO")
        
        tasks = [
            ("memory_sync", self._sync_loop),
            ("health_check", self._health_check_loop),
            ("cache_cleanup", self._cleanup_cache_loop)
        ]
        
        for name, target in tasks:
            thread = threading.Thread(target=self._thread_wrapper, args=(name, target), daemon=True)
            thread.start()
            self.background_threads.append(thread)
            self._log(f"   ✅ Задача '{name}' запущена", "SUCCESS")
    
    def _thread_wrapper(self, name: str, func):
        try:
            func()
        except Exception as e:
            self._log(f"💥 Задача '{name}' упала: {e}", "ERROR")
            traceback.print_exc()
    
    def _sync_loop(self):
        while not self.shutdown_flag:
            try:
                time.sleep(self.MEMORY_SYNC_INTERVAL)
                if self.shutdown_flag:
                    break
                self._sync_with_memory()
                gc.collect()
            except Exception as e:
                self._log(f"⚠️ Ошибка в синхронизации: {e}", "ERROR")
                time.sleep(10)
    
    def _health_check_loop(self):
        while not self.shutdown_flag:
            try:
                time.sleep(self.HEALTH_CHECK_INTERVAL)
                if self.shutdown_flag:
                    break
                self._check_components_health()
                with self.stats_lock:
                    self.stats['health_checks_performed'] += 1
            except Exception as e:
                self._log(f"⚠️ Ошибка в health check: {e}", "ERROR")
                time.sleep(5)
    
    def _cleanup_cache_loop(self):
        while not self.shutdown_flag:
            try:
                time.sleep(60)
                if self.shutdown_flag:
                    break
                self._cleanup_cache()
            except Exception as e:
                self._log(f"⚠️ Ошибка очистки кэша: {e}", "ERROR")
    
    def _check_components_health(self):
        """Проверка здоровья БЕЗ НАГРУЗКИ НА LLM"""
        with self.llm_busy_lock:
            llm_busy = self.llm_busy
        
        # Проверка LLM - только порт
        if self.llm is not None and not llm_busy:
            try:
                start = time.time()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex(('localhost', self.OLLAMA_PORT))
                sock.close()
                
                if result == 0:
                    response_time = time.time() - start
                    self._update_component_health('llm', True, response_time)
                    self._log("✅ Health check LLM: порт доступен", "DEBUG")
                else:
                    raise ConnectionError("Ollama port not available")
            except Exception as e:
                self._update_component_health('llm', False, error=str(e))
                self._log(f"⚠️ Health check LLM: {e}", "DEBUG")
        elif llm_busy:
            self._log("⏳ Health check LLM: пропущен (LLM занята)", "DEBUG")
        
        # Проверка Executor
        if self.executor is not None:
            try:
                status = self.executor.get_status()
                self._update_component_health('executor', True)
                self._log("✅ Health check Executor: OK", "DEBUG")
            except Exception as e:
                self._update_component_health('executor', False, error=str(e))
                self._log(f"⚠️ Health check Executor: {e}", "DEBUG")
        
        # Проверка Memory
        if self.memory is not None:
            try:
                if hasattr(self.memory, 'get_stats'):
                    self.memory.get_stats()
                self._update_component_health('memory', True)
                self._log("✅ Health check Memory: OK", "DEBUG")
            except Exception as e:
                self._update_component_health('memory', False, error=str(e))
                self._log(f"⚠️ Health check Memory: {e}", "DEBUG")
    
    def _cleanup_cache(self):
        now = time.time()
        with self.cache_lock:
            expired = [k for k, (_, ts) in self.response_cache.items() 
                      if now - ts > self.cache_ttl]
            for k in expired:
                del self.response_cache[k]
            if expired:
                self._log(f"🧹 Очищено {len(expired)} устаревших записей кэша", "DEBUG")
    
    def _sync_with_memory(self, force: bool = False):
        """Синхронизация с памятью"""
        if self.memory is None:
            return
        
        with self.history_lock:
            if not force and len(self.conversation_history) <= self.last_synced_index:
                return
            new_messages = list(self.conversation_history)[self.last_synced_index:]
            if not new_messages and not force:
                return
        
        try:
            if hasattr(self.memory, 'learn_from_log'):
                self.memory.learn_from_log({
                    'timestamp': datetime.now().isoformat(),
                    'messages': new_messages,
                    'total_messages': len(self.conversation_history),
                    'sync_type': 'final' if force else 'periodic'
                }, category="history")
                
                with self.history_lock:
                    self.last_synced_index = len(self.conversation_history)
                
                with self.stats_lock:
                    self.stats['memory_syncs'] += 1
                
                self.memory_sync_failures = 0
                sync_type = "принудительная" if force else "периодическая"
                self._log(f"✅ {sync_type} синхронизация: {len(new_messages)} сообщений")
            else:
                self._log("⚠️ Memory Manager не поддерживает learn_from_log", "WARNING")
        except Exception as e:
            self.memory_sync_failures += 1
            with self.stats_lock:
                self.stats['memory_sync_failures'] += 1
            self._log(f"⚠️ Ошибка синхронизации: {e}", "WARNING")
    
    def _graceful_shutdown(self):
        if self.shutdown_flag:
            return
        
        self.shutdown_flag = True
        self._log("🛑 Завершение работы...", "WARNING")
        
        if self._is_component_available('memory') and self.memory is not None:
            self._log("💾 Сохраняю историю...", "INFO")
            self._sync_with_memory(force=True)
        
        try:
            if self.executor and hasattr(self.executor, 'close'):
                self.executor.close()
                self._log("🔒 Соединения Executor закрыты", "INFO")
        except:
            pass
        
        for thread in self.background_threads:
            thread.join(timeout=1.0)
        
        self.shutdown_complete.set()
        self._log("👋 Завершено", "SUCCESS")
    
    def _signal_handler(self, signum, frame):
        self._log(f"📡 Сигнал {signum}", "WARNING")
        self._graceful_shutdown()
        sys.exit(0)
    
    # ==================== API ====================
    
    def get_health_status(self) -> Dict:
        with self.health_lock:
            result = {}
            for component, health in self.component_health.items():
                result[component] = {
                    'status': health['status'].value,
                    'last_ok': health['last_ok'].isoformat() if health['last_ok'] else None,
                    'failures': health['failures'],
                    'response_time': health.get('response_time'),
                    'last_error': health.get('last_error'),
                    'last_error_time': health['last_error_time'].isoformat() 
                                     if health.get('last_error_time') else None
                }
            return result
    
    def get_stats(self) -> Dict:
        with self.stats_lock:
            stats_copy = {
                k: (list(v) if isinstance(v, deque) else v)
                for k, v in self.stats.items()
            }
        
        with self.history_lock:
            history_len = len(self.conversation_history)
        
        memory_stats = {}
        if self.memory and hasattr(self.memory, 'get_stats'):
            try:
                memory_stats = self.memory.get_stats()
            except:
                pass
        
        return {
            **stats_copy,
            'messages_in_history': history_len,
            'components': self.get_health_status(),
            'system_prompt_sent': self.system_prompt_sent,
            'cache_size': len(self.response_cache),
            'shutdown_flag': self.shutdown_flag,
            'memory': memory_stats,
            'current_device': self._current_device
        }
    
    def get_conversation_history(self, limit: int = 100) -> List:
        with self.history_lock:
            return list(self.conversation_history)[-limit:]
    
    def get_logs(self, limit: int = 100) -> List:
        return list(self.event_log)[-limit:]
    
    def clear_history(self):
        if self.shutdown_flag:
            return
        with self.history_lock:
            self.conversation_history.clear()
            self.last_synced_index = 0
        self._log("🧹 История очищена", "INFO")
    
    def retry_failed_components(self):
        if self.shutdown_flag:
            return
        
        self._log("🔄 Переподключение компонентов...", "INFO")
        
        try:
            if NEEDS_API_KEY:
                self.llm = LLM_CLIENT(api_key=self.GITHUB_API_KEY)
            else:
                self.llm = LLM_CLIENT()
            self._update_component_status('llm', True)
            self._update_component_health('llm', True, 0)
            self._log(f"✅ {LLM_NAME} переподключен", "SUCCESS")
        except Exception as e:
            self.llm = None
            self._log(f"❌ LLM недоступен: {e}", "ERROR")
        
        try:
            from src.executor.executor import SocketExecutor
            self.executor = SocketExecutor()
            self._update_component_status('executor', True)
            self._update_component_health('executor', True)
            self._log("✅ Executor переподключен", "SUCCESS")
        except Exception as e:
            self.executor = None
            self._log(f"❌ Executor недоступен: {e}", "ERROR")
        
        try:
            from src.memory.manager import MemoryManager
            self.memory = MemoryManager()
            self._update_component_status('memory', True)
            self._update_component_health('memory', True)
            self._log("✅ Memory Manager переподключен", "SUCCESS")
        except Exception as e:
            self.memory = None
            self._log(f"⚠️ Memory Manager недоступен: {e}", "WARNING")
        
        self._print_status()


# ==================== ТЕСТ ====================

async def test_orchestrator():
    print("\n" + "="*80)
    print("🧪 ТЕСТ ОРКЕСТРАТОРА v5.3".center(80))
    print("="*80)
    
    orch = Orchestrator()
    
    try:
        print("\n📌 ТЕСТ: Приветствие")
        result = await orch.process_request("привет", from_web=True)
        print(f"\n📊 Ответ: {result[:100]}...")
        
        print("\n📌 ТЕСТ: Статистика")
        stats = orch.get_stats()
        print(f"\n📊 Статистика: {stats['messages_processed']} сообщений")
        
    finally:
        orch._graceful_shutdown()
    
    print("\n" + "="*80)
    print("✅ ТЕСТ ЗАВЕРШЁН".center(80))
    print("="*80)


if __name__ == "__main__":
    asyncio.run(test_orchestrator())