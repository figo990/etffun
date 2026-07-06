from flask import Blueprint, jsonify, request

from db import audit_huijin_data, get_cffex_position_rank, get_huijin_series, safe_error
from ..cache import cache

huijin_api = Blueprint('huijin_api', __name__)


@huijin_api.route('/api/huijin/audit')
def get_huijin_audit():
    try:
        return jsonify(audit_huijin_data())
    except Exception as e:
        return jsonify({'error': safe_error(e)}), 500


@huijin_api.route('/api/huijin/overview')
def get_huijin_overview_route():
    try:
        as_of_date = request.args.get('as_of_date') or None
        data = cache.get_huijin_overview(as_of_date=as_of_date)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': safe_error(e)}), 500


@huijin_api.route('/api/huijin/<code>/series')
def get_huijin_series_route(code):
    try:
        as_of_date = request.args.get('as_of_date') or None
        limit = request.args.get('limit', 250, type=int)
        return jsonify(get_huijin_series(code, as_of_date=as_of_date, limit=limit))
    except Exception as e:
        return jsonify({'error': safe_error(e)}), 500


@huijin_api.route('/api/huijin/backtest')
def get_huijin_backtest_route():
    try:
        as_of_date = request.args.get('as_of_date') or None
        raw_windows = request.args.get('windows') or '5,10,20,60'
        windows = []
        for part in raw_windows.split(','):
            part = part.strip()
            if part.isdigit():
                windows.append(int(part))
        include_warnings = str(request.args.get('include_warnings') or '').lower() in ('1', 'true', 'yes')
        data = cache.get_huijin_event_study(
            as_of_date=as_of_date,
            windows=windows or [5, 10, 20, 60],
            include_warnings=include_warnings,
        )
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': safe_error(e)}), 500


@huijin_api.route('/api/huijin/cffex-position-rank')
def get_huijin_cffex_position_rank():
    try:
        date = request.args.get('date') or None
        contract = request.args.get('contract') or None
        limit = request.args.get('limit', 200, type=int)
        return jsonify(get_cffex_position_rank(date=date, contract=contract, limit=limit))
    except Exception as e:
        return jsonify({'error': safe_error(e)}), 500
