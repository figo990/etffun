"""Test: queries imports and API routes"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['ETF_DB_PATH'] = os.path.join(os.path.dirname(__file__), '..', 'data', 'test_etf.duckdb')
os.environ['ETF_READ_DB_PATH'] = os.environ['ETF_DB_PATH']

# Test queries import
from db.queries import (
    upsert_kline, query_kline, get_codes_with_kline,
    upsert_sector_fund_flow, query_latest_sector_flow,
    upsert_index_valuation, query_latest_index_valuation,
    upsert_bond_yield, query_latest_bond_yield,
    upsert_margin_detail, query_latest_margin,
    get_all_codes,
    upsert_huijin_baseline, get_huijin_baseline, get_active_huijin_baseline,
    get_huijin_baseline_holders, seed_huijin_baselines_from_config,
    get_huijin_overview, get_huijin_series, get_cffex_position_rank,
)
print('queries.py imports OK')

# Test API routes import
from server.api.etf import etf_api
print('API routes OK')

# Test Flask app creates
from server.app import create_app
app = create_app()
print('Flask app OK')

# Test routes
with app.test_client() as c:
    r = c.get('/api/etf/kline?code=510050')
    assert r.status_code == 200
    print(f'/api/etf/kline: {r.status_code} {len(r.data)}B')
    
    r = c.get('/api/etf/sector-flow')
    assert r.status_code == 200
    print(f'/api/etf/sector-flow: {r.status_code} {len(r.data)}B')
    
    r = c.get('/api/etf/indices/valuation')
    assert r.status_code == 200
    print(f'/api/etf/indices/valuation: {r.status_code} {len(r.data)}B')
    
    r = c.get('/api/etf/bond-yield')
    assert r.status_code == 200
    print(f'/api/etf/bond-yield: {r.status_code} {len(r.data)}B')
    
    r = c.get('/api/etf/margin')
    assert r.status_code == 200
    print(f'/api/etf/margin: {r.status_code} {len(r.data)}B')

    r = c.get('/api/huijin/audit')
    assert r.status_code == 200
    print(f'/api/huijin/audit: {r.status_code} {len(r.data)}B')

    r = c.get('/api/huijin/overview')
    assert r.status_code == 200
    print(f'/api/huijin/overview: {r.status_code} {len(r.data)}B')

    r = c.get('/api/huijin/510300/series')
    assert r.status_code == 200
    print(f'/api/huijin/510300/series: {r.status_code} {len(r.data)}B')

    r = c.get('/api/huijin/cffex-position-rank')
    assert r.status_code == 200
    print(f'/api/huijin/cffex-position-rank: {r.status_code} {len(r.data)}B')

print('All API endpoints OK')
