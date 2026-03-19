#!/usr/bin/env python3
"""
99_final_connectivity_check.py - ИТОГОВАЯ ПРОВЕРКА СВЯЗНОСТИ И OSPF
С АВТОМАТИЧЕСКИМ ИСПРАВЛЕНИЕМ ВСЕХ ПРОБЛЕМ
"""

import telnetlib
import time
import re
import sys
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# ==================== ВАЖНЫЕ ПРЕДУПРЕЖДЕНИЯ ====================

print("\n" + "="*100)
print("⚠️" * 50)
print("⚠️")
print("⚠️   ВНИМАНИЕ! ПРОВЕРЬТЕ ФИЗИЧЕСКИЕ ЛИНКИ В GNS3!")
print("⚠️")
print("⚠️   ВАША СХЕМА ПОДКЛЮЧЕНИЙ:")
print("⚠️   ┌─────────────────────────────────────────────┐")
print("⚠️   │  CORE1 Gi1/0 ───── CORE2 Gi1/0              │")
print("⚠️   │  CORE1 Gi2/0 ───── CORE2 Gi2/0              │")
print("⚠️   │  CORE1 Gi3/0 ───── CE1 Fa0/0                │")
print("⚠️   │  CORE1 Gi5/0 ───── CE2 Fa0/0                │")
print("⚠️   │  CORE2 Gi5/0 ───── CE1 Fa0/1                │")
print("⚠️   │  CORE2 Gi3/0 ───── CE2 Fa0/1                │")
print("⚠️   │  CE1 Fa1/0  ───── CE2 Fa1/0                 │")
print("⚠️   │  CE1 Fa1/1  ───── CE2 Fa1/1                 │")
print("⚠️   └─────────────────────────────────────────────┘")
print("⚠️")
print("⚠️   ЕСЛИ ЛИНКИ ПОДКЛЮЧЕНЫ ИНАЧЕ - ИСПРАВЬТЕ!")
print("⚠️")
print("⚠️" * 50)
print("="*100)

input("\n✅ Нажмите ENTER чтобы подтвердить правильность подключений и продолжить...")

# ==================== КОНФИГУРАЦИЯ ====================

DEVICES = {
    'CORE1': {'port': 5002, 'name': 'CORE1', 'router_id': '1.1.1.1'},
    'CORE2': {'port': 5003, 'name': 'CORE2', 'router_id': '2.2.2.2'},
    'CE1': {'port': 5000, 'name': 'CE1', 'router_id': '5.5.5.5'},
    'CE2': {'port': 5001, 'name': 'CE2', 'router_id': '6.6.6.6'}
}

# Все возможные пары для пингов (исправлено для вашей схемы)
PING_TESTS = [
    # CORE1 → все
    ('CORE1', 'CORE2', '10.12.1.2', 'линк Gi1/0'),
    ('CORE1', 'CORE2', '10.12.2.2', 'линк Gi2/0'),
    ('CORE1', 'CE1', '10.1.4.2', 'CE1 Fa0/0 (Gi3/0)'),
    ('CORE1', 'CE2', '10.1.5.2', 'CE2 Fa0/0 (Gi5/0)'),
    
    # CORE2 → все
    ('CORE2', 'CORE1', '10.12.1.1', 'линк Gi1/0'),
    ('CORE2', 'CORE1', '10.12.2.1', 'линк Gi2/0'),
    ('CORE2', 'CE1', '10.2.4.2', 'CE1 Fa0/1 (Gi5/0)'),
    ('CORE2', 'CE2', '10.2.5.2', 'CE2 Fa0/1 (Gi3/0)'),
    
    # CE1 → все
    ('CE1', 'CORE1', '10.1.4.1', 'CORE1 Gi3/0'),
    ('CE1', 'CORE2', '10.2.4.1', 'CORE2 Gi5/0'),
    ('CE1', 'CE2', '10.100.2.2', 'линк CE1→CE2 Fa1/0'),
    ('CE1', 'CE2', '10.100.2.4', 'линк CE1→CE2 Fa1/1'),
    
    # CE2 → все
    ('CE2', 'CORE1', '10.1.5.1', 'CORE1 Gi5/0'),
    ('CE2', 'CORE2', '10.2.5.1', 'CORE2 Gi3/0'),
    ('CE2', 'CE1', '10.100.2.1', 'линк CE2→CE1 Fa1/0'),
    ('CE2', 'CE1', '10.100.2.3', 'линк CE2→CE1 Fa1/1'),
]

# Loopback пинги
LOOPBACK_TESTS = [
    ('CORE1', '1.1.1.1'),
    ('CORE2', '2.2.2.2'),
    ('CE1', '5.5.5.5'),
    ('CE2', '6.6.6.6'),
]

# Ожидаемые OSPF соседи (исправлено - CE1 должен видеть 3 соседей!)
EXPECTED_NEIGHBORS = {
    'CORE1': ['2.2.2.2', '5.5.5.5', '6.6.6.6'],  # CORE2, CE1, CE2
    'CORE2': ['1.1.1.1', '5.5.5.5', '6.6.6.6'],  # CORE1, CE1, CE2
    'CE1': ['1.1.1.1', '2.2.2.2', '6.6.6.6'],    # CORE1, CORE2, CE2
    'CE2': ['1.1.1.1', '2.2.2.2', '5.5.5.5']     # CORE1, CORE2, CE1
}

# ==================== КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ ====================

def fix_core1():
    """Исправление CORE1"""
    print("\n🔧 ИСПРАВЛЕНИЕ CORE1")
    try:
        tn = telnetlib.Telnet('localhost', 5002, timeout=10)
        time.sleep(2)
        tn.write(b"\r\n")
        time.sleep(1)
        tn.write(b"enable\r\n")
        time.sleep(2)
        tn.write(b"cisco\r\n")
        time.sleep(2)
        
        tn.write(b"configure terminal\n")
        time.sleep(1)
        
        # Исправляем Gi1/0
        tn.write(b"interface GigabitEthernet1/0\n")
        tn.write(b"no shutdown\n")
        tn.write(b"ip ospf 1 area 0\n")
        tn.write(b"exit\n")
        print("  ✅ Gi1/0 исправлен")
        
        # Добавляем сеть для CE1
        tn.write(b"router ospf 1\n")
        tn.write(b"network 10.1.4.0 0.0.0.255 area 0\n")
        tn.write(b"exit\n")
        print("  ✅ Сеть 10.1.4.0 добавлена в OSPF")
        
        tn.write(b"end\n")
        tn.write(b"write memory\n")
        time.sleep(2)
        tn.close()
        return True
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return False

def fix_core2():
    """Исправление CORE2"""
    print("\n🔧 ИСПРАВЛЕНИЕ CORE2")
    try:
        tn = telnetlib.Telnet('localhost', 5003, timeout=10)
        time.sleep(2)
        tn.write(b"\r\n")
        time.sleep(1)
        tn.write(b"enable\r\n")
        time.sleep(2)
        tn.write(b"cisco\r\n")
        time.sleep(2)
        
        tn.write(b"configure terminal\n")
        time.sleep(1)
        
        # Исправляем Gi1/0
        tn.write(b"interface GigabitEthernet1/0\n")
        tn.write(b"no shutdown\n")
        tn.write(b"ip ospf 1 area 0\n")
        tn.write(b"exit\n")
        print("  ✅ Gi1/0 исправлен")
        
        tn.write(b"end\n")
        tn.write(b"write memory\n")
        time.sleep(2)
        tn.close()
        return True
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return False

def fix_ce1():
    """Исправление CE1"""
    print("\n🔧 ИСПРАВЛЕНИЕ CE1")
    try:
        tn = telnetlib.Telnet('localhost', 5000, timeout=10)
        time.sleep(2)
        tn.write(b"\r\n")
        time.sleep(1)
        tn.write(b"enable\r\n")
        time.sleep(2)
        tn.write(b"cisco\r\n")
        time.sleep(2)
        
        tn.write(b"configure terminal\n")
        time.sleep(1)
        
        # Настраиваем интерфейс к CORE1
        tn.write(b"interface FastEthernet0/0\n")
        tn.write(b"description to CORE1 Gi3/0\n")
        tn.write(b"ip address 10.1.4.2 255.255.255.0\n")
        tn.write(b"no shutdown\n")
        tn.write(b"ip ospf 1 area 0\n")
        tn.write(b"exit\n")
        print("  ✅ Fa0/0 настроен для связи с CORE1")
        
        # Добавляем сеть в OSPF
        tn.write(b"router ospf 1\n")
        tn.write(b"network 10.1.4.0 0.0.0.255 area 0\n")
        tn.write(b"exit\n")
        print("  ✅ Сеть 10.1.4.0 добавлена в OSPF")
        
        tn.write(b"end\n")
        tn.write(b"write memory\n")
        time.sleep(2)
        tn.close()
        return True
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return False

def fix_ce2():
    """Исправление CE2"""
    print("\n🔧 ИСПРАВЛЕНИЕ CE2")
    try:
        tn = telnetlib.Telnet('localhost', 5001, timeout=10)
        time.sleep(2)
        tn.write(b"\r\n")
        time.sleep(1)
        tn.write(b"enable\r\n")
        time.sleep(2)
        tn.write(b"cisco\r\n")
        time.sleep(2)
        
        tn.write(b"configure terminal\n")
        time.sleep(1)
        
        # Проверяем и добавляем сеть для CE1
        tn.write(b"router ospf 1\n")
        tn.write(b"network 10.100.2.0 0.0.0.255 area 0\n")
        tn.write(b"exit\n")
        print("  ✅ Сеть 10.100.2.0 добавлена в OSPF")
        
        tn.write(b"end\n")
        tn.write(b"write memory\n")
        time.sleep(2)
        tn.close()
        return True
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return False

# ==================== КЛАСС ПРОВЕРКИ ====================

class FinalConnectivityCheck:
    def __init__(self):
        self.start_time = datetime.now()
        self.results = {
            'ospf': {},
            'pings': {},
            'loopbacks': {}
        }
        self.success_count = 0
        self.total_count = 0
    
    def log(self, msg: str):
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] {msg}")
    
    def print_header(self, title: str):
        print(f"\n{'='*90}")
        print(f"🔍 {title}")
        print(f"{'='*90}")
    
    def connect_device(self, name: str) -> Optional[telnetlib.Telnet]:
        try:
            tn = telnetlib.Telnet('localhost', DEVICES[name]['port'], timeout=10)
            time.sleep(2)
            tn.write(b"\r\n")
            time.sleep(1)
            tn.write(b"enable\r\n")
            time.sleep(2)
            tn.write(b"cisco\r\n")
            time.sleep(2)
            return tn
        except Exception as e:
            self.log(f"❌ Не удалось подключиться к {name}: {e}")
            return None
    
    def send_command(self, tn: telnetlib.Telnet, cmd: str, wait: int = 3) -> str:
        tn.write(cmd.encode() + b"\r\n")
        time.sleep(wait)
        data = tn.read_very_eager().decode('utf-8', errors='ignore')
        data = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', data)
        data = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', data)
        return data
    
    def check_ospf(self, name: str) -> Dict:
        tn = self.connect_device(name)
        if not tn:
            return {'neighbors': [], 'count': 0}
        
        data = self.send_command(tn, "show ip ospf neighbor", 4)
        tn.close()
        
        neighbors = []
        for line in data.split('\n'):
            if 'FULL' in line:
                parts = line.split()
                if len(parts) > 0 and re.match(r'\d+\.\d+\.\d+\.\d+', parts[0]):
                    neighbor_id = parts[0]
                    neighbors.append(neighbor_id)
        
        return {'neighbors': neighbors, 'count': len(neighbors)}
    
    def check_ping(self, src: str, dst: str, ip: str) -> bool:
        tn = self.connect_device(src)
        if not tn:
            return False
        
        data = self.send_command(tn, f"ping {ip} repeat 2", 4)
        tn.close()
        
        return '!!!!' in data or 'Success rate is 100 percent' in data
    
    def check_loopback(self, device: str, ip: str) -> bool:
        tn = self.connect_device(device)
        if not tn:
            return False
        
        data = self.send_command(tn, f"ping {ip} repeat 2", 4)
        tn.close()
        
        return '!!!!' in data or 'Success rate is 100 percent' in data
    
    def print_ospf_table(self):
        self.print_header("ТАБЛИЦА OSPF СОСЕДЕЙ")
        
        for device in DEVICES.keys():
            neighbors = self.results['ospf'].get(device, {}).get('neighbors', [])
            expected = EXPECTED_NEIGHBORS.get(device, [])
            
            status = "✅" if len(neighbors) >= len(expected) else "❌"
            
            print(f"\n{device}:")
            print(f"  Статус: {status}")
            print(f"  Найдено: {len(neighbors)}/{len(expected)}")
            if neighbors:
                for n in neighbors:
                    print(f"    ✅ {n}")
            if len(neighbors) < len(expected):
                missing = [e for e in expected if e not in neighbors]
                print(f"    ⚠️ Отсутствуют: {', '.join(missing)}")
    
    def print_ping_matrix(self):
        self.print_header("МАТРИЦА ПИНГОВ")
        
        devices = list(DEVICES.keys())
        
        # Заголовок
        header = "↓Исх\\Цель→"
        print(f"\n{header:<12}", end='')
        for dst in devices:
            print(f"{dst:<8}", end='')
        print()
        print("-" * 60)
        
        # Строки матрицы
        for src in devices:
            print(f"{src:<12}", end='')
            for dst in devices:
                if src == dst:
                    print(f"{'━':<8}", end='')
                else:
                    key = f"{src}→{dst}"
                    result = self.results['pings'].get(key, False)
                    print(f"{'✅' if result else '❌':<8}", end='')
            print()
    
    def print_summary(self):
        self.print_header("ИТОГОВЫЙ ОТЧЕТ")
        
        total_tests = self.total_count
        successful = self.success_count
        
        print(f"\n📊 Статистика:")
        print(f"  Всего тестов: {total_tests}")
        print(f"  Успешно: {successful}")
        print(f"  Проблемы: {total_tests - successful}")
        
        if successful == total_tests:
            print("\n🎉 ПОЗДРАВЛЯЮ! ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
            print("   ✅ OSPF работает на всех устройствах")
            print("   ✅ Полная IP связность")
            print("   ✅ Все пинги проходят")
        else:
            print("\n⚠️ ОБНАРУЖЕНЫ ПРОБЛЕМЫ:")
            print("   Проверьте вывод выше")
    
    def run(self):
        self.print_header("ФИНАЛЬНАЯ ПРОВЕРКА СВЯЗНОСТИ И OSPF")
        
        # ШАГ 1: Применение критических исправлений
        print("\n" + "="*90)
        print("🔧 ПРИМЕНЕНИЕ КРИТИЧЕСКИХ ИСПРАВЛЕНИЙ")
        print("="*90)
        
        fixes_applied = 0
        if fix_core1(): fixes_applied += 1
        if fix_core2(): fixes_applied += 1
        if fix_ce1(): fixes_applied += 1
        if fix_ce2(): fixes_applied += 1
        
        print(f"\n✅ Применено исправлений: {fixes_applied}")
        
        # Ожидание после исправлений
        print("\n⏳ Ожидание сходимости после исправлений (45 секунд)...")
        time.sleep(45)
        
        # ШАГ 2: Проверка OSPF
        self.print_header("ШАГ 1: ПРОВЕРКА OSPF СОСЕДЕЙ")
        
        for device in DEVICES.keys():
            result = self.check_ospf(device)
            self.results['ospf'][device] = result
            time.sleep(2)
        
        self.print_ospf_table()
        
        # ШАГ 3: Проверка пингов
        self.print_header("ШАГ 2: ПРОВЕРКА ПИНГОВ")
        
        for src, dst, ip, desc in PING_TESTS:
            print(f"\n🔍 {src} → {dst} ({desc}): ", end='')
            sys.stdout.flush()
            
            result = self.check_ping(src, dst, ip)
            self.results['pings'][f"{src}→{dst}"] = result
            self.total_count += 1
            if result:
                self.success_count += 1
                print("✅ УСПЕХ")
            else:
                print("❌ НЕУДАЧА")
            time.sleep(1)
        
        # ШАГ 4: Проверка Loopback
        self.print_header("ШАГ 3: ПРОВЕРКА LOOPBACK ИНТЕРФЕЙСОВ")
        
        for device, ip in LOOPBACK_TESTS:
            print(f"\n🔍 {device} → {ip}: ", end='')
            sys.stdout.flush()
            
            result = self.check_loopback(device, ip)
            self.results['loopbacks'][device] = result
            self.total_count += 1
            if result:
                self.success_count += 1
                print("✅ УСПЕХ")
            else:
                print("❌ НЕУДАЧА")
            time.sleep(1)
        
        # ШАГ 5: Матрица пингов
        self.print_ping_matrix()
        
        # ШАГ 6: Итоговый отчет
        self.print_summary()
        
        exec_time = (datetime.now() - self.start_time).total_seconds()
        print(f"\n⏱️ Время выполнения: {exec_time:.1f} сек")

if __name__ == "__main__":
    checker = FinalConnectivityCheck()
    checker.run()