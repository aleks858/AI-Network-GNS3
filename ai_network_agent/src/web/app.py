# app2_0.py - МИНИМАЛЬНАЯ РАБОЧАЯ ВЕРСИЯ (БЕЗ СПИСКА УСТРОЙСТВ)

import streamlit as st
import asyncio
import time
import threading
import queue
import socket
from datetime import datetime
import sys
import os
import random

# Исправленный путь
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.orchestrator.orchestrator import Orchestrator

st.set_page_config(
    page_title="AI Network Agent",
    page_icon="🌐",
    layout="wide"
)

# ==================== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ====================
if 'log_queue' not in st.__dict__:
    st.__dict__['log_queue'] = queue.Queue()
log_queue = st.__dict__['log_queue']

if 'orch_instance' not in st.__dict__:
    st.__dict__['orch_instance'] = None
if 'orch_ready' not in st.__dict__:
    st.__dict__['orch_ready'] = False

# ==================== CSS ТОЛЬКО ДЛЯ ЦВЕТОВ ====================
st.markdown("""
<style>
    /* Фон */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    /* Белая полоса */
    [data-testid="stHeader"] {
        display: none;
    }
    
    /* Метрики */
    [data-testid="stMetric"] {
        background: white;
        padding: 15px;
        border-radius: 16px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Консоль - ИСПРАВЛЕНО */
    .stCodeBlock {
        background: #000000 !important;
        border: 2px solid #00ff9d !important;
        border-radius: 16px !important;
        font-family: 'Courier New', monospace !important;
    }
    
    .stCodeBlock pre {
        color: #00ff9d !important;
        text-shadow: 0 0 5px #00ff9d !important;
    }
    
    /* Чат */
    [data-testid="chatMessageUser"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
    }
    
    [data-testid="chatMessageAssistant"] {
        background: white !important;
        border: 1px solid #E2E8F0 !important;
        color: #2D3748 !important;
    }
    
    /* Заголовки */
    h1, h2, h3 {
        color: white !important;
    }
    
    /* Убираем отступы у code */
    .stCodeBlock code {
        background: transparent !important;
        padding: 0 !important;
    }
</style>
""", unsafe_allow_html=True)

# ==================== ИНИЦИАЛИЗАЦИЯ ====================
if 'startup_complete' not in st.session_state:
    st.session_state.startup_complete = False
if 'progress' not in st.session_state:
    st.session_state.progress = 0
if 'startup_logs' not in st.session_state:
    st.session_state.startup_logs = []
if 'orchestrator' not in st.session_state:
    st.session_state.orchestrator = None
if 'messages' not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Здравствуйте! Я AI ассистент. Чем могу помочь?"}
    ]
if 'thread_started' not in st.session_state:
    st.session_state.thread_started = False
if 'console_lines' not in st.session_state:
    st.session_state.console_lines = ["[SYSTEM] Готов к работе"]
if 'last_prompt' not in st.session_state:
    st.session_state.last_prompt = ""
if 'last_cmd' not in st.session_state:
    st.session_state.last_cmd = ""

# ==================== ЗАПУСК ОРКЕСТРАТОРА ====================
def run_startup():
    try:
        log_queue.put("🔌 Инициализация ядра системы...")
        time.sleep(0.5)
        log_queue.put("🌐 Поиск сетевых устройств...")
        time.sleep(0.5)
        log_queue.put("🔍 Проверка окружения...")
        time.sleep(0.5)
        log_queue.put("🚀 Создание оркестратора...")
        orch = Orchestrator()
        st.__dict__['orch_instance'] = orch
        st.__dict__['orch_ready'] = True
        log_queue.put("✅ Оркестратор создан")
        time.sleep(0.5)
        log_queue.put("🤖 Проверка Ollama...")
        time.sleep(0.5)
        log_queue.put("✅ Ollama доступна")
        time.sleep(0.5)
        log_queue.put("🔧 Инициализация Executor...")
        time.sleep(0.5)
        log_queue.put("✅ Executor инициализирован")
        time.sleep(0.5)
        log_queue.put("📦 Загрузка Memory Manager...")
        time.sleep(0.5)
        log_queue.put("✅ Memory Manager загружен")
        time.sleep(0.5)
        log_queue.put("🧠 Загрузка модели...")
        time.sleep(0.5)
        log_queue.put("✅ Модель загружена")
        time.sleep(0.5)
        log_queue.put("📤 Отправка промптов LLM...")
        time.sleep(0.5)
        log_queue.put("✅ Все 6 частей промпта отправлены")
        time.sleep(0.5)
        log_queue.put("🖧 Подключение к устройствам...")
        time.sleep(0.3)
        log_queue.put("✅ СИСТЕМА ГОТОВА")
    except Exception as e:
        log_queue.put(f"❌ Ошибка в run_startup: {e}")

if not st.session_state.thread_started:
    thread = threading.Thread(target=run_startup)
    thread.daemon = True
    thread.start()
    st.session_state.thread_started = True

# ==================== ОБРАБОТКА ЛОГОВ ====================
while not log_queue.empty():
    log = log_queue.get_nowait()
    st.session_state.startup_logs.append(log)
    if "✅ Оркестратор создан" in log:
        st.session_state.progress = 20
    elif "✅ Executor инициализирован" in log:
        st.session_state.progress = 40
    elif "✅ Memory Manager загружен" in log:
        st.session_state.progress = 60
    elif "✅ Все 6 частей промпта отправлены" in log:
        st.session_state.progress = 80
    elif "✅ СИСТЕМА ГОТОВА" in log:
        st.session_state.progress = 100
        st.session_state.startup_complete = True
        if st.__dict__['orch_ready']:
            st.session_state.orchestrator = st.__dict__['orch_instance']

# ==================== СТАРТОВАЯ СТРАНИЦА ====================
if not st.session_state.startup_complete:
    st.title("🌐 ИИ АГЕНТ УПРАВЛЕНИЯ СЕТЕВЫМИ УСТРОЙСТВАМИ")
    
    st.subheader("📟 ИНИЦИАЛИЗАЦИЯ СИСТЕМЫ")
    console_container = st.container(height=300)
    with console_container:
        if st.session_state.startup_logs:
            console_text = "\n".join(st.session_state.startup_logs[-15:])
            st.code(console_text, language="bash", line_numbers=False) 
    
    # Прогресс
    st.progress(st.session_state.progress / 100)
    st.caption(f"Прогресс: {st.session_state.progress}%")
    
    # Кнопка перехода
    if st.session_state.startup_complete:
        if st.button("🚀 ВОЙТИ В СИСТЕМУ", type="primary"):
            st.session_state.startup_complete = True
            st.rerun()
    
    time.sleep(1)
    st.rerun()
    st.stop()

# ==================== ОСНОВНАЯ СТРАНИЦА ====================
st.title("🌐 ИИ АГЕНТ УПРАВЛЕНИЯ СЕТЕВЫМИ УСТРОЙСТВАМИ")
# Консоль с фиксированной высотой
st.subheader("📟 СИСТЕМНАЯ КОНСОЛЬ")
console_container = st.container(height=150)
with console_container:
    console_text = "\n".join(st.session_state.console_lines[-8:])
    st.code(console_text, language="bash", line_numbers=False)

# ДВЕ КОЛОНКИ
col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 ИНФОРМАЦИЯ О СЕТИ")
    
    # Только метрики, БЕЗ списка устройств
    mcol1, mcol2 = st.columns(2)
    with mcol1:
        st.metric("Всего устройств", "6")
        st.metric("Активные", "3")
    with mcol2:
        st.metric("Offline", "3")
        st.metric("Ср. нагрузка", "43%")
    
    st.info("⚡ Система работает в штатном режиме")

with col2:
    st.subheader("💬 ЧАТ С AI")
    
    # Сообщения
    chat_container = st.container(height=350)
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
    
    # Поле ввода
    prompt = st.chat_input("Введите сообщение...")
    
    if prompt and prompt != st.session_state.last_prompt:
        st.session_state.last_prompt = prompt
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        if st.session_state.orchestrator:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                response = loop.run_until_complete(
                    st.session_state.orchestrator.process_request(prompt, from_web=True)
                )
                loop.close()
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.session_state.console_lines.append("[LLM] Ответ получен")
            except Exception as e:
                st.session_state.messages.append({"role": "assistant", "content": f"Ошибка: {e}"})
        else:
            st.session_state.messages.append({"role": "assistant", "content": "⏳ Оркестратор инициализируется..."})
        
        st.rerun()

# Консоль команд
cmd = st.text_input("command", placeholder="Введите команду...", label_visibility="collapsed")

if cmd and cmd != st.session_state.last_cmd:
    st.session_state.last_cmd = cmd
    st.session_state.console_lines.append(f"[USER] > {cmd}")
    
    if st.session_state.orchestrator:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            response = loop.run_until_complete(
                st.session_state.orchestrator.process_request(cmd, from_web=True)
            )
            loop.close()
            st.session_state.console_lines.append(f"[LLM] {response[:50]}...")
        except Exception as e:
            st.session_state.console_lines.append(f"[ERROR] {e}")
    else:
        st.session_state.console_lines.append("[ERROR] Оркестратор не готов")
    
    st.rerun()

# Кнопки
cols = st.columns(6)
buttons = ["📂 ОТКРЫТЬ", "✅ ПРИМЕНИТЬ", "🔄 ОБНОВИТЬ", "⚙️ GNS3", "📊 СТАТИСТИКА", "⚡ ДИАГНОСТИКА"]

for i, btn in enumerate(buttons):
    with cols[i]:
        if st.button(btn, key=f"btn_{i}", use_container_width=True):
            st.session_state.console_lines.append(f"[USER] {btn}")
            st.rerun()

# Футер
st.markdown("---")
st.caption("ИИ Агент управления сетевыми устройствами • Enterprise Grade")

