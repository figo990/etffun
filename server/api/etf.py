from flask import Blueprint, jsonify
from db import get_prices
from ..cache import cache

etf_api = Blueprint('etf_api', __name__)


@etf_api.route('/api/etf/all')
def get_all_etf():
    try:
        data = cache.get_etf_all()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@etf_api.route('/api/etf/prices')
def get_prices_route():
    try:
        data = get_prices()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
