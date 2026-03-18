"""
================================================================================
[ 🏛️ VIP 주식 전략 리포트 - 통합 설계 변경 이력 (Design Change History) ]
================================================================================
최종 수정일: 2026-03-18 | 현재 버전: v3.1
--------------------------------------------------------------------------------
날짜        | 버전         | 설계 변경 및 업데이트 내역
--------------------------------------------------------------------------------
2026-02-10 | v1.0         | 시스템 초기 구축 (AI 번역 기반 뉴스 수집)
2026-02-11 | v1.1         | AI 의존성 제거 및 BeautifulSoup 기반 크롤링 엔진 도입
2026-02-12 | v1.2         | 노이즈 필터링(-키워드) 및 16대 우량주 자동 매핑 구현
2026-02-13 | v1.3         | 주가 변동 연동 헤더 음영 UI 및 깃발(Flag) 시스템 도입
2026-02-15 | v2.0         | 기본적 분석 지표(PER, 배당률, 목표가 여력) 산출 로직 추가
2026-02-20 | v2.1         | 배당률 계산 정밀화 및 투자의견 한글화 매핑 (v1.0, v2.1)
2026-03-05 | v2.2         | 다중 수신인 발송 및 평일(월~금) 스케줄링 워크플로우 적용
2026-03-17 | v3.0         | when:1d 최신성 필터 및 사회/경제 헤드라인 섹션 추가
2026-03-18 | v3.1         | 헤드라인 중복 제거 및 사회/경제(4:3) 정밀 믹싱 로직 적용
================================================================================
"""

import os, smtplib, time, urllib.parse, requests, re
import yfinance as yf
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# [1. 환경 변수 및 수신인 설정] --------------------------------------------------
# 2026-03-05 v2.2: 다중 수신인 대응을 위해 리스트 구조 도입
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')

RECIPIENTS = [
    EMAIL_ADDRESS,           # 형님 본인
    "yhkwon@spigen.com",     # 파트너 1
    "jynoh@spigen.com",      # 파트너 2
    "mako@spigen.com",       # 파트너 3
    "jhkang@spigen.com"      # 파트너 4
]

# [2. 분석 대상 종목 데이터베이스] ------------------------------------------------
# 2026-02-12 v1.2: 16대 우량주 딕셔너리 구성
STOCK_MAP = {
    "애플": "AAPL", "마이크로소프트": "MSFT", "엔비디아": "NVDA", "알파벳": "GOOGL",
    "아마존": "AMZN", "메타": "META", "테슬라": "TSLA", "브로드컴": "AVGO",
    "일라이 릴리": "LLY", "비자": "V", "존슨앤존슨": "JNJ", "오라클": "ORCL",
    "버크셔 해서웨이": "BRK-B", "팔란티어": "PLTR", "월마트": "WMT", "코스트코": "COST"
}

def get_market_summary():
    """
    [2026-03-18 v1.3, v2.0]: 상단 지수 정보 및 컬러 지표 산출
    나스닥, S&P500의 등락률과 VIX 지수의 안정성을 판단합니다.
    """
    try:
        results = []
        indices = {"나스닥": "^IXIC", "S&P500": "^GSPC", "공포지수(VIX)": "^VIX"}
        for name, tk in indices.items():
            s = yf.Ticker(tk)
            f = s.fast_info
            curr = f['last_price']
            pct = ((curr - f['previous_close']) / f['previous_close']) * 100
            
            color = "#111"
            if name == "공포지수(VIX)":
                # VIX 수치에 따른 심리 상태 색상 구분
                color = "#1a73e8" if curr < 20 else ("#f9ab00" if curr < 30 else "#d93025")
                results.append(f"{name}: <b style='color:{color};'>{curr:.2f}</b>")
            else:
                # 지수 등락에 따른 색상 구분
                idx_color = "#d93025" if pct > 0 else "#1a73e8"
                results.append(f"{name}: <b style='color:{idx_color};'>{pct:+.2f}%</b>")
        return " | ".join(results)
    except: return "시장 데이터 로딩 중..."

def get_stock_details(ticker):
    """
    [2026-03-18 v2.0, v2.1]: 개별 종목 재무 지표 및 투자의견 한글화
    PER, 배당률(오류 수정 로직 포함), 목표주가 여력 및 깃발 시스템을 처리합니다.
    """
    try:
        s = yf.Ticker(ticker)
        f, info = s.fast_info, s.info
        curr, prev = f['last_price'], f['previous_close']
        pct = ((curr - prev) / prev) * 100
        
        # 상승여력 산출 및 색상 지정
        target = info.get('targetMeanPrice', 0)
        upside_val = ((target / curr) - 1) * 100 if target > 0 else 0
        u_color = "#1a73e8" if upside_val > 15 else ("#d93025" if upside_val < 0 else "#111")
        
        # PER 산출 및 색상 지정
        per = info.get('trailingPE', 0)
        p_color = "#1a73e8" if (isinstance(per, (int, float)) and per < 25) else ("#d93025" if (isinstance(per, (int, float)) and per > 40) else "#f9ab00")
        
        # 배당률 산출 (2026-02-20 v2.1: 뻥튀기 방지를 위한 데이터 단위 보정 로직 적용)
        div = info.get('dividendYield')
        if div is None: div_val = 0.0
        elif div > 0.1: div_val = div
        else: div_val = div * 100
        d_color = "#1a73e8" if div_val >= 3 else ("#f9ab00" if div_val >= 1 else "#d93025")
        
        # 52주 저점 대비 거리 산출
        dist_low = ((curr / f['year_low']) - 1) * 100
        l_color = "#1a73e8" if dist_low < 10 else ("#d93025" if dist_low > 30 else "#111")
        
        # 투자의견 한글 매핑 (2026-02-20 v1.0, v2.1)
        opinion_map = {
            'strong_buy': '강력 매수', 'buy': '매수', 
            'hold': '보유(중립)', 'underperform': '수익률 하회', 
            'sell': '매도', 'strong_sell': '강력 매도'
        }
        kor_opinion = opinion_map.get(info.get('recommendationKey', '').lower(), '의견 없음')

        # 깃발 시스템 (2026-02-13 v1.3): 실적, 변동성, 신고가 감지
        flags = []
        if abs(pct) >= 3.5: flags.append("⚠️")
        if curr >= (f['year_high'] * 0.98): flags.append("✨")
        try:
            if not s.calendar.empty:
                if 0 <= (s.calendar.iloc[0, 0] - datetime.now().date()).days <= 7: flags.append("🚩")
        except: pass

        return {
            "price": f"{curr:,.2f}", "pct": round(pct, 2), "flags": "".join(flags),
            "upside": f"{upside_val:+.1f}%", "u_color": u_color,
            "per": f"{per:.1f}" if isinstance(per, (int, float)) else "-", "p_color": p_color,
            "div": f"{div_val:.2f}%", "d_color": d_color,
            "dist_low": f"{dist_low:+.1f}%", "l_color": l_color,
            "opinion": kor_opinion,
            "cap": f"{info.get('marketCap', 0) / 1_000_000_000_000:,.1f}T"
        }
    except: return None

def fetch_korean_news(brand):
    """
    [2026-03-18 v1.1, v3.0]: 종목별 오늘자 최신 뉴스 수집
    when:1d 필터를 사용하여 24시간 이내의 한국어 기사만 추출합니다.
    """
    query = urllib.parse.quote(f"{brand} 주식 (마감 OR 종가 OR 속보) when:1d")
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.content, "xml")
        links = []
        for i in soup.find_all("item"):
            if bool(re.search('[가-힣]', i.title.text)):
                links.append(f"<li style='margin-bottom:5px;'><a href='{i.link.text}' style='color:#111; text-decoration:none; font-size:13px;'>• {i.title.text}</a></li>")
            if len(links) >= 3: break
        
        # 당일 마감 소식이 부족할 경우 분석용 기사로 확장 검색
        if not links:
            q_fallback = urllib.parse.quote(f"{brand} 주식 분석 when:1d")
            url_f = f"https://news.google.com/rss/search?q={q_fallback}&hl=ko&gl=KR&ceid=KR:ko"
            res_f = requests.get(url_f, timeout=5)
            soup_f = BeautifulSoup(res_f.content, "xml")
            for i in soup_f.find_all("item")[:3]:
                links.append(f"<li style='margin-bottom:5px;'><a href='{i.link.text}' style='color:#111; text-decoration:none; font-size:13px;'>• {i.title.text}</a></li>")
        return "".join(links)
    except: return "<li>오늘의 분석 뉴스를 불러오지 못했습니다.</li>"

def fetch_general_headlines():
    """
    [2026-03-18 v3.0, v3.1]: 사회/경제 헤드라인 7선 수집
    분야별 믹스(4:3)와 중복 제목 제거 로직이 탑재되어 있습니다.
    """
    def get_news_from_query(sub_query, count):
        q = urllib.parse.quote(f"{sub_query} when:1d")
        u = f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
        found = []
        try:
            r = requests.get(u, timeout=5)
            s = BeautifulSoup(r.content, "xml")
            for item in s.find_all("item"):
                title = item.title.text
                if bool(re.search('[가-힣]', title)):
                    found.append({"title": title, "link": item.link.text})
                if len(found) >= count: break
        except: pass
        return found

    # 사회 4개, 경제 3개 구성을 위해 넉넉히 수집 시작
    society_news = get_news_from_query("사회 속보", 5)
    economy_news = get_news_from_query("경제 속보", 5)

    combined = []
    seen_titles = set()

    # [2026-03-18 v3.1] 중복 기사 제거 및 사회/경제 데이터 믹싱 로직
    for item in (society_news + economy_news):
        clean_title = item['title'].strip()
        if clean_title not in seen_titles:
            combined.append(f"<li style='margin-bottom:6px;'><a href='{item['link']}' style='color:#111; text-decoration:none; font-size:13px;'>• {clean_title}</a></li>")
            seen_titles.add(clean_title)
        if len(combined) >= 7: break

    return "".join(combined)

if __name__ == "__main__":
    # [2026-03-18 v1.3, v2.2, v3.1]: 전체 조립 및 메일 구성 로직
    print("🚀 VIP 주식 전략 리포트 생성 프로세스를 가동합니다...")
    m_context = get_market_summary()
    headlines_html = fetch_general_headlines()
    
    html = f"""
    <html>
    <body style="font-family: 'Malgun Gothic', sans-serif; background-color: #ffffff; padding: 20px;">
        <div style="max-width: 650px; margin: auto; border: 2px solid #111; padding: 25px; border-radius: 10px;">
            <h1 style="border-bottom: 4px solid #111; padding-bottom: 10px; margin: 0; text-align: center;">🏛️ VIP 주식 전략 리포트</h1>
            
            <div style="background: #f8f9fa; border: 1px solid #ddd; padding: 15px; margin-top: 20px; font-size: 12px; line-height: 1.6;">
                <b style="font-size: 14px; color: #111;">[📊 투자 지표 컬러 가이드]</b><br>
                • <b>상승여력:</b> 전문가 목표가 대비 <span style="color:#1a73e8;">15%↑(🔵기회)</span> / <span style="color:#d93025;">마이너스(🔴위험)</span><br>
                • <b>저점대비:</b> 52주 저점에서 <span style="color:#1a73e8;">10%이내(🔵바닥)</span> / <span style="color:#d93025;">30%↑(🔴과열)</span><br>
                • <b>PER:</b> <span style="color:#1a73e8;">25미만(🔵저평가)</span> / <span style="color:#d93025;">40초과(🔴고평가)</span><br>
                • <b>배당률:</b> <span style="color:#1a73e8;">3%↑(🔵혜자)</span> / <span style="color:#d93025;">1%미만(🔴낮음)</span>
            </div>

            <div style="margin-top: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 8px;">
                <b style="font-size: 15px; color: #111;">📰 사회/경제 주요 헤드라인 (7)</b>
                <ul style="margin: 10px 0 0 0; padding-left: 18px;">{headlines_html}</ul>
            </div>

            <p style="padding: 12px; background: #111; color:#fff; font-size: 14px; margin-top: 15px;"><b>🌍 오늘의 전장 상황:</b> {m_context}</p>
    """

    for brand, ticker in STOCK_MAP.items():
        print(f"🔍 {brand}({ticker}) 분석 중...")
        d = get_stock_details(ticker)
        if not d: continue
        news = fetch_korean_news(brand)
        
        # 헤더 음영 로직 (2026-02-13 v1.3)
        header_bg = "#fce8e6" if d['pct'] > 0 else "#e8f0fe"
        text_color = "#d93025" if d['pct'] > 0 else "#1a73e8"

        html += f"""
        <div style="margin-top: 25px; border: 1px solid #eee; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
            <div style="background: {header_bg}; padding: 15px; display: flex; justify-content: space-between; align-items: center;">
                <b style="font-size: 18px; color: #111;">{brand} <small style="color:#666;">{ticker}</small> {d['flags']}</b>
                <div style="text-align: right;">
                    <b style="color:{text_color}; font-size: 20px;">{d['pct']:+.2f}%</b>
                    <div style="font-size: 14px; font-weight:bold;">${d['price']}</div>
                </div>
            </div>
            <div style="padding: 15px; background: #fff;">
                <table style="width: 100%; font-size: 13px; margin-bottom: 12px;">
                    <tr><td>상승여력: <b style="color:{d['u_color']};">{d['upside']}</b></td><td>저점대비: <b style="color:{d['l_color']};">{d['dist_low']}</b></td></tr>
                    <tr><td>PER: <b style="color:{d['p_color']};">{d['per']}배</b></td><td>배당률: <b style="color:{d['d_color']};">{d['div']}</b></td></tr>
                    <tr><td>투자의견: <b>{d['opinion']}</b></td><td>시가총액: <b>{d['cap']}</b></td></tr>
                </table>
                <ul style="margin: 0; padding-left: 18px; border-top: 1px solid #f5f5f5; padding-top: 10px;">{news}</ul>
            </div>
        </div>
        """
        time.sleep(0.5)

    html += "</div></body></html>"
    
    # [이메일 객체 생성 및 다중 수신인 설정] ----------------------------------------
    msg = MIMEMultipart("alternative")
    msg['Subject'] = f"[{datetime.now().strftime('%m/%d')}] 🏛️ 형님! 설계 이력 관리되는 VIP 리포트 배달왔습니다!"
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = ", ".join(RECIPIENTS)
    msg.attach(MIMEText(html, "html"))
    
    # [SMTP 서버 접속 및 발송] ----------------------------------------------------
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            s.send_message(msg)
        print(f"✅ 총 {len(RECIPIENTS)}명에게 리포트 발송 완료!")
    except Exception as e:
        print(f"❌ 발송 실패: {e}")
