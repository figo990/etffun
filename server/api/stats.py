from flask import Blueprint, jsonify
from db import get_northbound_latest, safe_error
from ..cache import cache

stats_api = Blueprint('stats_api', __name__)


@stats_api.route('/api/etf/stats')
def get_stats():
    try:
        data = cache.get_stats()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': safe_error(e)}), 500


@stats_api.route('/api/etf/northbound')
def get_northbound():
    try:
        data = get_northbound_latest()
        return jsonify(data or {})
    except Exception as e:
        return jsonify({'error': safe_error(e)}), 500
