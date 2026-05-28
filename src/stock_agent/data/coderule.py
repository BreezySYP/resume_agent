"""data/coderule.py — 股票代码前缀规则"""


def flat(ran, threshold):
    return [range(i, i + threshold) for i in range(ran.start, ran.stop, threshold)]


sh = [range(600000, 601000), range(601000, 602000), range(603000, 604000),
      range(688000, 689000), range(900000, 901000)]
sz = [range(0, 400), range(200000, 201000), range(201000, 202000), range(300000, 302000)]
bj = [range(430000, 440000), range(830000, 840000), range(870000, 880000)]


def add_prefix(code, upper=False, add_dot=False):
    num_part = int(code)
    _sz = ("SZ" if upper else "sz") + ("." if add_dot else "")
    _sh = ("SH" if upper else "sh") + ("." if add_dot else "")
    _bj = ("BJ" if upper else "bj") + ("." if add_dot else "")
    if num_part < 10:        return _sz + "00000" + str(num_part)
    elif num_part < 100:     return _sz + "0000"  + str(num_part)
    elif num_part < 1000:    return _sz + "000"   + str(num_part)
    elif num_part < 4000:    return _sz + "00"    + str(num_part)
    elif num_part <= 400000: return _sz + str(code)
    elif (600000 <= num_part <= 689000) or (900000 <= num_part <= 901000):
        return _sh + str(code)
    else:
        return _bj + str(code)


def remove_prefix(code):
    code = str(code)
    if code.lower()[:2] in ("sh", "sz", "bj"):
        code = code[2:]
    if code.startswith("."):
        code = code[1:]
    return code


def addZeros(code):
    return remove_prefix(add_prefix(code))
