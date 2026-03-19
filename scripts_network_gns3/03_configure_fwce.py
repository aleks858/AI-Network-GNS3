#!/usr/bin/env python3
"""
04_configure_ce_with_nat_ready.py - НАСТРОЙКА CE С NAT "НА ВЫРОСТ"
NAT настроен, но будет ждать появления внешнего интерфейса
"""

import telnetlib
import time
import re
import sys
from typing import Dict, List, Tuple
from datetime import datetime
from enum import Enum

# ==================== КОНФИГУРАЦИЯ С NAT "НА ВЫРОСТ" ====================

CE_CONFIGS = {
    'CE1': {
        'port': 5000,
        'hostname': 'CE1',
        'router_id': '5.5.5.5',
        'loopback': '5.5.5.5',
        'as_number': 65001,
        'interfaces': [
            # Inside интерфейсы (уже активны)
            {'name': 'FastEthernet0/0', 'ip': '10.1.4.2', 'mask': '255.255.255.0', 
             'desc': 'to CORE1 Gi5/0 (inside)', 'cdp': True},
            {'name': 'FastEthernet0/1', 'ip': '10.2.4.2', 'mask': '255.255.255.0', 
             'desc': 'to CORE2 Gi5/0 (inside)', 'cdp': True},
            {'name': 'FastEthernet1/0', 'ip': '10.100.2.1', 'mask': '255.255.255.0', 
             'desc': 'to CE2 Fa1/0 (inside)', 'cdp': False},
            {'name': 'FastEthernet1/1', 'ip': '10.100.2.3', 'mask': '255.255.255.0', 
             'desc': 'to CE2 Fa1/1 (inside)', 'cdp': False},
            # Outside интерфейс (пока Down, но настроен)
            {'name': 'FastEthernet1/2', 'ip': '192.168.1.1', 'mask': '255.255.255.252', 
             'desc': 'to ISP1 (outside) - WAITING FOR ISP', 'cdp': False, 'shutdown': True},
        ],
        'ospf_networks': [
            '10.1.4.0 0.0.0.255 area 0',
            '10.2.4.0 0.0.0.255 area 0',
            '10.100.2.0 0.0.0.255 area 0',
        ],
        'nat': {
            'inside_networks': ['10.1.4.0', '10.2.4.0', '10.100.2.0'],
            'acl': 1,
            'pool_name': 'NAT-POOL',
            'pool_start': '192.168.1.2',
            'pool_end': '192.168.1.2',
            'outside_interface': 'FastEthernet1/2'
        },
        'bgp': {
            'neighbor': '192.168.1.2',
            'remote_as': 65002,
            'shutdown': True,  # BGP пока выключен
            'networks': [
                {'network': '10.1.4.0', 'mask': '255.255.255.0'},
                {'network': '10.2.4.0', 'mask': '255.255.255.0'},
                {'network': '10.100.2.0', 'mask': '255.255.255.0'},
                {'network': '5.5.5.5', 'mask': '255.255.255.255'}
            ]
        }
    },
    'CE2': {
        'port': 5001,
        'hostname': 'CE2',
        'router_id': '6.6.6.6',
        'loopback': '6.6.6.6',
        'as_number': 65003,
        'interfaces': [
            {'name': 'FastEthernet0/0', 'ip': '10.1.5.2', 'mask': '255.255.255.0', 
             'desc': 'to CORE1 Gi5/0 (inside)', 'cdp': True},
            {'name': 'FastEthernet0/1', 'ip': '10.2.5.2', 'mask': '255.255.255.0', 
             'desc': 'to CORE2 Gi5/0 (inside)', 'cdp': True},
            {'name': 'FastEthernet1/0', 'ip': '10.100.2.2', 'mask': '255.255.255.0', 
             'desc': 'to CE1 Fa1/0 (inside)', 'cdp': False},
            {'name': 'FastEthernet1/1', 'ip': '10.100.2.4', 'mask': '255.255.255.0', 
             'desc': 'to CE1 Fa1/1 (inside)', 'cdp': False},
            {'name': 'FastEthernet1/2', 'ip': '192.168.2.1', 'mask': '255.255.255.252', 
             'desc': 'to ISP2 (outside) - WAITING FOR ISP', 'cdp': False, 'shutdown': True},
        ],
        'ospf_networks': [
            '10.1.5.0 0.0.0.255 area 0',
            '10.2.5.0 0.0.0.255 area 0',
            '10.100.2.0 0.0.0.255 area 0',
        ],
        'nat': {
            'inside_networks': ['10.1.5.0', '10.2.5.0', '10.100.2.0'],
            'acl': 1,
            'pool_name': 'NAT-POOL',
            'pool_start': '192.168.2.2',
            'pool_end': '192.168.2.2',
            'outside_interface': 'FastEthernet1/2'
        },
        'bgp': {
            'neighbor': '192.168.2.2',
            'remote_as': 65004,
            'shutdown': True,  # BGP пока выключен
            'networks': [
                {'network': '10.1.5.0', 'mask': '255.255.255.0'},
                {'network': '10.2.5.0', 'mask': '255.255.255.0'},
                {'network': '10.100.2.0', 'mask': '255.255.255.0'},
                {'network': '6.6.6.6', 'mask': '255.255.255.255'}
            ]
        }
    }
}

# ==================== КЛАССЫ ДИАГНОСТИКИ ====================

class CommandStatus(Enum):
    SUCCESS = "✅ УСПЕХ"
    FAILED = "❌ ОШИБКА"
    WARNING = "⚠️ ПРЕДУПРЕЖДЕНИЕ"

class ConfigurationError(Exception):
    pass

class DeepDiagnosticSystem:
    def __init__(self, device_name: str):
        self.device_name = device_name
        self.results = []
        self.start_time = datetime.now()
        self.stop_on_error = True
        self.cdp_messages = []
    
    def log(self, msg: str):
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] [{self.device_name}] {msg}")
    
    def analyze_output(self, output: str) -> Dict:
        analysis = {'has_error': False, 'error_type': None, 'error_msg': None, 'has_cdp': False}
        
        if re.search(r'% Invalid', output):
            analysis['has_error'] = True
            analysis['error_type'] = 'invalid'
            analysis['error_msg'] = re.findall(r'%[^\n]+', output)
        elif re.search(r'% Incomplete', output):
            analysis['has_error'] = True
            analysis['error_type'] = 'incomplete'
            analysis['error_msg'] = re.findall(r'%[^\n]+', output)
        elif re.search(r'overlaps with', output):
            analysis['has_error'] = True
            analysis['error_type'] = 'overlap'
            analysis['error_msg'] = ['IP address overlap detected']
        elif re.search(r'Duplicate address', output):
            analysis['has_error'] = True
            analysis['error_type'] = 'duplicate'
            analysis['error_msg'] = re.findall(r'%[^\n]+', output)
        
        if re.search(r'%CDP', output):
            analysis['has_cdp'] = True
            self.cdp_messages.extend(re.findall(r'%CDP[^\n]+', output))
        
        return analysis
    
    def add_result(self, command: str, output: str, status: CommandStatus, error_msg: str = None):
        analysis = self.analyze_output(output)
        
        self.results.append({
            'command': command,
            'output': output,
            'status': status,
            'error_msg': error_msg or analysis['error_msg'],
            'analysis': analysis,
            'timestamp': datetime.now()
        })
        
        if status == CommandStatus.SUCCESS:
            print(f"  ✅ {command}")
            if analysis['has_cdp'] and self.cdp_messages:
                print(f"     📢 {self.cdp_messages[-1]}")
        else:
            print(f"  ❌ {command}")
            if analysis['error_msg']:
                print(f"     {analysis['error_msg'][0]}")
            if self.stop_on_error:
                raise ConfigurationError(f"Критическая ошибка на команде: {command}")
    
    def print_detailed_report(self):
        print(f"\n{'='*70}")
        print(f"📊 ДЕТАЛЬНЫЙ ОТЧЕТ - {self.device_name}")
        print(f"{'='*70}")
        
        total = len(self.results)
        successful = sum(1 for r in self.results if r['status'] == CommandStatus.SUCCESS)
        failed = sum(1 for r in self.results if r['status'] == CommandStatus.FAILED)
        
        print(f"\n📈 Статистика:")
        print(f"  ✅ Успешно: {successful}/{total}")
        print(f"  ❌ Ошибки: {failed}")
        
        if failed > 0:
            print(f"\n🔍 Детали ошибок:")
            for r in self.results:
                if r['status'] == CommandStatus.FAILED:
                    print(f"\n  Команда: {r['command']}")
                    print(f"  Ошибка: {r['analysis']['error_msg']}")
        
        exec_time = (datetime.now() - self.start_time).total_seconds()
        print(f"\n⏱️ Время: {exec_time:.1f} сек")

# ==================== ОСНОВНОЙ КЛАСС ====================

class CEConfigurator:
    def __init__(self, device_name: str, password: str = 'cisco'):
        self.name = device_name
        self.config = CE_CONFIGS[device_name]
        self.port = self.config['port']
        self.password = password
        self.tn = None
        self.diag = DeepDiagnosticSystem(device_name)
    
    def log(self, msg: str):
        self.diag.log(msg)
    
    def _read(self, timeout: float = 1.0) -> str:
        time.sleep(timeout)
        try:
            return self.tn.read_very_eager().decode('utf-8', errors='ignore')
        except:
            return ""
    
    def _write(self, data: str):
        if self.tn:
            self.tn.write(data.encode('utf-8') + b"\r\n")
    
    def _reset_session(self):
        self._write("end")
        time.sleep(1)
        self._write("")
        time.sleep(0.5)
    
    def connect(self) -> bool:
        self.log(f"🔌 Подключение к порту {self.port}...")
        
        try:
            self.tn = telnetlib.Telnet('localhost', self.port, timeout=10)
            time.sleep(2)
            self._reset_session()
            self._write("enable")
            time.sleep(2)
            self._write(self.password)
            time.sleep(2)
            self.log("✅ Подключено")
            return True
        except Exception as e:
            self.log(f"❌ Ошибка: {e}")
            return False
    
    def send_command(self, command: str, wait: int = 2) -> Tuple[bool, str]:
        if not self.tn:
            return False, "Нет соединения"
        self._read(0.1)
        self._write(command)
        time.sleep(wait)
        return True, self._read()
    
    def send_with_feedback(self, command: str, wait: int = 2) -> bool:
        success, response = self.send_command(command, wait)
        if not success:
            self.diag.add_result(command, response, CommandStatus.FAILED, "Ошибка отправки")
            return False
        
        if any(err in response for err in ['% Invalid', '% Incomplete', 'overlaps with', 'Duplicate address']):
            self.diag.add_result(command, response, CommandStatus.FAILED)
            return False
        
        self.diag.add_result(command, response, CommandStatus.SUCCESS)
        return True
    
    def configure_basic(self) -> bool:
        self.log("\n📋 Базовая конфигурация")
        commands = [
            "configure terminal", f"hostname {self.config['hostname']}",
            "enable password cisco", "enable secret cisco", "service password-encryption",
            "no ip domain-lookup", "line console 0", "password cisco", "logging synchronous",
            "exec-timeout 30 0", "exit", "line vty 0 4", "password cisco",
            "transport input telnet", "login", "exit", "end", "write memory"
        ]
        for cmd in commands:
            wait = 3 if 'write memory' in cmd else 2
            if not self.send_with_feedback(cmd, wait):
                return False
            time.sleep(0.5)
        return True
    
    def configure_interfaces(self) -> bool:
        self.log("\n🌐 Настройка интерфейсов")
        
        if not self.send_with_feedback("configure terminal"):
            return False
        
        for intf in self.config['interfaces']:
            print(f"\n--- {intf['name']} ---")
            
            commands = [
                f"interface {intf['name']}",
                f"description {intf['desc']}",
                f"ip address {intf['ip']} {intf['mask']}",
            ]
            
            # Если интерфейс должен быть выключен (ожидание ISP)
            if intf.get('shutdown', False):
                commands.append("shutdown")
                print(f"     ⏳ Интерфейс {intf['name']} в режиме ожидания ISP")
            else:
                commands.append("no shutdown")
            
            for cmd in commands:
                if not self.send_with_feedback(cmd):
                    return False
                time.sleep(0.5)
            
            if not intf.get('cdp', True):
                if not self.send_with_feedback("no cdp enable"):
                    return False
                time.sleep(0.5)
            
            if not self.send_with_feedback("exit"):
                return False
        
        self.send_with_feedback("end")
        self.send_with_feedback("write memory", 3)
        return True
    
    def configure_nat(self) -> bool:
        self.log("\n🌍 Настройка NAT (в режиме ожидания)")
        
        if not self.send_with_feedback("configure terminal"):
            return False
        
        nat = self.config['nat']
        
        # Создаем ACL для внутренних сетей
        if not self.send_with_feedback(f"access-list {nat['acl']} permit {nat['inside_networks'][0]} 0.0.0.255"):
            return False
        
        # Создаем NAT pool
        pool_cmd = f"ip nat pool {nat['pool_name']} {nat['pool_start']} {nat['pool_end']} netmask 255.255.255.252"
        if not self.send_with_feedback(pool_cmd):
            return False
        
        # Source NAT overload (будет активен, когда появится outside интерфейс)
        if not self.send_with_feedback(f"ip nat inside source list {nat['acl']} pool {nat['pool_name']} overload"):
            return False
        
        self.send_with_feedback("end")
        self.send_with_feedback("write memory", 3)
        return True
    
    def configure_bgp(self) -> bool:
        self.log("\n🌐 Настройка BGP (в режиме ожидания)")
        
        if not self.send_with_feedback("configure terminal"):
            return False
        
        bgp = self.config['bgp']
        
        # Включаем BGP
        if not self.send_with_feedback(f"router bgp {self.config['as_number']}"):
            return False
        
        # Router ID
        if not self.send_with_feedback(f"bgp router-id {self.config['router_id']}"):
            return False
        
        # Сосед (провайдер) - пока закомментирован или в shutdown
        if bgp.get('shutdown', False):
            self.log(f"  ⏳ BGP сосед {bgp['neighbor']} в режиме ожидания")
            # Добавляем соседа, но в пассивном режиме
            if not self.send_with_feedback(f"neighbor {bgp['neighbor']} remote-as {bgp['remote_as']}"):
                return False
            if not self.send_with_feedback(f"neighbor {bgp['neighbor']} shutdown"):
                return False
        
        # Анонсируем свои сети (они готовы)
        for net in bgp['networks']:
            if not self.send_with_feedback(f"network {net['network']} mask {net['mask']}"):
                return False
            time.sleep(0.5)
        
        self.send_with_feedback("exit")
        self.send_with_feedback("end")
        self.send_with_feedback("write memory", 3)
        return True
    
    def configure_ospf(self) -> bool:
        self.log("\n🔄 Настройка OSPF (активен внутри)")
        
        if not self.send_with_feedback("configure terminal"):
            return False
        
        # Loopback
        commands = [
            "interface Loopback0",
            f"ip address {self.config['loopback']} 255.255.255.255",
            "exit"
        ]
        for cmd in commands:
            if not self.send_with_feedback(cmd):
                return False
            time.sleep(0.5)
        
        # Router OSPF
        if not self.send_with_feedback("router ospf 1"):
            return False
        
        if not self.send_with_feedback(f"router-id {self.config['router_id']}"):
            return False
        
        for network in self.config['ospf_networks']:
            if not self.send_with_feedback(f"network {network}"):
                return False
            time.sleep(0.5)
        
        self.send_with_feedback("exit")
        self.send_with_feedback("end")
        self.send_with_feedback("write memory", 3)
        return True
    
    def deep_diagnostic(self) -> Dict:
        self.log("\n🔍 ГЛУБОКАЯ ДИАГНОСТИКА")
        results = {'interfaces': {}, 'ospf': {'neighbors': 0}, 'bgp': {}, 'nat': {}}
        
        # Проверка интерфейсов
        success, response = self.send_command("show ip interface brief", 3)
        if success:
            print("\n📋 ИНТЕРФЕЙСЫ:")
            for line in response.split('\n'):
                if 'FastEthernet' in line:
                    parts = line.split()
                    if len(parts) >= 6:
                        name = parts[0]
                        ip = parts[1]
                        status = parts[4]
                        print(f"  {status} {name}: {ip}")
        
        # Проверка OSPF
        success, response = self.send_command("show ip ospf neighbor", 3)
        if success:
            results['ospf']['neighbors'] = len(re.findall(r'FULL', response))
            print(f"\n🤝 OSPF соседей: {results['ospf']['neighbors']}")
        
        return results
    
    def run(self) -> Dict:
        print(f"\n{'='*70}")
        print(f"🚀 {self.name} (NAT+BGP в режиме ожидания)")
        print(f"{'='*70}")
        
        results = {'basic': False, 'interfaces': False, 'nat': False, 'bgp': False, 'ospf': False}
        
        try:
            if not self.connect():
                return results
            
            results['basic'] = self.configure_basic()
            results['interfaces'] = self.configure_interfaces()
            results['nat'] = self.configure_nat()
            results['bgp'] = self.configure_bgp()
            results['ospf'] = self.configure_ospf()
            
            print("\n⏳ Ожидание сходимости OSPF (15 сек)...")
            time.sleep(15)
            
            results['diagnostic'] = self.deep_diagnostic()
            self.diag.print_detailed_report()
            
        except ConfigurationError as e:
            print(f"\n❌ ОШИБКА: {e}")
            self.diag.print_detailed_report()
            sys.exit(1)
        
        return results
    
    def close(self):
        if self.tn:
            self.tn.close()
            self.log("🔒 Закрыто")

# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================

def main():
    print("\n" + "="*90)
    print("🚀 НАСТРОЙКА CE1 И CE2 (NAT+BGP В РЕЖИМЕ ОЖИДАНИЯ ISP)")
    print("="*90)
    print("📋 ОСОБЕННОСТИ:")
    print("   • NAT настроен и готов к работе")
    print("   • BGP настроен в режиме shutdown (ждет ISP)")
    print("   • Outside интерфейсы выключены (shutdown)")
    print("   • OSPF внутри сети активен")
    print("="*90)
    
    results = {}
    
    try:
        for device in ['CE1', 'CE2']:
            print(f"\n{'='*70}")
            print(f"🔧 {device}")
            print(f"{'='*70}")
            cfg = CEConfigurator(device)
            results[device] = cfg.run()
            cfg.close()
            
    except SystemExit:
        print("\n🛑 СКРИПТ ОСТАНОВЛЕН ИЗ-ЗА ОШИБКИ")
        return
    
    print("\n" + "="*90)
    print("📊 ИТОГ")
    print("="*90)
    
    for device, res in results.items():
        print(f"\n{device}:")
        print(f"  Базовая: {'✅' if res.get('basic') else '❌'}")
        print(f"  Интерфейсы: {'✅' if res.get('interfaces') else '❌'}")
        print(f"  NAT: {'✅' if res.get('nat') else '❌'}")
        print(f"  BGP: {'✅' if res.get('bgp') else '❌'}")
        print(f"  OSPF: {'✅' if res.get('ospf') else '❌'}")
    
    print("\n" + "="*90)
    print("✅ НАСТРОЙКА ЗАВЕРШЕНА")
    print("   NAT и BGP готовы, ждут появления ISP")
    print("="*90)

if __name__ == "__main__":
    main()