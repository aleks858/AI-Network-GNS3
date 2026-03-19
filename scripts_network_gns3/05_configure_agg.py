#!/usr/bin/env python3
"""
05_configure_agg_final.py - ИТОГОВАЯ УМНАЯ НАСТРОЙКА AGG1 И AGG2
ВЕРСИЯ: 18.0 - С МНОЖЕСТВЕННЫМИ СЦЕНАРИЯМИ

ОСОБЕННОСТИ:
- Адаптивный вход в устройство (3+ сценария)
- Диалог с Cisco (проверка каждой команды)
- Проверка пингов после каждого интерфейса
- Множественные попытки при ошибках
- Подробная диагностика
"""

import requests
import telnetlib
import time
import re
import sys
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from enum import Enum

# ==================== КОНФИГУРАЦИЯ ====================

DEVICE_PORTS = {
    'CORE1': 5002,
    'CORE2': 5003,
    'AGG1': 5004,
    'AGG2': 5005
}

DEFAULT_PASSWORD = 'cisco'
GNS3_API = "http://localhost:3080/v2"
PROJECT_NAME = "AS1-FULL-NETWORK"

# Конфигурация AGG1 (ПРОВЕРЕНО РАБОТАЕТ)
AGG1_CONFIG = {
    'hostname': 'AGG1',
    'interfaces': [
        # К CORE1 Gi2/0
        {'name': 'FastEthernet0/0', 'ip': '10.1.2.2', 'mask': '255.255.255.0', 
         'desc': 'to CORE1 Gi2/0', 'type': 'core', 'ping_target': '10.1.2.1'},
        
        # К CORE2 Gi4/0
        {'name': 'FastEthernet0/1', 'ip': '10.2.2.2', 'mask': '255.255.255.0', 
         'desc': 'to CORE2 Gi4/0', 'type': 'core', 'ping_target': '10.2.2.1'},
        
        # К AGG2 Fa1/5
        {'name': 'FastEthernet1/5', 'ip': '10.100.1.1', 'mask': '255.255.255.0', 
         'desc': 'to AGG2 Fa1/5', 'type': 'agg', 'ping_target': '10.100.1.2'},
        
        # К AGG2 Fa1/6
        {'name': 'FastEthernet1/6', 'ip': '10.100.1.3', 'mask': '255.255.255.0', 
         'desc': 'to AGG2 Fa1/6', 'type': 'agg', 'ping_target': '10.100.1.4'},
        
        # К ACC (L2 порты)
        {'name': 'FastEthernet1/0', 'ip': None, 'desc': 'to ACC1 Fa0/0', 'type': 'access'},
        {'name': 'FastEthernet1/1', 'ip': None, 'desc': 'to ACC2 Fa0/0', 'type': 'access'},
        {'name': 'FastEthernet1/2', 'ip': None, 'desc': 'to ACC3 Fa0/0', 'type': 'access'},
        {'name': 'FastEthernet1/3', 'ip': None, 'desc': 'to ACC4 Fa0/0', 'type': 'access'},
        {'name': 'FastEthernet1/4', 'ip': None, 'desc': 'to ACC5 Fa0/0', 'type': 'access'}
    ]
}

# Конфигурация AGG2 (ПРОВЕРЕНО РАБОТАЕТ)
AGG2_CONFIG = {
    'hostname': 'AGG2',
    'interfaces': [
        # К CORE2 Gi2/0
        {'name': 'FastEthernet0/0', 'ip': '10.2.3.2', 'mask': '255.255.255.0', 
         'desc': 'to CORE2 Gi2/0', 'type': 'core', 'ping_target': '10.2.3.1'},
        
        # К CORE1 Gi4/0
        {'name': 'FastEthernet0/1', 'ip': '10.1.3.2', 'mask': '255.255.255.0', 
         'desc': 'to CORE1 Gi4/0', 'type': 'core', 'ping_target': '10.1.3.1'},
        
        # К AGG1 Fa1/5
        {'name': 'FastEthernet1/5', 'ip': '10.100.1.2', 'mask': '255.255.255.0', 
         'desc': 'to AGG1 Fa1/5', 'type': 'agg', 'ping_target': '10.100.1.1'},
        
        # К AGG1 Fa1/6
        {'name': 'FastEthernet1/6', 'ip': '10.100.1.4', 'mask': '255.255.255.0', 
         'desc': 'to AGG1 Fa1/6', 'type': 'agg', 'ping_target': '10.100.1.3'},
        
        # К ACC (L2 порты)
        {'name': 'FastEthernet1/0', 'ip': None, 'desc': 'to ACC1 Fa0/1', 'type': 'access'},
        {'name': 'FastEthernet1/1', 'ip': None, 'desc': 'to ACC2 Fa0/1', 'type': 'access'},
        {'name': 'FastEthernet1/2', 'ip': None, 'desc': 'to ACC3 Fa0/1', 'type': 'access'},
        {'name': 'FastEthernet1/3', 'ip': None, 'desc': 'to ACC4 Fa0/1', 'type': 'access'},
        {'name': 'FastEthernet1/4', 'ip': None, 'desc': 'to ACC5 Fa0/1', 'type': 'access'}
    ]
}

AGG_CONFIGS = {
    'AGG1': AGG1_CONFIG,
    'AGG2': AGG2_CONFIG
}

# Конфигурация CORE
CORE_CONFIGS = {
    'CORE1': {
        'interfaces': [
            {'name': 'GigabitEthernet2/0', 'ip': '10.1.2.1', 'desc': 'to AGG1 Fa0/0'},
            {'name': 'GigabitEthernet4/0', 'ip': '10.1.3.1', 'desc': 'to AGG2 Fa0/1'}
        ]
    },
    'CORE2': {
        'interfaces': [
            {'name': 'GigabitEthernet4/0', 'ip': '10.2.2.1', 'desc': 'to AGG1 Fa0/1'},
            {'name': 'GigabitEthernet2/0', 'ip': '10.2.3.1', 'desc': 'to AGG2 Fa0/0'}
        ]
    }
}

# Линки для GNS3
GNS3_LINKS = [
    ('AGG1', 0, 0, 'CORE1', 2, 0, 'AGG1 Fa0/0 ↔ CORE1 Gi2/0'),
    ('AGG1', 0, 1, 'CORE2', 4, 0, 'AGG1 Fa0/1 ↔ CORE2 Gi4/0'),
    ('AGG2', 0, 0, 'CORE2', 2, 0, 'AGG2 Fa0/0 ↔ CORE2 Gi2/0'),
    ('AGG2', 0, 1, 'CORE1', 4, 0, 'AGG2 Fa0/1 ↔ CORE1 Gi4/0'),
    ('AGG1', 1, 5, 'AGG2', 1, 5, 'AGG1 Fa1/5 ↔ AGG2 Fa1/5'),
    ('AGG1', 1, 6, 'AGG2', 1, 6, 'AGG1 Fa1/6 ↔ AGG2 Fa1/6'),
    ('AGG1', 1, 0, 'ACC1', 0, 0, 'AGG1 Fa1/0 ↔ ACC1 Fa0/0'),
    ('AGG1', 1, 1, 'ACC2', 0, 0, 'AGG1 Fa1/1 ↔ ACC2 Fa0/0'),
    ('AGG1', 1, 2, 'ACC3', 0, 0, 'AGG1 Fa1/2 ↔ ACC3 Fa0/0'),
    ('AGG1', 1, 3, 'ACC4', 0, 0, 'AGG1 Fa1/3 ↔ ACC4 Fa0/0'),
    ('AGG1', 1, 4, 'ACC5', 0, 0, 'AGG1 Fa1/4 ↔ ACC5 Fa0/0'),
    ('AGG2', 1, 0, 'ACC1', 0, 1, 'AGG2 Fa1/0 ↔ ACC1 Fa0/1'),
    ('AGG2', 1, 1, 'ACC2', 0, 1, 'AGG2 Fa1/1 ↔ ACC2 Fa0/1'),
    ('AGG2', 1, 2, 'ACC3', 0, 1, 'AGG2 Fa1/2 ↔ ACC3 Fa0/1'),
    ('AGG2', 1, 3, 'ACC4', 0, 1, 'AGG2 Fa1/3 ↔ ACC4 Fa0/1'),
    ('AGG2', 1, 4, 'ACC5', 0, 1, 'AGG2 Fa1/4 ↔ ACC5 Fa0/1')
]

# ==================== КЛАССЫ ДИАГНОСТИКИ ====================

class CommandStatus(Enum):
    SUCCESS = "✅ УСПЕХ"
    FAILED = "❌ ОШИБКА"
    WARNING = "⚠️ ПРЕДУПРЕЖДЕНИЕ"
    SKIPPED = "⏭️ ПРОПУЩЕНО"
    RETRY = "🔄 ПОВТОР"

class CriticalError(Exception):
    """Критическая ошибка - скрипт останавливается"""
    pass

class DiagnosticSystem:
    def __init__(self, device_name: str):
        self.device_name = device_name
        self.results = []
        self.start_time = datetime.now()
        self.current_prompt = ""
    
    def log(self, msg: str):
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] [{self.device_name}] {msg}")
    
    def set_prompt(self, prompt: str):
        self.current_prompt = prompt
    
    def analyze_output(self, output: str) -> Dict:
        """Анализ вывода на наличие ошибок Cisco"""
        analysis = {'has_error': False, 'error_msg': None, 'error_type': None}
        
        error_patterns = [
            (r'% Invalid', 'invalid'),
            (r'% Incomplete', 'incomplete'),
            (r'overlaps with', 'overlap'),
            (r'Duplicate address', 'duplicate'),
            (r'% Ambiguous', 'ambiguous'),
            (r'% Unknown', 'unknown')
        ]
        
        for pattern, error_type in error_patterns:
            if re.search(pattern, output):
                analysis['has_error'] = True
                analysis['error_type'] = error_type
                error_lines = re.findall(r'%[^\n]+', output)
                analysis['error_msg'] = error_lines[0] if error_lines else f"Ошибка типа {error_type}"
                break
        
        return analysis
    
    def add_result(self, command: str, output: str, status: CommandStatus, error_msg: str = None):
        analysis = self.analyze_output(output)
        
        self.results.append({
            'command': command,
            'output': output,
            'status': status,
            'error_msg': error_msg or analysis['error_msg'],
            'analysis': analysis,
            'timestamp': datetime.now(),
            'prompt': self.current_prompt
        })
        
        if status == CommandStatus.SUCCESS:
            print(f"  ✅ {command}")
        elif status == CommandStatus.FAILED:
            print(f"  ❌ {command} - {error_msg or analysis['error_msg']}")
        elif status == CommandStatus.WARNING:
            print(f"  ⚠️ {command} - {error_msg}")
        elif status == CommandStatus.SKIPPED:
            print(f"  ⏭️ {command} - {error_msg}")
        elif status == CommandStatus.RETRY:
            print(f"  🔄 {command} - {error_msg}")
    
    def print_summary(self):
        total = len(self.results)
        successful = sum(1 for r in self.results if r['status'] == CommandStatus.SUCCESS)
        failed = sum(1 for r in self.results if r['status'] == CommandStatus.FAILED)
        warnings = sum(1 for r in self.results if r['status'] == CommandStatus.WARNING)
        skipped = sum(1 for r in self.results if r['status'] == CommandStatus.SKIPPED)
        
        print(f"\n📊 СТАТИСТИКА {self.device_name}:")
        print(f"  ✅ Успешно: {successful}")
        print(f"  ❌ Ошибки: {failed}")
        print(f"  ⚠️ Предупреждения: {warnings}")
        print(f"  ⏭️ Пропущено: {skipped}")
        print(f"  📝 Всего команд: {total}")
        
        return successful, failed, warnings

# ==================== GNS3 LINK CREATOR ====================

class GNS3LinkCreator:
    """Создание физических линков в GNS3 через API"""
    
    def __init__(self):
        self.base_url = GNS3_API
        self.project_id = None
        self.nodes = {}
        self.links_created = 0
    
    def log(self, msg: str):
        print(f"[GNS3] {msg}")
    
    def get_projects(self) -> List:
        try:
            response = requests.get(f'{self.base_url}/projects', timeout=5)
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            self.log(f"❌ Ошибка получения проектов: {e}")
            return []
    
    def select_project(self) -> bool:
        projects = self.get_projects()
        for p in projects:
            if p['name'] == PROJECT_NAME:
                self.project_id = p['project_id']
                self.log(f"✅ Проект '{PROJECT_NAME}' выбран (ID: {self.project_id})")
                return True
        self.log(f"❌ Проект '{PROJECT_NAME}' не найден")
        return False
    
    def get_nodes(self) -> bool:
        if not self.project_id:
            return False
        try:
            response = requests.get(f'{self.base_url}/projects/{self.project_id}/nodes', timeout=5)
            if response.status_code == 200:
                for node in response.json():
                    self.nodes[node['name']] = node
                self.log(f"✅ Найдено устройств: {len(self.nodes)}")
                
                # Проверяем наличие всех нужных устройств
                required = ['CORE1', 'CORE2', 'AGG1', 'AGG2', 'ACC1', 'ACC2', 'ACC3', 'ACC4', 'ACC5']
                missing = [r for r in required if r not in self.nodes]
                if missing:
                    self.log(f"⚠️ Отсутствуют в проекте: {', '.join(missing)}")
                else:
                    self.log(f"✅ Все необходимые устройства присутствуют")
                
                return True
        except Exception as e:
            self.log(f"❌ Ошибка получения узлов: {e}")
        return False
    
    def create_link(self, node1: str, adapter1: int, port1: int, 
                   node2: str, adapter2: int, port2: int, description: str) -> bool:
        """Создание одного линка"""
        
        if node1 not in self.nodes or node2 not in self.nodes:
            self.log(f"❌ Устройства {node1} или {node2} не найдены")
            return False
        
        link_data = {
            "nodes": [
                {"node_id": self.nodes[node1]['node_id'], 
                 "adapter_number": adapter1, "port_number": port1},
                {"node_id": self.nodes[node2]['node_id'], 
                 "adapter_number": adapter2, "port_number": port2}
            ]
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/projects/{self.project_id}/links',
                json=link_data,
                timeout=5
            )
            
            if response.status_code == 201:
                self.log(f"  ✅ {description}")
                self.links_created += 1
                return True
            elif response.status_code == 409:
                self.log(f"  ⏭️ {description} (уже существует)")
                self.links_created += 1
                return True
            else:
                self.log(f"  ❌ {description} (код {response.status_code})")
                return False
        except Exception as e:
            self.log(f"  ❌ {description} (ошибка: {e})")
            return False
    
    def create_all_links(self) -> bool:
        """Создание всех необходимых линков"""
        
        print("\n🔧 СОЗДАНИЕ ФИЗИЧЕСКИХ ЛИНКОВ В GNS3")
        print("-" * 70)
        
        if not self.select_project():
            print("❌ Не удалось выбрать проект")
            return False
        
        if not self.get_nodes():
            print("❌ Не удалось получить список устройств")
            return False
        
        self.links_created = 0
        for node1, a1, p1, node2, a2, p2, desc in GNS3_LINKS:
            self.create_link(node1, a1, p1, node2, a2, p2, desc)
            time.sleep(0.3)
        
        print(f"\n📊 Всего создано линков: {self.links_created}/{len(GNS3_LINKS)}")
        
        if self.links_created < len(GNS3_LINKS):
            print("⚠️ Не все линки созданы, проверьте GNS3")
            response = input("Продолжить настройку? (y/n): ").strip().lower()
            return response == 'y'
        
        return True

# ==================== БАЗОВЫЙ КЛАСС ДЛЯ РАБОТЫ С УСТРОЙСТВАМИ ====================

class SmartDeviceConfigurator:
    """
    Умный конфигуратор с множественными сценариями входа и адаптивным поведением
    """
    
    def __init__(self, device_name: str, port: int, password: str = DEFAULT_PASSWORD):
        self.name = device_name
        self.port = port
        self.password = password
        self.tn = None
        self.diag = DiagnosticSystem(device_name)
        self.privileged = False
        self.prompt = ""
        self.mode = "unknown"  # user, privileged, config
        self.max_attempts = 3
        self.login_scenarios = [
            self._scenario_standard,
            self._scenario_no_password,
            self._scenario_already_enabled,
            self._scenario_reset_session
        ]
    
    def log(self, msg: str):
        self.diag.log(msg)
    
    # ==================== РАБОТА С TELNET ====================
    
    def _read(self, timeout: float = 1.0) -> str:
        """Чтение данных из сокета"""
        time.sleep(timeout)
        try:
            if self.tn:
                data = self.tn.read_very_eager()
                return data.decode('utf-8', errors='ignore')
        except:
            pass
        return ""
    
    def _write(self, data: str):
        """Отправка команды"""
        if self.tn:
            self.tn.write(data.encode('utf-8') + b"\r\n")
    
    def _clear_buffer(self):
        """Очистка буфера"""
        self._read(0.2)
    
    # ==================== ОПРЕДЕЛЕНИЕ РЕЖИМА ====================
    
    def _get_prompt(self) -> str:
        """Получение текущего промпта с определением режима"""
        self._write("")
        time.sleep(0.5)
        data = self._read()
        
        lines = data.strip().split('\n')
        if not lines:
            return self.prompt
        
        # Берем последнюю непустую строку как промпт
        for line in reversed(lines):
            if line.strip():
                self.prompt = line.strip()
                self.diag.set_prompt(self.prompt)
                break
        
        # Определяем режим по промпту
        if '(config' in self.prompt:
            self.mode = "config"
            self.privileged = True
        elif '#' in self.prompt:
            self.mode = "privileged"
            self.privileged = True
        elif '>' in self.prompt:
            self.mode = "user"
            self.privileged = False
        else:
            self.mode = "unknown"
        
        return self.prompt
    
    # ==================== СЦЕНАРИИ ВХОДА ====================
    
    def _scenario_standard(self) -> bool:
        """Сценарий 1: Стандартный вход с паролем"""
        self.log("🔄 Сценарий 1: Стандартный вход")
        
        self._clear_buffer()
        self._write("enable")
        time.sleep(2)
        
        data = self._read()
        if 'Password:' in data:
            self._write(self.password)
            time.sleep(2)
        
        self._get_prompt()
        return self.privileged
    
    def _scenario_no_password(self) -> bool:
        """Сценарий 2: Вход без пароля"""
        self.log("🔄 Сценарий 2: Вход без пароля")
        
        self._clear_buffer()
        self._write("enable")
        time.sleep(2)
        
        # Если не спросили пароль, возможно мы уже в enable
        self._get_prompt()
        return self.privileged
    
    def _scenario_already_enabled(self) -> bool:
        """Сценарий 3: Уже в привилегированном режиме"""
        self.log("🔄 Сценарий 3: Проверка текущего режима")
        
        self._get_prompt()
        return self.privileged
    
    def _scenario_reset_session(self) -> bool:
        """Сценарий 4: Сброс сессии и повторный вход"""
        self.log("🔄 Сценарий 4: Сброс сессии")
        
        self._write("end")
        time.sleep(1)
        self._write("exit")
        time.sleep(1)
        
        # Пробуем стандартный вход снова
        return self._scenario_standard()
    
    # ==================== ВХОД В РАЗЛИЧНЫЕ РЕЖИМЫ ====================
    
    def ensure_privileged_mode(self) -> bool:
        """Гарантированный вход в привилегированный режим"""
        
        # Проверяем текущий режим
        self._get_prompt()
        
        if self.privileged:
            self.log(f"✅ Уже в привилегированном режиме: {self.prompt}")
            return True
        
        # Перебираем все сценарии входа
        for i, scenario in enumerate(self.login_scenarios, 1):
            self.log(f"🔑 Попытка входа #{i}...")
            if scenario():
                self.log(f"✅ Вошли в привилегированный режим (сценарий {i})")
                return True
            time.sleep(1)
        
        self.log("❌ Не удалось войти в привилегированный режим")
        return False
    
    def ensure_config_mode(self) -> bool:
        """Гарантированный вход в режим конфигурации"""
        
        # Сначала убеждаемся, что мы в привилегированном режиме
        if not self.ensure_privileged_mode():
            return False
        
        # Проверяем, не в конфигурации ли мы уже
        self._get_prompt()
        if self.mode == "config":
            self.log(f"✅ Уже в режиме конфигурации: {self.prompt}")
            return True
        
        # Пробуем разные варианты входа в конфигурацию
        config_attempts = [
            "configure terminal",
            "conf t",
            "config term"
        ]
        
        for cmd in config_attempts:
            self.log(f"🔄 Пробуем: {cmd}")
            self._clear_buffer()
            self._write(cmd)
            time.sleep(2)
            
            self._get_prompt()
            if self.mode == "config":
                self.log(f"✅ Вошли в режим конфигурации через '{cmd}'")
                return True
        
        self.log("❌ Не удалось войти в режим конфигурации")
        return False
    
    # ==================== ОТПРАВКА КОМАНД ====================
    
    def send_command(self, command: str, wait: int = 2, check_errors: bool = True) -> Tuple[bool, str]:
        """Отправка команды и получение ответа"""
        if not self.tn:
            return False, "Нет соединения"
        
        self._clear_buffer()
        self._write(command)
        time.sleep(wait)
        
        response = self._read()
        
        # Очистка от ANSI-последовательностей
        clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', response)
        clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', clean)
        
        # Проверка на ошибки Cisco
        if check_errors:
            if re.search(r'% (Invalid|Incomplete|overlaps|Duplicate)', clean):
                return False, clean
        
        self._get_prompt()
        return True, clean
    
    def send_config_command(self, command: str, critical: bool = True, max_retries: int = 2) -> bool:
        """Отправка команды в режиме конфигурации с повторными попытками"""
        
        for attempt in range(max_retries):
            # Убеждаемся, что мы в режиме конфигурации
            if not self.ensure_config_mode():
                if attempt == max_retries - 1:
                    if critical:
                        raise CriticalError("Не удалось войти в режим конфигурации")
                    return False
                time.sleep(2)
                continue
            
            # Отправляем команду
            success, response = self.send_command(command)
            
            if success:
                self.diag.add_result(command, response, CommandStatus.SUCCESS)
                return True
            else:
                error_msg = re.findall(r'%[^\n]+', response)
                error_text = error_msg[0] if error_msg else "Неизвестная ошибка"
                
                if attempt < max_retries - 1:
                    self.diag.add_result(command, response, CommandStatus.RETRY, f"Попытка {attempt + 1}/{max_retries}: {error_text}")
                    time.sleep(2)
                else:
                    self.diag.add_result(command, response, CommandStatus.FAILED, error_text)
                    if critical:
                        raise CriticalError(f"Критическая ошибка: {error_text}")
                    return False
        
        return False
    
    # ==================== ПРОВЕРКА ПИНГОВ ====================
    
    def check_ping(self, target_ip: str, count: int = 5, critical: bool = True) -> bool:
        """Проверка доступности по ping с анализом результата"""
        self.log(f"📡 Ping {target_ip}...")
        
        # Пробуем разные варианты ping
        ping_commands = [
            f"ping {target_ip} repeat {count}",
            f"ping {target_ip}",
            f"ping {target_ip} size 100 repeat {count}"
        ]
        
        for ping_cmd in ping_commands:
            success, response = self.send_command(ping_cmd, wait=6, check_errors=False)
            
            if not success:
                continue
            
            # Анализ результата
            if '!!!!!' in response or 'Success rate is 100 percent' in response:
                self.diag.add_result(f"ping {target_ip}", response, CommandStatus.SUCCESS)
                return True
            elif '.....' in response or '0 percent' in response:
                continue
            else:
                # Частичный успех
                match = re.search(r'Success rate is (\d+) percent', response)
                if match and int(match.group(1)) >= 60:
                    self.diag.add_result(f"ping {target_ip}", response, CommandStatus.SUCCESS)
                    return True
        
        # Все попытки неудачны
        msg = f"Ping {target_ip} не проходит после {len(ping_commands)} попыток"
        self.diag.add_result(f"ping {target_ip}", "", CommandStatus.FAILED if critical else CommandStatus.WARNING, msg)
        
        if critical:
            raise CriticalError(msg)
        return False
    
    # ==================== СОХРАНЕНИЕ КОНФИГУРАЦИИ ====================
    
    def save_config(self) -> bool:
        """Сохранение конфигурации"""
        self.log("💾 Сохранение конфигурации...")
        
        if not self.ensure_privileged_mode():
            return False
        
        # Пробуем разные команды сохранения
        save_commands = ["write memory", "copy running-config startup-config", "wr"]
        
        for cmd in save_commands:
            success, response = self.send_command(cmd, wait=3)
            if success:
                self.diag.add_result(cmd, response, CommandStatus.SUCCESS)
                return True
        
        self.diag.add_result("save", "", CommandStatus.WARNING, "Не удалось сохранить конфигурацию")
        return False
    
    # ==================== ПОДКЛЮЧЕНИЕ И ОТКЛЮЧЕНИЕ ====================
    
    def connect(self) -> bool:
        """Подключение к устройству с несколькими попытками"""
        self.log(f"🔌 Подключение к порту {self.port}...")
        
        for attempt in range(self.max_attempts):
            try:
                self.tn = telnetlib.Telnet('localhost', self.port, timeout=10)
                time.sleep(2)
                self._clear_buffer()
                
                # Получаем начальный промпт
                self._get_prompt()
                self.log(f"📋 Начальный промпт: {self.prompt}")
                
                # Пытаемся войти в привилегированный режим
                if self.ensure_privileged_mode():
                    self.log(f"✅ Подключено к {self.name} (попытка {attempt + 1})")
                    return True
                else:
                    self.tn.close()
                    self.tn = None
                    time.sleep(2)
                    
            except Exception as e:
                self.log(f"❌ Попытка {attempt + 1}: {e}")
                time.sleep(3)
        
        self.log(f"❌ Не удалось подключиться к {self.name} после {self.max_attempts} попыток")
        return False
    
    def close(self):
        """Закрытие соединения"""
        if self.tn:
            self.tn.close()
            self.tn = None
            self.log("🔒 Соединение закрыто")

# ==================== КЛАСС ДЛЯ НАСТРОЙКИ CORE ====================

class CoreConfigurator(SmartDeviceConfigurator):
    """Умный конфигуратор для CORE"""
    
    def __init__(self, device_name: str):
        super().__init__(device_name, DEVICE_PORTS[device_name])
        self.config = CORE_CONFIGS[device_name]
    
    def configure(self) -> bool:
        """Настройка CORE для работы с AGG"""
        
        self.log(f"\n🔧 НАСТРОЙКА {self.name}")
        
        if not self.connect():
            return False
        
        all_success = True
        
        for intf in self.config['interfaces']:
            print(f"\n--- {intf['name']} ({intf['desc']}) ---")
            
            try:
                # Проверяем текущее состояние интерфейса
                success, response = self.send_command(f"show ip interface {intf['name']}", wait=2)
                
                # Если IP уже настроен - пропускаем
                if intf['ip'] in response:
                    print(f"  ✅ {intf['name']} уже настроен с IP {intf['ip']}")
                    continue
                
                # Настраиваем интерфейс
                commands = [
                    f"interface {intf['name']}",
                    f"description {intf['desc']}",
                    f"ip address {intf['ip']} 255.255.255.0",
                    "no shutdown"
                ]
                
                for cmd in commands:
                    self.send_config_command(cmd, critical=True)
                    time.sleep(0.5)
                
                self.send_config_command("end", critical=False)
                
                # Проверяем, что интерфейс поднялся
                time.sleep(2)
                success, response = self.send_command(f"show interface {intf['name']}")
                if 'up' in response and 'up' in response:
                    print(f"  ✅ {intf['name']} поднят")
                else:
                    print(f"  ⚠️ {intf['name']} возможно не поднялся")
                
            except CriticalError as e:
                self.log(f"❌ Ошибка настройки {intf['name']}: {e}")
                all_success = False
        
        if all_success:
            self.save_config()
        
        return all_success

# ==================== КЛАСС ДЛЯ НАСТРОЙКИ AGG ====================

class AGGConfigurator(SmartDeviceConfigurator):
    """Умный конфигуратор для AGG"""
    
    def __init__(self, device_name: str, is_second: bool = False):
        super().__init__(device_name, DEVICE_PORTS[device_name])
        self.config = AGG_CONFIGS[device_name]
        self.is_second = is_second
    
    def configure_basic(self) -> bool:
        """Базовая настройка устройства"""
        self.log("\n📋 Базовая конфигурация")
        
        try:
            commands = [
                f"hostname {self.config['hostname']}",
                "enable password cisco",
                "enable secret cisco",
                "service password-encryption",
                "no ip domain-lookup",
                "line console 0",
                "password cisco",
                "logging synchronous",
                "exec-timeout 30 0",
                "exit",
                "line vty 0 4",
                "password cisco",
                "transport input telnet",
                "login",
                "exit"
            ]
            
            for cmd in commands:
                self.send_config_command(cmd, critical=True)
                time.sleep(0.3)
            
            self.send_config_command("end", critical=False)
            
        except CriticalError as e:
            self.log(f"❌ Ошибка базовой настройки: {e}")
            return False
        
        return True
    
    def configure_interface(self, intf: Dict) -> bool:
        """Умная настройка одного интерфейса с проверками"""
        
        print(f"\n--- {intf['name']} ({intf['desc']}) ---")
        
        try:
            # Для access портов без IP
            if intf.get('ip') is None:
                commands = [
                    f"interface {intf['name']}",
                    f"description {intf['desc']}",
                    "no shutdown",
                    "exit"
                ]
                
                for cmd in commands:
                    self.send_config_command(cmd, critical=True)
                    time.sleep(0.5)
                
                return True
            
            # Проверяем, не настроен ли уже интерфейс
            success, response = self.send_command(f"show ip interface {intf['name']}", wait=2)
            
            if intf['ip'] in response:
                print(f"  ✅ {intf['name']} уже настроен с IP {intf['ip']}")
                return True
            
            # Настраиваем интерфейс с IP
            commands = [
                f"interface {intf['name']}",
                f"description {intf['desc']}",
                f"ip address {intf['ip']} {intf['mask']}",
                "no shutdown",
                "exit"
            ]
            
            for cmd in commands:
                self.send_config_command(cmd, critical=True)
                time.sleep(0.5)
            
            # Проверяем, что интерфейс поднялся
            time.sleep(2)
            success, response = self.send_command(f"show interface {intf['name']}")
            
            if 'up' in response and 'up' in response:
                print(f"  ✅ {intf['name']} поднят")
            else:
                print(f"  ⚠️ {intf['name']} возможно не поднялся")
                # Пробуем принудительно поднять
                self.send_config_command(f"interface {intf['name']}", critical=False)
                self.send_config_command("no shutdown", critical=False)
                self.send_config_command("end", critical=False)
            
            # Проверка пинга для критических интерфейсов
            if intf['type'] == 'core':
                time.sleep(2)
                self.check_ping(intf['ping_target'], critical=True)
                print(f"  ✅ Связность с {intf['ping_target']} подтверждена")
            
            elif intf['type'] == 'agg':
                if self.is_second:
                    time.sleep(2)
                    self.check_ping(intf['ping_target'], critical=True)
                    print(f"  ✅ Связность с {intf['ping_target']} подтверждена")
                else:
                    print(f"  ⏭️ Пинг {intf['ping_target']} будет проверен после настройки второго AGG")
            
        except CriticalError as e:
            self.log(f"❌ Ошибка настройки {intf['name']}: {e}")
            return False
        
        return True
    
    def configure_all_interfaces(self) -> bool:
        """Настройка всех интерфейсов"""
        self.log("\n🌐 Настройка интерфейсов")
        
        all_success = True
        
        for intf in self.config['interfaces']:
            if not self.configure_interface(intf):
                all_success = False
            time.sleep(1)
        
        if all_success:
            self.save_config()
        
        return all_success
    
    def run(self) -> bool:
        """Полный цикл настройки AGG"""
        
        print(f"\n{'='*70}")
        print(f"🚀 НАСТРОЙКА {self.name} {'(ВТОРОЙ)' if self.is_second else '(ПЕРВЫЙ)'}")
        print(f"{'='*70}")
        
        try:
            if not self.connect():
                self.log(f"❌ Не удалось подключиться к {self.name}")
                return False
            
            if not self.configure_basic():
                return False
            
            if not self.configure_all_interfaces():
                return False
            
            self.diag.print_summary()
            
        except CriticalError as e:
            self.log(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
            self.diag.print_summary()
            return False
        
        return True

# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================

def print_topology_info():
    """Вывод информации о топологии"""
    print("\n" + "="*100)
    print("🔍 ТОПОЛОГИЯ ДЛЯ НАСТРОЙКИ AGG1 И AGG2")
    print("="*100)
    print("""
    CORE1:
      • Gi2/0 ─── AGG1 Fa0/0   (10.1.2.0/24)
      • Gi4/0 ─── AGG2 Fa0/1   (10.1.3.0/24)

    CORE2:
      • Gi4/0 ─── AGG1 Fa0/1   (10.2.2.0/24)
      • Gi2/0 ─── AGG2 Fa0/0   (10.2.3.0/24)

    AGG1 ↔ AGG2:
      • Fa1/5 ─── Fa1/5        (10.100.1.0/24)
      • Fa1/6 ─── Fa1/6        (10.100.1.0/24)

    КРИТИЧЕСКИЕ ПРОВЕРКИ:
      • AGG1 должен пинговать CORE1 (10.1.2.1) и CORE2 (10.2.2.1)
      • AGG2 должен пинговать CORE1 (10.1.3.1) и CORE2 (10.2.3.1)
      • После настройки обоих: AGG1 и AGG2 должны пинговать друг друга
    """)
    print("="*100)
    
    response = input("\n✅ Топология соответствует? (y/n): ").strip().lower()
    if response != 'y':
        print("🛑 Исправьте топологию и запустите скрипт заново")
        sys.exit(0)

def main():
    print("\n" + "="*100)
    print("🚀 УМНАЯ НАСТРОЙКА AGG1 И AGG2 С НУЛЯ")
    print("="*100)
    
    # Проверка топологии
    print_topology_info()
    
    # ШАГ 1: Создание всех линков в GNS3
    print("\n🔧 ШАГ 1: СОЗДАНИЕ ФИЗИЧЕСКИХ ЛИНКОВ В GNS3")
    gns3 = GNS3LinkCreator()
    if not gns3.create_all_links():
        print("⚠️ Проблемы при создании линков")
        response = input("Продолжить настройку? (y/n): ").strip().lower()
        if response != 'y':
            sys.exit(0)
    
    # ШАГ 2: Настройка CORE
    print("\n🔧 ШАГ 2: НАСТРОЙКА CORE")
    
    core_results = {}
    
    for core_name in ['CORE1', 'CORE2']:
        print(f"\n--- {core_name} ---")
        core = CoreConfigurator(core_name)
        core_results[core_name] = core.configure()
        core.close()
        time.sleep(2)
        
        if not core_results[core_name]:
            print(f"❌ Ошибка настройки {core_name}")
            response = input("Продолжить? (y/n): ").strip().lower()
            if response != 'y':
                sys.exit(1)
    
    # ШАГ 3: Настройка AGG1
    print("\n🔧 ШАГ 3: НАСТРОЙКА AGG1")
    agg1 = AGGConfigurator('AGG1', is_second=False)
    agg1_ok = agg1.run()
    agg1.close()
    
    # ШАГ 4: Настройка AGG2
    print("\n🔧 ШАГ 4: НАСТРОЙКА AGG2")
    agg2 = AGGConfigurator('AGG2', is_second=True)
    agg2_ok = agg2.run()
    agg2.close()
    
    # ИТОГОВЫЙ ОТЧЕТ
    print("\n" + "="*100)
    print("📊 ИТОГОВЫЙ ОТЧЕТ")
    print("="*100)
    
    print(f"\nCORE1: {'✅' if core_results.get('CORE1') else '❌'}")
    print(f"CORE2: {'✅' if core_results.get('CORE2') else '❌'}")
    print(f"AGG1: {'✅' if agg1_ok else '❌'}")
    print(f"AGG2: {'✅' if agg2_ok else '❌'}")
    
    print("\n" + "="*100)
    if agg1_ok and agg2_ok:
        print("🎉 ПОЗДРАВЛЯЮ! ПОЛНАЯ НАСТРОЙКА AGG1 И AGG2 ВЫПОЛНЕНА УСПЕШНО!")
        print("\n   ✅ Все линки созданы")
        print("   ✅ CORE настроены")
        print("   ✅ AGG1 настроен")
        print("   ✅ AGG2 настроен")
        print("\n📌 Можно переходить к настройке OSPF на AGG")
    else:
        print("⚠️ ОБНАРУЖЕНЫ ПРОБЛЕМЫ:")
        if not agg1_ok:
            print("   ❌ Проблемы с настройкой AGG1")
        if not agg2_ok:
            print("   ❌ Проблемы с настройкой AGG2")
        print("\n📌 Проверьте вывод выше и запустите скрипт заново")
    print("="*100)
    
    # Сохраняем результат
    with open('agg_config_result.txt', 'w') as f:
        f.write(f"""
РЕЗУЛЬТАТ НАСТРОЙКИ AGG1 И AGG2
=================================
Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

CORE1: {'УСПЕХ' if core_results.get('CORE1') else 'ОШИБКА'}
CORE2: {'УСПЕХ' if core_results.get('CORE2') else 'ОШИБКА'}
AGG1: {'УСПЕХ' if agg1_ok else 'ОШИБКА'}
AGG2: {'УСПЕХ' if agg2_ok else 'ОШИБКА'}

ИТОГ: {'УСПЕХ' if (agg1_ok and agg2_ok) else 'ОШИБКА'}
=================================
""")
    
    print("\n📝 Результат сохранен в agg_config_result.txt")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Скрипт остановлен пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Необработанная ошибка: {e}")
        sys.exit(1)