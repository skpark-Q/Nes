import os, json, gspread, smtplib, time
from email.mime.text import MIMEText
from newsapi import NewsApiClient
from google import genai 
from datetime import datetime, timedelta

# [환경 변수] 기존 설정 그대로!
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
        # 공백 제거 및 필터링
        return [{str(k).strip(): v for k, v in r.items()} for r in records if r.get('Status') == 'Active']
    except Exception as e:
        print(f"시트 에러: {e}")
        return []

def fetch_news_brief(ticker):
    """뉴스 양을 2~3개로 대폭 줄여서 AI의 부담을 덜어줍니다!"""
    three_days = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    try:
        news = newsapi.get_everything(q=ticker, from_param=three_days, language='en', sort_by='relevancy')
        # 🔥 딱 2개만 가져옵니다. 이것만 해도 요약엔 충분합니다!
        return news['articles'][:2]
    except: return []

def analyze_with_retry(ticker, name, news_list, is_discovery=False):
    """
    🔥 [특급 A/S] 끈질긴 재시도 로직
    """
    news_text = "\n".join([f"- {n['title']}" for n in news_list])
    prompt = f"{ticker}({name}) 뉴스 2줄 요약 및 투자 심리 알려줘.\n뉴스:\n{news_text}"
    
    # 모델을 더 가벼운 'flash-lite'로 변경합니다!
    target_model = "gemini-1.5-flash-lite" 
    
    for attempt in range(5): # 최대 5번까지 매달립니다!
        try:
            response = client.models.generate_content(model=target_model, contents=prompt)
            return response.text
        except Exception as e:
            if "429" in str(e):
                wait_time = 40 + (attempt * 20) # 점점 더 길게 기다립니다.
                print(f"🚨 {ticker} 제한 발생! {wait_time}초 대기 중... (시도 {attempt+1})")
                time.sleep(wait_time)
            else:
                return f"⚠️ 분석 불가: {e}"
    return "❌ 구글 서버가 끝까지 거부했습니다. 내일 다시 시도해야 할 것 같습니다."

def discover_hot_tickers():
    """오늘의 주인공 발굴 (최대한 가볍게!)"""
    try:
        top = newsapi.get_top_headlines(category='business', country='us')
        headlines = "\n".join([a['title'] for a in top['articles'][:10]])
        prompt = f"다음 뉴스 중 가장 핫한 주식 티커 2개만 골라줘. 형식: ['티커1', '티커2']\n뉴스: {headlines}"
        response = client.models.generate_content(model="gemini-1.5-flash-lite", contents=prompt)
        return eval(response.text.strip())
    except: return ["AAPL", "NVDA"]

if __name__ == "__main__":
    print("🚀 작업을 시작합니다, 형님!!")
    stocks = get_stock_keywords()
    total_report = "🇺🇸 형님! 끈질기게 매달려 받아온 리포트입니다! 🇺🇸\n\n"
    
    # 1. 시트 종목 분석 (형님, 시트에서 10개로 줄이시면 더 빨리 끝납니다!)
    for stock in stocks:
        t, n = stock.get('Ticker'), stock.get('Name')
        print(f"🔍 {n}({t}) 분석 중...")
        news = fetch_news_brief(t)
        if news:
            total_report += f"📊 [{t} - {n}]\n{analyze_with_retry(t, n, news)}\n"
            time.sleep(15) # 종목 간 기본 휴식
        total_report += "="*40 + "\n"

    # 2. AI 발굴 종목 (2개만!)
    hot_tickers = discover_hot_tickers()
    total_report += "\n🚀 [AI 특별 발굴 종목]\n"
    for t in hot_tickers:
        news = fetch_news_brief(t)
        if news:
            total_report += f"🌟 HOT - {t}\n{analyze_with_retry(t, t, news, True)}\n"
            time.sleep(15)
        total_report += "="*40 + "\n"
    
    # 이메일 전송
    msg = MIMEText(total_report)
    msg['Subject'] = f"[{datetime.now().strftime('%Y-%m-%d')}] 형님! 오늘의 주식 소식 (필승 버전!)"
    msg['From'], msg['To'] = EMAIL_ADDRESS, EMAIL_ADDRESS
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
        s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        s.send_message(msg)
    print("✅ 완료!")
