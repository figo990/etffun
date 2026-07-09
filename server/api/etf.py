from flask import Blueprint, jsonify, request
from db import get_prices, query_kline, query_latest_sector_flow, query_latest_index_valuation, query_latest_bond_yield, query_latest_margin, safe_error, bootstrap_huijin_support_data
from db.sync import sync_all_tables
from ..cache import cache

etf_api = Blueprint('etf_api', __name__)


@etf_api.route('/api/etf/all')
def get_all_etf():
    try:
        data = cache.get_etf_all()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': safe_error(e)}), 500


@etf_api.route('/api/etf/prices')
def get_prices_route():
    try:
        data = get_prices()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': safe_error(e)}), 500


@etf_api.route('/api/etf/kline')
def get_kline():
    code = request.args.get('code', '')
    limit = request.args.get('limit', 120, type=int)
    if not code:
        return jsonify({'error': 'code required'}), 400
    try:
        data = query_kline(code, limit)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': safe_error(e)}), 500


@etf_api.route('/api/etf/sector-flow')
def get_sector_flow():
    period = request.args.get('period', '1d')
    try:
        result = query_latest_sector_flow(period=period)
        data = result.get('data', [])
        actual_days = result.get('actual_days', 0)
        resp = jsonify({'data': data, 'actual_days': actual_days, 'period': period})
        return resp
    except Exception as e:
        return jsonify({'error': safe_error(e)}), 500


@etf_api.route('/api/etf/indices/valuation')
def get_indices_valuation():
    try:
        data = query_latest_index_valuation()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': safe_error(e)}), 500


@etf_api.route('/api/etf/bond-yield')
def get_bond_yield():
    try:
        data = query_latest_bond_yield()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': safe_error(e)}), 500


@etf_api.route('/api/etf/sync', methods=['POST'])
def manual_sync():
    try:
        results = []

        # 1. Collect SSE shares
        try:
            from collector.tasks.shares_sse import SharesSSETask
            t = SharesSSETask()
            sse_count = t._execute()
            results.append(f'SSE({sse_count})')
        except ImportError:
            results.append('SSE(模块未加载)')
        except Exception as e:
            results.append(f'SSE({safe_error(e)})')

        # 2. Collect SZSE shares
        try:
            from collector.tasks.shares_szse import SharesSZSECTask
            t = SharesSZSECTask()
            szse_count = t._execute()
            results.append(f'SZSE({szse_count})')
        except ImportError:
            results.append('SZSE(模块未加载)')
        except Exception as e:
            results.append(f'SZSE({safe_error(e)})')

        # 3. Refresh Huijin state
        try:
            hr = bootstrap_huijin_support_data(refresh_issues=True, sync_read=False)
            results.append(f'汇金({hr.get("quality_issues", 0)}问题)')
        except Exception as e:
            results.append(f'汇金({safe_error(e)})')

        # 4. Sync write DB → read DB
        try:
            count = sync_all_tables()
            results.append(f'同步({count}张表)')
        except Exception as e:
            results.append(f'同步({safe_error(e)})')

        # 5. Invalidate cache
        cache.invalidate()

        msg = ' | '.join(results)
        return jsonify({'ok': True, 'message': msg})
    except Exception as e:
        return jsonify({'error': safe_error(e)}), 500


@etf_api.route('/api/etf/margin')
def get_margin():
    try:
        data = query_latest_margin()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': safe_error(e)}), 500
