# src/memory/manager.py
# Memory Manager - заведующий библиотекой знаний
# ВЕРСИЯ 2.0 - С ПОДДЕРЖКОЙ learn_from_log

import os
import json
import hashlib
import shutil
import gc
from datetime import datetime
from typing import List, Dict, Any, Optional
import re

# Используем LangChain для корректной разбивки
try:
    from langchain_community.text_splitter import RecursiveCharacterTextSplitter
except ImportError:
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
    except ImportError:
        # Резервный чанкер (на случай отсутствия LangChain)
        class RecursiveCharacterTextSplitter:
            def __init__(self, chunk_size=200, chunk_overlap=20, separators=None, length_function=len):
                self.chunk_size = chunk_size
                self.chunk_overlap = chunk_overlap
                self.separators = separators or ["\n\n", "\n", ". ", " ", ""]
                self.length_function = length_function

            def split_text(self, text: str) -> List[str]:
                chunks = []
                start = 0
                while start < len(text):
                    end = min(start + self.chunk_size, len(text))
                    for sep in self.separators:
                        idx = text.rfind(sep, start, end)
                        if idx != -1:
                            end = idx + len(sep)
                            break
                    chunk = text[start:end].strip()
                    if chunk:
                        chunks.append(chunk)
                    start = end - self.chunk_overlap + 1
                    if start <= 0:
                        start = end
                    if len(chunks) % 10 == 0:
                        gc.collect()
                return chunks


# Остальные импорты
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
import pypdf
from docx import Document
import yaml


class MemoryManager:
    """
    ЗАВЕДУЮЩИЙ БИБЛИОТЕКОЙ ЗНАНИЙ
    - Отвечает за все знания агента
    - Управляет загрузкой, поиском, обучением
    - Сохраняет историю диалогов
    """

    def __init__(self, knowledge_base_path: str = "C:/ai_network_agent/knowledge_base"):
        """
        Инициализация Memory Manager
        """
        self.kb_path = knowledge_base_path

        # === Папки ===
        self.raw_chat = f"{self.kb_path}/raw/chat"
        self.raw_docs = f"{self.kb_path}/raw/docs"
        self.raw_errors = f"{self.kb_path}/raw/errors"
        self.raw_history = f"{self.kb_path}/raw/history"
        self.raw_scripts = f"{self.kb_path}/raw/scripts"
        self.processed_chunks = f"{self.kb_path}/processed/chunks"
        self.chromadb_path = f"{self.kb_path}/chromadb"
        self.processed_dir = f"{self.kb_path}/processed"

        self._init_directory_structure()

        # === Инструменты ===
        self.chunker = RecursiveCharacterTextSplitter(
            chunk_size=200,
            chunk_overlap=20,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len
        )

        print("⏳ Загрузка модели векторизации...")
        self.vectorizer = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        print("✅ Модель загружена")

        self.client = chromadb.PersistentClient(path=self.chromadb_path)
        self.collection = self.client.get_or_create_collection(name="knowledge_base")

        # === Статистика ===
        self.stats = {
            'total_files': 0,
            'total_chunks': 0,
            'total_vectors': 0,
            'last_updated': None
        }
        self._load_stats()

        print(f"✅ Memory Manager инициализирован")
        print(f"   Коллекция: {self.collection.count()} чанков")

    def _init_directory_structure(self):
        """Создаёт структуру папок"""
        for dir_path in [
            self.raw_chat, self.raw_docs, self.raw_errors,
            self.raw_history, self.raw_scripts, self.processed_chunks,
            self.chromadb_path, self.processed_dir
        ]:
            os.makedirs(dir_path, exist_ok=True)

    def _sanitize_filename(self, filename: str) -> str:
        """Очищает имя файла от недопустимых символов"""
        return re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', filename)

    def _get_file_hash(self, file_path: str) -> str:
        """Вычисляет хеш файла"""
        h = hashlib.md5()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    def _file_already_exists(self, file_path: str) -> bool:
        """Проверяет, был ли уже добавлен файл"""
        hash_log = os.path.join(self.processed_dir, "file_hashes.jsonl")
        if not os.path.exists(hash_log):
            return False
        file_hash = self._get_file_hash(file_path)
        with open(hash_log, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    if json.loads(line).get('hash') == file_hash:
                        return True
                except:
                    continue
        return False

    def _save_file_hash(self, file_path: str):
        """Сохраняет хеш файла в лог"""
        hash_log = os.path.join(self.processed_dir, "file_hashes.jsonl")
        record = {
            'filename': os.path.basename(file_path),
            'hash': self._get_file_hash(file_path),
            'added': datetime.now().isoformat()
        }
        with open(hash_log, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    def _encode_in_batches(self, texts: List[str], batch_size: int = 8) -> List[List[float]]:
        """Векторизует тексты пакетами"""
        vectors = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            batch_vectors = self.vectorizer.encode(batch, convert_to_numpy=False)
            vectors.extend([v.tolist() for v in batch_vectors])
            gc.collect()
        return vectors

    def add_file(self, file_path: str, category: str = "docs") -> Dict[str, Any]:
        """
        Добавляет файл в базу знаний
        """
        filename = os.path.basename(file_path)
        print(f"\n📥 Добавление файла: {filename}")

        if not os.path.exists(file_path):
            return {"error": "Файл не найден"}

        if self._file_already_exists(file_path):
            print("⚠️ Файл уже добавлен (дубликат)")
            return {"status": "skipped", "reason": "duplicate"}

        dest_path = self._copy_to_raw(file_path, category)
        text = self._extract_text(dest_path)
        if not text:
            return {"error": "Не удалось извлечь текст"}

        print("   📄 Разбивка на чанки...")
        chunks = self._split_text_safe(text)
        print(f"   📄 Создано {len(chunks)} чанков")

        if not chunks:
            return {"error": "Нет чанков"}

        metadatas = []
        ids = []
        for i, chunk in enumerate(chunks):
            chunk_id = hashlib.md5(f"{file_path}_{i}".encode()).hexdigest()[:16]
            ids.append(chunk_id)
            metadatas.append({
                'source': filename,
                'category': category,
                'chunk_index': i,
                'date_added': datetime.now().isoformat()
            })

        print("   🧮 Векторизация...")
        vectors = self._encode_in_batches(chunks, batch_size=10)

        self.collection.add(documents=chunks, embeddings=vectors, metadatas=metadatas, ids=ids)
        self._save_chunks_to_processed(chunks, metadatas, file_path)

        self.stats['total_files'] += 1
        self.stats['total_chunks'] += len(chunks)
        self.stats['total_vectors'] += len(vectors)
        self.stats['last_updated'] = datetime.now().isoformat()
        self._save_stats()
        self._save_file_hash(file_path)

        print(f"✅ Файл добавлен: {len(chunks)} чанков")
        gc.collect()

        return {'status': 'success', 'chunks': len(chunks), 'ids': ids}

    def _split_text_safe(self, text: str) -> List[str]:
        """Безопасная разбивка текста"""
        return self.chunker.split_text(text.strip())

    def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Поиск по базе знаний
        """
        print(f"\n🔍 Поиск: '{query}'")
        query_vector = self.vectorizer.encode([query]).tolist()
        results = self.collection.query(query_embeddings=query_vector, n_results=n_results)
        
        formatted = []
        if results['documents'] and results['documents'][0]:
            for i in range(len(results['documents'][0])):
                formatted.append({
                    'text': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                    'similarity': 1 - results['distances'][0][i] if results['distances'] else 0
                })
        print(f"   Найдено {len(formatted)} результатов")
        return formatted

    def _extract_text(self, file_path: str) -> str:
        """Извлекает текст из файла"""
        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext == '.pdf':
                text = ""
                with open(file_path, 'rb') as f:
                    pdf = pypdf.PdfReader(f)
                    for page in pdf.pages:
                        if content := page.extract_text():
                            text += content + "\n"
                return text.strip()

            elif ext in ['.docx', '.doc']:
                doc = Document(file_path)
                return '\n'.join([p.text for p in doc.paragraphs if p.text.strip()])

            elif ext in ['.txt', '.log', '.yaml', '.yml', '.json', '.md', '.py']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read().strip()

            else:
                print(f"   ⚠️ Неподдерживаемый формат: {ext}")
                return ""

        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            return ""

    def _copy_to_raw(self, file_path: str, category: str) -> str:
        """Копирует файл в raw-папку"""
        filename = self._sanitize_filename(os.path.basename(file_path))
        dest_dir = {
            "scripts": self.raw_scripts,
            "docs": self.raw_docs,
            "chat": self.raw_chat,
            "errors": self.raw_errors
        }.get(category, self.raw_history)
        
        counter = 1
        dest_path = os.path.join(dest_dir, filename)
        original_name, ext = os.path.splitext(filename)
        while os.path.exists(dest_path):
            dest_path = os.path.join(dest_dir, f"{original_name}_{counter}{ext}")
            counter += 1
        shutil.copy2(file_path, dest_path)
        return dest_path

    def _save_chunks_to_processed(self, chunks: List[str], metadatas: List[Dict], source_file: str):
        """Сохраняет чанки в processed-папку"""
        try:
            filename = self._sanitize_filename(os.path.basename(source_file).split('.')[0])
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = os.path.join(self.processed_chunks, f"{filename}_{timestamp}.jsonl")
            with open(out_path, 'w', encoding='utf-8') as f:
                for i, chunk in enumerate(chunks):
                    record = {'chunk_id': i, 'text': chunk, 'metadata': metadatas[i]}
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
            print(f"   💾 Чанки сохранены: {out_path}")
        except Exception as e:
            print(f"   ⚠️ Ошибка: {e}")

    def _save_stats(self):
        """Сохраняет статистику"""
        try:
            stats_path = os.path.join(self.processed_dir, "stats.json")
            with open(stats_path, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка: {e}")

    def _load_stats(self):
        """Загружает статистику"""
        try:
            stats_path = os.path.join(self.processed_dir, "stats.json")
            if os.path.exists(stats_path):
                with open(stats_path, 'r') as f:
                    self.stats = json.load(f)
        except Exception as e:
            print(f"⚠️ Ошибка: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику"""
        return {
            'total_files': self.stats['total_files'],
            'total_chunks': self.stats['total_chunks'],
            'chroma_count': self.collection.count(),
            'last_updated': self.stats['last_updated']
        }

    # ==================== НОВЫЙ МЕТОД ====================
    def learn_from_log(self, log_data: Dict, category: str = "history"):
        """
        Сохраняет историю диалога в базу знаний
        Вызывается оркестратором при синхронизации
        """
        try:
            messages = log_data.get('messages', [])
            if not messages:
                return

            # Сохраняем в raw/history/
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            history_file = os.path.join(self.raw_history, f"session_{timestamp}.jsonl")

            with open(history_file, 'w', encoding='utf-8') as f:
                for msg in messages:
                    f.write(json.dumps(msg, ensure_ascii=False) + '\n')

            # Обновляем статистику
            self.stats['total_files'] += 1
            self.stats['last_updated'] = datetime.now().isoformat()
            self._save_stats()

            print(f"💾 История сохранена: {len(messages)} сообщений в {history_file}")

        except Exception as e:
            print(f"⚠️ Ошибка при сохранении истории: {e}")

    def info(self) -> str:
        """Возвращает информацию о менеджере"""
        stats = self.get_stats()
        return f"""
📚 MemoryManager Info:
   База: {self.kb_path}
   Файлов: {stats['total_files']}
   Чанков: {stats['total_chunks']} (Chroma: {stats['chroma_count']})
   Последнее обновление: {stats['last_updated']}
        """.strip()


# ==================== ТЕСТ ====================

def test_memory():
    """Тестирует Memory Manager"""
    print("=" * 80)
    print("🧪 ТЕСТ MEMORY MANAGER".center(80))
    print("=" * 80)

    mm = MemoryManager()
    
    # Тест сохранения истории
    print("\n📌 ТЕСТ: learn_from_log")
    test_log = {
        'messages': [
            {'role': 'user', 'content': 'привет', 'timestamp': '12:00'},
            {'role': 'assistant', 'content': 'здравствуйте', 'timestamp': '12:01'}
        ]
    }
    mm.learn_from_log(test_log)
    
    # Тест статистики
    print("\n📌 ТЕСТ: get_stats")
    stats = mm.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\n" + "=" * 80)
    print("✅ ТЕСТ ЗАВЕРШЁН".center(80))
    print("=" * 80)


if __name__ == "__main__":
    test_memory()