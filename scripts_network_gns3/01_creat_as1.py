#!/usr/bin/env python3
"""
01_create_as1.py - ФИНАЛЬНАЯ ВЕРСИЯ
Полная автономная система AS1 (Офис) с идеально выровненными координатами
Версия: 6.0 - ИТОГОВАЯ
"""

import requests
import time
import sys
import os

GNS3_SERVER = "http://localhost:3080"
PROJECT_NAME = "AS1-FULL-NETWORK"
PROJECT_ID_FILE = "project_id.txt"

# КООРДИНАТЫ С ИДЕАЛЬНЫМ ВЫРАВНИВАНИЕМ
COORDS = {
    # Левое плечо (CORE чуть левее для оптического выравнивания)
    "FW/CE1": {"x": 200, "y": 100},
    "CORE1":  {"x": 180, "y": 300},  # на 20 левее
    "AGG1":   {"x": 200, "y": 500},
    
    # Правое плечо
    "FW/CE2": {"x": 600, "y": 100},
    "CORE2":  {"x": 580, "y": 300},  # на 20 левее
    "AGG2":   {"x": 600, "y": 500},
    
    # Коммутаторы доступа (равномерно)
    "ACC1": {"x": 100, "y": 700},
    "ACC2": {"x": 300, "y": 700},
    "ACC3": {"x": 500, "y": 700},
    "ACC4": {"x": 700, "y": 700},
    "ACC5": {"x": 900, "y": 700},
    
    # Хосты (под своими ACC)
    "PC1":  {"x": 75,  "y": 850},
    "PC2":  {"x": 125, "y": 850},
    "PC3":  {"x": 275, "y": 850},
    "PC4":  {"x": 325, "y": 850},
    "PC5":  {"x": 475, "y": 850},
    "PC6":  {"x": 525, "y": 850},
    "PC7":  {"x": 675, "y": 850},
    "PC8":  {"x": 725, "y": 850},
    "PC9":  {"x": 875, "y": 850},
    "PC10": {"x": 925, "y": 850}
}

IMAGES = {
    "c7200": "/home/aleksandr/GNS3/images/IOS/7200/c7200-p-mz.123-19.bin",
    "c3745": "/home/aleksandr/GNS3/images/IOS/3745/c3745-adventerprisek9-mz.124-25.bin",
    "c3725": "/home/aleksandr/GNS3/images/IOS/3725/c3725-adventerprisek9-mz124-15.bin"
}

SYMBOLS = {
    "c7200": ":/symbols/router.svg",
    "c3745": ":/symbols/multilayer_switch.svg",
    "c3725": ":/symbols/ethernet_switch.svg"
}

def log(msg): print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def check_server():
    log("🔌 Проверка GNS3 сервера...")
    try:
        r = requests.get(f"{GNS3_SERVER}/v2/version", timeout=5)
        if r.status_code == 200:
            log(f"✅ Сервер доступен (версия {r.json().get('version')})")
            return True
    except Exception as e:
        log(f"❌ Ошибка: {e}")
    return False

def delete_old():
    log(f"\n📁 Удаляю старый проект {PROJECT_NAME}...")
    try:
        r = requests.get(f"{GNS3_SERVER}/v2/projects")
        for proj in r.json():
            if proj['name'] == PROJECT_NAME:
                requests.delete(f"{GNS3_SERVER}/v2/projects/{proj['project_id']}")
                time.sleep(2)
                log("✅ Старый проект удален")
                return
    except Exception as e:
        log(f"⚠️ Ошибка: {e}")

def create_project():
    log(f"\n📁 Создаю проект {PROJECT_NAME}...")
    r = requests.post(f"{GNS3_SERVER}/v2/projects", json={"name": PROJECT_NAME})
    if r.status_code == 201:
        pid = r.json()['project_id']
        requests.post(f"{GNS3_SERVER}/v2/projects/{pid}/open")
        log(f"✅ Проект создан. ID: {pid}")
        return pid
    else:
        log(f"❌ Ошибка: {r.status_code}")
        sys.exit(1)

def create_c7200(pid, name, x, y, symbol):
    print(f"    ➕ {name} (c7200)...", end=" ", flush=True)
    properties = {
        "platform": "c7200",
        "image": IMAGES["c7200"],
        "ram": 512,
        "slot0": "PA-GE",
        "slot1": "PA-GE",
        "slot2": "PA-GE",
        "slot3": "PA-GE",
        "slot4": "PA-GE",
        "slot5": "PA-GE"
    }
    payload = {
        "name": name,
        "node_type": "dynamips",
        "compute_id": "local",
        "x": x,
        "y": y,
        "properties": properties,
        "symbol": symbol
    }
    try:
        r = requests.post(f"{GNS3_SERVER}/v2/projects/{pid}/nodes", json=payload, timeout=10)
        if r.status_code == 201:
            node_id = r.json()['node_id']
            print(f"✅ создан (ID: {node_id[:8]}...)")
            return node_id
        else:
            print(f"❌ ошибка {r.status_code}")
            return None
    except Exception as e:
        print(f"❌ исключение: {e}")
        return None

def create_c3745(pid, name, x, y, symbol):
    print(f"    ➕ {name} (c3745)...", end=" ", flush=True)
    properties = {
        "platform": "c3745",
        "image": IMAGES["c3745"],
        "ram": 256,
        "slot1": "NM-16ESW",
        "slot2": "NM-16ESW"
    }
    payload = {
        "name": name,
        "node_type": "dynamips",
        "compute_id": "local",
        "x": x,
        "y": y,
        "properties": properties,
        "symbol": symbol
    }
    try:
        r = requests.post(f"{GNS3_SERVER}/v2/projects/{pid}/nodes", json=payload, timeout=10)
        if r.status_code == 201:
            node_id = r.json()['node_id']
            print(f"✅ создан (ID: {node_id[:8]}...)")
            return node_id
        else:
            print(f"❌ ошибка {r.status_code}")
            return None
    except Exception as e:
        print(f"❌ исключение: {e}")
        return None

def create_c3725(pid, name, x, y, symbol):
    print(f"    ➕ {name} (c3725 EtherSwitch)...", end=" ", flush=True)
    properties = {
        "platform": "c3725",
        "image": IMAGES["c3725"],
        "ram": 128,
        "slot1": "NM-16ESW"
    }
    payload = {
        "name": name,
        "node_type": "dynamips",
        "compute_id": "local",
        "x": x,
        "y": y,
        "properties": properties,
        "symbol": symbol
    }
    try:
        r = requests.post(f"{GNS3_SERVER}/v2/projects/{pid}/nodes", json=payload, timeout=10)
        if r.status_code == 201:
            node_id = r.json()['node_id']
            print(f"✅ создан (ID: {node_id[:8]}...)")
            return node_id
        else:
            print(f"❌ ошибка {r.status_code}")
            return None
    except Exception as e:
        print(f"❌ исключение: {e}")
        return None

def create_host(pid, name, x, y):
    print(f"    ➕ {name}...", end=" ", flush=True)
    payload = {
        "name": name,
        "node_type": "vpcs",
        "compute_id": "local",
        "x": x,
        "y": y
    }
    try:
        r = requests.post(f"{GNS3_SERVER}/v2/projects/{pid}/nodes", json=payload, timeout=5)
        if r.status_code == 201:
            node_id = r.json()['node_id']
            print(f"✅ создан")
            return node_id
        else:
            print(f"❌ ошибка {r.status_code}")
            return None
    except Exception as e:
        print(f"❌ исключение: {e}")
        return None

def create_link(pid, src_id, src_adap, src_port, dst_id, dst_adap, dst_port, desc):
    payload = {
        "nodes": [
            {"node_id": src_id, "adapter_number": src_adap, "port_number": src_port},
            {"node_id": dst_id, "adapter_number": dst_adap, "port_number": dst_port}
        ]
    }
    try:
        r = requests.post(f"{GNS3_SERVER}/v2/projects/{pid}/links", json=payload, timeout=5)
        if r.status_code == 201:
            print(f"      ✅ {desc}")
            return True
        else:
            print(f"      ❌ {desc} (код {r.status_code})")
            return False
    except Exception as e:
        print(f"      ❌ {desc} (ошибка: {e})")
        return False

def main():
    print("\n" + "="*90)
    print("🏗️  СОЗДАНИЕ AS1 (ИДЕАЛЬНОЕ ВЫРАВНИВАНИЕ)")
    print("="*90)
    
    if not check_server():
        sys.exit(1)
    
    delete_old()
    pid = create_project()
    node_ids = {}

    # === СОЗДАНИЕ УСТРОЙСТВ ===
    print("\n📌 Пограничные маршрутизаторы (FW/CE):")
    node_ids["FW/CE1"] = create_c3745(pid, "FW/CE1", COORDS["FW/CE1"]["x"], COORDS["FW/CE1"]["y"], SYMBOLS["c3745"])
    node_ids["FW/CE2"] = create_c3745(pid, "FW/CE2", COORDS["FW/CE2"]["x"], COORDS["FW/CE2"]["y"], SYMBOLS["c3745"])
    time.sleep(0.5)

    print("\n📌 Ядро (CORE):")
    node_ids["CORE1"] = create_c7200(pid, "CORE1", COORDS["CORE1"]["x"], COORDS["CORE1"]["y"], SYMBOLS["c7200"])
    node_ids["CORE2"] = create_c7200(pid, "CORE2", COORDS["CORE2"]["x"], COORDS["CORE2"]["y"], SYMBOLS["c7200"])
    time.sleep(0.5)

    print("\n📌 Агрегация (AGG):")
    node_ids["AGG1"] = create_c3745(pid, "AGG1", COORDS["AGG1"]["x"], COORDS["AGG1"]["y"], SYMBOLS["c3745"])
    node_ids["AGG2"] = create_c3745(pid, "AGG2", COORDS["AGG2"]["x"], COORDS["AGG2"]["y"], SYMBOLS["c3745"])
    time.sleep(0.5)

    print("\n📌 Коммутаторы доступа (ACC):")
    for i in range(1, 6):
        name = f"ACC{i}"
        node_ids[name] = create_c3725(pid, name, COORDS[name]["x"], COORDS[name]["y"], SYMBOLS["c3725"])
        time.sleep(0.3)

    print("\n📌 Хосты (PC):")
    for i in range(1, 11):
        name = f"PC{i}"
        node_ids[name] = create_host(pid, name, COORDS[name]["x"], COORDS[name]["y"])
        time.sleep(0.2)

    # Проверка
    expected = ['FW/CE1', 'FW/CE2', 'CORE1', 'CORE2', 'AGG1', 'AGG2', 
                'ACC1', 'ACC2', 'ACC3', 'ACC4', 'ACC5']
    if any(node_ids.get(d) is None for d in expected):
        print("\n❌ Ошибка создания устройств!")
        sys.exit(1)

    print(f"\n✅ Все {len(node_ids)} устройств созданы успешно!")

    # === СОЗДАНИЕ ЛИНКОВ ===
    print("\n🔗 Создание линков...")
    link_count = 0

    # CORE1 ↔ CORE2 (2 линка)
    print("\n  📍 CORE1 ↔ CORE2:")
    if create_link(pid, node_ids["CORE1"], 0, 0, node_ids["CORE2"], 0, 0, "Gi0/0 ↔ Gi0/0"): link_count += 1
    if create_link(pid, node_ids["CORE1"], 1, 0, node_ids["CORE2"], 1, 0, "Gi1/0 ↔ Gi1/0"): link_count += 1

    # CORE1 ↔ Левое плечо (AGG1, FW/CE1)
    print("\n  📍 CORE1 ↔ Левое плечо:")
    if create_link(pid, node_ids["CORE1"], 2, 0, node_ids["AGG1"], 0, 0, "Gi2/0 ↔ Fa0/0 (AGG1)"): link_count += 1
    if create_link(pid, node_ids["CORE1"], 3, 0, node_ids["FW/CE1"], 0, 0, "Gi3/0 ↔ Fa0/0 (FW/CE1)"): link_count += 1

    # CORE2 ↔ Правое плечо (AGG2, FW/CE2)
    print("\n  📍 CORE2 ↔ Правое плечо:")
    if create_link(pid, node_ids["CORE2"], 2, 0, node_ids["AGG2"], 0, 0, "Gi2/0 ↔ Fa0/0 (AGG2)"): link_count += 1
    if create_link(pid, node_ids["CORE2"], 3, 0, node_ids["FW/CE2"], 0, 0, "Gi3/0 ↔ Fa0/0 (FW/CE2)"): link_count += 1

    # Перекрёстные связи
    print("\n  📍 Перекрёстные связи:")
    if create_link(pid, node_ids["CORE1"], 4, 0, node_ids["AGG2"], 0, 1, "Gi4/0 ↔ Fa0/1 (AGG2)"): link_count += 1
    if create_link(pid, node_ids["CORE1"], 5, 0, node_ids["FW/CE2"], 0, 1, "Gi5/0 ↔ Fa0/1 (FW/CE2)"): link_count += 1
    if create_link(pid, node_ids["CORE2"], 4, 0, node_ids["AGG1"], 0, 1, "Gi4/0 ↔ Fa0/1 (AGG1)"): link_count += 1
    if create_link(pid, node_ids["CORE2"], 5, 0, node_ids["FW/CE1"], 0, 1, "Gi5/0 ↔ Fa0/1 (FW/CE1)"): link_count += 1

    # AGG ↔ ACC (10 линков)
    print("\n  📍 AGG ↔ ACC:")
    for i, acc in enumerate(["ACC1", "ACC2", "ACC3", "ACC4", "ACC5"]):
        if create_link(pid, node_ids["AGG1"], 1, i, node_ids[acc], 0, 0, f"Fa1/{i} ↔ Fa0/0 ({acc})"): link_count += 1
        if create_link(pid, node_ids["AGG2"], 1, i, node_ids[acc], 0, 1, f"Fa1/{i} ↔ Fa0/1 ({acc})"): link_count += 1

    # ACC ↔ Хосты (10 линков)
    print("\n  📍 ACC ↔ Хосты:")
    host_links = [
        ("ACC1", 1, 0, "PC1"), ("ACC1", 1, 1, "PC2"),
        ("ACC2", 1, 0, "PC3"), ("ACC2", 1, 1, "PC4"),
        ("ACC3", 1, 0, "PC5"), ("ACC3", 1, 1, "PC6"),
        ("ACC4", 1, 0, "PC7"), ("ACC4", 1, 1, "PC8"),
        ("ACC5", 1, 0, "PC9"), ("ACC5", 1, 1, "PC10")
    ]
    for acc, adap, port, host in host_links:
        if create_link(pid, node_ids[acc], adap, port, node_ids[host], 0, 0, f"{acc}:Fa{adap}/{port} ↔ {host}"): link_count += 1

    # Прямые связи между AGG и между FW/CE
    print("\n  📍 Прямые связи:")
    if create_link(pid, node_ids["AGG1"], 1, 5, node_ids["AGG2"], 1, 5, "AGG1:Fa1/5 ↔ AGG2:Fa1/5"): link_count += 1
    if create_link(pid, node_ids["AGG1"], 1, 6, node_ids["AGG2"], 1, 6, "AGG1:Fa1/6 ↔ AGG2:Fa1/6"): link_count += 1
    if create_link(pid, node_ids["FW/CE1"], 1, 0, node_ids["FW/CE2"], 1, 0, "FW/CE1:Fa1/0 ↔ FW/CE2:Fa1/0"): link_count += 1
    if create_link(pid, node_ids["FW/CE1"], 1, 1, node_ids["FW/CE2"], 1, 1, "FW/CE1:Fa1/1 ↔ FW/CE2:Fa1/1"): link_count += 1

    print(f"\n✅ Всего создано линков: {link_count}")

    with open(PROJECT_ID_FILE, "w") as f:
        f.write(pid)
    log(f"📝 ID проекта сохранен")

    print("\n" + "="*90)
    print("🎉 ПРОЕКТ AS1 УСПЕШНО СОЗДАН!")
    print("="*90)
    print(f"\n👉 Открой в GNS3 проект: {PROJECT_NAME}")
    print("\n   Визуальная структура:")
    print("   • Левое плечо: FW/CE1 (200,100) - CORE1 (180,300) - AGG1 (200,500)")
    print("   • Правое плечо: FW/CE2 (600,100) - CORE2 (580,300) - AGG2 (600,500)")
    print("   • Коммутаторы доступа: ACC1-ACC5 (Y=700)")
    print("   • Хосты: PC1-PC10 (Y=850)")
    print("="*90)

if __name__ == "__main__":
    main()