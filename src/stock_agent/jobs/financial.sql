CREATE TABLE financial_statement (
    code VARCHAR(20),
    name VARCHAR(100),
    report_date DATE,

    -- ===== 核心利润 =====
    revenue DOUBLE COMMENT '营业收入',
    net_profit DOUBLE COMMENT '归母净利润',
    deduct_net_profit DOUBLE COMMENT '扣非净利润',

    -- ===== 盈利能力 =====
    roe DOUBLE COMMENT '净资产收益率(ROE)',
    roa DOUBLE COMMENT '总资产收益率(ROA)',
    gross_margin DOUBLE COMMENT '毛利率',
    net_margin DOUBLE COMMENT '销售净利率',

    -- ===== 成长性 =====
    revenue_growth DOUBLE COMMENT '营业收入增长率',
    profit_growth DOUBLE COMMENT '归母净利润增长率',

    -- ===== 现金流 =====
    operating_cashflow DOUBLE COMMENT '经营现金流量净额',
    fcf DOUBLE COMMENT '自由现金流(每股/总量统一后)',

    -- ===== 杠杆 =====
    asset_liability_ratio DOUBLE COMMENT '资产负债率',
    equity_multiplier DOUBLE COMMENT '权益乘数',

    -- ===== 每股指标 =====
    eps DOUBLE COMMENT '每股收益',
    bvps DOUBLE COMMENT '每股净资产',
    ocfps DOUBLE COMMENT '每股经营现金流',

    PRIMARY KEY(code, report_date)
);

CREATE TABLE financial_feature (
    code VARCHAR(20),
    report_date DATE,

    revenue DOUBLE,
    net_profit DOUBLE,
    operating_cashflow DOUBLE,

    fcf_ratio DOUBLE,
    revenue_growth DOUBLE,
    profit_growth DOUBLE,

    roe DOUBLE,
    roa DOUBLE,
    leverage DOUBLE,

    PRIMARY KEY(code, report_date)
);

CREATE TABLE financial_factor (
    code VARCHAR(20),
    report_date DATE,

    -- 盈利能力
    profitability_score DOUBLE,

    -- 成长性
    growth_score DOUBLE,

    -- 财务质量
    quality_score DOUBLE,

    -- 安全性
    safety_score DOUBLE,

    -- 综合评分
    total_score DOUBLE,

    -- 排名
    profitability_rank INT,
    growth_rank INT,
    quality_rank INT,
    safety_rank INT,
    total_rank INT,

    PRIMARY KEY(code, report_date)
);

CREATE TABLE IF NOT EXISTS stock_factor (
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    date DATE NOT NULL,
    
    -- 技术面
    total_technical_score DOUBLE,
    technical_rank INT,
    trend_score DOUBLE,
    momentum_score DOUBLE,
    volume_score DOUBLE,
    
    -- 财务面
    total_financial_score DOUBLE,
    financial_rank INT,
    profitability_score DOUBLE,
    growth_score DOUBLE,
    quality_score DOUBLE,
    safety_score DOUBLE,
    
    -- 估值面（阶段1新增）
    pe_ttm DOUBLE,
    pb DOUBLE,
    peg DOUBLE,
    dividend_yield DOUBLE,
    valuation_score DOUBLE,
    
    -- 综合（动态计算，可存最新版）
    total_composite_score DOUBLE,
    composite_rank INT,
    
    -- 辅助字段
    market_cap DOUBLE,
    industry VARCHAR(100),
    sw_level1 VARCHAR(50),
    
    PRIMARY KEY (code, date)
);

CREATE OR REPLACE VIEW latest_stock_factor AS
SELECT * FROM stock_factor 
WHERE date = (SELECT MAX(date) FROM stock_factor);


DROP TABLE IF EXISTS capital_flow;

CREATE TABLE IF NOT EXISTS capital_flow (
    code VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    
    main_net_inflow DOUBLE,           -- 主力净流入（核心）
    large_net_inflow DOUBLE,          -- 大单
    northbound_net_inflow DOUBLE,     -- 北向资金（强烈建议保留）
    turnover_rate DOUBLE,             -- 换手率
    
    -- 可选扩展
    fetch_time TIMESTAMP,
    
    PRIMARY KEY (code, date)
);

-- 热门板块表
CREATE TABLE IF NOT EXISTS hot_sectors (
    date DATE NOT NULL,
    sector_name VARCHAR(100) NOT NULL,
    sector_type VARCHAR(20),          -- 'industry' 或 'concept'
    rank INT,
    rise_pct DOUBLE,
    turnover DOUBLE,
    top_stocks TEXT,                  -- JSON 字符串存储龙头股
    attention_score DOUBLE,
    PRIMARY KEY (date, sector_name)
);

-- 在 stock_factor 中增加字段（如果还没加）
ALTER TABLE stock_factor 
ADD COLUMN IF NOT EXISTS capital_flow_score DOUBLE,
ADD COLUMN IF NOT EXISTS hot_score DOUBLE;

-- 公告表
DROP TABLE IF EXISTS stock_news;

CREATE TABLE IF NOT EXISTS stock_news (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(20),
    title TEXT,
    publish_time TIMESTAMP,
    source VARCHAR(100),
    content MEDIUMTEXT,           -- 新闻正文
    summary TEXT,                 -- 摘要
    embedding TEXT,               -- 把向量转成 JSON 字符串存储（如 [0.1, 0.2, ...]）
    fetch_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_code (code),
    INDEX idx_publish (publish_time)
);
DROP TABLE IF EXISTS announcements;

CREATE TABLE IF NOT EXISTS announcements (
    announce_id VARCHAR(50) PRIMARY KEY,
    code VARCHAR(20),
    name VARCHAR(100),
    announce_date DATE,
    title TEXT,
    content MEDIUMTEXT,
    category VARCHAR(50),
    key_entities TEXT,            -- 改成 TEXT 存 JSON 字符串
    fetch_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_code_date (code, announce_date)
);

CREATE TABLE stock_news (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    
    -- 唯一标识（去重核心）
    unique_id VARCHAR(64) NOT NULL UNIQUE,
    
    -- 基础信息
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    title TEXT NOT NULL,
    content MEDIUMTEXT,                    -- 新闻正文/摘要
    summary TEXT,                          -- 短摘要（用于显示）
    
    -- 时间信息
    publish_time DATETIME NOT NULL,
    fetch_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- 来源与分类
    source VARCHAR(100),
    url TEXT,
    source_type ENUM('news', 'announcement', 'report') DEFAULT 'news',
    
    -- 元数据（用于过滤和因子关联）
    sector VARCHAR(50),                    -- 申万行业/概念
    importance_score FLOAT DEFAULT 0.5,    -- 可后续由LLM打分
    keywords JSON,                         -- 提取的关键词数组
    
    -- 向量检索辅助（如果需要存 embedding）
    embedding TEXT,                        -- JSON 格式向量（可选）
    
    -- 索引优化
    INDEX idx_code_time (code, publish_time),
    INDEX idx_unique (unique_id),
    INDEX idx_publish (publish_time),
    INDEX idx_source_type (source_type),
    FULLTEXT INDEX ft_title_content (title, content)   -- 关键词搜索
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 
  COMMENT='全市场新闻表 - 支持全局RAG和因子发现';

CREATE TABLE stock_profile (
    code VARCHAR(10) PRIMARY KEY,
    name VARCHAR(30),
    business TEXT,
    scope TEXT,
    update_time DATETIME
);


CREATE TABLE stock_business_breakdown (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(30),
    code VARCHAR(10),
    report_date DATE,
    category_type VARCHAR(50),
    category_name VARCHAR(100),
    revenue DOUBLE,
    revenue_ratio DOUBLE,
    cost DOUBLE,
    cost_ratio DOUBLE,
    profit DOUBLE,
    profit_ratio DOUBLE,
    gross_margin DOUBLE
);
