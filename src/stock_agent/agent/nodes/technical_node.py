import datetime
from typing import Any, Dict, Literal
from zoneinfo import ZoneInfo

import pandas as pd
from pydantic import BaseModel, Field
from shared.agents.agent_state import AgentState
from shared.code_rule import  remove_prefix
from shared.db.mysql import engine


def technical_node(state: AgentState) -> Dict[str, Any]:
    """技术面 - 纯数据节点"""
    if not state.get("stock_profile"):
        return {"stock_technique_factor": []}
    
    try:
        codes = [int(remove_prefix(p["code"])) for p in state["stock_profile"]]
        sql = f"""
            SELECT t.* FROM technical_factor t
            JOIN (
                SELECT code, MAX(date) AS max_date 
                FROM technical_factor 
                WHERE code IN ({str(codes)[1:-1]}) 
                GROUP BY code
            ) latest ON t.code = latest.code AND t.date = latest.max_date;
        """
        df = pd.read_sql(sql, engine.connect()).round(2)
        return {"stock_technique_factor": df.to_dict(orient="records")}
    except Exception as e:
        return {"stock_technique_factor": [], "error": str(e)}