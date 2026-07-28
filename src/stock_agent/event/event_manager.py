# shared/events/event_manager.py

from shared.db.redis import push_queue

from loguru import logger


class EventManager:

    def emit(self, thread_id: str, event: dict):
        logger.debug("set event for {} , content is {}", thread_id, event)
        push_queue(thread_id, event)

    def node_start(self, thread_id: str, node: str, message: str):
        self.emit(thread_id, {
            "type": "node",
            "status": "start",
            "node": node,
            "message": message,
        })

    def node_finish(self, thread_id: str, node: str):
        self.emit(thread_id, {
            "type": "node",
            "status": "finish",
            "node": node,
        })

    def graph_finish(self, thread_id: str, node: str, message: str):
        self.emit(thread_id, {
            "type": "node",
            "status": "done",
            "node": node,
            "done": True,
            "message": message
        })

    def node_error(self, thread_id: str, node: str, error: str):
        self.emit(thread_id, {
            "type": "node",
            "status": "error",
            "node": node,
            "message": error,
        })

    def progress(self, thread_id: str, message: str):
        self.emit(thread_id, {
            "type": "progress",
            "message": message,
        })


event = EventManager()