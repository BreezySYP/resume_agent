"""shared/code_rule.py — A 股股票代码前缀规则（sh/sz/bj），ETL 与 Agent 共用"""

SH_RANGES = [range(600000, 601000), range(601000, 602000), range(603000, 604000), range(688000, 689000), range(900000, 901000)]
SZ_RANGES = [range(0, 400), range(200000, 201000), range(201000, 202000), range(300000, 302000)]
BJ_RANGES = [range(430000, 440000), range(830000, 840000), range(870000, 880000)]


def add_prefix(code, upper: bool = False, add_dot: bool = False) -> str:
    """6 位代码补全市场前缀，如 '600519' -> 'sh600519'"""
    if str(code)[:2].lower() in ("sz", "sh", "bj"):
        return code
    num_part = int(code)
    sz = ("SZ" if upper else "sz") + ("." if add_dot else "")
    sh = ("SH" if upper else "sh") + ("." if add_dot else "")
    bj = ("BJ" if upper else "bj") + ("." if add_dot else "")
    if num_part < 10: return sz + "00000" + str(num_part)
    if num_part < 100: return sz + "0000" + str(num_part)
    if num_part < 1000: return sz + "000" + str(num_part)
    if num_part < 4000: return sz + "00" + str(num_part)
    if num_part <= 400000: return sz + str(code)
    if (600000 <= num_part <= 689000) or (900000 <= num_part <= 901000): return sh + str(code)
    return bj + str(code)


def remove_prefix(code) -> str:
    """去掉市场前缀和分隔符，如 'sh.600519' -> '600519'"""
    code = str(code)
    if code.lower()[:2] in ("sh", "sz", "bj"):
        code = code[2:]
    if code.startswith("."):
        code = code[1:]
    return code


def add_zeros(code) -> str:
    """补零并去前缀，统一为 6 位纯数字代码"""
    return remove_prefix(add_prefix(code))
