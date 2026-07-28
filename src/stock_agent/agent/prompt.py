from langchain_core.messages import SystemMessage



# ==================== 子节点专用 Prompt 示例 ====================
PROFILE_PROMPT = SystemMessage(content="你是公司研究员，专注于提取公司业务、经营范围和核心竞争力。")
NEWS_PROMPT = SystemMessage(content="你是新闻分析师，重点关注最新事件对股价的潜在影响。向量数据库查询相关行业信息。利用")