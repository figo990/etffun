import akshare as ak
import pandas as pd
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from db import get_all_index_spot, get_funds_without_mapping, update_fund_info
from ..task_base import BaseTask


KNOWN_MAP = {
    '512880': ('399975', '证券公司'),
    '512900': ('399975', '证券公司'),
    '159841': ('399975', '证券公司'),
    '512000': ('399975', '证券公司'),
    '512570': ('399975', '证券公司'),
    '159848': ('399975', '证券公司'),
    '159859': ('399967', '中证军工'),
    '512660': ('399967', '中证军工'),
    '512680': ('399967', '中证军工'),
    '512810': ('399967', '中证军工'),
    '159967': ('399986', '中证银行'),
    '512800': ('399986', '中证银行'),
    '512820': ('399986', '中证银行'),
    '159865': ('399989', '中证医疗'),
    '512170': ('399989', '中证医疗'),
    '159828': ('399989', '中证医疗'),
    '159992': ('931087', '科技龙头'),
    '515000': ('931087', '科技龙头'),
    '515050': ('931087', '科技龙头'),
    '159997': ('399808', '中证新能'),
    '515700': ('399808', '中证新能'),
    '516160': ('399808', '中证新能'),
    '512010': ('399989', '中证医疗'),
    '510230': ('000018', '180金融'),
    '510050': ('000016', '上证50'),
    '510300': ('000300', '沪深300'),
    '159919': ('000300', '沪深300'),
    '510330': ('000300', '沪深300'),
    '510500': ('000905', '中证500'),
    '512500': ('000905', '中证500'),
    '159922': ('000905', '中证500'),
    '512100': ('000852', '中证1000'),
    '159845': ('000852', '中证1000'),
    '159915': ('399006', '创业板指'),
    '159949': ('399006', '创业板指'),
    '159952': ('399006', '创业板指'),
    '588000': ('000688', '科创50'),
    '588080': ('000688', '科创50'),
    '510180': ('000010', '上证180'),
}


def _normalize(s):
    s = str(s)
    s = re.sub(r'[指数收益率价格\(\).]', '', s)
    s = s.replace(' ', '')
    return s.lower()


def _remove_issuer(s):
    known = ['华夏', '易方达', '华泰柏瑞', '南方', '嘉实', '广发', '富国',
             '博时', '招商', '鹏华', '华安', '天弘', '工银', '景顺长城',
             '汇添富', '国泰', '华宝', '万家', '大成', '银华', '中欧',
             '建信', '平安', '国联安', '长信', '国寿安保', '前海开源',
             '交银', '长城', '国投瑞银', '兴全', '农银', '华富',
             '东财', '方正富邦', '浦银安盛', '中银', '华商',
             '泰康', '信诚', '浙商', '摩根', '光大', '海富通',
             '银河', '财通', '中融', '民生', '上投摩根', '华泰柏瑞']
    for n in known:
        s = s.replace(n, '')
    return s


def _extract_issuer(etf_name):
    known = ['华夏', '易方达', '华泰柏瑞', '南方', '嘉实', '广发', '富国',
             '博时', '招商', '鹏华', '华安', '天弘', '工银', '景顺长城',
             '汇添富', '国泰', '华宝', '万家', '大成', '银华', '中欧',
             '建信', '平安', '国联安', '长信', '国寿安保', '前海开源',
             '交银', '长城', '国投瑞银', '兴全', '农银', '华富',
             '东财', '方正富邦', '浦银安盛', '中银', '华商',
             '泰康', '信诚', '浙商', '摩根', '光大', '海富通',
             '银河', '财通', '中融', '民生', '华泰柏瑞']
    for name in known:
        if name in etf_name:
            return f"{name}基金"
    return None


def _match_index(etf_name, index_list, min_match=2):
    clean = _remove_issuer(etf_name)
    clean = re.sub(r'\betf\b', '', clean, flags=re.IGNORECASE)
    en = _normalize(clean)

    best = None
    best_score = 0
    for idx in index_list:
        idx_name = _normalize(idx['name'])
        if len(idx_name) < min_match:
            continue
        if idx_name in en:
            score = len(idx_name)
            if score > best_score:
                best_score = score
                best = idx
        elif en in idx_name:
            score = len(en)
            if score > best_score:
                best_score = score
                best = idx
    return best


def _api_lookup(code):
    try:
        df = ak.fund_overview_em(symbol=code)
        row = df.iloc[0]
        target = str(row['跟踪标的']) if pd.notna(row['跟踪标的']) else ''
        issuer = str(row['基金管理人']) if pd.notna(row['基金管理人']) else ''
        return code, target, issuer
    except Exception as e:
        return code, None, None


class IndexMappingTask(BaseTask):
    task_name = 'index_mapping'
    display_name = 'ETF指数映射'

    def _execute(self):
        index_list = get_all_index_spot()
        funds = get_funds_without_mapping(limit=100)
        if not funds:
            print("[index_mapping] all funds already mapped")
            return 0

        name_matched = 0
        api_processed = 0
        api_codes = []

        for f in funds:
            code = f['code']
            etf_name = str(f['name'] or '')

            if code in KNOWN_MAP:
                ic, iname = KNOWN_MAP[code]
                update_fund_info(code, index_code=ic, index_name=iname)
                issuer = _extract_issuer(etf_name)
                if issuer:
                    update_fund_info(code, issuer_nm=issuer)
                name_matched += 1
                continue

            match = _match_index(etf_name, index_list)
            if match:
                update_fund_info(code, index_code=match['code'], index_name=match['name'])
                issuer = _extract_issuer(etf_name)
                if issuer:
                    update_fund_info(code, issuer_nm=issuer)
                name_matched += 1
                continue

            api_codes.append((code, etf_name))

        # Process API lookups in parallel
        if api_codes:
            print(f"  [index_mapping] API lookup for {len(api_codes)} funds...")
            with ThreadPoolExecutor(max_workers=5) as pool:
                futures = {pool.submit(_api_lookup, code): (code, name) for code, name in api_codes}
                for future in as_completed(futures):
                    code, name = futures[future]
                    try:
                        _, target, issuer = future.result()
                        if target:
                            api_match = _match_index(target, index_list)
                            if api_match:
                                update_fund_info(code, index_code=api_match['code'], index_name=api_match['name'])
                            else:
                                update_fund_info(code, index_name=target)
                        if issuer:
                            update_fund_info(code, issuer_nm=issuer)
                        elif not issuer:
                            issuer = _extract_issuer(name)
                            if issuer:
                                update_fund_info(code, issuer_nm=issuer)
                        api_processed += 1
                    except Exception as e:
                        print(f"    {code}: error={e}")

        total = name_matched + api_processed
        print(f"[index_mapping] {total} processed (name={name_matched}, api={api_processed})")
        return total