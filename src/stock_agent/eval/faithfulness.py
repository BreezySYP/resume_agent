import asyncio
import re
from functools import lru_cache
from typing import List

import numpy as np
from loguru import logger
from shared.metrics.prome import ainvoke_with_metrics
from shared.models.deepseek import get_deepseek
from shared.models.ollama_models import get_ollama_embedding

model_name = "deepseek-chat"


@lru_cache(maxsize=1)
def _get_model():
    return get_deepseek(model=model_name)


_MAX_CLAIM_NUM = 10
embeder = get_ollama_embedding()
_SAMPLE_SIZE = 100
_MAX_EMBED_CHARS = 300  # 单条文本截断长度，防止超长句子撑爆 bge-m3 上下文
_EMBED_BATCH_SIZE = 8  # 单次 embed 的条数上限，分批调用避免 "input length exceeds context length"


def assemble_rag(rag_context: list) -> list[str]:
    """把 rag_context 记录逐条转成文本并分句，返回句子列表。"""
    sentences: List[str] = []
    for record in rag_context:
        sentences.append(str(record))
    return sentences


def _embed_texts(texts: List[str]) -> np.ndarray:
    """截断 + 分批 embed，避免单次请求输入超过 Ollama 模型上下文长度。"""
    clipped = [t[:_MAX_EMBED_CHARS] for t in texts]
    vectors: List[np.ndarray] = []
    for i in range(0, len(clipped), _EMBED_BATCH_SIZE):
        batch = clipped[i : i + _EMBED_BATCH_SIZE]
        vectors.extend(embeder(batch))
    return np.array(vectors)


async def _chat(prompt: str) -> str:
    resp = await ainvoke_with_metrics(_get_model(), [prompt], "faithfulness", model_name)
    return str(resp.content)


def _build_claims_prompt(answer: str, question: str, max_claims: int) -> str:
    """构造 claim 拆分 prompt：要求涉及股票时必须附带 6 位股票代码。"""
    return f"""请把下面这段回答拆成独立的、可验证的事实性陈述（claims）。
        要求：
        - 每个 claim 是完整的一句话
        - 只保留有事实内容的部分，去掉过渡语、态度词
        - 按原顺序输出，每行一个 claim，不要编号
        - 选取最重要的跟用户问题相关的{max_claims}个claim
        - 如果陈述涉及某只股票，必须附带该股票的6位股票代码，格式如：能科科技（603859）

        用户问题：
        {question}

        
        回答：
        {answer}

        Claims："""


async def _extract_claims(answer: str, question: str, max_claims: int) -> List[str]:
    prompt = _build_claims_prompt(answer, question, max_claims)
    text = await _chat(prompt)
    claims = [c.strip() for c in text.split("\n") if c.strip()]
    claims = [re.sub(r"^\d+[\.\)]\s*", "", c) for c in claims]
    # 兜底：模型可能不遵守"最多 N 条"，强制截断到 N 条
    return claims[:max_claims]


def _deterministic_sample_indices(items_len: int, cap: int) -> List[int]:
    """超过 cap 时按位置均匀抽样索引（确定性），避免随机抽样把关键证据丢掉。"""
    if items_len <= cap:
        return list(range(items_len))
    indices = np.linspace(0, items_len - 1, cap).round().astype(int)
    return list(dict.fromkeys(indices.tolist()))


def _deterministic_sample(items: List[str], cap: int) -> List[str]:
    """超过 cap 时按位置均匀抽样（确定性），避免随机抽样把关键证据丢掉。"""
    indices = _deterministic_sample_indices(len(items), cap)
    return [items[i] for i in indices]


async def _claim_support(claim: str, evidence: List[str]) -> float:
    """判断陈述被证据支持的程度：0.0 不支持 / 0.5 部分支持 / 1.0 完全支持。

    原实现是严格二值判定（需要额外推理即 No），结论/建议类陈述会被一刀切，
    导致 faithfulness 结构性偏低；改为三级打分后更接近真实支持度。
    """
    if not evidence:
        return 0.0
    evidence_text = "\n".join(f"- {s}" for s in evidence)
    prompt = f"""你是一个严格的事实核查员。请判断「陈述」是否完全被「证据」支持。

        规则：
        - 证据明确、完整支持该陈述：完全支持
        - 证据支持陈述的大部分内容，或只需少量常识推理：部分支持
        - 证据中没有依据，或需要大量额外推理：不支持
        - 只回答三个词之一：完全支持 / 部分支持 / 不支持

        陈述：
        {claim}

        证据：
        {evidence_text}

        判断："""
    ans = (await _chat(prompt)).strip()
    if ans.startswith("完全"):
        return 1.0
    if ans.startswith("部分"):
        return 0.5
    return 0.0


async def _claim_ok(
    claim,
    score,
    sem: asyncio.Semaphore,
    sentences,
    top_k
):
    async with sem:
        logger.debug(" debug claim ", claim[:10])
        k = min(top_k, len(sentences))
        top_local = np.argpartition(-score, k - 1)[:k]
        top_local = top_local[np.argsort(-score[top_local])]
        relevant = [
            sentences[j]
            for j in top_local
            if score[j] >= 0.25
        ]
        support = await _claim_support(claim, relevant)
        return {"claim": claim, "supported": support, "evidence": relevant}


async def caculate_faithfulness_score(
    answer: str,
    question: str,
    rag_context: list,
    max_claim_num: int = _MAX_CLAIM_NUM,
    max_cocurrency: int = 5,
    topk : int = 10,
):
    """faithfulness：把 answer 拆成 claims，用 rag_context 证据做支持度判定。"""
    claims = await _extract_claims(answer, question, max_claim_num)
    if not claims:
        return 0.0, []
    sentences = assemble_rag(rag_context)
    if not sentences:
        return 0.0, []

    claims = _deterministic_sample(claims, _SAMPLE_SIZE)
    sample_idx = _deterministic_sample_indices(len(sentences), _SAMPLE_SIZE)
    sentences = [sentences[i] for i in sample_idx]

    logger.debug("embed context and claim")
    sent_embs = _embed_texts(sentences)  # shape: (S, d)
    claim_embs = _embed_texts(claims)  # shape: (C, d)

    # 归一化成余弦相似度，避免未归一化 embedding 的点积被向量模长扭曲
    sent_embs = sent_embs / np.maximum(np.linalg.norm(sent_embs, axis=1, keepdims=True), 1e-12)
    claim_embs = claim_embs / np.maximum(np.linalg.norm(claim_embs, axis=1, keepdims=True), 1e-12)

    sem = asyncio.Semaphore(max_cocurrency)
    scores = claim_embs @ sent_embs.T

    jobs = [
        _claim_ok(
            claim,
            scores[i],
            sem,
            sentences=sentences,
            top_k=topk,
        )
        for i, claim in enumerate(claims)
    ]

    results = await asyncio.gather(*jobs)

    return sum(r["supported"] for r in results) / len(results), results


if __name__ == "__main__":
    state = {}
    state["news_items"] = [
        {"query": "AI应用 AI+软件 A股 2026年8月 投资机会 中报",
        "follow_up_questions": "", 
        "answer": """The user's query seeks an analysis of investment opportunities in AI applications, specifically focusing on the AI+ software sector within A-shares for August 2026, 
        along with the release of the first half-year report. The provided data includes various articles related to AI applications, market trends, 
        and specific company performances. The analysis will be presented in a paragraph format, focusing on the key points and insights from the data.
        """, 
        "images": [], 
        "results": [
                {
                    "url": "https://hk.finance.yahoo.com/news/%E7%B8%BE%E5%BE%8C-%E6%96%87%E7%B6%9C%E5%90%88%E5%A4%A7%E8%A1%8C%E6%96%BC%E9%98%BF%E9%87%8C%E5%B7%B4%E5%B7%B4-09988-hk-%E5%85%AC%E5%B8%83%E6%A5%AD%E7%B8%BE%E6%9C%80%E6%96%B0%E7%9B%AE%E6%A8%99%E5%83%B9%E5%8F%8A%E8%A7%80%E9%BB%9E-043931672.html", 
                    "title": "《績後》一文綜合大行於阿里巴巴(09988.HK)公布業績最新目標價及觀點", 
                    "content": """# 《績後》一文綜合大行於阿里巴巴(09988.HK)公布業績最新目標價及觀點. 《績後》一文綜合大行於阿里巴巴(09988.HK)公布業績最新目標價及觀點 · AASTOCKS. 阿里巴巴(BABA.US)(09988.HK)上周五(8月29日)公布2026財年首財(截至今年6月底止財季)季業績，外媒《華爾街日報》報道阿里擬打造新AI晶片後，
                    今早裂口高開近15%後，盤中曾高見137.5元一度彈高18.8%，半日報135.7元搶上17.3%，成交額375.5億元。摩根士丹利發表題為「中國最優質的人工智慧賦能者(指阿里)正在上演」報告，指阿里雲第二財季(截至今年9月底止財季)進一步加速增長，收入增速達30%以上，
                    雖料即時零售第二財季錄350億人民幣虧損，但管理層承擔未來一至兩個月每單位經濟虧損半，估計此應會見頂。. 阿里巴巴上周五(29日)公布截至6月止首財季業績，純利按年升78%至431.16億元人民幣；攤薄每股收益2.25元人民幣，攤薄每股美國存託股收益17.98元人民幣。
                    季度收入按年增長1.8%至2,476.52億元人民幣；若不考慮高鑫零售和銀泰的已處置業務的收入，同口徑收入按年增長10%。非公認會計準則淨利潤下降18%至335.1億元人民幣。非公認會計準則攤薄每股收益及攤薄每股美國存託股收益分別為1.84及14.75元人民幣。
                    非公認會計準則歸屬於普通股股東淨利潤按年跌12%至352.91億元人民幣，高於本網綜合7間券商預測中位數344億元人民幣。經調整EBITA按年跌13.7%至388.44億元人民幣，高於本網綜合10間券商預測上限的384億元人民幣。經調整EBITA利潤率16%，按年降3個百分點。
                    . 期內中國電商集團收入增長10%至1,400.72億元人民幣，客戶管理收入增長10%至892.52億元人民幣，阿里今年4月底推出「淘寶閃購」服務，在8月前三周成功帶動淘寶應用程式月度活躍消費者按年增長25%。現季88VIP會員數量持續雙位數按年升幅，達到超過5,300萬。
                    國際電商業務季度收入增長19%至347.41億元人民幣，季內接近盈虧平衡。雲智能集團收入按年升26%至333.98億元人民幣，主要來自公共雲業務收入增長推動，AI相關產品收入連續八個季度實現三位數按年升幅。所有其他業務收入跌28%至585.99億元人民幣。. ## 【管理層料即時零售未來兩個單位虧損將減半】.
                    摩根士丹利指，阿里巴巴首財季客戶管理收入按年升10%，主要由於收取率提升，預計全站營銷工具進一步滲透將提高收取率，而快商業投資將進一步推動廣告支出和流量，支持客戶管理數入可持續增長。該行引述公司指，即時零售在未來數季可推動客戶管理收入增長2至3個百分點，該行預計現財季客戶管理收入增長10%。
                    該行估計公司首財季對即時零售的投資約110億元人民幣，高峰日訂單量達1.2億，相比美團(03690.HK)的1.5億，8月平均周日訂單量8,000萬。預計現財季即時零售虧損將進一步擴大至350億元人民幣，預計全年即時零售投資將達800億元人民幣(此前預測虧損500億人民幣)。
                    該行下調對阿里巴巴現財年及下財年經調整淨利潤預測11%及7%，基於即時零售投資擴大，但上調長期預測。該行將關注即時零售單量對比單位經濟趨勢、以及與核心商業的協同效應，從而平估投資回報率。該行維持對阿里巴巴「增持」評級。
                    
                    """
                    
                }
            ]
        }
    ]
    state["user_question"] = "AI应用相关的股票推荐"
    state["final_answer"] = """# 下半年AI应用领域投资价值分析报告
    **报告日期：2026年8月8日**\n**分析师：您的专属A股投资顾问**
    ## 一、报告概述\n\n本报告基于您提供的20只AI相关股票的全维度数据（基本面、技术面、新闻面），结合当前政策环境与市场热点，为您挖掘2026年下半年AI应用领域最具投资价值的标的。核心结论：**AI应用已进入政策驱动与业绩兑现的共振期，工业AI、AI视觉、AI营销等垂直场景成为确定主线。建议积极配置基本面与技术面共振、且拥有真实业务落地的标的，同时严格控制风险。**\n\n## 二、市场背景与政策驱动\n\n- **政策密集落地**：国资委推进央企"AI+"专项行动，投产万卡计算集群；"人工智能+制造"三年行动计划要求重点行业AI应用覆盖率2027年前达60%以上；"人工智能+消费"写入扩大消费规划。\n- **产业催化不断**：WAIC 2026确立"算力—数据—应用"方向，世界机器人大会（8月8-12日）聚焦具身智能，国产GPU资本化高潮（沐曦、摩尔线程等）带动AI算力与应用关注度。\n- **资金偏好**：AI芯片、算力基础设施持续吸金，资金从消费向AI迁移，但题材股波动剧烈，需警惕情绪退潮。\n\n## 三、筛选标准与逻辑\n\n1. **基本面**：财务总得分及排名（盈利、成长、现金流、财务安全）。\n2. **技术面**：技术总得分及排名（趋势、动量、量能）。\n3. **新闻面**：政策驱动、机构关注、业务落地验证。\n4. **风险排除**：退市股（赛隆退）、业绩恶化（恒宝股份）、基本面与题材背离（盛视科技）、数据缺失（汉鑫科技）等。\n\n## 四、核心推荐标的深度分析\n\n### 第一梯队：基本面与技术面共振，中线核心配置\n\n#### 1. 能科科技（603859）\n- **核心逻辑**：工业软件+AI，直接受益"AI+制造"政策，机构资金（沪股通）持续买入，6月多次涨停。\n- **基本面**：财务总分0.54，盈利能力较强（0.72），安全边际尚可。\n- **技术面**：技术总分0.81，排名692，趋势与动量均接近0.9，强势特征明显。\n- **点评**：工业AI场景明确，机构认可度高，是工业AI方向的代表标的。\n\n#### 2. 科远智慧（002380）\n- **核心逻辑**：工业自动化+工业AI+机器人，受益"人工智能+制造"专项行动。\n- **基本面**：财务总分0.67，排名919，盈利能力优秀（0.84），成长性良好（0.64）。\n- **技术面**：技术总分0.58，处于上升通道。\n- **点评**：业绩有支撑，政策催化下具备持续增长潜力，但因前期涨幅较大，需注意回调。\n\n#### 3. 泰禾智能（603656）\n- **核心逻辑**：AI视觉识别成套装备，工业应用场景落地，一季报净利润同比+168.56%。\n- **基本面**：财务总分0.65，排名1035，成长性突出（0.88），盈利质量良好（0.76）。\n- **技术面**：技术总分0.59，趋势稳定。\n- **点评**：小而美的AI+制造标的，业绩改善+政策受益。\n\n#### 4. 魅视科技（001229）\n- **核心逻辑**：多模态AI视觉应用解决方案，6月获203家机构密集调研，AI产品收入高速增长。\n- **基本面**：财务总分0.43，盈利质量（0.78）与安全性（0.93）较好。\n- **技术面**：技术总分0.71，排名1173，动量得分0.83，短期动能强。\n- **点评**：AI应用落地先锋，机构关注度极高，但体量小，波动较大。\n\n### 第二梯队：技术面强势或题材弹性大，适合波段操作\n\n#### 5. 云天励飞（688343）\n- **核心逻辑**：AI推理芯片+算法芯片化，受益国产算力政策，获机构调研。\n- **基本面**：财务总分0.43，成长性（0.78）良好，但盈利能力弱。\n- **技术面**：技术总分0.72，排名1137，动量0.75，量能0.9（资金活跃）。\n- **点评**：作为国产AI芯片稀缺标的，政策预期强，但业绩尚未兑现，适合高风险偏好者。\n\n#### 6. 亚康股份（301085）\n- **核心逻辑**：算力全生命周期服务，直接受益AIDC建设与AI推理需求。\n- **基本面**：财务总分0.62，排名1352，盈利能力（0.72）与成长性（0.79）均良好。\n- **技术面**：技术总分0.60，稳健。\n- **点评**：算力服务细分领域，订单预期较强，但新闻催化较少。\n\n#### 7. 天娱数科（002354）——高弹性高风险\n- **核心逻辑**：天星大模型+AI营销+空间智能MaaS，基本面与技术面双优。\n- **基本面**：财务总分0.78，排名179，盈利与成长均优秀。\n- **技术面**：技术总分0.85，排名515，趋势0.94，极强。\n- **风险**：2025年仍亏损，股价高位巨震（曾4连板后大跌），纯情绪驱动，仅适合激进型投资者小仓位参与。\n\n### 其他值得关注的标的\n- **星网锐捷（002396）**：ICT基础设施+AI应用，走势稳健，但基本面一般，适合稳健型中线。\n- **汉王科技（002362）**：AI智能终端+多模态数据，华为生态概念，技术面尚可，但基本面弱。\n- **歌尔股份（002241）**：AI硬件终端（AR/VR），产业布局积极，但受消费电子周期影响。\n\n## 五、风险提示\n\n1. **高位回调风险**：部分标的技术指标已偏高，如天娱数科、能科科技，短期可能剧烈波动。\n2. **业绩证伪风险**：AI新业务若无实际收入支撑，易被公告证伪，需跟踪订单与收入确认。\n3. **政策落地不及预期**：AI应用渗透率目标推进缓慢将压制板块估值。\n4. **市场风格切换风险**：高利率环境下高估值科技股存在估值压缩风险。\n5. **个股风险**：赛隆退已进入退市整理期，恒宝股份业绩恶化，*ST智胜（002253）存在退市风险，均须回避。\n\n## 六、总结与操作建议\n\n- **投资建议**：积极（精选个股，控制仓位）\n- **建议仓位**：中（建议不超过总仓位五成，单一个股不超过15%）\n- **信心指数**：0.76\n- **推荐优先顺序**：\n  1. 能科科技（603859）\n  2. 科远智慧（002380）\n  3. 泰禾智能（603656）\n  4. 魅视科技（001229）\n  5. 亚康股份（301085）\n  6. 云天励飞（688343）\n  7. 天娱数科（002354，高风险）\n\n> 建议以第一梯队为核心持仓，第二梯队为辅，严格执行止损纪律。密切关注8月中报披露与AI政策落地节奏。\n\n**免责声明**：本报告基于公开数据和模型计算，不构成任何投资建议。股市有风险，投资需谨慎。', 'recommendation': '积极', 'key_reasons': ['政策强力驱动：央企AI+专项行动、人工智能+制造/消费政策密集落地，工业AI、AI应用渗透率目标明确，下半年催化事件丰富（WAIC、世界机器人大会等）。', '业绩兑现逻辑：科远智慧、泰禾智能等财务基本面排名靠前（财务总分0.65-0.67，排名1000左右），AI业务已产生实际收入，属于能落地的AI应用。', '技术面共振：能科科技、魅视科技、天娱数科等技术总分均超0.7，趋势与动量指标优异，资金关注度高。', '机构认可：能科科技获沪股通买入，魅视科技获203家机构密集调研，验证了产业逻辑。', '风险控制：明确回避赛隆退（退市）、恒宝股份（业绩恶化）、盛视科技（基本面弱）等风险标的，优选基本面支撑的标的。'], 'main_risks': ['高位波动风险：部分推荐标的技术面已偏高（如天娱数科、能科科技），短期可能剧烈回调。', '业绩证伪风险：AI新业务若无实质收入支撑，易出现公告证伪（如高乐股份案例），需紧密跟踪订单与收入确认。', '政策落地不及预期：AI应用渗透率目标若推进缓慢，板块估值将承压。', '市场风格切换风险：若市场风险偏好下降或利率上行，高估值科技股可能经历估值压缩。', '个股风险：赛隆退已进入退市流程，*ST智胜存在退市风险，恒宝股份基本面恶化，均须回避。"""

    logger.debug("start")
    from eval.rag_input import state_to_rag_context

    rag_context = state_to_rag_context(state)
    score, results = asyncio.run(
        caculate_faithfulness_score(
            state["final_answer"], state["user_question"], rag_context
        )
    )
    logger.debug("score is {}", score)

    results = [(r["claim"][:10], r["supported"], r["evidence"][:10]) for r in results ]
    print(results)
