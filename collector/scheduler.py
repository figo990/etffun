import time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timezone

from .config import load_config
from .tasks.shares_sse import SharesSSETask
from .tasks.shares_szse import SharesSZSECTask
from .tasks.spot import SpotTask
from .tasks.nav import NavTask
from .tasks.index_spot import IndexSpotTask
from .tasks.index_mapping import IndexMappingTask
from .tasks.fund_holding import HoldingTask
from .tasks.northbound import NorthboundTask
from .tasks.etf_option import EtfOptionTask
from .tasks.inst_hold import InstHoldTask
from .tasks.kline import KlineTask
from .tasks.sector_fund_flow import SectorFundFlowTask
from .tasks.index_valuation import IndexValuationTask
from .tasks.bond_yield import BondYieldTask
from .tasks.margin_detail import MarginDetailTask
from .tasks.sync_db import SyncDbTask
from db import init_task_status, write_task_trigger, consume_task_triggers, init_db

TASK_CLASSES = {
    'shares_sse': SharesSSETask,
    'shares_szse': SharesSZSECTask,
    'spot': SpotTask,
    'nav': NavTask,
    'index_spot': IndexSpotTask,
    'index_mapping': IndexMappingTask,
    'fund_holding': HoldingTask,
    'northbound': NorthboundTask,
    'etf_option': EtfOptionTask,
    'inst_hold': InstHoldTask,
    'kline': KlineTask,
    'sector_fund_flow': SectorFundFlowTask,
    'index_valuation': IndexValuationTask,
    'bond_yield': BondYieldTask,
    'margin_detail': MarginDetailTask,
    'sync_db': SyncDbTask,
}


def _cron_dow_to_aps(dow_expr):
    """Convert cron day-of-week (0-7, 0/7=Sun, 1=Mon...) to APScheduler (0=Mon...6=Sun)."""
    if dow_expr == '*' or dow_expr is None:
        return '*'
    aps_parts = []
    for part in dow_expr.split(','):
        part = part.strip()
        if '-' in part:
            start, end = part.split('-', 1)
            s = (int(start) + 6) % 7
            e = (int(end) + 6) % 7
            aps_parts.append(f'{s}-{e}')
        else:
            aps_parts.append(str((int(part) + 6) % 7))
    return ','.join(aps_parts)


def _parse_cron(expr):
    """Parse: '0 17 * * 1-5' (cron), '*/10 * * * 1-5' (interval), '*/10 9:30-15:00 * * 1-5' (interval+range)."""
    parts = expr.strip().split()
    if parts[0].startswith('*/'):
        minutes = int(parts[0][2:])
        # Check for time range: */10 9:30-15:00 * * 1-5
        if len(parts) >= 2 and '-' in parts[1]:
            tr = parts[1]
            start_h, start_m = int(tr.split('-')[0].split(':')[0]), int(tr.split('-')[0].split(':')[1])
            end_h, end_m = int(tr.split('-')[1].split(':')[0]), int(tr.split('-')[1].split(':')[1])
            dow = _cron_dow_to_aps(parts[4] if len(parts) >= 5 else '*')
            return CronTrigger(
                minute=f'*/{minutes}', hour=f'{start_h}-{end_h}',
                day='*', month='*', day_of_week=dow
            )
        dow = _cron_dow_to_aps(parts[4] if len(parts) >= 5 else '*')
        return CronTrigger(minute=f'*/{minutes}', hour='*', day='*', month='*', day_of_week=dow)
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {expr}")
    return CronTrigger(
        minute=parts[0], hour=parts[1], day=parts[2],
        month=parts[3], day_of_week=_cron_dow_to_aps(parts[4])
    )


def build_scheduler():
    cfg = load_config()
    task_cfgs = cfg.get('tasks', {})

    # Register task metadata in DB
    task_meta = {}
    for name, tc in task_cfgs.items():
        task_meta[name] = {
            'display_name': tc.get('display_name', name),
            'schedule_cron': tc.get('schedule', ''),
            'enabled': tc.get('enabled', True),
        }

    init_db()
    init_task_status(task_meta)

    scheduler = BackgroundScheduler()

    for name, tc in task_cfgs.items():
        if not tc.get('enabled', True):
            continue
        task_cls = TASK_CLASSES.get(name)
        if not task_cls:
            continue
        task_instance = task_cls()
        cron_expr = tc['schedule']
        trigger = _parse_cron(cron_expr)
        scheduler.add_job(
            task_instance.run,
            trigger=trigger,
            id=name,
            name=name,
            replace_existing=True,
            misfire_grace_time=300,
        )
        print(f"  [scheduler] {name}: {cron_expr}")

    return scheduler


def trigger_poll_loop(scheduler):
    """Poll task_trigger table for manual triggers."""
    while True:
        try:
            triggers = consume_task_triggers()
            for t in triggers:
                task_name = t['task_name']
                action = t['action']
                if action == 'run_now':
                    job = scheduler.get_job(task_name)
                    if job:
                        scheduler.modify_job(task_name, next_run_time=datetime.now(timezone.utc))
                        print(f"  [trigger] {task_name} scheduled immediately")
        except Exception as e:
            print(f"  [trigger] poll error: {e}", flush=True)
        time.sleep(10)
