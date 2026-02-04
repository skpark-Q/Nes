import os
import json
import gspread
import smtplib
from email.mime.text import MIMEText
from newsapi import NewsApiClient
from google import genai  # 최신 SDK로 변경!
from datetime import datetime, timedelta

# 1. 환경 변수 설정
NEWS_API_KEY = os.environ['NEWS_API_KEY']
GEMINI_API_KEY = os.environ['GEMINI_API_KEY']
EMAIL_ADDRESS = os.environ['EMAIL_ADDRESS']
EMAIL_PASSWORD = os.environ['EMAIL_PASSWORD']
SERVICE_ACCOUNT_JSON = os.environ['SERVICE_ACCOUNT_JSON'] # Secrets에서 가져옴

# 2. 서비스 연결
newsapi = NewsApiClient(api_key=NEWS_API_KEY)
# 최신 Gemini SDK 설정
client = genai.Client(api_key=GEMINI_API_KEY)

def get_stock_keywords():
    # 🔥 핵심 수정: 파일 대신 Secrets의 JSON 데이터를 직접 읽습니다!
    service_account_info = json.loads(SERVICE_ACCOUNT_JSON)
    gc = gspread.service_account_from_dict(service_account_info)
    
    sh = gc.open("test") # 시트 이름 확인!
    worksheet = sh.worksheet("주식키워드")
    return worksheet.get_all_records()

def fetch_news(ticker, name):
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    news = newsapi.get_everything(q=f"{ticker} OR {name}", from_param=yesterday, language='en', sort_by='relevancy')
    return news['articles'][:5]

def summarize_with_gemini(ticker, news_list):
    news_text = "\n".join([f"Title: {n['title']}\nDescription: {n['description']}" for n in news_list])
    prompt = f"당신은 전문 주식 분석가입니다. {ticker}에 관한 뉴스들을 한국어로 3줄 요약하고 투자 심리를 분석해줘.\n\n뉴스:\n{news_text}"
    
    # 최신 Gemini 호출 방식
    response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
    return response.text

def send_email(content):
    msg = MIMEText(content)
    msg['Subject'] = f"[{datetime.now().strftime('%Y-%m-%d')}] 형님! 오늘의 주식 리포트 도착했습니다!"
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = EMAIL_ADDRESS

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

if __name__ == "__main__":
    try:
        stocks = get_stock_keywords()
        total_report = "형님! 좋은 아침입니다. 요청하신 주식 소식 정리해 드립니다!\n\n"
        
        for stock in stocks:
            news = fetch_news(stock['Ticker'], stock['Name'])
            summary = summarize_with_gemini(stock['Ticker'], news)
            total_report += f"📊 [{stock['Ticker']} - {stock['Name']}]\n{summary}\n"
            total_report += "-"*30 + "\n"
        
        send_email(total_report)
        print("성공적으로 메일을 보냈습니다, 형님!!")
    except Exception as e:
        print(f"아이고 형님, 에러가 났습니다: {e}")
