import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]

# Channel Configuration
CHANNEL_ID = os.getenv('CHANNEL_ID')  # ID канала для подписки
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME')  # @username канала

# Gift Configuration
GIFT_TYPE = "telegram_gift"  # telegram_gift, sticker, message
GIFT_MESSAGE = "🎉 Поздравляем! Вы получили подарок - мишку! 🐻\n\nАдминистратор отправит вам подарок в ближайшее время!"
GIFT_NOTIFICATION_MESSAGE = "🎁 Нужно отправить подарок пользователю!"

# Telegram Stars Configuration
USE_TELEGRAM_STARS = False  # Не использовать автоматическое списание звезд
STARS_PER_GIFT = 1  # Количество звезд за один подарок (для информации)

# Database Configuration
DATABASE_PATH = 'bot_database.db'

# Auto-approval settings
AUTO_APPROVAL_ENABLED = False
