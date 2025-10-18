import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных и создание таблиц"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Таблица пользователей
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        subscribed_at TIMESTAMP,
                        is_subscribed BOOLEAN DEFAULT FALSE,
                        gift_sent BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Таблица заявок на подписку
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS subscription_requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        status TEXT DEFAULT 'pending', -- pending, approved, rejected
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processed_at TIMESTAMP,
                        processed_by INTEGER,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                ''')
                
                # Таблица звезд (баланс бота) - реальные Telegram Stars
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS stars_balance (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        amount INTEGER,
                        operation_type TEXT, -- add, subtract, gift_sent
                        description TEXT,
                        user_id INTEGER, -- ID пользователя для подарков
                        gift_type TEXT, -- тип подарка
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Таблица настроек
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Инициализация баланса звезд
                cursor.execute('SELECT COUNT(*) FROM stars_balance')
                if cursor.fetchone()[0] == 0:
                    cursor.execute('''
                        INSERT INTO stars_balance (amount, operation_type, description)
                        VALUES (0, 'init', 'Initial balance')
                    ''')
                
                # Инициализация настроек
                cursor.execute('SELECT COUNT(*) FROM settings')
                if cursor.fetchone()[0] == 0:
                    cursor.execute('''
                        INSERT INTO settings (key, value) VALUES 
                        ('auto_approval', 'false'),
                        ('gift_sticker_id', ''),
                        ('gift_message', '🎉 Поздравляем! Вы получили подарок - мишку! 🐻')
                    ''')
                
                conn.commit()
                logger.info("Database initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> bool:
        """Добавление нового пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, username, first_name, last_name, datetime.now()))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            return False
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Получение информации о пользователе"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None
    
    def update_user_subscription(self, user_id: int, is_subscribed: bool) -> bool:
        """Обновление статуса подписки пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users 
                    SET is_subscribed = ?, subscribed_at = ?
                    WHERE user_id = ?
                ''', (is_subscribed, datetime.now() if is_subscribed else None, user_id))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating user subscription: {e}")
            return False
    
    def mark_gift_sent(self, user_id: int) -> bool:
        """Отметка о том, что подарок отправлен"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users 
                    SET gift_sent = TRUE
                    WHERE user_id = ?
                ''', (user_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error marking gift sent: {e}")
            return False
    
    def add_subscription_request(self, user_id: int, username: str = None, 
                               first_name: str = None, last_name: str = None) -> int:
        """Добавление заявки на подписку"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO subscription_requests (user_id, username, first_name, last_name)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, username, first_name, last_name))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error adding subscription request: {e}")
            return 0
    
    def get_pending_requests(self) -> List[Dict]:
        """Получение всех ожидающих заявок"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM subscription_requests 
                    WHERE status = 'pending' 
                    ORDER BY created_at ASC
                ''')
                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error(f"Error getting pending requests: {e}")
            return []
    
    def process_subscription_request(self, request_id: int, status: str, processed_by: int) -> bool:
        """Обработка заявки на подписку"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE subscription_requests 
                    SET status = ?, processed_at = ?, processed_by = ?
                    WHERE id = ?
                ''', (status, datetime.now(), processed_by, request_id))
                
                if status == 'approved':
                    # Получаем user_id из заявки
                    cursor.execute('SELECT user_id FROM subscription_requests WHERE id = ?', (request_id,))
                    result = cursor.fetchone()
                    if result:
                        user_id = result[0]
                        # Обновляем статус подписки пользователя
                        cursor.execute('''
                            UPDATE users 
                            SET is_subscribed = TRUE, subscribed_at = ?
                            WHERE user_id = ?
                        ''', (datetime.now(), user_id))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error processing subscription request: {e}")
            return False
    
    def get_stars_balance(self) -> int:
        """Получение текущего баланса звезд"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT SUM(CASE WHEN operation_type = 'add' THEN amount 
                                   WHEN operation_type = 'subtract' THEN -amount 
                                   ELSE 0 END) as balance
                    FROM stars_balance
                ''')
                result = cursor.fetchone()
                return result[0] if result[0] is not None else 0
        except Exception as e:
            logger.error(f"Error getting stars balance: {e}")
            return 0
    
    def add_stars(self, amount: int, description: str = "Manual addition") -> bool:
        """Пополнение баланса звезд"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO stars_balance (amount, operation_type, description)
                    VALUES (?, 'add', ?)
                ''', (amount, description))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding stars: {e}")
            return False
    
    def subtract_stars(self, amount: int, description: str = "Manual subtraction") -> bool:
        """Списание звезд"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO stars_balance (amount, operation_type, description)
                    VALUES (?, 'subtract', ?)
                ''', (amount, description))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error subtracting stars: {e}")
            return False
    
    def get_setting(self, key: str) -> Optional[str]:
        """Получение настройки"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting setting: {e}")
            return None
    
    def set_setting(self, key: str, value: str) -> bool:
        """Установка настройки"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                ''', (key, value, datetime.now()))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error setting setting: {e}")
            return False
    
    def get_auto_approval_status(self) -> bool:
        """Получение статуса автоматического одобрения"""
        value = self.get_setting('auto_approval')
        return value == 'true' if value else False
    
    def set_auto_approval_status(self, enabled: bool) -> bool:
        """Установка статуса автоматического одобрения"""
        return self.set_setting('auto_approval', 'true' if enabled else 'false')
    
    def send_gift_stars(self, user_id: int, amount: int, gift_type: str = "telegram_gift") -> bool:
        """Списание звезд за отправку подарка"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO stars_balance (amount, operation_type, description, user_id, gift_type)
                    VALUES (?, 'gift_sent', ?, ?, ?)
                ''', (amount, f"Gift sent to user {user_id}", user_id, gift_type))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error sending gift stars: {e}")
            return False
    
    def get_gifts_sent(self) -> List[Dict]:
        """Получение списка отправленных подарков"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM stars_balance 
                    WHERE operation_type = 'gift_sent' 
                    ORDER BY created_at DESC
                ''')
                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error(f"Error getting gifts sent: {e}")
            return []
    
    def get_total_gifts_sent(self) -> int:
        """Получение общего количества отправленных подарков"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*) FROM stars_balance 
                    WHERE operation_type = 'gift_sent'
                ''')
                result = cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error getting total gifts sent: {e}")
            return 0
    
    def get_total_stars_spent_on_gifts(self) -> int:
        """Получение общего количества звезд, потраченных на подарки"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT SUM(amount) FROM stars_balance 
                    WHERE operation_type = 'gift_sent'
                ''')
                result = cursor.fetchone()
                return result[0] if result[0] is not None else 0
        except Exception as e:
            logger.error(f"Error getting total stars spent on gifts: {e}")
            return 0
