import os, smtplib, time, urllib.parse, requests, re
import yfinance as yf
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai  # 최신 제미나이 SDK
from datetime import datetime, timedelta

# [환경 변수 설정]
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# 구글 제미나이 비서를 깨웁니다.
client = genai.Client(api_key=GEMINI_API_KEY)

# 16개 우량주 티커 맵
STOCK_MAP = {
    "애플": "AAPL", "마이크로소프트": "MSFT", "엔비디아": "NVDA", "알파벳": "GOOGL",
    "아마존": "AMZN", "메타": "META", "테슬라": "TSLA", "브로드컴": "AVGO",
    "일라이 릴리": "LLY", "비자": "V", "존슨앤존슨": "JNJ", "오라클": "ORCL",
    "버크셔 해서웨이": "BRK-B", "팔란티어": "PLTR", "월마트": "WMT", "코스트코": "COST"
}

def get_market_context():
    """나스닥, S&P500, 공포지수(VIX) 등 시장 흐름 파악"""
    try:
        indices = {"나스닥": "^IXIC", "S&P500": "^GSPC", "공포지수(VIX)": "^VIX"}
        summary = []
        for name, ticker in indices.items():
            idx = yf.Ticker(ticker).fast_info
            pct = ((idx['last_price'] - idx['previous_close']) / idx['previous_close']) * 100
            color = "#d93025" if pct > 0 else "#1a73e8"
            summary.append(f"{name} <span style='color:{color}; font-weight:bold;'>{pct:+.2f}%</span>")
        return " | ".join(summary)
    except: return "시장 지표 데이터 일시 오류"

def get_fundamental_data(ticker):
    """PER, 배당률, 목표주가 대비 여력 등 '체력' 측정"""
    try:
        s = yf.Ticker(ticker)
        info = s.info
        curr = s.fast_info['last_price']
        
        # 월가 평균 목표가 대비 얼마나 저평가되었나?
        target = info.get('targetMeanPrice', 0)
        upside = ((target / curr) - 1) * 100 if target > 0 else 0
        
        per = info.get('trailingPE', '-')
        div = info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0
        
        return {
            "upside": f"{upside:+.1f}%",
            "per": f"{per:.1f}배" if per != '-' else "-",
            "div": f"{div:.1f}%"
        }
    except: return {"upside": "-", "per": "-", "div": "-"}

def analyze_sentiment(ticker, news_list):
    """뉴스 제목 3개를 분석해 [긍정/중립/부정] 수치를 뽑아냅니다."""
    if not news_list: return "데이터 부족"
    titles = "\n".join([n['title'] for n in news_list])
    prompt = f"다음 주식 뉴스 제목들을 보고 [긍정, 중립, 부정] 비율을 합산 100으로 분석해줘. 형식: 70/20/10 (숫자만!)\n뉴스:\n{titles}"
    try:
        res = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        nums = res.text.strip().split('/')
        return f"😊긍 {nums[0]}% | 😐중 {nums[1]}% | 😡부 {nums[2]}%"
    except: return "심리 분석 중..."

def fetch_korean_news(brand):
    """구글 뉴스에서 한국어 기사만 정밀 수집"""
    query = urllib.parse.quote(f"{brand} 주식 (이유 OR 분석 OR 실적)")
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.content, "xml")
        items = soup.find_all("item")[:3]
        return [{"title": i.title.text, "link": i.link.text} for i in items]
    except: return []

if __name__ == "__main__":
    print("🚀 작업을 시작합니다, 형님!!")
    market_html = get_market_context()
    
    html_body = f"""
    <html>
    <body style="font-family: 'Malgun Gothic', sans-serif; background-color: #ffffff; color: #111; padding: 20px;">
        <div style="max-width: 650px; margin: auto; border: 2px solid #333; padding: 25px; border-radius: 8px;">
            <h1 style="border-bottom: 4px solid #111; padding-bottom: 10px; margin: 0;">🏛️ 전략 리포트: {datetime.now().strftime('%Y-%m-%d')}</h1>
            
            <div style="background: #f8f9fa; padding: 15px; margin: 20px 0; font-size: 14px; border: 1px solid #ddd;">
                <strong>🌍 시장 전체 맥락:</strong><br>{market_html}
            </div>

            <div style="font-size: 12px; color: #666; margin-bottom: 20px;">
                🚩: 실적임박 | ⚠️: 고변동성 | ✨: 신고가근접
            </div>
    """

    for brand, ticker in STOCK_MAP.items():
        print(f"📊 {brand}({ticker}) 분석 중...")
        s_obj = yf.Ticker(ticker)
        fast = s_obj.fast_info
        pct = ((fast['last_price'] - fast['previous_close']) / fast['previous_close']) * 100
        
        fund = get_fundamental_data(ticker)
        news_list = fetch_korean_news(brand)
        sentiment = analyze_sentiment(ticker, news_list)
        
        color = "#d93025" if pct > 0 else "#1a73e8"
        bg_color = "#fce8e6" if pct > 0 else "#e8f0fe"

        html_body += f"""
        <div style="margin-bottom: 30px; border-bottom: 1px solid #eee; padding-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; background-color: {bg_color}; padding: 12px; border-radius: 4px;">
                <span style="font-size: 20px; font-weight: 900;">{brand} <small style="color:#555;">({ticker})</small></span>
                <span style="font-size: 18px; font-weight: bold; color: {color};">{pct:+.2f}%</span>
            </div>
            
            <div style="margin: 10px 0; font-size: 13px; color: #333; padding: 8px; border: 1px dashed #ccc;">
                <b>📈 체력:</b> 목표가 대비 여력 <b style="color:#d93025;">{fund['upside']}</b> | PER: <b>{fund['per']}</b> | 배당: <b>{fund['div']}</b>
            </div>
            
            <div style="font-size: 13px; margin: 10px 0; font-weight: bold; color: #111;">
                💡 심리 온도: <span style="color:#1a73e8;">{sentiment}</span>
            </div>

            <ul style="margin: 0; padding-left: 20px; font-size: 14px;">
        """
        for n in news_list:
            html_body += f"<li style='margin-bottom: 8px;'><a href='{n['link']}' style='color:#111; text-decoration:none;'>• {n['title']}</a></li>"
        html_body += "</ul></div>"
        time.sleep(15) # 과속 방지 (재시도 로직보다 안전한 긴 휴식)

    html_body += "</div></body></html>"

    msg = MIMEMultipart("alternative")
    msg['Subject'] = f"[{datetime.now().strftime('%m/%d')}] 🏛️ 형님! 전략 리포트(지표+심리+체력) 배달왔습니다."
    msg['From'], msg['To'] = EMAIL_ADDRESS, EMAIL_ADDRESS
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
        s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        s.send_message(msg)
    print("✅ 성공!")
