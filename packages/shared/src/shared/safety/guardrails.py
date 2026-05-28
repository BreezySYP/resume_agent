"""shared/safety/guardrails.py"""
import re
from typing import Dict, Any


class Guardrails:
    @staticmethod
    def check_input_safety(text: str) -> Dict[str, Any]:
        issues = []
        for pat in [r'(密码|password|token|secret)', r'(rm -rf|drop table)', r'(越权|admin)']:
            if re.search(pat, text, re.IGNORECASE):
                issues.append(f"敏感内容: {pat}")
        if len(text) > 8000:
            issues.append("输入过长")
        return {"safe": not issues, "issues": issues, "score": max(0, 1 - len(issues) * 0.3)}

    @staticmethod
    def check_output_safety(text: str) -> Dict[str, Any]:
        issues = [p for p in [r'(炸弹|毒药|越狱)', r'(种族歧视|暴力)']
                  if re.search(p, text, re.IGNORECASE)]
        return {"safe": not issues, "issues": issues}
