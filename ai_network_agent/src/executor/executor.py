# src/executor/executor.py
# Универсальный исполнитель команд через socket
# ВЕРСИЯ 7.0 - ФИНАЛЬНАЯ С ПРАВИЛЬНЫМ ПОДКЛЮЧЕНИЕМ

import socket
import time
import re
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('executor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ConnectionMode:
    """Режимы подключения (как в оригинальных скриптах)"""
    USER = "user"        # пользовательский режим (>)
    PRIVILEGED = "priv"  # привилегированный режим (#)
    CONFIG = "config"    # режим конфигурации (config)#
    UNKNOWN = "unknown"


class CommandResult:
    """Результат выполнения команды"""
    def __init__(self, success: bool, response: str, error: str = None):
        self.success = success
        self.response = response
        self.error = error
        self.timestamp = datetime.now()
        self.duration = 0
        self.mode_before = None
        self.mode_after = None


class SocketExecutor:
    """
    👐 ИСПОЛНИТЕЛЬ КОМАНД ЧЕРЕЗ SOCKET
    С контролем режимов и правильным ожиданием
    """

    # Порты устройств
    DEVICE_PORTS = {
        'CORE1': 5002,
        'CORE2': 5003,
        'AGG1': 5004,
        'AGG2': 5005,
        'CE1': 5000,
        'CE2': 5001,
    }

    def __init__(self, memory_manager=None):
        self.memory = memory_manager
        self.connections = {}      # device -> socket
        self.modes = {}             # device -> текущий режим
        self.prompts = {}           # device -> последний промпт
        self.buffer_size = 4096
        self.timeout = 5
        self.ping_timeout = 8
        self.password = os.getenv('DEVICE_PASSWORD', 'cisco')
        
        logger.info("=" * 60)
        logger.info("✅ SocketExecutor инициализирован")
        logger.info(f"📊 Режим: с контролем режимов")
        logger.info(f"📊 Устройства: {', '.join(self.DEVICE_PORTS.keys())}")
        logger.info(f"🔐 Пароль: {'из переменной окружения' if os.getenv('DEVICE_PASSWORD') else 'по умолчанию'}")
        logger.info("=" * 60)

    # ==================== КОНТРОЛЬ РЕЖИМОВ ====================

    def _detect_mode(self, prompt: str) -> str:
        """Определяет режим по промпту"""
        if not prompt:
            return ConnectionMode.UNKNOWN
        
        if '(config' in prompt:
            return ConnectionMode.CONFIG
        elif '#' in prompt:
            return ConnectionMode.PRIVILEGED
        elif '>' in prompt:
            return ConnectionMode.USER
        else:
            return ConnectionMode.UNKNOWN

    def _get_prompt(self, sock: socket.socket) -> str:
        """Получает текущий промпт"""
        try:
            sock.send(b"\n")
            time.sleep(0.5)
            data = self._read_all_available(sock)
            lines = data.strip().split('\n')
            if lines:
                prompt = lines[-1].strip()
                logger.debug(f"📋 Промпт: {prompt}")
                return prompt
        except Exception as e:
            logger.debug(f"Ошибка получения промпта: {e}")
        return ""

    def _ensure_privileged(self, device: str) -> bool:
        """Обеспечивает привилегированный режим"""
        if device not in self.connections:
            return False
        
        sock = self.connections[device]
        
        # Проверяем текущий режим
        prompt = self._get_prompt(sock)
        mode = self._detect_mode(prompt)
        
        if mode == ConnectionMode.PRIVILEGED or mode == ConnectionMode.CONFIG:
            self.modes[device] = mode
            self.prompts[device] = prompt
            return True
        
        # Пытаемся войти в привилегированный режим
        logger.info(f"🔑 Вход в привилегированный режим на {device}")
        
        try:
            # Очищаем буфер
            self._hard_clear_buffer(sock)
            
            # Отправляем enable
            sock.send(b"enable\r\n")
            time.sleep(1)
            
            # Читаем запрос пароля
            data = self._read_all_available(sock)
            
            if "Password" not in data:
                logger.warning("⚠️ Запрос пароля не получен")
                return False
            
            # Отправляем пароль
            sock.send(f"{self.password}\r\n".encode())
            time.sleep(1)
            
            # Проверяем результат
            prompt = self._get_prompt(sock)
            mode = self._detect_mode(prompt)
            
            if mode == ConnectionMode.PRIVILEGED or mode == ConnectionMode.CONFIG:
                self.modes[device] = mode
                self.prompts[device] = prompt
                logger.info(f"✅ Вошли в привилегированный режим на {device}")
                return True
            else:
                logger.warning(f"❌ Не удалось войти в привилегированный режим")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка входа в привилегированный режим: {e}")
            return False

    # ==================== РАБОТА С СОКЕТОМ ====================

    def _hard_clear_buffer(self, sock: socket.socket):
        """Жёсткая очистка буфера - читает всё, что есть"""
        try:
            sock.settimeout(0.5)
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                logger.debug(f"🧹 Очищено: {repr(data)[:100]}")
        except socket.timeout:
            pass
        except Exception as e:
            logger.debug(f"Ошибка очистки: {e}")
        finally:
            sock.settimeout(self.timeout)

    def _read_all_available(self, sock: socket.socket) -> str:
        """Читает все доступные данные"""
        data = b""
        try:
            sock.settimeout(0.5)
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
        except socket.timeout:
            pass
        finally:
            sock.settimeout(self.timeout)
        return data.decode('utf-8', errors='ignore')

    # ==================== ПОДКЛЮЧЕНИЕ ====================

    def connect(self, device: str) -> bool:
        """
        Подключается к устройству с правильным ожиданием
        """
        if device not in self.DEVICE_PORTS:
            logger.error(f"❌ Неизвестное устройство: {device}")
            return False

        port = self.DEVICE_PORTS[device]
        logger.info(f"🔌 Подключение к {device} (порт {port})...")

        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect(('localhost', port))

            # 🔥 ЖЕСТКАЯ ОЧИСТКА БУФЕРА
            logger.info("🧹 Очистка буфера...")
            self._hard_clear_buffer(sock)
            
            # ШАГ 1: Отправляем Enter для получения приглашения
            logger.info("⏳ Шаг 1/5: Запрос приглашения...")
            sock.send(b"\r\n")
            time.sleep(1)
            
            # Читаем приглашение
            data = self._read_all_available(sock)
            logger.info(f"📥 Приглашение: {repr(data)}")
            
            if ">" not in data:
                logger.warning("⚠️ Приглашение не получено")
            
            # ШАГ 2: Отправляем enable с \r\n
            logger.info("⏳ Шаг 2/5: Отправка enable...")
            sock.send(b"enable\r\n")
            time.sleep(1)
            
            # Читаем запрос пароля
            data = self._read_all_available(sock)
            logger.info(f"📥 Ответ на enable: {repr(data)}")
            
            if "Password" in data:
                logger.info("✅ Запрос пароля получен")
            else:
                logger.warning("⚠️ Запрос пароля не получен")
            
            # ШАГ 3: Отправляем пароль с \r\n
            logger.info("⏳ Шаг 3/5: Отправка пароля...")
            sock.send(f"{self.password}\r\n".encode())
            time.sleep(2)
            
            # Читаем ответ
            data = self._read_all_available(sock)
            logger.info(f"📥 Ответ на пароль: {repr(data)}")
            
            # ШАГ 4: Проверяем результат
            logger.info("⏳ Шаг 4/5: Проверка привилегированного режима...")
            sock.send(b"\r\n")
            time.sleep(1)
            
            data = self._read_all_available(sock)
            logger.info(f"📥 Финальный ответ: {repr(data)}")
            
            if "#" in data:
                self.connections[device] = sock
                self.modes[device] = ConnectionMode.PRIVILEGED
                logger.info(f"✅ Подключено к {device}")
                return True
            else:
                logger.error(f"❌ Не удалось войти в привилегированный режим")
                logger.error(f"   Ответ: {repr(data)}")
                sock.close()
                return False

        except ConnectionRefusedError:
            logger.error(f"❌ Соединение отклонено. Проверьте GNS3 и устройство {device}")
            if sock:
                sock.close()
            return False
        except socket.timeout:
            logger.error(f"❌ Таймаут подключения к {device}")
            if sock:
                sock.close()
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка подключения: {type(e).__name__}: {e}")
            if sock:
                sock.close()
            return False

    # ==================== ОТПРАВКА КОМАНД ====================

    def _has_cisco_error(self, text: str) -> bool:
        """Проверяет наличие ошибок Cisco"""
        if not text:
            return False

        error_patterns = [
            r'% Invalid',
            r'% Incomplete',
            r'% Ambiguous',
            r'% Unknown',
            r'overlaps with',
            r'Duplicate address',
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _clean_response(self, text: str) -> str:
        """Очищает ответ от служебных символов"""
        if not text:
            return ""

        # Удаляем ANSI escape sequences
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        text = ansi_escape.sub('', text)

        # Удаляем управляющие символы
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

        # Удаляем пустые строки
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return '\n'.join(lines)

    def send(self, device: str, command: str, timeout: float = None) -> CommandResult:
        """
        Отправляет команду на устройство с контролем режима
        """
        start_time = time.time()
        
        result = CommandResult(
            success=False,
            response="",
            error=None
        )

        # Проверка подключения
        if device not in self.connections:
            if not self.connect(device):
                result.error = f"Не удалось подключиться к {device}"
                result.duration = time.time() - start_time
                return result

        sock = self.connections[device]
        
        # Получаем режим ДО команды
        prompt_before = self._get_prompt(sock)
        mode_before = self._detect_mode(prompt_before)
        result.mode_before = mode_before
        
        # Проверяем, что в правильном режиме
        if mode_before == ConnectionMode.USER:
            logger.warning(f"⚠️ Устройство {device} в пользовательском режиме, восстанавливаю...")
            if not self._ensure_privileged(device):
                result.error = "Не удалось восстановить привилегированный режим"
                result.duration = time.time() - start_time
                return result
            sock = self.connections[device]  # обновляем ссылку
        
        try:
            # Очищаем буфер перед командой
            self._hard_clear_buffer(sock)
            
            # Отправляем команду
            logger.info(f"⚙️ {device}> {command} [режим: {mode_before}]")
            sock.send(f"{command}\r\n".encode())
            time.sleep(1)
            
            # Читаем ответ
            response = self._read_all_available(sock)
            
            # Получаем режим ПОСЛЕ команды
            prompt_after = self._get_prompt(sock)
            mode_after = self._detect_mode(prompt_after)
            result.mode_after = mode_after
            
            # Обновляем сохранённый режим
            self.modes[device] = mode_after
            self.prompts[device] = prompt_after
            
            # Очищаем ответ
            clean_response = self._clean_response(response)
            result.response = clean_response
            
            # Проверяем ошибки
            if self._has_cisco_error(clean_response):
                result.error = clean_response
                logger.warning(f"⚠️ Обнаружена ошибка Cisco")
            else:
                result.success = True
            
            result.duration = time.time() - start_time
            logger.info(f"✅ Команда выполнена за {result.duration:.2f} сек")
            
            return result

        except Exception as e:
            result.error = f"Ошибка выполнения: {type(e).__name__}: {e}"
            result.duration = time.time() - start_time
            logger.error(f"❌ {result.error}")
            return result

    def send_sequence(self, device: str, commands: List[str], stop_on_error: bool = True) -> List[CommandResult]:
        """Отправляет последовательность команд"""
        results = []
        
        for i, cmd in enumerate(commands):
            logger.info(f"🔄 Команда {i+1}/{len(commands)}")
            result = self.send(device, cmd)
            results.append(result)
            
            if not result.success and stop_on_error:
                error_msg = result.error[:100] if result.error else "Неизвестная ошибка"
                logger.warning(f"⚠️ Остановка из-за ошибки: {error_msg}")
                break
            
            time.sleep(0.3)
        
        return results

    def show(self, device: str, command: str) -> CommandResult:
        """Выполняет show команду"""
        if not command:
            return CommandResult(False, "", "Не указана show-команда")
        
        if not command.startswith('show'):
            command = f"show {command}"
        return self.send(device, command, timeout=self.timeout * 1.5)

    def ping(self, device: str, target_ip: str, count: int = 5) -> CommandResult:
        """Выполняет ping"""
        if not target_ip:
            return CommandResult(False, "", "Не указан IP-адрес")
        
        return self.send(device, f"ping {target_ip} repeat {count}", timeout=self.ping_timeout)

    def configure(self, device: str, commands: List[str]) -> List[CommandResult]:
        """Выполняет конфигурацию"""
        if not commands:
            return []
        
        clean_commands = [cmd.strip() for cmd in commands if cmd and cmd.strip()]
        if not clean_commands:
            return []
        
        full_commands = ['configure terminal'] + clean_commands + ['end']
        return self.send_sequence(device, full_commands)

    def close(self, device: str = None):
        """Закрывает соединение"""
        if device:
            if device in self.connections:
                try:
                    self.connections[device].close()
                    logger.info(f"🔒 Соединение с {device} закрыто")
                except Exception as e:
                    logger.error(f"❌ Ошибка при закрытии {device}: {e}")
                finally:
                    del self.connections[device]
                    if device in self.modes:
                        del self.modes[device]
        else:
            for dev in list(self.connections.keys()):
                try:
                    self.connections[dev].close()
                    logger.info(f"🔒 Соединение с {dev} закрыто")
                except Exception as e:
                    logger.error(f"❌ Ошибка при закрытии {dev}: {e}")
            self.connections.clear()
            self.modes.clear()
            self.prompts.clear()

    def get_status(self, device: str = None) -> Dict[str, Any]:
        """Возвращает статус"""
        if device:
            if device in self.connections:
                return {
                    'device': device,
                    'connected': True,
                    'mode': self.modes.get(device),
                    'prompt': self.prompts.get(device)
                }
            else:
                return {
                    'device': device,
                    'connected': False
                }
        else:
            return {
                'connections': list(self.connections.keys()),
                'modes': self.modes.copy(),
                'total': len(self.connections)
            }


# ==================== ТЕСТ ====================

def test_executor():
    """Тестирует Executor"""
    print("=" * 80)
    print("🧪 ТЕСТ EXECUTOR (С КОНТРОЛЕМ РЕЖИМОВ)")
    print("=" * 80)

    executor = SocketExecutor()
    
    # Тест подключения
    print("\n📌 ТЕСТ: Подключение к CORE1")
    if executor.connect('CORE1'):
        print("   ✅ Подключение успешно")
        status = executor.get_status('CORE1')
        print(f"   📊 Статус: {status}")
    else:
        print("   ❌ Ошибка подключения")

    executor.close()


if __name__ == "__main__":
    test_executor()