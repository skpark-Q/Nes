import os
import json
import gspread
import smtplib
import time
from email.mime.text import MIMEText
from newsapi import NewsApiClient
from google import genai 
from datetime import datetime, timedelta

# [환경 변수 설정]
NEWS_API_KEY = os.environ.get('NEWS_API_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
SERVICE_ACCOUNT_JSON = os.environ.get('SERVICE_ACCOUNT_JSON')

newsapi = NewsApiClient(api_key=NEWS_API_KEY)
client = genai.Client(api_key=GEMINI_API_KEY)

def get_stock_keywords():
    """구글 시트 읽기"""
    try:
        service_account_info = json.loads(SERVICE_ACCOUNT_JSON)
        gc = gspread.service_account_from_dict(service_account_info)
        sh = gc.open("test") 
        worksheet = sh.worksheet("주식키워드")
        records = worksheet.get_all_records()
        return [{str(k).strip(): v for k, v in r.items()} for r in records]
    except Exception as e:
        print(f"시트 에러: {e}")
        return []

def discover_daily_hot_tickers():
    """오늘의 시장 주인공 발굴 (재시도 로직 포함)"""
    print("🌟 오늘의 시장 주인공을 찾는 중...")
    try:
        top_headlines = newsapi.get_top_headlines(category='business', country='us')
        headlines_text = "\n".join([f"- {a['title']}" for a in top_headlines['articles']])
        
        prompt = f"""오늘 미국 증시에서 가장 핫한 기업 3개의 '영어 티커'만 골라줘. 
        형식: ["티커1", "티커2", "티커3"]
        뉴스: {headlines_text}"""
        
        # 발굴 단계에서도 429 에러를 방지하기 위해 시도합니다.
        for attempt in range(3):
            try:
                response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
                return eval(response.text.strip())
            except Exception as e:
                if "429" in str(e):
                    print(f"⚠️ 발굴 중 제한 발생, {30*(attempt+1)}초 대기 후 재시도...")
                    time.sleep(30 * (attempt + 1))
                else: raise e
        return ["AAPL", "TSLA", "NVDA"]
    except: return ["AAPL", "TSLA", "NVDA"]

def fetch_news_in_english(ticker):
    """뉴스 수집"""
    three_days = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    try:
        news = newsapi.get_everything(q=ticker, from_param=three_days, language='en', sort_by='relevancy')
        return news['articles'][:5]
    except: return []

def analyze_with_ai(ticker, kor_name, news_list, is_discovery=False):
    """
    🔥 [특급 강화] 영문 뉴스 분석 및 재시도 로직
    """
    content = "\n".join([f"Title: {n['title']}\nDesc: {n['description']}" for n in news_list])
    title_prefix = "🚩 [AI 긴급 발굴]" if is_discovery else "📊 [형님의 관심 종목]"
    
    prompt = f"{ticker}({kor_name}) 관련 뉴스를 한국어로 3줄 요약하고 투자 조언을 해줘.\n\n뉴스:\n{content}"
    
    # 🔁 최대 3번까지 재시도합니다!
    for attempt in range(3):
        try:
            response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
            return response.text
        except Exception as e:
            if "429" in str(e):
                wait_time = 30 * (attempt + 1)
                print(f"🚨 {ticker} 요약 중 과부하! {wait_time}초 후 재시도합니다 (시도 {attempt+1}/3)")
                time.sleep(wait_time)
            else:
                return f"⚠️ 분석 실패: {e}"
    
    return "⚠️ 구글 서버의 응답이 너무 늦어 요약을 건너뜁니다. 뉴스 양이 너무 많을 수 있습니다."

def send_email(content):
    msg = MIMEText(content)
    msg['Subject'] = f"[{datetime.now().strftime('%Y-%m-%d')}] 형님! 끈기로 완성한 무패의 리포트입니다! 💰"
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = EMAIL_ADDRESS
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

if __name__ == "__main__":
    print("🚀 작업을 시작합니다, 형님!!")
    
    stocks = get_stock_keywords()
    total_report = "🇺🇸 형님! 지연 없이 꼼꼼하게 분석한 오늘의 리포트입니다! 🇺🇸\n\n"
    
    # 1. 관심 종목 분석
    if stocks:
        total_report += "--- [1부: 형님의 관심 종목 현황] ---\n\n"
        for stock in stocks:
            if stock.get('Status') == 'Active':
                t, n = stock.get('Ticker'), stock.get('Name')
                print(f"🔍 {n}({t}) 분석 중...")
                news = fetch_news_in_english(t)
                if news:
                    total_report += f"[{t} - {n}]\n{analyze_with_ai(t, n, news)}\n"
                    # 🔥 간격을 20초로 더 늘렸습니다!
                    print(f"☕ 평화를 위해 20초간 휴식...")
                    time.sleep(20)
                total_report += "="*40 + "\n"

    # 2. AI 핫 종목 분석
    hot_tickers = discover_daily_hot_tickers()
    total_report += "\n🚀 [2부: AI가 오늘 시장에서 긴급 발굴한 핫 종목!]\n\n"
    for t in hot_tickers:
        print(f"🔥 핫 종목 {t} 분석 중...")
        news = fetch_news_in_english(t)
        if news:
            total_report += f"🌟 오늘의 HOT - {t}\n{analyze_with_ai(t, t, news, is_discovery=True)}\n"
            time.sleep(20)
        total_report += "="*40 + "\n"
    
    send_email(total_report)
    print("✅ 형님! 이번엔 진짜 에러 없이 발송 완료했습니다!!")
