import requests
import json
import os
from datetime import datetime, timedelta

API_KEY = os.environ.get('LOFIN_API_KEY', '')
BASE_URL = 'https://www.lofin365.go.kr/lf/hub/WCEGCF'

KEYWORDS = [
    '방역', '소독', '해충', '방제', '살균',
    '정수기', '공기청정기', '비데', '냉온수기',
    '청소용역', '에어컨청소', '위생', '식품위생', '착한가격'
]

TARGET_SIDOS = ['부산', '울산', '경남', '경상남']

JURISDICTION_MAP = {
    '부산동래': ['동래구', '연제구'],
    '부산수영': ['수영구'],
    '부산진구': ['부산진구'],
    '부산기장': ['기장군'],
    '해운대': ['해운대구', '금정구'],
    '부산서부': ['서구', '중구', '동구', '영도구'],
    '부산남부': ['남구'],
    '부산북부': ['북구', '사상구'],
    '부산사하': ['사하구', '강서구'],
    '김해남부': ['김해시'],
    '김해북부': ['김해시'],
    '울산북부': ['북구', '울주군'],
    '울산남부': ['남구'],
    '울산서부': ['울주군'],
    '울산중부': ['중구', '동구'],
    '양산': ['양산시'],
    '창원동부': ['창원시', '의창구', '성산구'],
    '창원서부': ['창원시', '마산합포구', '마산회원구'],
    '창원남부': ['창원시', '진해구'],
    '창원북부': ['창원시'],
    '진주동부': ['진주시'],
    '진주서부': ['진주시', '사천시', '남해군', '하동군', '산청군', '함양군', '거창군', '합천군'],
    '거제통영': ['거제시', '통영시', '고성군'],
    '사천남해': ['사천시', '남해군'],
}

def find_branch(org_name):
    if not org_name:
        return None
    for branch, orgs in JURISDICTION_MAP.items():
        if any(o in org_name for o in orgs):
            return branch
    return None

def fetch_by_date(keyword, date_str):
    params = {
        'Key': API_KEY,
        'Type': 'json',
        'pIndex': 1,
        'pSize': 1000,
        'ctrt_trgt_nm': keyword,
        'smz_ctrt_ymd': date_str,
    }
    try:
        resp = requests.get(BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        rows = data.get('WCEGCF', [{}])[1].get('row', []) if len(data.get('WCEGCF', [])) > 1 else []
        return rows
    except Exception as e:
        print(f"  오류: {keyword} / {date_str} — {e}")
        return []

def main():
    # 최근 1년치 날짜 생성
    today = datetime.today()
    one_year_ago = today - timedelta(days=365)
    dates = []
    cur = one_year_ago
    while cur <= today:
        dates.append(cur.strftime('%Y%m%d'))
        cur += timedelta(days=1)

    all_results = []
    seen = set()

    for kw in KEYWORDS:
        print(f"키워드: {kw} ({len(dates)}일)")
        for date_str in dates:
            items = fetch_by_date(kw, date_str)
            for item in items:
                sido = item.get('wa_laf_hg_nm', '')
                # 부산/울산/경남 필터
                if not any(s in sido for s in TARGET_SIDOS):
                    continue
                key = item.get('ctrt_ldgr_mng_no') or json.dumps(item, ensure_ascii=False)
                if key in seen:
                    continue
                seen.add(key)
                # 지사 매핑
                org = item.get('laf_hg_nm', '')
                item['_branch'] = find_branch(org)
                item['_keyword'] = kw
                all_results.append(item)

    # 계약일 내림차순 정렬
    all_results.sort(key=lambda x: x.get('smz_ctrt_ymd', ''), reverse=True)

    output = {
        'updated_at': today.strftime('%Y-%m-%d %H:%M'),
        'total': len(all_results),
        'data': all_results
    }

    os.makedirs('contract-data', exist_ok=True)
    with open('contract-data/data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n완료! 총 {len(all_results)}건 → contract-data/data.json 저장")

if __name__ == '__main__':
    main()
