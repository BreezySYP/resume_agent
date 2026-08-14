
import asyncio
from datetime import datetime

from agent.tools import search_stock_profile
from eval.faithfulness import caculate_faithfulness_score
from eval.golden_standard import get_golden_standard
from loguru import logger
from observe.metrics import record_eval_scores, track_eval_run
from shared.agents.agent_state import AgentState
from shared.configs.tracing import get_tracer
from shared.metrics.prome import ainvoke_with_metrics
from shared.models.deepseek import get_deepseek
from shared.rag.eval import push_to_langsmith

_tracer = get_tracer("stock_agent.ragas")

_SEARCH_WIDTH = 200


async def calculate_scores(state: AgentState):
    answer = state.get("final_answer")
    question = state.get("user_question")
    stock_profile = state.get("stock_profile")
    run_id = state.get("job_id")

    if run_id is None:
        logger.error("failed to give feedback: run_id is None")
        return []
    # stock_news = state.get("stock_news")
        
    # 2. Answer Relevancy：回答是否切题
    rel_prompt = f"""请判断下面的回答与问题的相关程度。
        只输出 0 到 1 的分数（1 表示非常相关）。

        问题：{question}
        回答：{answer}

        分数："""

    async def get_relavance():
        logger.debug("get relavance")
        model_name = "deepseek-chat"
        model = get_deepseek(model=model_name)
        result = await ainvoke_with_metrics(model, rel_prompt, "relavance", model_name)
        return float(result.content.strip()[:4])

    with track_eval_run():
        candidate = search_stock_profile.invoke({"query": question, "topk": _SEARCH_WIDTH})

        (faith_score, results), goldenStandard, rel_score = await asyncio.gather(caculate_faithfulness_score(state),
                                                    get_golden_standard(question, candidate), get_relavance())
        retrived_codes = [profile["code"] for profile in stock_profile]
        common_codes = set(goldenStandard) & set(retrived_codes)
        profile_recall = ( len(common_codes) / len(goldenStandard) ) if goldenStandard else 0.0
        profile_precision = (len(common_codes) / len(retrived_codes)) if retrived_codes else 0.0

        scores = {
            "faithfulness": faith_score,
            "answer_relevancy": rel_score,
            "profile_recall": profile_recall,
            "profile_precision": profile_precision,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "question": question[:80],
        }
        record_eval_scores(scores=scores)
        push_to_langsmith(scores, question, answer, run_id)
        return scores



if  __name__ == "__main__":
    state = AgentState()
    from uuid import uuid4

    state["job_id"] = uuid4()
    state["stock_profile"] = data = [
        {
            "rank": 1,
            "business": "研发、设计和销售应用于人工智能训练和推理、通用计算与图形渲染领域的全栈GPU产品，并围绕GPU芯片提供配套的软件栈与计算平台。",
            "code": "688802",
            "name": "沐曦股份",
            "update_time": "2026-07-06 05:57:01",
            "id": 5210,
            "original_score": 0.05,
            "rerank_score": 0.07463503889650006
        },
        {
            "rank": 2,
            "business": "提供分布式视听与多模态AI视觉应用的解决方案。",
            "code": "001229",
            "name": "魅视科技",
            "update_time": "2026-07-05 15:06:51",
            "id": 440,
            "original_score": 0.5,
            "rerank_score": 0.06477170097147576
        },
        {
            "rank": 3,
            "business": "ICT基础设施与AI应用方案的研发、生产和销售。",
            "code": "002396",
            "name": "星网锐捷",
            "update_time": "2026-07-05 15:23:31",
            "id": 907,
            "original_score": 0.25,
            "rerank_score": 0.06244528561398407
        },
        {
            "rank": 4,
            "business": "AI与内容驱动的数字消费服务。",
            "code": "300785",
            "name": "值得买",
            "update_time": "2026-07-05 16:13:09",
            "id": 2232,
            "original_score": 0.125,
            "rerank_score": 0.0483160702678493
        }
    ]
    state["rag_contexts"] = [
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

    state["user_question"] = "ai应用前景怎么样"
    state["final_answer"] = """# 下半年AI应用领域投资价值分析报告
    **报告日期：2026年8月8日**\n**分析师：您的专属A股投资顾问**
    ## 一、报告概述\n\n本报告基于您提供的20只AI相关股票的全维度数据（基本面、技术面、新闻面），结合当前政策环境与市场热点，为您挖掘2026年下半年AI应用领域最具投资价值的标的。核心结论：**AI应用已进入政策驱动与业绩兑现的共振期，工业AI、AI视觉、AI营销等垂直场景成为确定主线。建议积极配置基本面与技术面共振、且拥有真实业务落地的标的，同时严格控制风险。**\n\n## 二、市场背景与政策驱动\n\n- **政策密集落地**：国资委推进央企"AI+"专项行动，投产万卡计算集群；"人工智能+制造"三年行动计划要求重点行业AI应用覆盖率2027年前达60%以上；"人工智能+消费"写入扩大消费规划。\n- **产业催化不断**：WAIC 2026确立"算力—数据—应用"方向，世界机器人大会（8月8-12日）聚焦具身智能，国产GPU资本化高潮（沐曦、摩尔线程等）带动AI算力与应用关注度。\n- **资金偏好**：AI芯片、算力基础设施持续吸金，资金从消费向AI迁移，但题材股波动剧烈，需警惕情绪退潮。\n\n## 三、筛选标准与逻辑\n\n1. **基本面**：财务总得分及排名（盈利、成长、现金流、财务安全）。\n2. **技术面**：技术总得分及排名（趋势、动量、量能）。\n3. **新闻面**：政策驱动、机构关注、业务落地验证。\n4. **风险排除**：退市股（赛隆退）、业绩恶化（恒宝股份）、基本面与题材背离（盛视科技）、数据缺失（汉鑫科技）等。\n\n## 四、核心推荐标的深度分析\n\n### 第一梯队：基本面与技术面共振，中线核心配置\n\n#### 1. 能科科技（603859）\n- **核心逻辑**：工业软件+AI，直接受益"AI+制造"政策，机构资金（沪股通）持续买入，6月多次涨停。\n- **基本面**：财务总分0.54，盈利能力较强（0.72），安全边际尚可。\n- **技术面**：技术总分0.81，排名692，趋势与动量均接近0.9，强势特征明显。\n- **点评**：工业AI场景明确，机构认可度高，是工业AI方向的代表标的。\n\n#### 2. 科远智慧（002380）\n- **核心逻辑**：工业自动化+工业AI+机器人，受益"人工智能+制造"专项行动。\n- **基本面**：财务总分0.67，排名919，盈利能力优秀（0.84），成长性良好（0.64）。\n- **技术面**：技术总分0.58，处于上升通道。\n- **点评**：业绩有支撑，政策催化下具备持续增长潜力，但因前期涨幅较大，需注意回调。\n\n#### 3. 泰禾智能（603656）\n- **核心逻辑**：AI视觉识别成套装备，工业应用场景落地，一季报净利润同比+168.56%。\n- **基本面**：财务总分0.65，排名1035，成长性突出（0.88），盈利质量良好（0.76）。\n- **技术面**：技术总分0.59，趋势稳定。\n- **点评**：小而美的AI+制造标的，业绩改善+政策受益。\n\n#### 4. 魅视科技（001229）\n- **核心逻辑**：多模态AI视觉应用解决方案，6月获203家机构密集调研，AI产品收入高速增长。\n- **基本面**：财务总分0.43，盈利质量（0.78）与安全性（0.93）较好。\n- **技术面**：技术总分0.71，排名1173，动量得分0.83，短期动能强。\n- **点评**：AI应用落地先锋，机构关注度极高，但体量小，波动较大。\n\n### 第二梯队：技术面强势或题材弹性大，适合波段操作\n\n#### 5. 云天励飞（688343）\n- **核心逻辑**：AI推理芯片+算法芯片化，受益国产算力政策，获机构调研。\n- **基本面**：财务总分0.43，成长性（0.78）良好，但盈利能力弱。\n- **技术面**：技术总分0.72，排名1137，动量0.75，量能0.9（资金活跃）。\n- **点评**：作为国产AI芯片稀缺标的，政策预期强，但业绩尚未兑现，适合高风险偏好者。\n\n#### 6. 亚康股份（301085）\n- **核心逻辑**：算力全生命周期服务，直接受益AIDC建设与AI推理需求。\n- **基本面**：财务总分0.62，排名1352，盈利能力（0.72）与成长性（0.79）均良好。\n- **技术面**：技术总分0.60，稳健。\n- **点评**：算力服务细分领域，订单预期较强，但新闻催化较少。\n\n#### 7. 天娱数科（002354）——高弹性高风险\n- **核心逻辑**：天星大模型+AI营销+空间智能MaaS，基本面与技术面双优。\n- **基本面**：财务总分0.78，排名179，盈利与成长均优秀。\n- **技术面**：技术总分0.85，排名515，趋势0.94，极强。\n- **风险**：2025年仍亏损，股价高位巨震（曾4连板后大跌），纯情绪驱动，仅适合激进型投资者小仓位参与。\n\n### 其他值得关注的标的\n- **星网锐捷（002396）**：ICT基础设施+AI应用，走势稳健，但基本面一般，适合稳健型中线。\n- **汉王科技（002362）**：AI智能终端+多模态数据，华为生态概念，技术面尚可，但基本面弱。\n- **歌尔股份（002241）**：AI硬件终端（AR/VR），产业布局积极，但受消费电子周期影响。\n\n## 五、风险提示\n\n1. **高位回调风险**：部分标的技术指标已偏高，如天娱数科、能科科技，短期可能剧烈波动。\n2. **业绩证伪风险**：AI新业务若无实际收入支撑，易被公告证伪，需跟踪订单与收入确认。\n3. **政策落地不及预期**：AI应用渗透率目标推进缓慢将压制板块估值。\n4. **市场风格切换风险**：高利率环境下高估值科技股存在估值压缩风险。\n5. **个股风险**：赛隆退已进入退市整理期，恒宝股份业绩恶化，*ST智胜（002253）存在退市风险，均须回避。\n\n## 六、总结与操作建议\n\n- **投资建议**：积极（精选个股，控制仓位）\n- **建议仓位**：中（建议不超过总仓位五成，单一个股不超过15%）\n- **信心指数**：0.76\n- **推荐优先顺序**：\n  1. 能科科技（603859）\n  2. 科远智慧（002380）\n  3. 泰禾智能（603656）\n  4. 魅视科技（001229）\n  5. 亚康股份（301085）\n  6. 云天励飞（688343）\n  7. 天娱数科（002354，高风险）\n\n> 建议以第一梯队为核心持仓，第二梯队为辅，严格执行止损纪律。密切关注8月中报披露与AI政策落地节奏。\n\n**免责声明**：本报告基于公开数据和模型计算，不构成任何投资建议。股市有风险，投资需谨慎。', 'recommendation': '积极', 'key_reasons': ['政策强力驱动：央企AI+专项行动、人工智能+制造/消费政策密集落地，工业AI、AI应用渗透率目标明确，下半年催化事件丰富（WAIC、世界机器人大会等）。', '业绩兑现逻辑：科远智慧、泰禾智能等财务基本面排名靠前（财务总分0.65-0.67，排名1000左右），AI业务已产生实际收入，属于能落地的AI应用。', '技术面共振：能科科技、魅视科技、天娱数科等技术总分均超0.7，趋势与动量指标优异，资金关注度高。', '机构认可：能科科技获沪股通买入，魅视科技获203家机构密集调研，验证了产业逻辑。', '风险控制：明确回避赛隆退（退市）、恒宝股份（业绩恶化）、盛视科技（基本面弱）等风险标的，优选基本面支撑的标的。'], 'main_risks': ['高位波动风险：部分推荐标的技术面已偏高（如天娱数科、能科科技），短期可能剧烈回调。', '业绩证伪风险：AI新业务若无实质收入支撑，易出现公告证伪（如高乐股份案例），需紧密跟踪订单与收入确认。', '政策落地不及预期：AI应用渗透率目标若推进缓慢，板块估值将承压。', '市场风格切换风险：若市场风险偏好下降或利率上行，高估值科技股可能经历估值压缩。', '个股风险：赛隆退已进入退市流程，*ST智胜存在退市风险，恒宝股份基本面恶化，均须回避。"""

    logger.add("begin")
    asyncio.run(calculate_scores(state))
    logger.success("done")