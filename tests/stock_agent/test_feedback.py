"""feedback 逐 claim 报告格式化的单测（不触发外部服务）。"""
from eval.feedback import _support_label, build_faithfulness_claims


def test_support_label():
    assert _support_label(1.0) == "完全支持"
    assert _support_label(0.5) == "部分支持"
    assert _support_label(0.0) == "不支持"
    assert _support_label(0.3) == "不支持"


def test_build_faithfulness_claims():
    results = [
        {
            "claim": "能科科技（603859）财务总分0.54。",
            "supported": 1.0,
            "evidence": ["[603859] total_score: 0.54"],
            "claim_codes": ["603859"],
            "candidate_count": 3,
            "evidence_count": 1,
        },
        {
            "claim": "建议积极配置。",
            "supported": 0.0,
            "evidence": [],
            "claim_codes": [],
            "candidate_count": 0,
            "evidence_count": 0,
        },
    ]
    assert build_faithfulness_claims(results) == [
        {
            "claim": "能科科技（603859）财务总分0.54。",
            "sentences": ["[603859] total_score: 0.54"],
            "result": "完全支持",
        },
        {
            "claim": "建议积极配置。",
            "sentences": [],
            "result": "不支持",
        },
    ]
