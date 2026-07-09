import os
from flask import Blueprint, jsonify, request
from db import get_prices, query_kline, query_latest_sector_flow, query_latest_index_valuation, query_latest_bond_yield, query_latest_margin, safe_error
from db.sync import sync_all_tables, get_db_paths
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
        write_path, read_path = get_db_paths()
        if not os.path.exists(write_path):
            return jsonify({'ok': False, 'message': '写数据库不存在'}), 400

        write_mtime = os.path.getmtime(write_path)
        read_mtime = os.path.getmtime(read_path) if os.path.exists(read_path) else 0

        if write_mtime <= read_mtime:
            return jsonify({'ok': True, 'synced': False, 'message': '数据已最新，无需同步'})

        count = sync_all_tables()
        cache.invalidate()
        return jsonify({'ok': True, 'synced': True, 'message': f'同步完成（{count} 张表）'})
    except Exception as e:
        return jsonify({'error': safe_error(e)}), 500


@etf_api.route('/api/etf/margin')
def get_margin():
    try:
        data = query_latest_margin()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': safe_error(e)}), 500
