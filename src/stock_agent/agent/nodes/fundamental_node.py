import datetime
from typing import Any, Dict, Literal
from zoneinfo import ZoneInfo

from langchain_core.messages import (AIMessage, HumanMessage, SystemMessage,
                                     ToolMessage)
from langchain_core.output_parsers import JsonOutputParser
import pandas as pd
from pydantic import BaseModel, Field
from shared.agents.agent_state import AgentState
from shared.code_rule import add_prefix
from shared.db.mysql import engine
from shared.models.deepseek import get_deepseek


def fundamental_node(state: AgentState) -> Dict[str, Any]:
    """基本面 - 纯数据节点"""
    if not state.get("stock_profile"):
        return {"stock_financial_factor": []}
    
    try:
        codes = [add_prefix(p["code"]) for p in state["stock_profile"]]
        sql = f"""
            SELECT t.* FROM financial_factor t
            JOIN (
                SELECT code, MAX(report_date) AS max_date 
                FROM financial_factor 
                WHERE code IN ({str(codes)[1:-1]}) 
                GROUP BY code
            ) latest ON t.code = latest.code AND t.report_date = latest.max_date;
        """
        df = pd.read_sql(sql, engine.connect()).round(2)
        return {"stock_financial_factor": df.to_dict(orient="records")}
    except Exception as e:
        return {"stock_financial_factor": [], "error": str(e)}