from flask import Blueprint, jsonify, request
from db import get_task_status_all, write_task_trigger, get_task_history, safe_error
from ..cache import cache

admin_api = Blueprint('admin_api', __name__)

ADMIN_PASSWORD = 'etf2026'


@admin_api.route('/api/admin/auth', methods=['POST'])
def admin_auth():
    data = request.get_json(silent=True) or {}
    if data.get('password') == ADMIN_PASSWORD:
        return jsonify({'ok': True})
    return jsonify({'ok': False, 'error': '密码错误'}), 401


@admin_api.route('/api/admin/tasks', methods=['GET'])
def list_tasks():
    if request.headers.get('X-Admin-Token') != ADMIN_PASSWORD:
        return jsonify({'error': '未授权'}), 401
    try:
        data = cache.get_tasks(force=request.args.get('force') == '1')
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': safe_error(e)}), 500


@admin_api.route('/api/admin/tasks/<name>/run', methods=['POST'])
def trigger_task(name):
    if request.headers.get('X-Admin-Token') != ADMIN_PASSWORD:
        return jsonify({'error': '未授权'}), 401
    try:
        write_task_trigger(name, 'run_now')
        return jsonify({'ok': True, 'message': f'Task {name} triggered'})
    except Exception as e:
        return jsonify({'error': safe_error(e)}), 500


@admin_api.route('/api/admin/tasks/<name>/toggle', methods=['POST'])
def toggle_task(name):
    if request.headers.get('X-Admin-Token') != ADMIN_PASSWORD:
        return jsonify({'error': '未授权'}), 401
    try:
        from db import toggle_task_enabled
        new_state = toggle_task_enabled(name)
        return jsonify({'ok': True, 'enabled': new_state})
    except Exception as e:
        return jsonify({'error': safe_error(e)}), 500


@admin_api.route('/api/admin/tasks/<name>/history', methods=['GET'])
def task_history(name):
    if request.headers.get('X-Admin-Token') != ADMIN_PASSWORD:
        return jsonify({'error': '未授权'}), 401
    try:
        limit = request.args.get('limit', 20, type=int)
        data = get_task_history(name, limit)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': safe_error(e)}), 500
