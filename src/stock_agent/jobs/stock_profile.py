import random

import akshare as ak
import pandas as pd
import requests
from core.db import engine, insert_ignore
from datetime import datetime
import time
from loguru import logger
import pandas as pd

from data.coderule import add_prefix

def stock_zygc_em(symbol: str = "SH688041") -> pd.DataFrame:
    """
    东方财富网-个股-主营构成
    https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/Index?type=web&code=SH688041#
    :param symbol: 带市场标识的股票代码
    :type symbol: str
    :return: 主营构成
    :rtype: pandas.DataFrame
    """
    url = "https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/PageAjax"
    params = {"code": symbol}
    r = requests.get(url, params=params)
    data_json = r.json()
    if 'status' in data_json.keys() and data_json['status'] < 0:
        logger.error(f"error call for {symbol} {data_json}")
        return pd.DataFrame()
    temp_df = pd.DataFrame(data_json["zygcfx"])
    if  temp_df.empty:
        return temp_df
    temp_df.rename(
        columns={
            "SECUCODE": "-",
            "SECURITY_CODE": "股票代码",
            "REPORT_DATE": "报告日期",
            "MAINOP_TYPE": "分类类型",
            "ITEM_NAME": "主营构成",
            "MAIN_BUSINESS_INCOME": "主营收入",
            "MBI_RATIO": "收入比例",
            "MAIN_BUSINESS_COST": "主营成本",
            "MBC_RATIO": "成本比例",
            "MAIN_BUSINESS_RPOFIT": "主营利润",
            "MBR_RATIO": "利润比例",
            "GROSS_RPOFIT_RATIO": "毛利率",
            "RANK": "-",
        },
        inplace=True,
    )

    temp_df = temp_df[
        [
            "股票代码",
            "报告日期",
            "分类类型",
            "主营构成",
            "主营收入",
            "收入比例",
            "主营成本",
            "成本比例",
            "主营利润",
            "利润比例",
            "毛利率",
        ]
    ]
    temp_df["报告日期"] = pd.to_datetime(temp_df["报告日期"], errors="coerce").dt.date
    temp_df["分类类型"] = temp_df["分类类型"].map(
        {"1": "按行业分类", "2": "按产品分类", "3": "按地区分类"}
    )
    temp_df["主营收入"] = pd.to_numeric(temp_df["主营收入"], errors="coerce")
    temp_df["收入比例"] = pd.to_numeric(temp_df["收入比例"], errors="coerce")
    temp_df["主营成本"] = pd.to_numeric(temp_df["主营成本"], errors="coerce")
    temp_df["成本比例"] = pd.to_numeric(temp_df["成本比例"], errors="coerce")
    temp_df["主营利润"] = pd.to_numeric(temp_df["主营利润"], errors="coerce")
    temp_df["利润比例"] = pd.to_numeric(temp_df["利润比例"], errors="coerce")
    temp_df["毛利率"] = pd.to_numeric(temp_df["毛利率"], errors="coerce")
    return temp_df


def get_board():

    codes = [(c["code"], c["name"]) for c in ak.stock_info_a_code_name().to_dict("records") if c["code"] >= '689009']

    for code, name in codes:
        df1 = ak.stock_zyjs_ths(code)
        df_profile = df1[["股票代码", "主营业务", "经营范围"]].rename(columns={
            "股票代码":"code",
            "主营业务":"business",
            "经营范围":"scope"
        })
        
        df_profile["update_time"] = datetime.now()
        df_profile["name"] = name
        
        df_profile.to_sql("stock_profile", engine, if_exists="append", index=False, method=insert_ignore)
        
        logger.info(f"saved {len(df_profile)} to stock_profile for {code} {name}")
        
        time.sleep(random.uniform(1, 2))
        df2 = stock_zygc_em(add_prefix(code, upper=True))
        if df2.empty:
            logger.warning(f"no zygc for {code} {name}")
            continue
        df_break = df2.rename(columns={
            "股票代码":"code",
            "报告日期":"report_date",
            "分类类型":"category_type",
            "主营构成":"category_name",
            "主营收入":"revenue",
            "收入比例":"revenue_ratio",
            "主营成本":"cost",
            "成本比例":"cost_ratio",
            "主营利润":"profit",
            "利润比例":"profit_ratio",
            "毛利率":"gross_margin"
        })
        df_break["name"] = name
        df_break.to_sql("stock_business_breakdown", engine, if_exists="append", index=False, method=insert_ignore)
        logger.info(f"saved {len(df_break)} to stock_business_breakdown for {code} {name}")
        time.sleep(random.uniform(1, 2))
    logger.success("saved stock_business_breakdown and stock_profile")

if __name__ == "__main__":
    get_board()