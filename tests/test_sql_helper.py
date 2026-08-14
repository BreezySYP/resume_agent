"""service.sql_helper 的纯逻辑测试。"""
import pandas as pd
from service.sql_helper import attach_scores, clean_sql


def test_clean_sql_plain():
    assert clean_sql("  SELECT 1  ") == "SELECT 1"


def test_clean_sql_sql_fence():
    assert clean_sql("```sql\nSELECT 1\n```") == "SELECT 1"


def test_clean_sql_generic_fence():
    assert clean_sql("```\nSELECT 2\n```") == "SELECT 2"


def test_attach_scores_joins_and_sorts():
    df = pd.DataFrame({"id": ["1", "2", "3"], "name": ["a", "b", "c"]})
    hits = pd.DataFrame({"id": ["2", "1"], "score": [0.9, 0.5]})
    out = attach_scores(df, hits)
    assert out["id"].tolist() == ["2", "1", "3"]
    assert out["original_score"].iloc[0] == 0.9
    assert out["original_score"].iloc[1] == 0.5
    assert pd.isna(out["original_score"].iloc[2])


def test_attach_scores_empty_hits():
    df = pd.DataFrame({"id": ["1", "2"]})
    out = attach_scores(df, pd.DataFrame(columns=["id", "score"]))
    assert out.equals(df)


def test_attach_scores_empty_df():
    out = attach_scores(pd.DataFrame(), pd.DataFrame({"id": ["1"], "score": [1.0]}))
    assert out.empty
