from flask import Blueprint, jsonify, request
from db import get_prices, query_kline, query_latest_sector_flow, query_latest_index_valuation, query_latest_bond_yield, query_latest_margin, safe_error
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


@etf_api.route('/api/etf/margin')
def get_margin():
    try:
        data = query_latest_margin()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': safe_error(e)}), 500
