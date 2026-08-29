"""eval.context_text 单元测试：rag_context 解析 / 清洗 / 分句（真实线上数据形态）。

所有断言均为完整字符串/列表的精确相等，不使用 in / not in。
"""
from eval.context_text import clean_text, context_to_text, parse_repr, split_sentences

# 真实 rag_context 形态 1：股票档案（dict 列表，含元数据字段）
REAL_PROFILES = [
    {
        "id": 4487,
        "code": "603986",
        "name": "XD兆易创",
        "business": "存储器、微控制器、传感器和模拟芯片的研发、技术支持和销售。",
        "update_time": "2026-08-27 10:57:42",
        "original_score": 0.33333334,
        "rerank_score": 0.06644,
    },
    {
        "id": 4488,
        "code": "300785",
        "name": "值得买",
        "business": "AI与内容驱动的数字消费服务。",
        "update_time": "2026-08-27 09:28:21",
        "original_score": 0.032258064,
        "rerank_score": 0.0572,
    },
    {
        "id": 4489,
        "code": "002256",
        "name": "兆新股份",
        "business": "新能源、精细化工两大类业务。",
        "update_time": "2026-08-27 08:58:26",
        "original_score": 0.09090909,
        "rerank_score": 0.01312,
    },
]

# 真实 rag_context 形态 2：新闻 dict 的字符串 repr（HTML 标签、字面 \u3000、Timestamp）
REAL_NEWS_REPR = (
    "{'title': '兆易创新(<em>603986</em>.<em>SH)2<em>0</em>2<em>6</em>年中报净利润为<em>68</em>.57亿元、"
    "较去年同期上涨1<em>09</em>1.5<em>0</em>%', "
    "'content': '2026年8月19日，兆易创新(603986.SH)发布2026年中报。\\u3000\\u3000公司营业总收入为115.66亿元，"
    "较去年同报告期营业总收入增加74.15亿元，实现3年连续上涨，同比较去年同期上涨178.67%。', "
    "'summary': None, 'date': '2026-08-19 10:15:07', "
    "'fetch_time': Timestamp('2026-08-19 10:15:07'), "
    "'url': 'http://finance.eastmoney.com/a/202608193845843755.html', "
    "'source_type': 'news', 'sector': None, 'importance_score': 0.5}"
)

# 真实 rag_context 形态 3：截断的 dict repr（... 截断、无法完整解析）
REAL_TRUNCATED_REPR = (
    "{'title': '兆易创新', 'content': '存储龙头兆易创新近三个交易日股价下跌24.4%...', "
    "'summary': None, 'date': '2026-07-21', ...}"
)


def test_profiles_exact_text():
    assert context_to_text(REAL_PROFILES) == (
        "XD兆易创（603986）\n"
        "存储器、微控制器、传感器和模拟芯片的研发、技术支持和销售。\n"
        "值得买（300785）\n"
        "AI与内容驱动的数字消费服务。\n"
        "兆新股份（002256）\n"
        "新能源、精细化工两大类业务。"
    )


def test_news_dict_repr_exact_text():
    assert context_to_text(REAL_NEWS_REPR) == (
        "兆易创新(603986.SH)2026年中报净利润为68.57亿元、较去年同期上涨1091.50%\n"
        "2026年8月19日，兆易创新(603986.SH)发布2026年中报。 "
        "公司营业总收入为115.66亿元，较去年同报告期营业总收入增加74.15亿元，"
        "实现3年连续上涨，同比较去年同期上涨178.67%。"
    )


def test_truncated_repr_exact_text():
    assert context_to_text(REAL_TRUNCATED_REPR) == (
        "兆易创新 存储龙头兆易创新近三个交易日股价下跌24.4%... 2026-07-21"
    )


def test_parse_repr():
    assert parse_repr("普通文本") is None
    assert parse_repr("http://finance.eastmoney.com/a.html") is None
    parsed = parse_repr(REAL_NEWS_REPR)
    assert isinstance(parsed, dict)
    assert set(parsed) == {
        "title",
        "content",
        "summary",
        "date",
        "fetch_time",
        "url",
        "source_type",
        "sector",
        "importance_score",
    }
    assert parsed["fetch_time"] is None
    assert parsed["summary"] is None


def test_clean_text_exact():
    raw = "A<em>B</em>\\u3000公司\\n发布&nbsp;公告&emsp;Timestamp('2026-08-19 10:15:07')"
    assert clean_text(raw) == "AB 公司 发布 公告 2026-08-19 10:15:07"


def test_split_sentences_keeps_exchange_suffix_exact():
    assert split_sentences("兆易创新(603986.SH)发布2026年中报。公司营业总收入为115.66亿元。") == [
        "兆易创新(603986.SH)发布2026年中报。",
        "公司营业总收入为115.66亿元。",
    ]


def test_split_sentences_filters_junk_exact():
    text = (
        "这里是一句有效的证据句子。http://finance.eastmoney.com/a.html "
        "2026-08-19 10:15:07 None 123.45 兆易创新（603986）主营业务是存储芯片。"
    )
    assert split_sentences(text) == [
        "这里是一句有效的证据句子。",
        "兆易创新（603986）主营业务是存储芯片。",
    ]


def test_full_real_context_pipeline_exact():
    """用真实线上 rag_context 整体跑一遍：混合形态 → 正文 → 分句，全部精确断言。"""
    contexts = [REAL_PROFILES, REAL_NEWS_REPR, REAL_TRUNCATED_REPR]
    text = "\n\n".join(context_to_text(c) for c in contexts)

    assert text == (
        "XD兆易创（603986）\n"
        "存储器、微控制器、传感器和模拟芯片的研发、技术支持和销售。\n"
        "值得买（300785）\n"
        "AI与内容驱动的数字消费服务。\n"
        "兆新股份（002256）\n"
        "新能源、精细化工两大类业务。\n\n"
        "兆易创新(603986.SH)2026年中报净利润为68.57亿元、较去年同期上涨1091.50%\n"
        "2026年8月19日，兆易创新(603986.SH)发布2026年中报。 "
        "公司营业总收入为115.66亿元，较去年同报告期营业总收入增加74.15亿元，"
        "实现3年连续上涨，同比较去年同期上涨178.67%。\n\n"
        "兆易创新 存储龙头兆易创新近三个交易日股价下跌24.4%... 2026-07-21"
    )

    assert split_sentences(text) == [
        "XD兆易创（603986） 存储器、微控制器、传感器和模拟芯片的研发、技术支持和销售。",
        "值得买（300785） AI与内容驱动的数字消费服务。",
        "兆新股份（002256） 新能源、精细化工两大类业务。",
        "兆易创新(603986.SH)2026年中报净利润为68.57亿元、较去年同期上涨1091.50% "
        "2026年8月19日，兆易创新(603986.SH)发布2026年中报。",
        "公司营业总收入为115.66亿元，较去年同报告期营业总收入增加74.15亿元，"
        "实现3年连续上涨，同比较去年同期上涨178.67%。",
        "兆易创新 存储龙头兆易创新近三个交易日股价下跌24.4%.",
    ]
