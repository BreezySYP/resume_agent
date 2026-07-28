# shared/checkpointer/mysql_messages_only.py
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.base import Checkpoint
from typing import Any, Optional, Dict
from sqlalchemy import text
import json
import pickle
from shared.db.mysql import engine
from service.sse_queue import push_sse

def push(thread_id, status, messages):
    push_sse(thread_id=thread_id, status=status, message=(messages[-1].content[:20] + "..."))

class SQLCheckpointer(BaseCheckpointSaver):
    """只持久化 messages + status 的 Checkpointer"""
    
    def __init__(self):
        super().__init__()
        self._create_table()

    def _create_table(self):
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS langgraph_messages (
                    thread_id VARCHAR(255) PRIMARY KEY,
                    messages BLOB NOT NULL,
                    status VARCHAR(50) DEFAULT 'pending',
                    current_node VARCHAR(100) DEFAULT '',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """))
            conn.commit()

    def put(self, config: Dict[str, Any], checkpoint: Checkpoint, metadata: Dict[str, Any]) -> None:
        thread_id = config["configurable"]["thread_id"]
        
        messages = checkpoint.get("messages", [])
        status = checkpoint.get("status", "pending")
        current_node = checkpoint.get("current_node", "")
        
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO langgraph_messages (thread_id, messages, status, current_node)
                VALUES (:thread_id, :messages, :status, :current_node)
                ON DUPLICATE KEY UPDATE 
                messages = VALUES(messages),
                status = VALUES(status),
                current_node = VALUES(current_node)
            """), {
                "thread_id": thread_id,
                "messages": pickle.dumps(messages),
                "status": status,
                "current_node": current_node
            })
            conn.commit()
        push(thread_id=thread_id, status=status, messages=messages)

    def get(self, config: Dict[str, Any]) -> Optional[Checkpoint]:
        thread_id = config["configurable"]["thread_id"]
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT messages, status, current_node 
                FROM langgraph_messages 
                WHERE thread_id = :thread_id
            """), {"thread_id": thread_id})
            
            row = result.fetchone()
            if row:
                return {
                    "messages": pickle.loads(row[0]),
                    "status": row[1],
                    "current_node": row[2]
                }
        return None