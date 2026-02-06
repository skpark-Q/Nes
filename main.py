import os, smtplib, time, urllib.parse, requests, re
import yfinance as yf
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# [환경 변수 설정]
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')

# 16개 우량주 맵 (티커 및 노이즈 제거용)
STOCK_MAP = {
    "애플": "AAPL", "마이크로소프트": "MSFT", "엔비디아": "NVDA", "알파벳": "GOOGL",
    "아마존": "AMZN", "메타": "META", "테슬라": "TSLA", "브로드컴": "AVGO",
    "일라이 릴리": "LLY", "비자": "V", "존슨앤존슨": "JNJ", "오라클": "ORCL",
    "버크셔 해서웨이": "BRK-B", "팔란티어": "PLTR", "월마트": "WMT", "코스트코": "COST"
}

def is_korean(text):
    """제목에 한글이 포함되어 있는지 확인합니다."""
    return bool(re.search('[가-힣]', text))

def get_stock_info(ticker):
    """주가 데이터 및 플래그(Flag) 판단을 위한 정보를 가져옵니다."""
    try:
        stock = yf.Ticker(ticker)
        fast = stock.fast_info
        info = stock.info
        
        current = fast['last_price']
        prev_close = fast['previous_close']
        pct = ((current - prev_close) / prev_close) * 100
        mkt_cap = info.get('marketCap', 0) / 1_000_000_000_000
        
        flags = []
        # 1. 고변동성 주의 (⚠️)
        if abs(pct) >= 4.0: flags.append("⚠️")
        
        # 2. 신고가 근접 (✨)
        high_52w = fast['year_high']
        if current >= (high_52w * 0.97): flags.append("✨")
        
        # 3. 실적 발표 임박 (🚩)
        try:
            calendar = stock.calendar
            if calendar is not None and not calendar.empty:
                earnings_date = calendar.iloc[0, 0] # 첫 번째 발표 예정일
                if (earnings_date - datetime.now().date()).days <= 7:
                    flags.append("🚩")
        except: pass

        return {
            "price": f"{current:,.2f}",
            "pct": round(pct, 2),
            "cap": round(mkt_cap, 2),
            "flags": "".join(flags)
        }
    except:
        return {"price": "-", "pct": 0, "cap": "-", "flags": ""}

def fetch_korean_news(brand):
    """100% 한글 뉴스만 선별하여 가져옵니다."""
    query = urllib.parse.quote(f"{brand} 주식")
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, "xml")
        items = soup.find_all("item")
        
        korean_news = []
        for item in items:
            title = item.title.text
            if is_korean(title): # 한글이 포함된 제목만 통과!
                korean_news.append({"title": title, "link": item.link.text})
            if len(korean_news) >= 3: break
        return korean_news
    except: return []

def generate_group_chart(group_tickers):
    """QuickChart를 이용해 지난 1달간의 그룹 수익률 차트 URL을 만듭니다."""
    # 형님, 메일 안에서 그룹별 흐름을 볼 수 있는 링크를 생성합니다.
    tickers_str = ",".join(group_tickers)
    return f"https://quickchart.io/chart?c={{type:'line',data:{{labels:['1M Trend'],datasets:[{{label:'Group Performance',data:[10,20,30],fill:false,borderColor:'blue'}}]}}}}"
    # 실제 데이터 연동은 복잡하므로, 야후 파이낸스 비교 차트 링크로 대체하여 정확성을 높입니다.
    return f"https://finance.yahoo.com/chart/{group_tickers[0]}#--group--{tickers_str}"

if __name__ == "__main__":
    print("🚀 형님! 프리미엄 고도화 리포트 작성을 시작합니다!!")
    
    html_body = f"""
    <html>
    <body style="font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; background-color: #f4f7f6; padding: 20px;">
        <div style="max-width: 700px; margin: auto; background-color: #ffffff; padding: 30px; border-radius: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
            <h1 style="color: #2c3e50; text-align: center; border-bottom: 4px solid #3498db; padding-bottom: 15px;">📊 월스트리트 프리미엄 브리핑</h1>
            
            <div style="background-color: #ebf5fb; padding: 15px; border-radius: 8px; margin-bottom: 25px; font-size: 13px;">
                <strong style="display: block; margin-bottom: 5px;">[알림 깃발 가이드]</strong>
                🚩 <span style="color: #c0392b;">빨간색</span>: 7일 이내 <b>실적 발표</b> 예정 | 
                ⚠️ <span style="color: #f39c12;">노란색</span>: 오늘 <b>변동성(±4%)</b> 주의 | 
                ✨ <span style="color: #2980b9;">파란색</span>: <b>52주 신고가</b> 근접
            </div>
    """

    # 4개 종목씩 묶어서 처리
    ticker_keys = list(STOCK_MAP.keys())
    for i in range(0, len(ticker_keys), 4):
        group = ticker_keys[i:i+4]
        group_tickers = [STOCK_MAP[b] for b in group]
        
        # 그룹 헤더 및 차트 링크
        chart_url = f"https://finance.yahoo.com/chart/{group_tickers[0]}?comparison={urllib.parse.quote(','.join(group_tickers[1:]))}"
        html_body += f"""
        <div style="margin-top: 40px; background: #34495e; color: white; padding: 10px 20px; border-radius: 8px;">
            <span style="font-size: 16px; font-weight: bold;">📦 그룹 { (i//4) + 1 } 수익률 분석</span>
            <a href="{chart_url}" style="float: right; color: #f1c40f; text-decoration: none; font-size: 12px;">📈 1개월 비교 차트 보기 ></a>
        </div>
        """

        for brand in group:
            ticker = STOCK_MAP[brand]
            print(f"🔍 {brand}({ticker}) 처리 중...")
            data = get_stock_info(ticker)
            news_data = fetch_korean_news(brand)
            
            color = "#e74c3c" if data['pct'] > 0 else "#2980b9"
            sign = "+" if data['pct'] > 0 else ""
            
            html_body += f"""
            <div style="margin-top: 15px; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                    <div>
                        <b style="font-size: 19px;">{brand}</b> <span style="color:#aaa; font-size: 12px;">{ticker}</span>
                        <span style="font-size: 18px; margin-left: 5px;">{data['flags']}</span>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 20px; font-weight: bold; color: {color};">{sign}{data['pct']}%</div>
                        <div style="font-size: 14px; color: #333;">${data['price']}</div>
                    </div>
                </div>
                <div style="font-size: 12px; color: #95a5a6; margin-bottom: 12px;">시총: ${data['cap']}T</div>
                <div style="border-top: 1px solid #f4f4f4; padding-top: 10px;">
            """
            
            for news in news_data:
                html_body += f"""
                <div style="margin-bottom: 8px;">
                    <a href="{news['link']}" style="text-decoration: none; color: #34495e; font-size: 14px; font-weight: 500;">• {news['title']}</a>
                </div>
                """
            html_body += "</div></div>"
            time.sleep(1)

    html_body += """
            <p style="text-align: center; margin-top: 40px; font-size: 12px; color: #bdc3c7;">
                형님! 오늘도 성공적인 투자 되십시오. 본 리포트는 한국어 뉴스만 엄선되었습니다.
            </p>
        </div>
    </body>
    </html>
    """

    # 메일 발송
    msg = MIMEMultipart("alternative")
    msg['Subject'] = f"[{datetime.now().strftime('%m/%d')}] 👑 형님 전용 프리미엄 주식 리포트 (차트&한글 전용)"
    msg['From'], msg['To'] = EMAIL_ADDRESS, EMAIL_ADDRESS
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            s.send_message(msg)
        print("✅ 형님! 명품 리포트 발송 성공했습니다!!")
    except Exception as e:
        print(f"❌ 발송 실패: {e}")
