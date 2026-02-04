import os
import gspread
import smtplib
from email.mime.text import MIMEText
from newsapi import NewsApiClient
import google.generativeai as genai
from datetime import datetime, timedelta

# 1. 환경 변수 설정 (GitHub Secrets에서 가져올 예정입니다!)
NEWS_API_KEY = os.environ['NEWS_API_KEY']
GEMINI_API_KEY = os.environ['GEMINI_API_KEY']
EMAIL_ADDRESS = os.environ['EMAIL_ADDRESS']
EMAIL_PASSWORD = os.environ['EMAIL_PASSWORD'] # 앱 비밀번호

# 2. 서비스 연결
newsapi = NewsApiClient(api_key=NEWS_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def get_stock_keywords():
    # 'test' 시트의 '주식키워드' 탭 데이터 읽기
    gc = gspread.service_account(filename='service_account.json')
    sh = gc.open("test")
    worksheet = sh.worksheet("주식키워드")
    records = worksheet.get_all_records()
    return [r for r in records if r['Status'] == 'Active']

def fetch_news(ticker, name):
    # 어제부터 오늘까지의 최신 뉴스 검색
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    news = newsapi.get_everything(q=f"{ticker} OR {name}", from_param=yesterday, language='en', sort_by='relevancy')
    return news['articles'][:5] # 상위 5개 추출

def summarize_with_gemini(ticker, news_list):
    news_text = "\n".join([f"Title: {n['title']}\nDescription: {n['description']}" for n in news_list])
    prompt = f"""
    당신은 전문 주식 분석가입니다. 다음은 {ticker}에 관한 최신 뉴스입니다.
    핵심 내용을 한국어로 3줄 요약하고, 투자 심리를 '긍정/중립/부정'으로 판단해 주세요.
    뉴스:
    {news_text}
    """
    response = model.generate_content(prompt)
    return response.text

def send_email(content):
    msg = MIMEText(content)
    msg['Subject'] = f"[{datetime.now().strftime('%Y-%m-%d')}] 형님! 오늘의 주식 리포트 도착했습니다!"
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = EMAIL_ADDRESS # 본인에게 발송

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

# 메인 실행부
if __name__ == "__main__":
    stocks = get_stock_keywords()
    total_report = "형님! 좋은 아침입니다. 요청하신 주식 소식 정리해 드립니다!\n\n"
    
    for stock in stocks:
        news = fetch_news(stock['Ticker'], stock['Name'])
        summary = summarize_with_gemini(stock['Ticker'], news)
        total_report += f"📊 [{stock['Ticker']} - {stock['Name']}]\n{summary}\n"
        total_report += "-"*30 + "\n"
    
    send_email(total_report)
