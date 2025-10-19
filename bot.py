import logging
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Sticker
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes
)
from telegram.error import TelegramError

from config import *
from database import Database

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
db = Database(DATABASE_PATH)

class TelegramBot:
    def __init__(self):
        self.application = Application.builder().token(BOT_TOKEN).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настройка обработчиков команд"""
        # Основные команды
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("subscribe", self.subscribe_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        
        # Админ команды
        self.application.add_handler(CommandHandler("admin", self.admin_panel))
        self.application.add_handler(CommandHandler("balance", self.balance_command))
        self.application.add_handler(CommandHandler("requests", self.requests_command))
        self.application.add_handler(CommandHandler("auto_approval", self.auto_approval_command))
        self.application.add_handler(CommandHandler("gift_sent", self.gift_sent_command))
        
        # Обработчики кнопок
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Обработчик текстовых сообщений
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        # Добавляем пользователя в базу данных
        db.add_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        welcome_text = f"""
👋 Привет, {user.first_name}!

🎁 Добро пожаловать в наш бот подарков!

Чтобы получить подарок в виде мишки 🐻, вам нужно:
1️⃣ Подписаться на наш канал: @{CHANNEL_USERNAME}
2️⃣ Нажать кнопку "Проверить подписку" ниже

После проверки подписки вы получите замечательный подарок! 🎉
        """
        
        keyboard = [
            [InlineKeyboardButton("📺 Перейти к каналу", url=f"https://t.me/{CHANNEL_USERNAME}")],
            [InlineKeyboardButton("✅ Проверить подписку", callback_data="check_subscription")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
🤖 Помощь по боту:

📋 Основные команды:
/start - Начать работу с ботом
/subscribe - Подписаться на канал и получить подарок
/status - Проверить статус подписки
/help - Показать эту справку

🎁 Как получить подарок:
1. Подпишитесь на канал @{channel_username}
2. Нажмите кнопку "Проверить подписку"
3. Получите подарок - мишку! 🐻

❓ Если у вас есть вопросы, обратитесь к администратору.
        """.format(channel_username=CHANNEL_USERNAME)
        
        await update.message.reply_text(help_text)
    
    async def subscribe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /subscribe"""
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        # Проверяем, подписан ли пользователь уже
        user_data = db.get_user(user.id)
        if user_data and user_data.get('is_subscribed'):
            await update.message.reply_text(
                "✅ Вы уже подписаны на канал и получили подарок! 🎁"
            )
            return
        
        # Создаем заявку на подписку
        request_id = db.add_subscription_request(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        if request_id:
            # Проверяем, включено ли автоматическое одобрение
            if db.get_auto_approval_status():
                # Автоматически одобряем заявку
                await self.auto_approve_subscription(user.id, request_id)
            else:
                # Уведомляем администраторов
                await self.notify_admins_new_request(user, request_id)
                
                await update.message.reply_text(
                    "📝 Ваша заявка на подписку отправлена администраторам. "
                    "Ожидайте одобрения! ⏳"
                )
        else:
            await update.message.reply_text(
                "❌ Произошла ошибка при создании заявки. Попробуйте позже."
            )
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /status"""
        user = update.effective_user
        user_data = db.get_user(user.id)
        
        if not user_data:
            await update.message.reply_text("❌ Пользователь не найден в базе данных.")
            return
        
        status_text = f"""
📊 Ваш статус:

👤 Пользователь: {user_data.get('first_name', 'Не указано')}
📅 Дата регистрации: {user_data.get('created_at', 'Не указано')}
📺 Подписка на канал: {'✅ Подписан' if user_data.get('is_subscribed') else '❌ Не подписан'}
🎁 Подарок получен: {'✅ Получен' if user_data.get('gift_sent') else '❌ Не получен'}
        """
        
        await update.message.reply_text(status_text)
    
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Админ панель"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ У вас нет прав администратора.")
            return
        
        auto_approval = db.get_auto_approval_status()
        pending_requests = len(db.get_pending_requests())
        
        admin_text = f"""
🔧 Админ панель:

🔄 Автоодобрение: {'✅ Включено' if auto_approval else '❌ Выключено'}
📋 Ожидающих заявок: {pending_requests}

Выберите действие:
        """
        
        keyboard = [
            [InlineKeyboardButton("📋 Заявки на подписку", callback_data="admin_requests")],
            [InlineKeyboardButton("🔄 Автоодобрение", callback_data="admin_auto_approval")],
            [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(admin_text, reply_markup=reply_markup)
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для проверки баланса звезд"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ У вас нет прав администратора.")
            return
        
        balance = db.get_stars_balance()
        await update.message.reply_text(f"⭐ Текущий баланс звезд: {balance}")
    
    async def requests_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для просмотра заявок"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ У вас нет прав администратора.")
            return
        
        await self.show_pending_requests(update, context)
    
    async def auto_approval_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для управления автоодобрением"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ У вас нет прав администратора.")
            return
        
        if len(context.args) > 0:
            action = context.args[0].lower()
            if action in ['on', 'enable', 'включить']:
                db.set_auto_approval_status(True)
                await update.message.reply_text("✅ Автоодобрение включено!")
            elif action in ['off', 'disable', 'выключить']:
                db.set_auto_approval_status(False)
                await update.message.reply_text("❌ Автоодобрение выключено!")
            else:
                await update.message.reply_text("Использование: /auto_approval on/off")
        else:
            status = db.get_auto_approval_status()
            await update.message.reply_text(
                f"🔄 Автоодобрение: {'✅ Включено' if status else '❌ Выключено'}\n"
                f"Использование: /auto_approval on/off"
            )
    
    async def gift_sent_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для отметки о том, что подарок отправлен"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ У вас нет прав администратора.")
            return
        
        if len(context.args) < 1:
            await update.message.reply_text(
                "Использование: /gift_sent <user_id>\n"
                "Пример: /gift_sent 123456789"
            )
            return
        
        try:
            target_user_id = int(context.args[0])
            
            # Отмечаем, что подарок отправлен
            success = db.mark_gift_sent(target_user_id)
            
            if success:
                # Получаем информацию о пользователе
                user_data = db.get_user(target_user_id)
                
                if user_data:
                    await update.message.reply_text(
                        f"✅ Подарок отмечен как отправленный!\n\n"
                        f"👤 Пользователь: {user_data.get('first_name', 'Неизвестно')} (ID: {target_user_id})\n"
                        f"🎁 Подарок: Игрушечный медведь 🐻\n"
                        f"⭐ Стоимость: {STARS_PER_GIFT} звезда (списана вручную)"
                    )
                else:
                    await update.message.reply_text(
                        f"✅ Подарок отмечен как отправленный!\n\n"
                        f"👤 Пользователь ID: {target_user_id}\n"
                        f"🎁 Подарок: Игрушечный медведь 🐻\n"
                        f"⭐ Стоимость: {STARS_PER_GIFT} звезда (списана вручную)"
                    )
            else:
                await update.message.reply_text("❌ Ошибка при обновлении статуса подарка.")
                
        except ValueError:
            await update.message.reply_text("❌ Неверный формат ID пользователя.")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        # Здесь можно добавить обработку специальных сообщений
        pass
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user = update.effective_user
        
        if data == "check_subscription":
            await self.check_subscription(query, user, context)
        elif data == "admin_stars":
            await self.admin_stars_menu(query, user)
        elif data == "admin_requests":
            await self.admin_requests_menu(query, user)
        elif data == "admin_auto_approval":
            await self.admin_auto_approval_menu(query, user)
        elif data == "admin_stats":
            await self.admin_stats_menu(query, user)
        elif data == "admin_back":
            await self.admin_panel_callback(query, user)
        elif data.startswith("approve_"):
            request_id = int(data.split("_")[1])
            await self.approve_request(query, user, request_id, context)
        elif data.startswith("reject_"):
            request_id = int(data.split("_")[1])
            await self.reject_request(query, user, request_id, context)
        elif data.startswith("add_stars_"):
            amount = int(data.split("_")[2])
            await self.add_stars(query, user, amount)
        elif data.startswith("toggle_auto_"):
            await self.toggle_auto_approval(query, user)
    
    async def check_subscription(self, query, user, context):
        """Проверка подписки пользователя"""
        try:
            # Проверяем подписку через API Telegram
            member = await context.bot.get_chat_member(CHANNEL_ID, user.id)
            
            if member.status in ['member', 'administrator', 'creator']:
                # Пользователь подписан
                user_data = db.get_user(user.id)
                
                if user_data and not user_data.get('gift_sent'):
                    # Отправляем подарок
                    await self.send_gift(query, user, context)
                    db.update_user_subscription(user.id, True)
                    db.mark_gift_sent(user.id)
                else:
                    await query.edit_message_text("✅ Вы уже получили подарок! 🎁")
            else:
                await query.edit_message_text(
                    "❌ Вы не подписаны на канал. Пожалуйста, подпишитесь и попробуйте снова."
                )
        except TelegramError as e:
            logger.error(f"Error checking subscription: {e}")
            await query.edit_message_text(
                "❌ Ошибка при проверке подписки. Попробуйте позже."
            )
    
    async def send_gift(self, query, user, context):
        """Отправка подарка пользователю"""
        try:
            # Отправляем сообщение с поздравлением
            await context.bot.send_message(
                chat_id=user.id,
                text=GIFT_MESSAGE
            )
            
            # Уведомляем администраторов о необходимости отправить подарок
            await self.notify_admin_send_gift(user)
            
            await query.edit_message_text("🎉 Заявка одобрена! Администратор отправит вам подарок! 🐻")
            
        except TelegramError as e:
            logger.error(f"Error sending gift: {e}")
            await query.edit_message_text("❌ Ошибка при отправке подарка.")
    
    async def auto_approve_subscription(self, user_id: int, request_id: int):
        """Автоматическое одобрение подписки"""
        try:
            # Обновляем статус заявки
            db.process_subscription_request(request_id, 'approved', 0)  # 0 = система
            
            # Отправляем подарок
            user = await self.application.bot.get_chat(user_id)
            # Создаем контекст для send_gift_to_user
            from telegram.ext import ContextTypes
            context = ContextTypes.DEFAULT_TYPE()
            context.bot = self.application.bot
            await self.send_gift_to_user(user_id, user.first_name, context)
            
            logger.info(f"Auto-approved subscription for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error auto-approving subscription: {e}")
    
    async def send_gift_to_user(self, user_id: int, first_name: str, context):
        """Отправка подарка конкретному пользователю"""
        try:
            # Отправляем сообщение с поздравлением
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 {first_name}, поздравляем! Вы получили подарок - мишку! 🐻\n\nАдминистратор отправит вам подарок в ближайшее время!"
            )
            
            # Уведомляем администраторов
            await self.notify_admin_send_gift_by_id(user_id, first_name)
            
        except TelegramError as e:
            logger.error(f"Error sending gift to user {user_id}: {e}")
    
    async def notify_admins_new_request(self, user, request_id: int):
        """Уведомление администраторов о новой заявке"""
        notification_text = f"""
🔔 Новая заявка на подписку!

👤 Пользователь: {user.first_name} {user.last_name or ''}
🆔 ID: {user.id}
👤 Username: @{user.username or 'не указан'}
📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}
🆔 ID заявки: {request_id}

Используйте /requests для просмотра всех заявок.
        """
        
        for admin_id in ADMIN_IDS:
            try:
                await self.application.bot.send_message(
                    chat_id=admin_id,
                    text=notification_text
                )
            except TelegramError as e:
                logger.error(f"Error notifying admin {admin_id}: {e}")
    
    async def notify_admin_send_gift(self, user):
        """Уведомление администратора о необходимости отправить подарок"""
        gift_notification = f"""
🎁 НУЖНО ОТПРАВИТЬ ПОДАРОК!

👤 Пользователь: {user.first_name} {user.last_name or ''}
🆔 ID: {user.id}
👤 Username: @{user.username or 'не указан'}

🎁 Подарок: Игрушечный медведь 🐻
⭐ Стоимость: {STARS_PER_GIFT} Telegram Star

📋 Инструкция:
1. Откройте чат с пользователем
2. Нажмите на скрепку (📎)
3. Выберите "Подарок" 🎁
4. Выберите "Игрушечный медведь" 🐻
5. Отправьте подарок
6. Используйте команду: /gift_sent {user.id}

⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}
        """
        
        for admin_id in ADMIN_IDS:
            try:
                await self.application.bot.send_message(
                    chat_id=admin_id,
                    text=gift_notification
                )
            except TelegramError as e:
                logger.error(f"Error notifying admin about gift {admin_id}: {e}")
    
    async def notify_admin_send_gift_by_id(self, user_id: int, first_name: str):
        """Уведомление администратора о необходимости отправить подарок по ID"""
        gift_notification = f"""
🎁 НУЖНО ОТПРАВИТЬ ПОДАРОК!

👤 Пользователь: {first_name}
🆔 ID: {user_id}

📋 Инструкция:
1. Откройте чат с пользователем (ID: {user_id})
2. Нажмите на скрепку (📎)
3. Выберите "Подарок" 🎁
4. Выберите "Игрушечный медведь" 🐻
5. Отправьте подарок

⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}
        """
        
        for admin_id in ADMIN_IDS:
            try:
                await self.application.bot.send_message(
                    chat_id=admin_id,
                    text=gift_notification
                )
            except TelegramError as e:
                logger.error(f"Error notifying admin about gift {admin_id}: {e}")
    
    async def show_pending_requests(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показ ожидающих заявок"""
        requests = db.get_pending_requests()
        
        if not requests:
            await update.message.reply_text("📋 Нет ожидающих заявок.")
            return
        
        text = "📋 Ожидающие заявки на подписку:\n\n"
        
        for req in requests:
            text += f"""
🆔 ID: {req['id']}
👤 Пользователь: {req['first_name']} {req.get('last_name', '')}
🆔 User ID: {req['user_id']}
👤 Username: @{req.get('username', 'не указан')}
📅 Дата: {req['created_at']}

"""
        
        await update.message.reply_text(text)
    
    async def admin_stars_menu(self, query, user):
        """Меню управления звездами"""
        balance = db.get_stars_balance()
        
        text = f"⭐ Управление звездами\n\nТекущий баланс: {balance}\n\nВыберите действие:"
        
        keyboard = [
            [InlineKeyboardButton("➕ Добавить 100", callback_data="add_stars_100")],
            [InlineKeyboardButton("➕ Добавить 500", callback_data="add_stars_500")],
            [InlineKeyboardButton("➕ Добавить 1000", callback_data="add_stars_1000")],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def admin_requests_menu(self, query, user):
        """Меню управления заявками"""
        requests = db.get_pending_requests()
        
        if not requests:
            text = "📋 Нет ожидающих заявок."
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]]
        else:
            text = f"📋 Заявки на подписку ({len(requests)} ожидают):\n\n"
            keyboard = []
            
            for req in requests[:5]:  # Показываем только первые 5
                text += f"🆔 {req['id']}: {req['first_name']} (@{req.get('username', 'нет')})\n"
                keyboard.append([
                    InlineKeyboardButton(f"✅ {req['id']}", callback_data=f"approve_{req['id']}"),
                    InlineKeyboardButton(f"❌ {req['id']}", callback_data=f"reject_{req['id']}")
                ])
            
            keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def admin_auto_approval_menu(self, query, user):
        """Меню автоодобрения"""
        status = db.get_auto_approval_status()
        
        text = f"🔄 Автоодобрение заявок\n\nТекущий статус: {'✅ Включено' if status else '❌ Выключено'}\n\nВыберите действие:"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Переключить", callback_data="toggle_auto_approval")],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def admin_stats_menu(self, query, user):
        """Меню статистики"""
        balance = db.get_stars_balance()
        pending_requests = len(db.get_pending_requests())
        auto_approval = db.get_auto_approval_status()
        total_gifts = db.get_total_gifts_sent()
        stars_spent = db.get_total_stars_spent_on_gifts()
        
        text = f"""
📊 Статистика бота:

🎁 Отправлено подарков: {total_gifts}
📋 Ожидающих заявок: {pending_requests}
🔄 Автоодобрение: {'✅ Включено' if auto_approval else '❌ Выключено'}

💡 Стоимость одного подарка: {STARS_PER_GIFT} звезда
⭐ Звезды списываются вручную при отправке подарков
        """
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def admin_panel_callback(self, query, user):
        """Возврат в админ панель"""
        auto_approval = db.get_auto_approval_status()
        pending_requests = len(db.get_pending_requests())
        
        admin_text = f"""
🔧 Админ панель:

🔄 Автоодобрение: {'✅ Включено' if auto_approval else '❌ Выключено'}
📋 Ожидающих заявок: {pending_requests}

Выберите действие:
        """
        
        keyboard = [
            [InlineKeyboardButton("📋 Заявки на подписку", callback_data="admin_requests")],
            [InlineKeyboardButton("🔄 Автоодобрение", callback_data="admin_auto_approval")],
            [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(admin_text, reply_markup=reply_markup)
    
    async def approve_request(self, query, user, request_id: int, context):
        """Одобрение заявки"""
        if user.id not in ADMIN_IDS:
            await query.answer("❌ Нет прав администратора", show_alert=True)
            return
        
        # Получаем данные заявки
        requests = db.get_pending_requests()
        request_data = next((req for req in requests if req['id'] == request_id), None)
        
        if not request_data:
            await query.answer("❌ Заявка не найдена", show_alert=True)
            return
        
        # Одобряем заявку
        success = db.process_subscription_request(request_id, 'approved', user.id)
        
        if success:
            # Отправляем подарок пользователю
            await self.send_gift_to_user(request_data['user_id'], request_data['first_name'], context)
            
            await query.answer("✅ Заявка одобрена! Подарок отправлен.")
            await self.admin_requests_menu(query, user)  # Обновляем меню
        else:
            await query.answer("❌ Ошибка при одобрении заявки", show_alert=True)
    
    async def reject_request(self, query, user, request_id: int, context):
        """Отклонение заявки"""
        if user.id not in ADMIN_IDS:
            await query.answer("❌ Нет прав администратора", show_alert=True)
            return
        
        success = db.process_subscription_request(request_id, 'rejected', user.id)
        
        if success:
            await query.answer("❌ Заявка отклонена.")
            await self.admin_requests_menu(query, user)  # Обновляем меню
        else:
            await query.answer("❌ Ошибка при отклонении заявки", show_alert=True)
    
    async def add_stars(self, query, user, amount: int):
        """Добавление звезд"""
        if user.id not in ADMIN_IDS:
            await query.answer("❌ Нет прав администратора", show_alert=True)
            return
        
        success = db.add_stars(amount, f"Added by admin {user.id}")
        
        if success:
            await query.answer(f"✅ Добавлено {amount} звезд!")
            await self.admin_stars_menu(query, user)  # Обновляем меню
        else:
            await query.answer("❌ Ошибка при добавлении звезд", show_alert=True)
    
    async def toggle_auto_approval(self, query, user):
        """Переключение автоодобрения"""
        if user.id not in ADMIN_IDS:
            await query.answer("❌ Нет прав администратора", show_alert=True)
            return
        
        current_status = db.get_auto_approval_status()
        new_status = not current_status
        
        success = db.set_auto_approval_status(new_status)
        
        if success:
            status_text = "включено" if new_status else "выключено"
            await query.answer(f"✅ Автоодобрение {status_text}!")
            await self.admin_auto_approval_menu(query, user)  # Обновляем меню
        else:
            await query.answer("❌ Ошибка при изменении настроек", show_alert=True)
    
    def run(self):
        """Запуск бота"""
        logger.info("Starting bot...")
        self.application.run_polling()

if __name__ == "__main__":
    bot = TelegramBot()
    bot.run()
#   U p d a t e d   1 0 / 1 9 / 2 0 2 5   2 2 : 3 9 : 3 0  
 