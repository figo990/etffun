"""Download production database to local"""
import os, sys, paramiko, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

config_path = os.path.join(os.path.dirname(__file__), '..', 'deploy', 'config.json')
if not os.path.exists(config_path):
    print("ERROR: deploy/config.json not found. Copy config.json.example and fill in credentials.")
    sys.exit(1)

with open(config_path) as f:
    cfg = json.load(f)

host = cfg.get('host')
user = cfg.get('user', 'root')
password = cfg.get('password')
ssh_key = cfg.get('ssh_key')

data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
local_path = os.path.join(data_dir, 'etf.duckdb')
remote_path = '/home/devops/etffun_data/etf.duckdb'

print(f"Downloading {remote_path} from {host}...")
print(f"  To: {local_path}")

transport = paramiko.Transport((host, 22))
if ssh_key:
    transport.connect(username=user, key_filename=ssh_key)
else:
    transport.connect(username=user, password=password)

sftp = paramiko.SFTPClient.from_transport(transport)
sftp.get(remote_path, local_path)
sftp.close()
transport.close()

size = os.path.getsize(local_path)
print(f"Done: {size/1024/1024:.1f} MB downloaded")
print(f"Restart your Flask app to use the new database.")