"""stock_dashboard/schemas.py — Pydantic 响应模型"""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ── Links ────────────────────────────────────────────────────────────────────

class StockLinks(BaseModel):
    eastmoney:   str = ""
    xueqiu:      str = ""
    tonghuashun: str = ""


# ── Step Status ───────────────────────────────────────────────────────────────

class CheckpointInfo(BaseModel):
    start_date:          Optional[str] = None
    start_code:          Optional[str] = None
    last_completed_date: Optional[str] = None
    last_completed_at:   Optional[datetime] = None


class StepStatus(BaseModel):
    step:         str                       = Field(..., description="step 名称")
    status:       Optional[str]             = Field(None, description="pending/running/success/failed")
    last_success: Optional[datetime]        = Field(None, description="最后一次成功时间")
    row_count:    int                       = Field(0,    description="最近一次处理行数")
    error_msg:    Optional[str]             = Field(None, description="最近一次错误信息")
    checkpoint:   Optional[CheckpointInfo]  = Field(None, description="断点信息")


# ── Stock ────────────────────────────────────────────────────────────────────

class StockBase(BaseModel):
    code: str = Field(..., description="股票代码，如 600519")
    name: str = Field(..., description="股票名称")


class StockSummary(StockBase):
    """股票列表行数据，含各 step 最新状态"""
    latest_close: Optional[float]          = Field(None, description="最新收盘价")
    latest_date:  Optional[datetime]       = Field(None, description="最新数据日期")
    step_status:  dict[str, StepStatus]    = Field(default_factory=dict, description="各 step 的最新状态")
    links:        StockLinks               = Field(default_factory=StockLinks)

    class Config:
        from_attributes = True


class StockListResponse(BaseModel):
    total:     int
    page:      int
    page_size: int
    items:     List[StockSummary]


# ── ETL Job ───────────────────────────────────────────────────────────────────

class JobLog(BaseModel):
    id:           int
    code:         str
    step:         str
    status:       str
    triggered_by: str
    started_at:   Optional[datetime]
    finished_at:  Optional[datetime]
    duration_ms:  Optional[int]
    row_count:    int
    error_msg:    Optional[str]

    class Config:
        from_attributes = True


class TriggerRequest(BaseModel):
    code:  str       = Field(..., description="股票代码，全量触发时传 ALL")
    steps: List[str] = Field(..., description="要执行的 step 列表")


class TriggerResponse(BaseModel):
    job_ids: List[int] = Field(..., description="创建的 job log id 列表")
    message: str


# ── Stock Detail ──────────────────────────────────────────────────────────────

class OHLCRow(BaseModel):
    date:         datetime
    open:         Optional[float]
    high:         Optional[float]
    low:          Optional[float]
    close:        Optional[float]
    volume:       Optional[float]
    price_change: Optional[float]

    class Config:
        from_attributes = True


class NewsRow(BaseModel):
    id:      int
    title:   str
    content: Optional[str]
    source:  Optional[str]
    url:     Optional[str]
    date:    Optional[datetime]

    class Config:
        from_attributes = True


class FinancialRow(BaseModel):
    report_date: Optional[datetime]
    revenue:     Optional[float]
    net_profit:  Optional[float]
    eps:         Optional[float]
    roe:         Optional[float]
    report_type: Optional[str]

    class Config:
        from_attributes = True


class ProfileRow(BaseModel):
    code:          str
    name:          Optional[str]
    industry:      Optional[str]
    main_business: Optional[str]
    employees:     Optional[int]
    listing_date:  Optional[datetime]

    class Config:
        from_attributes = True


class StockDetail(BaseModel):
    code:      str
    name:      str
    profile:   Optional[ProfileRow] = None
    ohlc:      List[OHLCRow]        = []
    news:      List[NewsRow]        = []
    financial: List[FinancialRow]   = []
    links:     StockLinks           = Field(default_factory=StockLinks)


# ── SSE Event ─────────────────────────────────────────────────────────────────

class SSEEvent(BaseModel):
    job_id:   int
    code:     str
    step:     str
    status:   str
    message:  str
    progress: Optional[float] = None   # 0.0 ~ 1.0


# ── Pipeline ──────────────────────────────────────────────────────────────────

class PipelineStatus(BaseModel):
    steps:        List[str]    = Field(..., description="所有可用 step")
    daily_steps:  List[str]    = Field(..., description="每日默认 step")
    season_steps: List[str]    = Field(..., description="季报默认 step")
    running_jobs: List[JobLog] = Field(default_factory=list)