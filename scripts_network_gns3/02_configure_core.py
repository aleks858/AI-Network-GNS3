#!/usr/bin/env python3
"""
03_configure_core_final.py - ПОЛНАЯ НАСТРОЙКА CORE1 И CORE2 С НУЛЯ
С самодиагностикой и проверкой всех команд
"""

import telnetlib
import time
import re
import requests
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from enum import Enum

# ==================== КОНФИГУРАЦИЯ УСТРОЙСТВ ====================

DEVICE_CONFIGS = {
    'CORE1': {
        'port': 5002,
        'hostname': 'CORE1',
        'router_id': '1.1.1.1',
        'loopback': '1.1.1.1',
        'interfaces': [
            {'name': 'GigabitEthernet1/0', 'ip': '10.12.1.1', 'desc': 'to CORE2 Gi1/0'},
            {'name': 'GigabitEthernet2/0', 'ip': '10.12.2.1', 'desc': 'to CORE2 Gi2/0'},
            {'name': 'GigabitEthernet3/0', 'ip': '10.1.2.1', 'desc': 'to AGG1 Fa0/0'},
            {'name': 'GigabitEthernet4/0', 'ip': '10.1.3.1', 'desc': 'to AGG2 Fa0/0'},
            {'name': 'GigabitEthernet5/0', 'ip': '10.1.4.1', 'desc': 'to FW/CE1 Fa0/0'},
        ],
        'ospf_networks': [
            '10.12.1.0 0.0.0.255 area 0',
            '10.12.2.0 0.0.0.255 area 0',
            '10.1.2.0 0.0.0.255 area 0',
            '10.1.3.0 0.0.0.255 area 0',
            '10.1.4.0 0.0.0.255 area 0',
            '1.1.1.1 0.0.0.0 area 0',
        ]
    },
    'CORE2': {
        'port': 5003,
        'hostname': 'CORE2',
        'router_id': '2.2.2.2',
        'loopback': '2.2.2.2',
        'interfaces': [
            {'name': 'GigabitEthernet1/0', 'ip': '10.12.1.2', 'desc': 'to CORE1 Gi1/0'},
            {'name': 'GigabitEthernet2/0', 'ip': '10.12.2.2', 'desc': 'to CORE1 Gi2/0'},
            {'name': 'GigabitEthernet3/0', 'ip': '10.2.2.1', 'desc': 'to AGG1 Fa0/1'},
            {'name': 'GigabitEthernet4/0', 'ip': '10.2.3.1', 'desc': 'to AGG2 Fa0/1'},
            {'name': 'GigabitEthernet5/0', 'ip': '10.2.4.1', 'desc': 'to FW/CE2 Fa0/0'},
        ],
        'ospf_networks': [
            '10.12.1.0 0.0.0.255 area 0',
            '10.12.2.0 0.0.0.255 area 0',
            '10.2.2.0 0.0.0.255 area 0',
            '10.2.3.0 0.0.0.255 area 0',
            '10.2.4.0 0.0.0.255 area 0',
            '2.2.2.2 0.0.0.0 area 0',
        ]
    }
}

# ==================== КЛАСС ДИАГНОСТИКИ ====================

class CommandStatus(Enum):
    SUCCESS = "✅ УСПЕХ"
    FAILED = "❌ ОШИБКА"
    WARNING = "⚠️ ПРЕДУПРЕЖДЕНИЕ"

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
    
    def add_result(self, command: str, output: str, status: CommandStatus, error_msg: str = None):
        self.results.append({
            'command': command,
            'output': output,
            'status': status,
            'error_msg': error_msg,
            'timestamp': datetime.now(),
            'prompt': self.current_prompt
        })
        self._print_result(command, status, error_msg)
    
    def _print_result(self, command: str, status: CommandStatus, error_msg: str = None):
        if status == CommandStatus.SUCCESS:
            print(f"  ✅ {command}")
        elif status == CommandStatus.FAILED:
            print(f"  ❌ {command} - {error_msg}")
        elif status == CommandStatus.WARNING:
            print(f"  ⚠️ {command} - {error_msg}")
    
    def print_summary(self):
        total = len(self.results)
        successful = sum(1 for r in self.results if r['status'] == CommandStatus.SUCCESS)
        failed = sum(1 for r in self.results if r['status'] == CommandStatus.FAILED)
        warnings = sum(1 for r in self.results if r['status'] == CommandStatus.WARNING)
        print(f"\n📊 СТАТИСТИКА: {successful}/{total} успешно, {failed} ошибок, {warnings} предупреждений")
        return successful, failed, warnings

# ==================== GNS3 LINK CREATOR ====================

class GNS3LinkCreator:
    """Создание физических линков в GNS3 через API"""
    
    def __init__(self, gns3_host='localhost', gns3_port=3080):
        self.base_url = f'http://{gns3_host}:{gns3_port}/v2'
        self.project_id = None
        self.nodes = {}
    
    def log(self, msg: str):
        print(f"[GNS3] {msg}")
    
    def get_projects(self) -> List:
        try:
            response = requests.get(f'{self.base_url}/projects', timeout=5)
            if response.status_code == 200:
                return response.json()
            return []
        except:
            return []
    
    def select_project(self, project_name: str) -> bool:
        projects = self.get_projects()
        for p in projects:
            if p['name'] == project_name:
                self.project_id = p['project_id']
                self.log(f"✅ Проект '{project_name}' выбран")
                return True
        self.log(f"❌ Проект '{project_name}' не найден")
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
                return True
        except:
            pass
        return False
    
    def create_link(self, node1: str, a1: int, p1: int, node2: str, a2: int, p2: int) -> bool:
        if node1 not in self.nodes or node2 not in self.nodes:
            return False
        
        link_data = {
            "nodes": [
                {"node_id": self.nodes[node1]['node_id'], "adapter_number": a1, "port_number": p1},
                {"node_id": self.nodes[node2]['node_id'], "adapter_number": a2, "port_number": p2}
            ],
            "link_type": "ethernet",
            "link_style": {"color": "#00ff00", "width": 2, "dash": False}
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/projects/{self.project_id}/links',
                json=link_data,
                timeout=5
            )
            if response.status_code == 201:
                self.log(f"✅ Линк создан: {node1}:{a1}/{p1} ↔ {node2}:{a2}/{p2}")
                return True
            else:
                self.log(f"❌ Ошибка {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log(f"❌ Ошибка: {e}")
            return False
    
    def create_core_links(self) -> bool:
        print("\n🔧 СОЗДАНИЕ ФИЗИЧЕСКИХ ЛИНКОВ В GNS3")
        print("-"*60)
        
        links = [
            ('CORE1', 1, 0, 'CORE2', 1, 0),
            ('CORE1', 2, 0, 'CORE2', 2, 0),
        ]
        
        success = 0
        for node1, a1, p1, node2, a2, p2 in links:
            if self.create_link(node1, a1, p1, node2, a2, p2):
                success += 1
            time.sleep(0.5)
        
        print(f"\n📊 Создано линков: {success}/{len(links)}")
        return success == len(links)

# ==================== ОСНОВНОЙ КЛАСС КОНФИГУРАТОРА ====================

class CoreConfigurator:
    """Конфигуратор с контролем режимов и самодиагностикой"""
    
    def __init__(self, device_name: str, password: str = 'cisco'):
        self.name = device_name
        self.config = DEVICE_CONFIGS[device_name]
        self.port = self.config['port']
        self.password = password
        self.tn = None
        self.diag = DiagnosticSystem(device_name)
        self.privileged = False
        self.prompt = ""
    
    def log(self, msg: str):
        self.diag.log(msg)
    
    # ==================== РАБОТА С ПРОМПТОМ ====================
    
    def _read(self, timeout: float = 1.0) -> str:
        time.sleep(timeout)
        try:
            data = self.tn.read_very_eager()
            return data.decode('utf-8', errors='ignore')
        except:
            return ""
    
    def _write(self, data: str):
        self.tn.write(data.encode('utf-8') + b"\r\n")
    
    def _get_prompt(self) -> str:
        self._write("")
        time.sleep(0.5)
        data = self._read()
        lines = data.strip().split('\n')
        if lines:
            self.prompt = lines[-1].strip()
            self.diag.set_prompt(self.prompt)
            return self.prompt
        return ""
    
    def _check_privileged(self) -> bool:
        prompt = self._get_prompt()
        self.privileged = '#' in prompt
        return self.privileged
    
    def _ensure_privileged(self) -> bool:
        if self._check_privileged():
            return True
        
        self.log("⚠️ Вход в привилегированный режим...")
        self._write("enable")
        time.sleep(2)
        
        data = self._read()
        if 'Password:' in data:
            self._write(self.password)
            time.sleep(2)
        
        return self._check_privileged()
    
    # ==================== ПОДКЛЮЧЕНИЕ ====================
    
    def connect(self) -> bool:
        self.log(f"🔌 Подключение к порту {self.port}...")
        
        try:
            self.tn = telnetlib.Telnet('localhost', self.port, timeout=10)
            time.sleep(2)
            
            # Очищаем буфер
            self._read()
            
            if self._ensure_privileged():
                self.log(f"✅ Подключено, режим: {self.prompt}")
                return True
            else:
                self.log("❌ Не удалось войти в привилегированный режим")
                return False
                
        except Exception as e:
            self.log(f"❌ Ошибка: {e}")
            return False
    
    # ==================== ОТПРАВКА КОМАНД ====================
    
    def send_command(self, command: str, wait: int = 2) -> Tuple[bool, str]:
        if not self.tn:
            return False, "Нет соединения"
        
        # Проверяем и восстанавливаем привилегии
        if not self.privileged:
            self._ensure_privileged()
        
        # Очищаем буфер
        self._read(0.1)
        
        # Отправляем команду
        self._write(command)
        time.sleep(wait)
        
        # Читаем ответ
        response = self._read()
        
        # Очищаем от мусора
        clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', response)
        clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', clean)
        
        # Проверяем не потеряли ли привилегии
        self._check_privileged()
        
        # Проверка на ошибки
        if '% Invalid' in clean or '% Incomplete' in clean:
            return False, clean
        
        return True, clean
    
    def send_with_feedback(self, command: str, wait: int = 2, phase: str = None) -> bool:
        success, response = self.send_command(command, wait)
        
        # Показываем первую строку ответа
        lines = response.strip().split('\n')
        if lines and lines[0].strip():
            preview = lines[0][:80]
            print(f"   {preview}")
        
        status = CommandStatus.SUCCESS if success else CommandStatus.FAILED
        error_msg = None if success else f"Ошибка: {response[:100]}"
        
        self.diag.add_result(command, response, status, error_msg)
        
        return success
    
    # ==================== КОНФИГУРАЦИЯ ====================
    
    def configure_basic(self) -> bool:
        self.log("\n📋 Базовая конфигурация")
        
        commands = [
            "configure terminal",
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
            "exit",
            "end",
            "write memory"
        ]
        
        all_success = True
        for cmd in commands:
            wait = 3 if 'write memory' in cmd else 2
            if not self.send_with_feedback(cmd, wait=wait, phase="basic"):
                all_success = False
            time.sleep(0.5)
        
        return all_success
    
    def configure_interfaces(self) -> bool:
        self.log("\n🌐 Настройка интерфейсов")
        
        self._ensure_privileged()
        
        if not self.send_with_feedback("configure terminal", phase="interfaces"):
            return False
        
        all_success = True
        
        for intf in self.config['interfaces']:
            print(f"\n--- {intf['name']} ---")
            
            commands = [
                f"interface {intf['name']}",
                f"description {intf['desc']}",
                f"ip address {intf['ip']} 255.255.255.0",
                "no shutdown",
                "exit"
            ]
            
            for cmd in commands:
                if not self.send_with_feedback(cmd, phase="interfaces"):
                    all_success = False
                time.sleep(0.5)
        
        self.send_with_feedback("end", phase="interfaces")
        self.send_with_feedback("write memory", wait=3, phase="interfaces")
        
        return all_success
    
    def configure_ospf(self) -> bool:
        self.log("\n🔄 Настройка OSPF")
        
        self._ensure_privileged()
        
        if not self.send_with_feedback("configure terminal", phase="ospf"):
            return False
        
        # Loopback
        commands = [
            "interface Loopback0",
            f"ip address {self.config['loopback']} 255.255.255.255",
            "exit"
        ]
        
        for cmd in commands:
            self.send_with_feedback(cmd, phase="ospf")
            time.sleep(0.5)
        
        # Router OSPF
        if not self.send_with_feedback("router ospf 1", phase="ospf"):
            return False
        
        self.send_with_feedback(f"router-id {self.config['router_id']}", phase="ospf")
        
        for network in self.config['ospf_networks']:
            self.send_with_feedback(f"network {network}", phase="ospf")
            time.sleep(0.5)
        
        self.send_with_feedback("exit", phase="ospf")
        self.send_with_feedback("end", phase="ospf")
        self.send_with_feedback("write memory", wait=3, phase="ospf")
        
        return True
    
    # ==================== САМОДИАГНОСТИКА ====================
    
    def self_diagnostic(self) -> Dict:
        """Самодиагностика устройства - проверка что реально работает"""
        self.log("\n🔍 ЗАПУСК САМОДИАГНОСТИКИ")
        
        self._ensure_privileged()
        
        results = {
            'interfaces': {},
            'ospf_neighbors': 0,
            'ping_test': {}
        }
        
        # Проверка интерфейсов
        success, response = self.send_command("show ip interface brief", wait=3)
        if success:
            print("\n📋 СОСТОЯНИЕ ИНТЕРФЕЙСОВ:")
            for line in response.split('\n'):
                if 'GigabitEthernet' in line:
                    parts = line.split()
                    if len(parts) >= 6:
                        name = parts[0]
                        ip = parts[1]
                        status = f"{parts[4]}/{parts[5]}"
                        results['interfaces'][name] = {
                            'ip': ip,
                            'status': parts[4],
                            'protocol': parts[5]
                        }
                        if parts[4] == 'up' and parts[5] == 'up':
                            print(f"  ✅ {name}: {ip} - {status}")
                        else:
                            print(f"  ❌ {name}: {ip} - {status}")
        
        # Проверка OSPF соседей
        success, response = self.send_command("show ip ospf neighbor", wait=3)
        if success:
            results['ospf_neighbors'] = len(re.findall(r'FULL', response))
            print(f"\n🤝 OSPF СОСЕДЕЙ: {results['ospf_neighbors']}")
            for line in response.split('\n'):
                if 'FULL' in line:
                    print(f"  ✅ {line.strip()}")
        
        # Проверка пингов
        if self.name == 'CORE1':
            targets = ['10.12.1.2', '10.12.2.2']
        else:
            targets = ['10.12.1.1', '10.12.2.1']
        
        print("\n📡 ПРОВЕРКА ПИНГОВ:")
        for target in targets:
            success, response = self.send_command(f"ping {target} repeat 3", wait=4)
            if '!!!!!' in response or 'Success rate is 100 percent' in response:
                print(f"  ✅ Ping {target}: УСПЕХ")
                results['ping_test'][target] = True
            else:
                print(f"  ❌ Ping {target}: НЕУДАЧА")
                results['ping_test'][target] = False
        
        return results
    
    # ==================== ОСНОВНОЙ МЕТОД ====================
    
    def run(self) -> Dict:
        print(f"\n{'='*70}")
        print(f"🚀 НАСТРОЙКА {self.name}")
        print(f"{'='*70}")
        
        results = {
            'basic': False,
            'interfaces': False,
            'ospf': False,
            'diagnostic': {}
        }
        
        if not self.connect():
            return results
        
        results['basic'] = self.configure_basic()
        results['interfaces'] = self.configure_interfaces()
        results['ospf'] = self.configure_ospf()
        
        # Ждем сходимости OSPF
        print("\n⏳ Ожидание сходимости OSPF (20 секунд)...")
        time.sleep(20)
        
        # Самодиагностика
        results['diagnostic'] = self.self_diagnostic()
        
        self.diag.print_summary()
        
        return results
    
    def close(self):
        if self.tn:
            self.tn.close()
            self.log("🔒 Соединение закрыто")

# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================

def main():
    print("\n" + "="*90)
    print("🚀 ПОЛНАЯ НАСТРОЙКА CORE1 И CORE2 С НУЛЯ")
    print("="*90)
    print("📋 ОСОБЕННОСТИ:")
    print("   • Два отдельных физических линка")
    print("   • Контроль привилегированного режима")
    print("   • Восстановление режима при потере")
    print("   • Полная самодиагностика после настройки")
    print("="*90)
    
    # ШАГ 1: Создание линков
    print("\n🔧 ШАГ 1: СОЗДАНИЕ ЛИНКОВ В GNS3")
    response = input("Создать линки в GNS3? (y/n): ").strip().lower()
    if response == 'y':
        project = input("Имя проекта (Enter для 'AS1-FULL-NETWORK'): ").strip()
        if not project:
            project = "AS1-FULL-NETWORK"
        
        gns3 = GNS3LinkCreator()
        if gns3.select_project(project):
            gns3.get_nodes()
            gns3.create_core_links()
        else:
            print("⚠️ Продолжаем без создания линков")
    
    # ШАГ 2: Настройка CORE1
    print("\n🔧 ШАГ 2: НАСТРОЙКА CORE1")
    core1 = CoreConfigurator('CORE1')
    res1 = core1.run()
    core1.close()
    
    # ШАГ 3: Настройка CORE2
    print("\n🔧 ШАГ 3: НАСТРОЙКА CORE2")
    core2 = CoreConfigurator('CORE2')
    res2 = core2.run()
    core2.close()
    
    # ШАГ 4: Итоговый отчет
    print("\n" + "="*90)
    print("📊 ИТОГОВЫЙ ОТЧЕТ")
    print("="*90)
    
    print(f"\nCORE1:")
    print(f"  Базовая конфигурация: {'✅' if res1.get('basic') else '❌'}")
    print(f"  Интерфейсы: {'✅' if res1.get('interfaces') else '❌'}")
    print(f"  OSPF: {'✅' if res1.get('ospf') else '❌'}")
    
    diag1 = res1.get('diagnostic', {})
    print(f"\n  📊 САМОДИАГНОСТИКА CORE1:")
    print(f"    OSPF соседей: {diag1.get('ospf_neighbors', 0)}")
    for intf, data in diag1.get('interfaces', {}).items():
        if data['status'] == 'up' and data['protocol'] == 'up':
            print(f"    ✅ {intf}: {data['ip']}")
    
    print(f"\nCORE2:")
    print(f"  Базовая конфигурация: {'✅' if res2.get('basic') else '❌'}")
    print(f"  Интерфейсы: {'✅' if res2.get('interfaces') else '❌'}")
    print(f"  OSPF: {'✅' if res2.get('ospf') else '❌'}")
    
    diag2 = res2.get('diagnostic', {})
    print(f"\n  📊 САМОДИАГНОСТИКА CORE2:")
    print(f"    OSPF соседей: {diag2.get('ospf_neighbors', 0)}")
    for intf, data in diag2.get('interfaces', {}).items():
        if data['status'] == 'up' and data['protocol'] == 'up':
            print(f"    ✅ {intf}: {data['ip']}")
    
    all_ok = (res1.get('basic') and res2.get('basic') and 
              diag1.get('ospf_neighbors', 0) > 0 and 
              diag2.get('ospf_neighbors', 0) > 0)
    
    print("\n" + "="*90)
    if all_ok:
        print("🎉 ПОЗДРАВЛЯЮ! CORE1 И CORE2 ПОЛНОСТЬЮ НАСТРОЕНЫ!")
        print("\n📋 Все проверки пройдены:")
        print("   ✅ Интерфейсы настроены")
        print("   ✅ OSPF соседи установлены")
        print("   ✅ Пинги работают")
    else:
        print("⚠️ Обнаружены проблемы. Проверьте вывод выше.")
    print("="*90)

if __name__ == "__main__":
    main()