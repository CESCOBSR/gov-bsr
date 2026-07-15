import requests
import json
import os
import ssl
import urllib3
import xml.etree.ElementTree as ET
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from datetime import datetime, timedelta

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = 'https://www.lofin365.go.kr/lf/hub/WCEGCF'

KEYWORDS = [
    '방역', '소독', '해충', '방제', '살균',
    '정수기', '공기청정기', '비데', '냉온수기',
    '청소용역', '에어컨청소', '위생', '식품위생', '착한가격',
    '전통시장', '냉난방기', '자가품질', 'HACCP', '영양성분', '유효성평가', 'CCP'
]

TARGET_SIDOS = ['부산', '울산', '경남', '경상남']

# 수집 시작일 고정 (2025-01-01) ~ 오늘까지
START_DATE = datetime(2025, 1, 1)

class LegacySSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.set_ciphers('DEFAULT:@SECLEVEL=1')
        ctx.options |= 0x4
        kwargs['ssl_context'] = ctx
        super(LegacySSLAdapter, self).init_poolmanager(*args, **kwargs)

def create_session():
    session = requests.Session()
    session.mount('https://', LegacySSLAdapter())
    return session

def parse_xml(xml_text):
    try:
        root = ET.fromstring(xml_text)
        rows = []
        for row in root.findall('row'):
            item = {}
            for child in row:
                item[child.tag] = child.text or ''
            rows.append(item)
        return rows
    except Exception:
        return []

def fetch_by_date(session, keyword, date_str):
    params = {
        'pIndex': 1,
        'pSize': 1000,
        'ctrt_trgt_nm': keyword,
        'smz_ctrt_ymd': date_str,
    }
    try:
        resp = session.get(BASE_URL, params=params, verify=False, timeout=15)
        resp.raise_for_status()
        return parse_xml(resp.text)
    except Exception as e:
        print(f"  오류: {keyword} / {date_str} — {e}")
        return []

def main():
    today = datetime.today()
    dates = []
    cur = START_DATE
    while cur <= today:
        dates.append(cur.strftime('%Y%m%d'))
        cur += timedelta(days=1)

    total_calls = len(KEYWORDS) * len(dates)
    est_minutes = round(total_calls / 170)  # 과거 실측 기준 대략치
    print(f"수집 기간: {dates[0]} ~ {dates[-1]} ({len(dates)}일)")
    print(f"키워드: {len(KEYWORDS)}개")
    print(f"총 API 호출 예정: {total_calls}회 (예상 소요 약 {est_minutes}분)\n")

    session = create_session()
    all_results = []
    seen = set()

    for kw in KEYWORDS:
        print(f"키워드: [{kw}] 수집 중...")
        kw_count = 0
        for date_str in dates:
            items = fetch_by_date(session, kw, date_str)
            for item in items:
                sido = item.get('wa_laf_hg_nm', '')
                if not any(s in sido for s in TARGET_SIDOS):
                    continue
                key = item.get('ctrt_ldgr_mng_no') or json.dumps(item, ensure_ascii=False)
                if key in seen:
                    continue
                seen.add(key)
                item['_keyword'] = kw
                all_results.append(item)
                kw_count += 1
        print(f"  → {kw_count}건 수집")

    all_results.sort(key=lambda x: x.get('smz_ctrt_ymd', ''), reverse=True)

    # 시도/자치단체 요약 (참고용 로그)
    jurisdictions = {}
    for r in all_results:
        sido = r.get('wa_laf_hg_nm', '기타')
        gu = r.get('laf_hg_nm', '미상')
        jurisdictions.setdefault(sido, set()).add(gu)
    print("\n[수집된 자치단체 현황]")
    for sido, gus in jurisdictions.items():
        print(f"  {sido}: {len(gus)}개 자치단체 ({', '.join(sorted(gus))})")

    output = {
        'updated_at': today.strftime('%Y-%m-%d %H:%M'),
        'collection_start': START_DATE.strftime('%Y-%m-%d'),
        'total': len(all_results),
        'data': all_results
    }

    os.makedirs('contract-data', exist_ok=True)
    with open('contract-data/data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n완료! 총 {len(all_results)}건 → contract-data/data.json 저장")

if __name__ == '__main__':
    main()
