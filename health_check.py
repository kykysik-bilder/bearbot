#!/usr/bin/env python3
"""
РЎРєСЂРёРїС‚ РґР»СЏ РїСЂРѕРІРµСЂРєРё Р·РґРѕСЂРѕРІСЊСЏ Telegram Р±РѕС‚Р°
"""

import requests
import sqlite3
import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

# РќР°СЃС‚СЂРѕР№РєР° Р»РѕРіРёСЂРѕРІР°РЅРёСЏ
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class BotHealthChecker:
    def __init__(self, bot_token: str, db_path: str = "bot_database.db"):
        self.bot_token = bot_token
        self.db_path = db_path
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
    
    def check_telegram_api(self) -> bool:
        """РџСЂРѕРІРµСЂРєР° РґРѕСЃС‚СѓРїРЅРѕСЃС‚Рё Telegram API"""
        try:
            response = requests.get(f"{self.api_url}/getMe", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    logger.info(f"Telegram API РґРѕСЃС‚СѓРїРµРЅ. Р‘РѕС‚: {data['result']['first_name']}")
                    return True
                else:
                    logger.error(f"Telegram API РІРµСЂРЅСѓР» РѕС€РёР±РєСѓ: {data}")
                    return False
            else:
                logger.error(f"HTTP РѕС€РёР±РєР°: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"РћС€РёР±РєР° РїРѕРґРєР»СЋС‡РµРЅРёСЏ Рє Telegram API: {e}")
            return False
    
    def run_health_check(self) -> bool:
        """Р—Р°РїСѓСЃРє РїРѕР»РЅРѕР№ РїСЂРѕРІРµСЂРєРё Р·РґРѕСЂРѕРІСЊСЏ"""
        logger.info("=" * 50)
        logger.info("Р—Р°РїСѓСЃРє РїСЂРѕРІРµСЂРєРё Р·РґРѕСЂРѕРІСЊСЏ Р±РѕС‚Р°")
        logger.info("=" * 50)
        
        if self.check_telegram_api():
            logger.info("вњ… Telegram API: OK")
            return True
        else:
            logger.error("вќЊ Telegram API: FAILED")
            return False

def main():
    """РћСЃРЅРѕРІРЅР°СЏ С„СѓРЅРєС†РёСЏ"""
    # РџРѕР»СѓС‡Р°РµРј С‚РѕРєРµРЅ Р±РѕС‚Р° РёР· РїРµСЂРµРјРµРЅРЅС‹С… РѕРєСЂСѓР¶РµРЅРёСЏ
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        logger.error("BOT_TOKEN РЅРµ СѓСЃС‚Р°РЅРѕРІР»РµРЅ РІ РїРµСЂРµРјРµРЅРЅС‹С… РѕРєСЂСѓР¶РµРЅРёСЏ")
        sys.exit(1)
    
    # РЎРѕР·РґР°РµРј РїСЂРѕРІРµСЂСЏР»СЊС‰РёРє
    checker = BotHealthChecker(bot_token)
    
    # Р—Р°РїСѓСЃРєР°РµРј РїСЂРѕРІРµСЂРєСѓ
    success = checker.run_health_check()
    
    # Р’РѕР·РІСЂР°С‰Р°РµРј РєРѕРґ РІС‹С…РѕРґР°
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
