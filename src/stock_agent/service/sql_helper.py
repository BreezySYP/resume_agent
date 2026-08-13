from __future__ import annotations

from typing import Sequence

import pandas as pd
from shared.db.mysql import engine


def fetch_by_ids(table: str, ids: Sequence, id_col: str = "id") -> pd.DataFrame:
    ids = [str(i) for i in ids if i is not None]
    if not ids:
        return pd.DataFrame()
    # 用参数化更安全；这里保持与你现有风格接近，生产建议改成 bindparam
    placeholders = ", ".join([f"'{i}'" for i in ids])
    sql = f"SELECT * FROM {table} WHERE {id_col} IN ({placeholders})"
    return pd.read_sql(sql, con=engine.connect())


def attach_scores(df: pd.DataFrame, hits: pd.DataFrame, id_col: str = "id") -> pd.DataFrame:
    if df.empty or hits.empty:
        return df
    score_map = dict(zip(hits["id"].astype(str), hits["score"]))
    out = df.copy()
    out["original_score"] = out[id_col].astype(str).map(score_map)
    return out.sort_values("original_score", ascending=False).reset_index(drop=True)