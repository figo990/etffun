import os
import shutil
import sys
import tempfile
import atexit


def reset_runtime_modules():
    for name in list(sys.modules):
        if name == 'db' or name.startswith('db.') or name == 'server' or name.startswith('server.'):
            sys.modules.pop(name, None)


def use_temp_db(prefix):
    test_dir = tempfile.mkdtemp(prefix=prefix)
    db_path = os.path.join(test_dir, 'test.duckdb')
    os.environ['ETF_DB_PATH'] = db_path
    os.environ['ETF_READ_DB_PATH'] = db_path
    atexit.register(lambda: shutil.rmtree(test_dir, ignore_errors=True))
    reset_runtime_modules()
    return test_dir, db_path
