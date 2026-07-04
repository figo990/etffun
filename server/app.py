import os
from flask import Flask, send_from_directory
from flask_cors import CORS
import yaml
from .cache import cache

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, 'config', 'server.yaml')


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def create_app():
    cfg = load_config()
    cache.configure((cfg.get('cache') or {}).get('ttl_seconds', 30))

    app = Flask(__name__,
                static_folder=os.path.join(BASE_DIR, 'public'),
                template_folder=os.path.join(BASE_DIR, 'server', 'templates'))

    CORS(app)

    from .api.etf import etf_api
    from .api.stats import stats_api
    from .api.admin import admin_api

    app.register_blueprint(etf_api)
    app.register_blueprint(stats_api)
    app.register_blueprint(admin_api)

    @app.route('/')
    def index():
        return send_from_directory(os.path.join(BASE_DIR, 'public'), 'index.html')

    @app.route('/admin.html')
    def admin_page():
        return send_from_directory(os.path.join(BASE_DIR, 'server', 'templates'), 'admin.html')

    @app.route('/css/<path:filename>')
    def css(filename):
        return send_from_directory(os.path.join(BASE_DIR, 'public', 'css'), filename)

    @app.route('/js/<path:filename>')
    def js(filename):
        return send_from_directory(os.path.join(BASE_DIR, 'public', 'js'), filename)

    return app


app = create_app()

if __name__ == '__main__':
    cfg = load_config()
    srv = cfg.get('server', {})
    app.run(
        host=srv.get('host', '127.0.0.1'),
        port=srv.get('port', 5000),
        debug=srv.get('debug', False),
    )
