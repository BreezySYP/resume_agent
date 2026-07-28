# middleware/error_handler.py
from langgraph.types import RetryPolicy
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import  SystemMessage
import traceback
from loguru import logger

def error_handler_middleware(node_func):
    """节点级错误处理 middleware"""
    def wrapper(state, config=None):
        try:
            return node_func(state)
        except Exception as e:
            error_msg = f"Node error in {node_func.__name__}: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            
            # 记录错误到 state
            return {
                "errors": [error_msg],
                "messages": [SystemMessage(content=f"错误: {str(e)}")],
                "status": "partly error",
                "current_node": node_func.__name__
            }
    return wrapper