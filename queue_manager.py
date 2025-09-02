import asyncio

# глобальная очередь
task_queue = asyncio.Queue()

# словарь активных задач {user_id: True}
active_tasks = {}
