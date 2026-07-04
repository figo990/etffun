"""Test: collector task imports and scheduler registration"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Test task classes import
from collector.tasks.kline import KlineTask
print('KlineTask OK')
from collector.tasks.sector_fund_flow import SectorFundFlowTask
print('SectorFundFlowTask OK')
from collector.tasks.index_valuation import IndexValuationTask
print('IndexValuationTask OK')
from collector.tasks.bond_yield import BondYieldTask
print('BondYieldTask OK')
from collector.tasks.margin_detail import MarginDetailTask
print('MarginDetailTask OK')

# Test scheduler knows about them
from collector.scheduler import TASK_CLASSES
assert 'kline' in TASK_CLASSES
assert 'sector_fund_flow' in TASK_CLASSES
assert 'index_valuation' in TASK_CLASSES
assert 'bond_yield' in TASK_CLASSES
assert 'margin_detail' in TASK_CLASSES
print(f'Scheduler has {len(TASK_CLASSES)} tasks: {list(TASK_CLASSES.keys())}')

# Test yaml config
from collector.config import load_config
cfg = load_config()
task_names = set(cfg['tasks'].keys())
for name in ['kline', 'sector_fund_flow', 'index_valuation', 'bond_yield', 'margin_detail']:
    assert name in task_names, f'{name} missing from collector.yaml'
print('collector.yaml has all new tasks')

print('All collector tests OK')