import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import nodriver as uc

from dynamic_hook_system import DynamicHookSystem


class FakeTab:
    def __init__(self):
        self.handlers = {}

    async def send(self, command):
        return None

    def add_handler(self, event_type, handler):
        self.handlers.setdefault(event_type, []).append(handler)

    def remove_handler(self, event_type, handler=None):
        if event_type not in self.handlers:
            return
        if handler is None:
            self.handlers.pop(event_type, None)
            return
        self.handlers[event_type].remove(handler)
        if not self.handlers[event_type]:
            self.handlers.pop(event_type, None)

    def emit(self, event_type, event):
        for handler in list(self.handlers.get(event_type, [])):
            handler(event)


class DynamicHookCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_cleanup_cancels_request_tasks_and_removes_handler(self):
        system = DynamicHookSystem()
        tab = FakeTab()
        instance_id = "browser-1"
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def pending_request(tab, event, request_instance_id):
            started.set()
            try:
                await asyncio.Future()
            finally:
                cancelled.set()

        system._on_request_paused = pending_request
        system.add_instance(instance_id)
        await system.setup_interception(tab, instance_id)

        self.assertIn(uc.cdp.fetch.RequestPaused, tab.handlers)
        tab.emit(uc.cdp.fetch.RequestPaused, object())
        await asyncio.wait_for(started.wait(), timeout=1)

        request_task = next(iter(system._request_tasks[instance_id]))
        await system.cleanup_instance(instance_id)

        self.assertTrue(request_task.cancelled())
        self.assertTrue(cancelled.is_set())
        self.assertNotIn(uc.cdp.fetch.RequestPaused, tab.handlers)
        self.assertNotIn(instance_id, system._request_tasks)
        self.assertNotIn(instance_id, system._interception_handlers)
        self.assertNotIn(instance_id, system.instance_hooks)


if __name__ == "__main__":
    unittest.main()
