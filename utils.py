import logging
from aiogram import Bot

logger = logging.getLogger(__name__)

async def check_subscription(bot: Bot, user_id: int, channels: list[str]) -> bool:
    """Проверяем подписку пользователя на все каналы"""
    for channel in channels:
        ch = channel.strip()
        if not ch:
            continue
        try:
            member = await bot.get_chat_member(ch, user_id)
            if member.status not in ("creator", "administrator", "member"):
                return False
        except Exception as e:
            logger.warning(f"Не удалось проверить подписку {user_id} на {ch}: {e}")
            return False
    return True
