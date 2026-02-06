import os, smtplib, time, urllib.parse, requests, re
import yfinance as yf
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai
from datetime import datetime, timedelta

# [환경 변수 설정]
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

client = genai.Client(api_key=GEMINI_API_KEY)

# 16개 우량주 맵
STOCK_MAP = {
    "애플": "AAPL", "마이크로소프트": "MSFT", "엔비디아": "NVDA", "알파벳": "GOOGL",
    "아마존": "AMZN", "메타": "META", "테슬라": "TSLA", "브로드컴": "AVGO",
    "일라이 릴리": "LLY", "비자": "V", "존슨앤존슨": "JNJ", "오라클": "ORCL",
    "버크셔 해서웨이": "BRK-B", "팔란티어": "PLTR", "월마트": "WMT", "코스트코": "COST"
}

def get_market_context():
    """상단 시장 요약 (나스닥, S&P500, VIX)"""
    try:
        indices = {"나스닥": "^IXIC", "S&P500": "^GSPC", "공포지수(VIX)": "^VIX"}
        summary = []
        for name, ticker in indices.items():
            idx = yf.Ticker(ticker).fast_info
            pct = ((idx['last_price'] - idx['previous_close']) / idx['previous_close']) * 100
            color = "#d93025" if pct > 0 else "#1a73e8"
            summary.append(f"{name}: <b style='color:{color};'>{pct:+.2f}%</b>")
        return " | ".join(summary)
    except: return "시장 지표를 불러오는 중입니다..."

def get_fundamental_data(ticker):
    """체력 측정 데이터 수집 ($PER$, 배당률, 목표주가)"""
    try:
        s = yf.Ticker(ticker)
        info = s.info
        fast = s.fast_info
        
        curr = fast['last_price']
        target = info.get('targetMeanPrice', 0)
        # 전문가 목표가 대비 상승 여력 계산
        upside = ((target / curr) - 1) * 100 if target > 0 else 0
        
        per = info.get('trailingPE', '-')
        div = info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0
        
        return {
            "upside": round(upside, 1),
            "per": f"{per:.1f}" if per != '-' else "-",
            "div": f"{div:.1f}%"
        }
    except: return {"upside": 0, "per": "-", "div": "-"}

def analyze_sentiment(ticker, news_list):
    """AI가 기사 제목으로 심리 온도 분석"""
    if not news_list: return "[데이터 없음]"
    titles = "\n".join([n['title'] for n in news_list])
    prompt = f"다음 {ticker} 뉴스 제목들을 보고 [긍정, 중립, 부정] 비율을 합쳐서 100이 되게 숫자만 보내줘. 형식: 70/20/10\n뉴스:\n{titles}"
    try:
        res = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        nums = res.text.strip().split('/')
        return f"😊긍정 {nums[0]}% | 😐중립 {nums[1]}% | 😡부정 {nums[2]}%"
    except: return "투자 심리 분석 중..."

def fetch_reason_news(brand):
    """한국어 뉴스 수집"""
    query = urllib.parse.quote(f"{brand} 주식 (이유 OR 분석 OR 전망)")
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.content, "xml")
        items = soup.find_all("item")
        results = []
        for item in items:
            title = item.title.text
            if bool(re.search('[가-힣]', title)) and len(results) < 3:
                results.append({"title": title, "link": item.link.text})
        return results
    except: return []

if __name__ == "__main__":
    print("🚀 형님! 고도화 리포트 작성을 시작합니다!!")
    market_html = get_market_context()
    
    html_body = f"""
    <html>
    <body style="font-family: 'Malgun Gothic', sans-serif; background-color: #ffffff; color: #111; padding: 20px;">
        <div style="max-width: 650px; margin: auto; border: 1px solid #000; padding: 25px;">
            <h1 style="border-bottom: 3px solid #000; padding-bottom: 10px; margin: 0;">🏛️ 월스트리트 전략 리포트 (2026)</h1>
            <div style="background: #f9f9f9; padding: 15px; margin-top: 15px; font-size: 14px; border: 1px solid #ddd;">
                <strong>🌍 시장 전체 맥락:</strong> {market_html}
            </div>
    """

    for brand, ticker in STOCK_MAP.items():
        print(f"🔍 {brand}({ticker}) 처리 중...")
        # 기존 데이터 + 신규 데이터 합치기
        stock_obj = yf.Ticker(ticker)
        fast = stock_obj.fast_info
        pct = ((fast['last_price'] - fast['previous_close']) / fast['previous_close']) * 100
        
        fund = get_fundamental_data(ticker)
        news = fetch_reason_news(brand)
        sent = analyze_sentiment(ticker, news)
        
        color = "#d93025" if pct > 0 else "#1a73e8"
        upside_color = "#d93025" if fund['upside'] > 0 else "#1a73e8"

        html_body += f"""
        <div style="margin-top: 30px; border-bottom: 1px solid #eee; padding-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: baseline;">
                <span style="font-size: 22px; font-weight: 900;">{brand} <small style="color:#777;">{ticker}</small></span>
                <span style="font-size: 18px; font-weight: bold; color: {color};">{pct:+.2f}%</span>
            </div>
            
            <div style="margin: 10px 0; font-size: 13px; color: #444; background: #fdfdfd; padding: 10px; border: 1px solid #eee;">
                <b>📈 체력 측정:</b> 목표가 대비 <span style="color:{upside_color}; font-weight:bold;">{fund['upside']:+.1f}% 여력</span> | 
                $PER$: <b>{fund['per']}배</b> | 배당: <b>{fund['div']}</b>
            </div>
            
            <div style="font-size: 13px; margin-bottom: 10px; color: #1a73e8; font-weight: bold;">
                🔥 심리 온도: {sent}
            </div>

            <ul style="margin: 0; padding-left: 20px; font-size: 14px;">
        """
        for n in news:
            html_body += f"<li style='margin-bottom: 8px;'><a href='{n['link']}' style='color:#111; text-decoration:none;'>• {n['title']}</a></li>"
        html_body += "</ul></div>"
        time.sleep(12)

    html_body += "</div></body></html>"

    # [발송] (이전 코드와 동일하므로 생략 가능하나 완결성을 위해 유지)
    msg = MIMEMultipart("alternative")
    msg['Subject'] = f"[{datetime.now().strftime('%m/%d')}] 🏛️ 형님! 전략 리포트(지표+심리+체력) 도착했습니다."
    msg['From'], msg['To'] = EMAIL_ADDRESS, EMAIL_ADDRESS
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
        s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        s.send_message(msg)
    print("✅ 발송 성공!")
