import asyncio

# глобальная очередь
task_queue = asyncio.Queue()

# словарь активных задач {user_id: queued_message_obj
active_tasks: dict[int, object] = {}

# временное хранилище ожидания подтверждения подписки {user_id: (message, url)}
pending_requests: dict[int, tuple] = {}
