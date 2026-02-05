import os, json, gspread, smtplib, time
from email.mime.text import MIMEText
from newsapi import NewsApiClient
from google import genai 
from datetime import datetime, timedelta

# [환경 변수]
NEWS_API_KEY = os.environ.get('NEWS_API_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
SERVICE_ACCOUNT_JSON = os.environ.get('SERVICE_ACCOUNT_JSON')

newsapi = NewsApiClient(api_key=NEWS_API_KEY)
client = genai.Client(api_key=GEMINI_API_KEY)

def get_stock_keywords():
    try:
        service_account_info = json.loads(SERVICE_ACCOUNT_JSON)
        gc = gspread.service_account_from_dict(service_account_info)
        sh = gc.open("test") 
        worksheet = sh.worksheet("주식키워드")
        records = worksheet.get_all_records()
        return [{str(k).strip(): v for k, v in r.items()} for r in records if r.get('Status') == 'Active']
    except Exception as e:
        print(f"시트 에러: {e}")
        return []

def fetch_news_brief(ticker):
    """뉴스 양을 딱 2개로 제한해서 서버 부담을 최소화합니다."""
    three_days = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    try:
        news = newsapi.get_everything(q=ticker, from_param=three_days, language='en', sort_by='relevancy')
        return news['articles'][:2]
    except: return []

def analyze_with_iron_will(ticker, name, news_list):
    """
    🔥 [근성 모드] 에러 나면 1분을 쉬더라도 다시 시도합니다.
    """
    news_text = "\n".join([f"- {n['title']}" for n in news_list])
    prompt = f"{ticker}({name}) 뉴스 핵심 요약 및 투자 심리 알려줘.\n뉴스:\n{news_text}"
    
    # 🌟 가장 검증된 모델명 'gemini-1.5-flash'를 사용합니다.
    target_model = "gemini-1.5-flash" 
    
    for attempt in range(4): # 최대 4번 재시도
        try:
            response = client.models.generate_content(model=target_model, contents=prompt)
            return response.text
        except Exception as e:
            # 429(한도초과) 또는 500(서버장애) 발생 시 대기
            wait_time = 60 if "429" in str(e) else 30
            print(f"🚨 {ticker} 처리 중 문제 발생({e}). {wait_time}초 후 재시도... ({attempt+1}/4)")
            time.sleep(wait_time)
            
    return "❌ 구글 서버 상태가 불안정하여 요약에 실패했습니다. 뉴스 제목만 참고해 주세요."

def discover_hot_tickers():
    """오늘의 핫 종목 발굴 (최대한 안정적으로!)"""
    try:
        top = newsapi.get_top_headlines(category='business', country='us')
        headlines = "\n".join([a['title'] for a in top['articles'][:5]])
        prompt = f"다음 뉴스 중 가장 핫한 주식 티커 2개만 골라줘. 형식: ['티커1', '티커2']\n뉴스: {headlines}"
        # 발굴 단계도 정석 모델 사용
        response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        return eval(response.text.strip())
    except: return ["AAPL", "NVDA"]

if __name__ == "__main__":
    print("🚀 작업을 시작합니다, 형님!!")
    stocks = get_stock_keywords()
    total_report = "🇺🇸 형님! 끈질기게 매달려 받아온 리포트입니다! 🇺🇸\n\n"
    
    # 1. 시트 종목 분석 (10개 정도로 줄이셨으니 금방 할 겁니다!)
    for stock in stocks:
        t, n = stock.get('Ticker'), stock.get('Name')
        print(f"🔍 {n}({t}) 분석 중...")
        news = fetch_news_brief(t)
        if news:
            total_report += f"📊 [{t} - {n}]\n{analyze_with_iron_will(t, n, news)}\n"
            print("☕ 다음 종목을 위해 30초간 쉽니다...")
            time.sleep(30) # 넉넉하게 30초 휴식!
        total_report += "="*40 + "\n"

    # 2. AI 발굴 종목
    hot_tickers = discover_hot_tickers()
    total_report += "\n🚀 [AI 특별 발굴 종목]\n"
    for t in hot_tickers:
        news = fetch_news_brief(t)
        if news:
            total_report += f"🌟 HOT - {t}\n{analyze_with_iron_will(t, t, news)}\n"
            time.sleep(30)
        total_report += "="*40 + "\n"
    
    # 이메일 전송
    msg = MIMEText(total_report)
    msg['Subject'] = f"[{datetime.now().strftime('%Y-%m-%d')}] 형님! 필승의 리포트 도착했습니다!"
    msg['From'], msg['To'] = EMAIL_ADDRESS, EMAIL_ADDRESS
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
        s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        s.send_message(msg)
    print("✅ 형님! 이번엔 진짜 성공입니다!")
