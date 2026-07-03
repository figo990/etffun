from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import akshare as ak
import pandas as pd
import json
import os
import io
import requests
import warnings
import threading
from datetime import datetime, timedelta

app = Flask(__name__, static_folder='public')
CORS(app)
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# ---- helpers ----

def get_szse_scale():
    try:
        url = "https://fund.szse.cn/api/report/ShowReport"
        params = {"SHOWTYPE": "xlsx", "CATALOGID": "1000_lf", "TABKEY": "tab1", "random": "0.07610353191740105"}
        headers = {"Referer": "https://fund.szse.cn/marketdata/fundslist/index.html", "User-Agent": "Mozilla/5.0"}
        r = requests.get(url, params=params, headers=headers, timeout=30)
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            temp_df = pd.read_excel(io.BytesIO(r.content), engine="openpyxl", dtype={"基金代码": str})
        temp_df.rename(columns={"当前规模(份)": "基金份额"}, inplace=True)
        temp_df = temp_df[["基金代码", "基金简称", "基金类别", "基金份额", "基金管理人", "基金托管人", "净值"]]
        temp_df["基金份额"] = temp_df["基金份额"].astype(str).str.replace(",", "", regex=False)
        temp_df["基金份额"] = pd.to_numeric(temp_df["基金份额"], errors="coerce")
        temp_df["净值"] = pd.to_numeric(temp_df["净值"], errors="coerce")
        return temp_df
    except Exception as e:
        print(f"get_szse_scale error: {e}")
        return pd.DataFrame()

def to_ymd(dt):
    return dt.strftime('%Y%m%d')

def get_recent_trading_days(base, n=5):
    days = []
    d = base
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return [to_ymd(d) for d in days]

def load_json(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---- spot cache ----

_spot_cache = {'data': None, 'time': None}

def get_spot_data():
    now = datetime.now()
    if _spot_cache['data'] is not None and _spot_cache['time'] is not None:
        if (now - _spot_cache['time']).total_seconds() < 300:
            return _spot_cache['data']
    try:
        df = ak.fund_etf_spot_em()
        result = {}
        for _, row in df.iterrows():
            code = str(row['代码'])
            result[code] = {
                '最新价': float(row['最新价']) if pd.notna(row['最新价']) else None,
                '涨跌幅': float(row['涨跌幅']) if pd.notna(row['涨跌幅']) else None,
                '昨收': float(row['昨收']) if pd.notna(row['昨收']) else None,
                '成交额': float(row['成交额']) if pd.notna(row['成交额']) else None,
            }
        _spot_cache.update({'data': result, 'time': now})
        return result
    except Exception as e:
        print(f'get_spot_data error: {e}')
        return _spot_cache['data'] or {}

# ---- price snapshots for weekly/monthly price returns ----

PRICE_SNAPSHOT_PATH = os.path.join(DATA_DIR, 'price_snapshots.json')

def update_price_snapshot(spot_data, date_str):
    snapshots = load_json(PRICE_SNAPSHOT_PATH) or {}
    if date_str in snapshots:
        return snapshots
    prices = {}
    for code, info in spot_data.items():
        if info['最新价'] is not None:
            prices[code] = info['最新价']
    snapshots[date_str] = prices
    dates = sorted(snapshots.keys(), reverse=True)
    clean = {}
    for d in dates[:100]:
        clean[d] = snapshots[d]
    save_json(PRICE_SNAPSHOT_PATH, clean)
    return snapshots

def calc_batch_price_ret(spot_data, date_str, snapshots):
    if not snapshots:
        return {}, {}
    dates = sorted(snapshots.keys())
    try:
        idx = dates.index(date_str)
    except ValueError:
        for i, d in enumerate(dates):
            if d >= date_str:
                idx = i
                break
        else:
            idx = len(dates) - 1
    weekly_map, monthly_map = {}, {}
    for code, info in spot_data.items():
        cur = info.get('最新价')
        if cur is None:
            continue
        wp, mp = None, None
        for i in range(idx - 1, max(idx - 6, -1), -1):
            d = dates[i]
            if code in snapshots.get(d, {}) and snapshots[d][code] is not None:
                wp = snapshots[d][code]
                break
        if wp is None:
            for d in reversed(dates[:idx]):
                if code in snapshots.get(d, {}) and snapshots[d][code] is not None:
                    wp = snapshots[d][code]
                    break
        for i in range(idx - 1, max(idx - 21, -1), -1):
            d = dates[i]
            if code in snapshots.get(d, {}) and snapshots[d][code] is not None:
                mp = snapshots[d][code]
                break
        if mp is None:
            for d in reversed(dates[:idx]):
                if code in snapshots.get(d, {}) and snapshots[d][code] is not None:
                    mp = snapshots[d][code]
                    break
        weekly_map[code] = round((cur - wp) / wp * 100, 2) if wp and wp > 0 else None
        monthly_map[code] = round((cur - mp) / mp * 100, 2) if mp and mp > 0 else None
    return weekly_map, monthly_map

# ---- share snapshots for weekly/monthly share changes ----

SHARE_SNAPSHOT_PATH = os.path.join(DATA_DIR, 'share_snapshots.json')

def update_share_snapshot(share_map, date_str):
    snapshots = load_json(SHARE_SNAPSHOT_PATH) or {}
    if date_str in snapshots:
        return snapshots
    snapshots[date_str] = share_map
    dates = sorted(snapshots.keys(), reverse=True)
    clean = {}
    for d in dates[:100]:
        clean[d] = snapshots[d]
    save_json(SHARE_SNAPSHOT_PATH, clean)
    return snapshots

def calc_batch_share_change(share_map_today, date_str, snapshots):
    if not snapshots:
        return {}, {}, {}, {}
    dates = sorted(snapshots.keys())
    try:
        idx = dates.index(date_str)
    except ValueError:
        for i, d in enumerate(dates):
            if d >= date_str:
                idx = i
                break
        else:
            idx = len(dates) - 1
    weekly_chg_map, monthly_chg_map = {}, {}
    weekly_pct_map, monthly_pct_map = {}, {}
    for code, today in share_map_today.items():
        ws, ms = None, None
        for i in range(idx - 1, max(idx - 6, -1), -1):
            d = dates[i]
            if code in snapshots.get(d, {}) and snapshots[d][code] is not None:
                ws = snapshots[d][code]
                break
        if ws is None:
            for d in reversed(dates[:idx]):
                if code in snapshots.get(d, {}) and snapshots[d][code] is not None:
                    ws = snapshots[d][code]
                    break
        for i in range(idx - 1, max(idx - 21, -1), -1):
            d = dates[i]
            if code in snapshots.get(d, {}) and snapshots[d][code] is not None:
                ms = snapshots[d][code]
                break
        if ms is None:
            for d in reversed(dates[:idx]):
                if code in snapshots.get(d, {}) and snapshots[d][code] is not None:
                    ms = snapshots[d][code]
                    break
        weekly_chg_map[code] = round((today - ws) / 1e4, 2) if ws is not None else None
        monthly_chg_map[code] = round((today - ms) / 1e4, 2) if ms is not None else None
        weekly_pct_map[code] = round((today - ws) / ws * 100, 2) if ws and ws > 0 else None
        monthly_pct_map[code] = round((today - ms) / ms * 100, 2) if ms and ms > 0 else None
    return weekly_chg_map, monthly_chg_map, weekly_pct_map, monthly_pct_map

# ---- Huijin config ----

def load_huijin():
    path = os.path.join(BASE_DIR, 'huijin_config.json')
    cfg = load_json(path) or {}
    return cfg.get('持仓', {})

# ---- routes ----

_etf_cache = {'data': None, 'time': None}

def build_etf_data():
    today = datetime.now()
    today_str = to_ymd(today)
    trading_days = get_recent_trading_days(today, 25)
    data_date = None
    sse_today_df, sse_yesterday_df = pd.DataFrame(), pd.DataFrame()

    for d in trading_days:
        try:
            sse_today_df = ak.fund_etf_scale_sse(date=d)
            data_date = d
            break
        except:
            continue

    if data_date:
        for d in trading_days:
            if d >= data_date:
                continue
            try:
                sse_yesterday_df = ak.fund_etf_scale_sse(date=d)
                break
            except:
                continue

    szse_data = get_szse_scale()
    spot_data = get_spot_data()

    date_key = data_date or today_str
    price_snapshots = {}
    if spot_data:
        price_snapshots = update_price_snapshot(spot_data, date_key)
    weekly_ret_map, monthly_ret_map = calc_batch_price_ret(spot_data, date_key, price_snapshots)

    huijin = load_huijin()
    szse_yesterday_path = os.path.join(DATA_DIR, 'szse_yesterday.json')
    yesterday_snapshot = load_json(szse_yesterday_path)

    all_share_map = {}
    items = []

    if not sse_today_df.empty:
        sse_map = {}
        if not sse_yesterday_df.empty:
            sse_map = dict(zip(sse_yesterday_df['基金代码'].astype(str), sse_yesterday_df['基金份额']))
        for _, row in sse_today_df.iterrows():
            code = str(row['基金代码'])
            today_share = float(row['基金份额'])
            yesterday_share = float(sse_map[code]) if code in sse_map else None
            change_d = today_share - yesterday_share if yesterday_share is not None else None
            change_d_pct = round(change_d / yesterday_share * 100, 2) if yesterday_share and yesterday_share > 0 else None
            spot = spot_data.get(code, {})
            hj = huijin.get(code, {})
            all_share_map[code] = today_share
            items.append({
                '交易所': '沪', '代码': code, '名称': row['基金简称'],
                '日期': str(row['统计日期']),
                '总份额_亿': round(today_share / 1e8, 4),
                '份额日改变': round(change_d / 1e4, 2) if change_d is not None else None,
                '份额日改变比例': change_d_pct,
                '最新价': spot.get('最新价'),
                '涨跌幅': spot.get('涨跌幅'),
                '周涨跌幅': weekly_ret_map.get(code),
                '月涨跌幅': monthly_ret_map.get(code),
                '比汇金改变比': round(change_d / 1e8 / hj['汇金总持股(亿)'] * 100, 4) if change_d is not None and hj.get('汇金总持股(亿)') else None,
                '汇金持股_亿': hj.get('汇金总持股(亿)'),
            })

    if not szse_data.empty:
        today_snapshot = {}
        for _, row in szse_data.iterrows():
            code = str(row['基金代码'])
            today_share = float(row['基金份额'])
            today_snapshot[code] = today_share
        save_json(szse_yesterday_path, today_snapshot)

        for _, row in szse_data.iterrows():
            code = str(row['基金代码'])
            today_share = float(row['基金份额'])
            yesterday_share = yesterday_snapshot.get(code) if yesterday_snapshot else None
            change_d = today_share - yesterday_share if yesterday_share is not None else None
            change_d_pct = round(change_d / yesterday_share * 100, 2) if yesterday_share and yesterday_share > 0 else None
            spot = spot_data.get(code, {})
            hj = huijin.get(code, {})
            all_share_map[code] = today_share
            items.append({
                '交易所': '深', '代码': code, '名称': row['基金简称'],
                '日期': date_key,
                '总份额_亿': round(today_share / 1e8, 4),
                '份额日改变': round(change_d / 1e4, 2) if change_d is not None else None,
                '份额日改变比例': change_d_pct,
                '最新价': spot.get('最新价'),
                '涨跌幅': spot.get('涨跌幅'),
                '周涨跌幅': weekly_ret_map.get(code),
                '月涨跌幅': monthly_ret_map.get(code),
                '比汇金改变比': round(change_d / 1e8 / hj['汇金总持股(亿)'] * 100, 4) if change_d is not None and hj.get('汇金总持股(亿)') else None,
                '汇金持股_亿': hj.get('汇金总持股(亿)'),
            })

    share_snapshots = update_share_snapshot(all_share_map, date_key)
    w_chg, m_chg, w_pct, m_pct = calc_batch_share_change(all_share_map, date_key, share_snapshots)

    for item in items:
        code = item['代码']
        item['份额周改变'] = w_chg.get(code)
        item['份额月改变'] = m_chg.get(code)
        item['份额周改变比例'] = w_pct.get(code)
        item['份额月改变比例'] = m_pct.get(code)

    return items

@app.route('/api/etf/all')
def get_all_etf():
    now = datetime.now()
    if _etf_cache['data'] is not None and _etf_cache['time'] is not None:
        if (now - _etf_cache['time']).total_seconds() < 300:
            return jsonify(_etf_cache['data'])
    try:
        items = build_etf_data()
        _etf_cache.update({'data': items, 'time': now})
        return jsonify(items)
    except Exception as e:
        print(f"get_all_etf error: {e}")
        if _etf_cache['data'] is not None:
            return jsonify(_etf_cache['data'])
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

def auto_backfill():
    try:
        share_snapshots = load_json(SHARE_SNAPSHOT_PATH) or {}
        today = datetime.now()
        trading_days = get_recent_trading_days(today, 30)
        added = 0
        for d in trading_days:
            if d in share_snapshots:
                continue
            try:
                df = ak.fund_etf_scale_sse(date=d)
                if df.empty:
                    continue
                smap = {}
                for _, row in df.iterrows():
                    smap[str(row['基金代码'])] = float(row['基金份额'])
                share_snapshots[d] = smap
                added += 1
            except:
                continue
        if added:
            save_json(SHARE_SNAPSHOT_PATH, dict(sorted(share_snapshots.items())))
            print(f"Backfilled {added} days of SSE share data")
    except Exception as e:
        print(f"Backfill error: {e}")

def warm_cache():
    try:
        print("Warming cache...")
        auto_backfill()
        items = build_etf_data()
        _etf_cache.update({'data': items, 'time': datetime.now()})
        print(f"Cache warmed: {len(items)} ETFs")
    except Exception as e:
        print(f"Warm cache error: {e}")

if __name__ == '__main__':
    threading.Thread(target=warm_cache, daemon=True).start()
    app.run(host='127.0.0.1', port=5000, debug=False)
