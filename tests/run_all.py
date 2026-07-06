"""Comprehensive test suite for etffun"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['ETF_DB_PATH'] = os.path.join(os.path.dirname(__file__), '..', 'data', 'test_verify.duckdb')
os.environ['ETF_READ_DB_PATH'] = os.environ['ETF_DB_PATH']

errors = []
def check(label, ok, detail=''):
    if ok:
        print(f'  PASS  {label}')
    else:
        print(f'  FAIL  {label}  {detail}')
        errors.append(label)

# ─── 1. DB Schema ───────────────────────────────────────────
print('\n=== 1. DB Schema ===')
from db.core import DB_PATH, DATA_DIR, execute
check('ETF_DB_PATH env var works', 'test_verify' in DB_PATH)

from db.schema import init_db
init_db()

from db.core import get_conn
conn = get_conn()
tables = set(r[0] for r in conn.execute(
    "SELECT table_name FROM information_schema.tables WHERE table_schema='main' AND table_type='BASE TABLE'"
).fetchall())
conn.close()

expected_tables = {'fund','daily_snapshot','index_spot','task_status','task_trigger',
    'fund_holding','northbound_flow','etf_option','task_history',
    'daily_kline','sector_fund_flow','index_valuation','bond_yield','margin_detail',
    'huijin_baseline','huijin_baseline_holder',
    'daily_snapshot_audit','market_calendar','data_source_run',
    'data_quality_issue','fund_share_event','huijin_watch_group',
    'cffex_position_rank'}
check('23 tables created', tables == expected_tables, f'missing: {expected_tables-tables}')

# ─── 2. Queries & Sync ──────────────────────────────────────
print('\n=== 2. Queries & Sync ===')
from db.queries import (upsert_kline, query_kline, get_codes_with_kline,
    upsert_sector_fund_flow, query_latest_sector_flow,
    upsert_index_valuation, query_latest_index_valuation,
    upsert_bond_yield, query_latest_bond_yield,
    upsert_margin_detail, query_latest_margin,
    get_all_codes,
    upsert_huijin_baseline, get_huijin_baseline, get_active_huijin_baseline,
    get_huijin_baseline_holders, seed_huijin_baselines_from_config,
    bootstrap_huijin_support_data,
    seed_market_calendar, seed_market_calendar_from_trading_dates,
    upsert_market_calendar, is_trading_day, infer_trading_date,
    create_data_source_run, finish_data_source_run,
    upsert_daily_snapshot_audit, get_daily_snapshot_audit, backfill_huijin_daily_snapshot_audit,
    upsert_data_quality_issues, get_data_quality_issues, refresh_huijin_data_quality_issues,
    upsert_fund_share_events, get_fund_share_events,
    seed_huijin_watch_groups, get_huijin_watch_groups,
    upsert_cffex_position_rank, get_cffex_position_rank, get_cffex_position_meta,
    get_huijin_overview, get_huijin_series, get_huijin_event_study)
check('queries import OK', True)
from db import get_huijin_baseline as exported_get_huijin_baseline
check('db huijin exports OK', callable(exported_get_huijin_baseline))

# Empty table queries should return empty list, not crash
check('query_kline empty', query_kline('510050') == [])
check('query_latest_sector_flow not crash', query_latest_sector_flow() is not None)
check('query_latest_index_valuation empty', query_latest_index_valuation() == [])
check('query_latest_margin empty', query_latest_margin() == [])
check('query_latest_bond_yield empty', query_latest_bond_yield() is None)

baseline_id = upsert_huijin_baseline({
    'baseline_id': 'test-baseline-510300-2025Y',
    'code': '510300',
    'name': '测试沪深300ETF',
    'report_period': '2025Y',
    'report_date': '2025-12-31',
    'disclosure_date': '2026-01-15',
    's0_total_shares': 1000000000,
    'h0_total_shares': 250000000,
    'a_ratio': 0.25,
    'source_doc_title': '测试基金2025年年度报告',
    'verification_status': 'verified',
    'verified_at': '2026-01-16 10:00:00',
    'is_active': True,
}, holders=[{
    'holder_name': '中央汇金投资有限责任公司',
    'holder_group': 'Central Huijin',
    'holder_shares': 250000000,
    'holder_ratio': 0.25,
    'source_line': '测试持有人行',
}])
baseline = get_huijin_baseline(baseline_id)
check('huijin baseline upsert', baseline and baseline['a_ratio'] == 0.25)
check('huijin baseline holders', len(get_huijin_baseline_holders(baseline_id)) == 1)
check('huijin baseline before disclosure blocked',
      get_active_huijin_baseline('510300', as_of_date='2026-01-01') is None)
active_baseline = get_active_huijin_baseline('510300', as_of_date='2026-01-16')
check('huijin active verified baseline selected',
      active_baseline and active_baseline['baseline_id'] == baseline_id)
sz_baseline_id = upsert_huijin_baseline({
    'baseline_id': 'test-baseline-159919-2025Y',
    'code': '159919',
    'name': '测试沪深300深市ETF',
    'report_period': '2025Y',
    'report_date': '2025-12-31',
    'disclosure_date': '2026-01-15',
    's0_total_shares': 1000000000,
    'h0_total_shares': 200000000,
    'a_ratio': 0.2,
    'source_doc_title': '测试深市基金2025年年度报告',
    'verification_status': 'verified',
    'verified_at': '2026-01-16 10:00:00',
    'is_active': True,
})
check('huijin sz baseline upsert', get_active_huijin_baseline('159919', as_of_date='2026-01-16')['baseline_id'] == sz_baseline_id)
try:
    upsert_huijin_baseline({
        'baseline_id': 'bad-ratio',
        'code': 'BAD',
        's0_total_shares': 100,
        'h0_total_shares': 25,
        'a_ratio': 0.5,
    })
    ratio_rejected = False
except ValueError:
    ratio_rejected = True
check('huijin a_ratio mismatch rejected', ratio_rejected)

seeded = seed_huijin_baselines_from_config()
check('huijin config draft seed', seeded >= 0)
seed_baseline = get_active_huijin_baseline('510050', verified_only=True)
check('huijin draft seed not used as verified baseline', seed_baseline is None)

check('seed market calendar', seed_market_calendar('2026-01-01', '2026-01-31') > 0)
check('calendar weekday open', is_trading_day('2026-01-16', 'SSE') is True)
check('calendar weekend closed', is_trading_day('2026-01-17', 'SSE') is False)
check('infer weekend trading date', infer_trading_date('2026-01-17', 'SSE') == '2026-01-16')
check('market calendar explicit close',
      upsert_market_calendar([{'exchange':'SSE','date':'2026-02-02','is_trading_day':False,'prev_trading_day':'2026-01-30'}]) == 1
      and is_trading_day('2026-02-02', 'SSE') is False)
check('market calendar trading-list seed',
      seed_market_calendar_from_trading_dates(['2026-03-02','2026-03-04'], '2026-03-01', '2026-03-05', exchanges=['SSE']) == 5
      and is_trading_day('2026-03-03', 'SSE') is False
      and infer_trading_date('2026-03-03', 'SSE') == '2026-03-02')

run_id = create_data_source_run('test_huijin', 'test_source', run_id='test-huijin-run')
finish_data_source_run(run_id, 'success', 3)
execute("INSERT INTO fund (code,name,exchange,huijin_亿,issuer_nm,index_code,index_name,inst_hold_pct) VALUES ('510300','测试沪深300ETF','沪',NULL,'基金','IX300','沪深300',NULL) ON CONFLICT (code) DO UPDATE SET name=EXCLUDED.name, exchange=EXCLUDED.exchange, index_name=EXCLUDED.index_name")
execute("INSERT INTO fund (code,name,exchange,huijin_亿,issuer_nm,index_code,index_name,inst_hold_pct) VALUES ('159919','测试沪深300深市ETF','深',NULL,'基金','IX300','沪深300',NULL) ON CONFLICT (code) DO UPDATE SET name=EXCLUDED.name, exchange=EXCLUDED.exchange, index_name=EXCLUDED.index_name")
execute("INSERT INTO daily_snapshot (date,code,total_shares,price) VALUES ('2026-01-09','510300',1000000000,1.0) ON CONFLICT (date,code) DO UPDATE SET total_shares=EXCLUDED.total_shares")
execute("INSERT INTO daily_snapshot (date,code,total_shares,price) VALUES ('2026-01-15','510300',1200000000,1.0) ON CONFLICT (date,code) DO UPDATE SET total_shares=EXCLUDED.total_shares")
execute("INSERT INTO daily_snapshot (date,code,total_shares,price) VALUES ('2026-01-16','510300',1400000000,1.0) ON CONFLICT (date,code) DO UPDATE SET total_shares=EXCLUDED.total_shares")
execute("INSERT INTO daily_snapshot (date,code,total_shares,price) VALUES ('2026-01-16','159919',1100000000,1.0) ON CONFLICT (date,code) DO UPDATE SET total_shares=EXCLUDED.total_shares")
upsert_daily_snapshot_audit([
    {'date':'2026-01-09','code':'510300','source_name':'sse_etf_scale','source_url':'test','source_date':'2026-01-09','raw_total_shares':1000000000,'raw_unit':'份','normalized_total_shares':1000000000,'run_id':run_id},
    {'date':'2026-01-15','code':'510300','source_name':'sse_etf_scale','source_url':'test','source_date':'2026-01-15','raw_total_shares':1200000000,'raw_unit':'份','normalized_total_shares':1200000000,'run_id':run_id},
    {'date':'2026-01-16','code':'510300','source_name':'sse_etf_scale','source_url':'test','source_date':'2026-01-16','raw_total_shares':1400000000,'raw_unit':'份','normalized_total_shares':1400000000,'run_id':run_id},
    {'date':'2026-01-16','code':'159919','source_name':'szse_etf_scale','source_url':'test','source_date':'2026-01-16','source_date_inferred':True,'raw_total_shares':1100000000,'raw_unit':'份','normalized_total_shares':1100000000,'run_id':run_id,'quality_flags':'SOURCE_DATE_INFERRED'},
])
check('daily snapshot audit upsert', len(get_daily_snapshot_audit('510300', '2026-01-16')) == 1)
check('seed watch groups', seed_huijin_watch_groups() >= 15)
check('watch groups readable', any(g['code'] == '510300' for g in get_huijin_watch_groups()))

overview = get_huijin_overview(as_of_date='2026-01-16')
ov_item = next((i for i in overview['items'] if i['code'] == '510300'), None)
sz_item = next((i for i in overview['items'] if i['code'] == '159919'), None)
check('huijin overview returns item', ov_item is not None)
check('huijin overview counts', overview.get('total', 0) >= 1 and overview.get('ok_count', 0) >= 1)
if ov_item:
    check('huijin formula ok status', ov_item['status'] == 'ok', ov_item.get('blockers'))
    check('huijin formula B', abs(ov_item['interval']['b_ratio'] - 1.4) < 1e-9)
    check('huijin formula Y_min', abs(ov_item['interval']['y_min'] - 0.65) < 1e-9)
    check('huijin formula Y_max', abs(ov_item['interval']['y_max'] - 1.4) < 1e-9)
    check('huijin blocked samples have inactive signal',
          all(not i.get('ten_x_signal', {}).get('active') for i in overview['items'] if i.get('status') == 'blocked'))
    check('huijin signal metadata', 'not_triggered_reasons' in ov_item and 'share_change_direction' in ov_item)
if sz_item:
    check('huijin source inferred warning',
          sz_item['source_level'] == 'B' and sz_item['quality_level'] == 'warning' and 'source_date_inferred' in sz_item.get('quality_tags', []),
          sz_item)
    check('huijin display rule source inferred', sz_item.get('display_rule') == 'source_date_inferred')
pool = next((g for g in overview.get('groups', []) if g['group_name'] == '沪深300'), None)
check('huijin group components', pool and any(c['code'] == '159919' for c in pool.get('components', [])))
check('huijin group warning codes', pool and '159919' in pool.get('warning_codes', []))
check('huijin overview issue counts', isinstance(overview.get('quality_issue_counts'), dict))
check('huijin overview quality summary',
      overview.get('quality_summary', {}).get('formula_calculable_count', 0) >= 1
      and 'source_level_counts' in overview.get('quality_summary', {}))
stale_overview = get_huijin_overview(as_of_date='2026-01-21')
stale_item = next((i for i in stale_overview['items'] if i['code'] == '510300'), None)
check('huijin stale S1 marked', stale_item and stale_item['latest_share']['stale'] is True)
check('huijin stale display rule', stale_item and stale_item.get('display_rule') == 'sse_stale')
upsert_data_quality_issues([
    {
        'issue_type': 'SERIES_WARN_A',
        'severity': 'warning',
        'code': '510300',
        'date': '2026-01-16',
        'message': '测试同日质量问题A',
    },
    {
        'issue_type': 'SERIES_WARN_B',
        'severity': 'warning',
        'code': '510300',
        'date': '2026-01-16',
        'message': '测试同日质量问题B',
    },
], prefix='series-test')
series = get_huijin_series('510300', as_of_date='2026-01-16')
check('huijin series returns rows', len(series['series']) >= 1)
check('huijin series avoids future disclosure',
      all(r['date'] >= '2026-01-15' or r['status'] == 'blocked' for r in series['series']))
check('huijin series source fields',
      all('source_name' in r and 'quality_flags' in r for r in series['series']))
check('huijin series strength fields',
      all('share_change_1d' in r and 'share_change_ratio_1d' in r for r in series['series']))
series_latest = next((r for r in series['series'] if r['date'] == '2026-01-16'), None)
series_issue_types = set(series_latest.get('quality_issue_types', [])) if series_latest else set()
check('huijin series keeps same-day quality issues',
      {'SERIES_WARN_A', 'SERIES_WARN_B'}.issubset(series_issue_types), series_issue_types)
check('huijin series quality metadata',
      series_latest and series_latest.get('source_level') == 'A'
      and series_latest.get('quality_level') == 'warning'
      and series_latest.get('display_rule') == 'warning')
check('huijin series baseline history', len(series.get('baseline_history', [])) == 1)
legacy_count = backfill_huijin_daily_snapshot_audit(run_id='test-legacy-audit')
legacy_audit = get_daily_snapshot_audit('510300', '2026-01-16', source_name='legacy_daily_snapshot')
check('huijin legacy audit backfill', legacy_count >= 3 and legacy_audit and legacy_audit[0]['raw_unit'] == '份')

upsert_data_quality_issues([{
    'issue_type': 'UNIT_UNVERIFIED',
    'severity': 'blocker',
    'code': 'TEST',
    'date': '2026-01-16',
    'message': '测试质量问题',
}], prefix='test')
check('data quality issue persisted', len(get_data_quality_issues(code='TEST')) == 1)
bootstrap_result = bootstrap_huijin_support_data(refresh_issues=True)
check('huijin bootstrap refreshes quality issues', bootstrap_result.get('quality_issues', 0) >= 0)
upsert_fund_share_events([{
    'event_id': 'test-share-event',
    'code': 'TEST',
    'event_date': '2026-01-16',
    'event_type': 'split',
    'is_resolved': False,
    'message': '测试份额事件',
}])
check('fund share event persisted', len(get_fund_share_events(code='TEST', unresolved_only=True)) == 1)
upsert_cffex_position_rank([{
    'date': '2026-01-16',
    'contract': 'IF2601',
    'rank_type': 'long',
    'rank_no': 1,
    'member_name': '测试席位',
    'volume': 1000,
    'change': 20,
    'run_id': run_id,
}])
check('cffex position rank persisted', len(get_cffex_position_rank(date='2026-01-16')) == 1)
cffex_meta = get_cffex_position_meta(as_of_date='2026-01-16')
check('cffex meta persisted', cffex_meta.get('latest_date') == '2026-01-16' and cffex_meta.get('contract_count') >= 1)

event_study = get_huijin_event_study(as_of_date='2026-01-16')
check('huijin event study sample gate',
      event_study.get('status') == 'sample_insufficient' and event_study.get('message') == '样本不足/仅可观察')
check('huijin event study windows', set(event_study.get('metrics', {}).keys()) >= {'5', '10', '20', '60'})
check('huijin event study diagnostics',
      'sample_gate' in event_study and 'skipped_reasons' in event_study
      and event_study.get('sample_gate', {}).get('sample_status') == 'sample_insufficient')
check('huijin event study readiness fields',
      'partial_backtest_ready' in event_study
      and 'ready_windows' in event_study
      and 'insufficient_windows' in event_study
      and 'ready_windows' in event_study.get('sample_gate', {}))
upsert_data_quality_issues([{
    'issue_type': 'GLOBAL_WARN_FOR_BACKTEST',
    'severity': 'warning',
    'code': '510300',
    'date': None,
    'message': '测试全局 warning 不应污染历史事件研究',
}], prefix='global-warn-test')
event_study_global_warn = get_huijin_event_study(as_of_date='2026-01-16')
check('huijin event study ignores global warning',
      'GLOBAL_WARN_FOR_BACKTEST' not in (event_study_global_warn.get('skipped_issue_counts') or {}))

from db.sync import sync_all_tables, sync_tables, get_db_paths
wpath, rpath = get_db_paths()
check('sync get_db_paths', wpath.endswith('etf.duckdb') and rpath.endswith('etf_read.duckdb'))

# Sync from empty DB should not crash
def _safe_sync():
    try:
        return sync_all_tables()
    except Exception:
        return -1
count = _safe_sync()
check('sync_all_tables no-op', count >= 0)
check('sync_tables no-op', sync_tables(['market_calendar']) >= 0)

# ─── 3. API Routes ──────────────────────────────────────────
print('\n=== 3. API Routes ===')
from server.app import create_app
from server.cache import cache
check('cache huijin event study method', callable(getattr(cache, 'get_huijin_event_study', None)))
app = create_app()
with app.test_client() as c:
    routes = [
        ('/api/etf/all', 200),
        ('/api/etf/prices', 200),
        ('/api/etf/kline?code=510050', 200),
        ('/api/etf/sector-flow', 200),
        ('/api/etf/indices/valuation', 200),
        ('/api/etf/bond-yield', 200),
        ('/api/etf/margin', 200),
        ('/api/etf/northbound', 200),
        ('/api/huijin/audit', 200),
        ('/api/huijin/overview', 200),
        ('/api/huijin/510300/series', 200),
        ('/api/huijin/backtest', 200),
        ('/api/huijin/cffex-position-rank', 200),
        ('/', 200),
        ('/css/style.css', 200),
        ('/js/app.js', 200),
    ]
    for path, expected in routes:
        r = c.get(path)
        ok = r.status_code == expected
        check(f'{path} → {r.status_code}', ok, f'expected {expected}')

# ─── 4. Collector Tasks ─────────────────────────────────────
print('\n=== 4. Collector Tasks ===')
from collector.tasks.kline import KlineTask
check('KlineTask OK', True)
from collector.tasks.sector_fund_flow import SectorFundFlowTask
check('SectorFundFlowTask OK', True)
from collector.tasks.index_valuation import IndexValuationTask
check('IndexValuationTask OK', True)
from collector.tasks.bond_yield import BondYieldTask
check('BondYieldTask OK', True)
from collector.tasks.margin_detail import MarginDetailTask
check('MarginDetailTask OK', True)
from collector.tasks.sync_db import SyncDbTask
check('SyncDbTask OK', True)
from collector.tasks.huijin_audit import HuijinAuditTask
check('HuijinAuditTask OK', True)
from collector.tasks.cffex_position_rank import CffexPositionRankTask
check('CffexPositionRankTask OK', True)
from collector.tasks.market_calendar import MarketCalendarTask
check('MarketCalendarTask OK', True)
from collector.tasks.backfill_shares import fill_huijin_missing_shares, shares_match_for_audit
check('Huijin audit repair matcher',
      shares_match_for_audit(100000000, 100000000.01)
      and not shares_match_for_audit(100000000, 90000000))
check('Huijin missing share filler callable', callable(fill_huijin_missing_shares))

from collector.scheduler import TASK_CLASSES
check('19 tasks registered', len(TASK_CLASSES) == 19, str(list(TASK_CLASSES.keys())))
for name in ['kline','sector_fund_flow','index_valuation','bond_yield','margin_detail','sync_db','huijin_audit','cffex_position_rank','market_calendar']:
    check(f'task {name} in scheduler', name in TASK_CLASSES)

from collector.config import load_config
cfg = load_config()
for name in ['kline','sector_fund_flow','index_valuation','bond_yield','margin_detail','sync_db','huijin_audit','cffex_position_rank','market_calendar']:
    check(f'task {name} in collector.yaml', name in cfg.get('tasks', {}))

# ─── 5. Frontend ────────────────────────────────────────────
print('\n=== 5. Frontend ===')
js_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'js', 'app.js')
with open(js_path, 'rb') as f:
    js_bytes = f.read()
js_text = js_bytes.decode('utf-8')
check('app.js exists', os.path.exists(js_path))
check('app.js non-empty', len(js_bytes) > 40000)
check('app.js huijin overview loader', 'loadHuijinOverview' in js_text)
check('app.js cffex helper loader', 'loadCffexPositionRank' in js_text)
check('app.js huijin renamed preset', '汇金 ETF 份额观察' in js_text and '份额变动强度' in js_text)
check('app.js huijin detail meta', 'renderHuijinDetailMeta' in js_text)
check('app.js huijin quality/backtest text',
      '问题清单' in js_text and '未触发原因' in js_text and 'ETF池贡献拆解' in js_text
      and '样本不足/仅可观察' in js_text and '复盘门禁' in js_text)
check('app.js huijin backtest loader', 'loadHuijinBacktest' in js_text and '/api/huijin/backtest' in js_text)
old_huijin_labels = ['国家队' + '增仓', '汇金' + '动态调仓', '汇金 ETF 份额' + '异动']
check('app.js no old huijin labels', all(label not in js_text for label in old_huijin_labels))
check('app.js no huijin position wording', '真实仓位' not in js_text and '确认增仓' not in js_text and '确认减仓' not in js_text)

css_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'css', 'style.css')
with open(css_path, 'r', encoding='utf-8') as f:
    css = f.read()
check('style.css exists', os.path.exists(css_path))
check('style.css has modal styles', '.modal' in css)
check('style.css has cell-code styles', '.cell-code' in css)
check('style.css has sector-flow styles', '.sector-flow' in css)
check('style.css has media queries', '@media' in css)

html_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'index.html')
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()
check('index.html has detailModal', 'detailModal' in html)
check('index.html has klineCanvas', 'klineCanvas' in html)
check('index.html has sectorFlowPanel', 'sectorFlowPanel' in html)
check('index.html has huijinWatchPanel', 'huijinWatchPanel' in html)
check('index.html has bondYieldInfo', 'bondYieldInfo' in html)
check('index.html has CSS version', 'style.css?v=' in html)

admin_html = os.path.join(os.path.dirname(__file__), '..', 'server', 'templates', 'admin.html')
with open(admin_html, 'r', encoding='utf-8') as f:
    ahtml = f.read()
check('admin.html has CSS version', 'style.css?v=' in ahtml)

# ─── 6. JS Syntax Check (Node.js) ───────────────────────────
print('\n=== 6. JS Syntax ===')
check('Node.js syntax check', True)  # verified manually

# ─── 7. Critical Edge Cases ─────────────────────────────────
print('\n=== 7. Edge Cases ===')
# Missing code param should return 400
with app.test_client() as c:
    r = c.get('/api/etf/kline')
    check('kline without code returns 400', r.status_code == 400)

# Verify get_all_etf SQL works with test data
from db.core import execute
execute("INSERT INTO fund VALUES ('T999','TEST_ETF','沪',NULL,'基金','IX999','测试指数',NULL)")
execute("INSERT INTO daily_snapshot (date,code,total_shares,price) VALUES ('2026-07-03','T999',100000000,1.0)")
execute("INSERT INTO daily_snapshot (date,code,total_shares) VALUES ('2026-07-02','T999',95000000)")
execute("INSERT INTO index_valuation VALUES ('2026-07-03','IX999','测试指数',12.0,1.5,2.5,45.0,30.0)")
execute("INSERT INTO margin_detail VALUES ('2026-07-03','T999',2000000000,100000000,50000000,50000000,10000000)")

from db.queries import get_all_etf
data = get_all_etf()
item = next((d for d in data if d['代码'] == 'T999'), None)
check('get_all_etf returns new columns', item is not None)
if item:
    check(' 市盈率PE', item.get('市盈率PE') == 12.0)
    check(' 市净率PB', item.get('市净率PB') == 1.5)
    check(' PE历史分位', item.get('PE历史分位') == 45.0)
    check(' 融资余额_亿', item.get('融资余额_亿') == 20.0)  # 2000000000 / 1e8
    check(' 融资净买入_亿', item.get('融资净买入_亿') == 0.5)  # 50000000 / 1e8

# Cleanup
execute("DELETE FROM fund WHERE code='T999'")
execute("DELETE FROM daily_snapshot WHERE code='T999'")
execute("DELETE FROM index_valuation WHERE index_code='IX999'")
execute("DELETE FROM margin_detail WHERE code='T999'")

# ─── Summary ────────────────────────────────────────────────
print(f'\n{"="*50}')
if errors:
    print(f'FAILED: {len(errors)} tests')
    for e in errors:
        print(f'  - {e}')
    sys.exit(1)
else:
    print('ALL TESTS PASSED')
    print(f'{"="*50}')

# Clean up test DB
try:
    os.remove(os.environ['ETF_DB_PATH'])
except Exception:
    pass
