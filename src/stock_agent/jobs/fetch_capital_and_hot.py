from datetime import datetime

import pandas as pd
import requests

from core.db import engine

def fetch_hot_sectors(pz=300):
    print("正在获取热门概念板块...")
    url = "https://79.push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": pz,
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",                    # 按涨跌幅排序
        "fs": "m:90 t:3 f:!50",
        "fields": "f2,f3,f4,f8,f12,f14,f15,f16,f17,f18,f20,f21,f24,f25,f22,f33,f11,f62,f128,f124,f107,f104,f105,f136",
    }
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        df = pd.DataFrame(data["data"]["diff"])
        
        rename_map = {
            "f12": "sector_code",
            "f14": "sector_name",
            "f3": "change_pct",
            "f2": "index_value",
            "f8": "turnover_rate",
            "f62": "net_inflow",
            "f128": "leading_stock_name",
            "f140": "leading_stock_code",
        }
        df = df.rename(columns=rename_map)
        
        df['date'] = datetime.now().date()
        df['sector_type'] = 'concept'
        df['fetch_time'] = datetime.now()
        df['attention_score'] = df['change_pct'].rank(pct=True)   # 简单热度分
        
        # 保存
        save_cols = [
            'date', 'sector_code', 'sector_name', 'sector_type',
            'change_pct', 'index_value', 'turnover_rate', 'net_inflow',
            'leading_stock_name', 'leading_stock_code',
            'attention_score', 'fetch_time'
        ]
        
        df[save_cols].to_sql('hot_sectors', engine, if_exists='append', index=False)
        print(f"✅ 保存成功，共 {len(df)} 条概念板块")
        return df
    except Exception as e:
        print(f"❌ 失败: {e}")
        return None
    

def fetch_capital_flow(pz=100):
    print("正在获取个股主力资金流排名...")
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": pz,
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f62",                    # 按主力净流入排序
        "fs": "m:0 t:6 f:!2",            # A股个股
        "fields": "f12,f14,f2,f3,f62,f184,f183,f105,f162,f109,f175,f177",
    }
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        df = pd.DataFrame(data["data"]["diff"])
        
        rename_map = {
            "f12": "code",
            "f14": "name",
            "f62": "main_net_inflow",     # 主力净流入
            "f184": "large_net_inflow",   # 大单
            "f3": "change_pct",
        }
        df = df.rename(columns=rename_map)
        
        df['date'] = datetime.now().date()
        df['code'] = df['code'].str.zfill(6)
        
        save_cols = ['code', 'date', 'main_net_inflow', 'large_net_inflow', 'change_pct']
        
        df[save_cols].to_sql('capital_flow', engine, if_exists='append', index=False)
        print(f"✅ 主力资金流保存成功，共 {len(df)} 条")
        return df
    except Exception as e:
        print(f"❌ 资金流获取失败: {e}")
        return None
    
if __name__ == "__main__":
    # fetch_hot_sectors()
    fetch_capital_flow()