import os
import json
import gspread
import smtplib
from email.mime.text import MIMEText
from newsapi import NewsApiClient
from google import genai  # 최신 2026년형 SDK
from datetime import datetime, timedelta

# 1. 환경 변수 설정 (GitHub Secrets에서 안전하게 가져오는 비결!)
NEWS_API_KEY = os.environ['NEWS_API_KEY']
GEMINI_API_KEY = os.environ['GEMINI_API_KEY']
EMAIL_ADDRESS = os.environ['EMAIL_ADDRESS']
EMAIL_PASSWORD = os.environ['EMAIL_PASSWORD']
SERVICE_ACCOUNT_JSON = os.environ['SERVICE_ACCOUNT_JSON']

# 2. 서비스 연결 (비서들 출근 준비!)
newsapi = NewsApiClient(api_key=NEWS_API_KEY)
client = genai.Client(api_key=GEMINI_API_KEY)

def get_stock_keywords():
    """구글 시트에서 종목 정보를 읽어오는 함수"""
    try:
        # 🔐 사원증(JSON)을 가상 비서에게 건네줍니다.
        service_account_info = json.loads(SERVICE_ACCOUNT_JSON)
        gc = gspread.service_account_from_dict(service_account_info)
        
        # 📄 'test' 시트의 '주식키워드' 탭을 엽니다.
        sh = gc.open("test")
        worksheet = sh.worksheet("주식키워드")
        
        # 🧹 [핵심 수정 부분] 데이터 청소 작업
        records = worksheet.get_all_records()
        if not records:
            return []

        clean_records = []
        for r in records:
            # 이름표(Key) 앞뒤에 붙은 '눈에 안 보이는 공백'을 싹 지워줍니다!
            # 예: "Ticker " -> "Ticker"
            clean_row = {str(k).strip(): v for k, v in r.items()}
            clean_records.append(clean_row)
            
        return clean_records
    except Exception as e:
        print(f"구글 시트 읽기 오류: {e}")
        return []

def fetch_news(ticker, name):
    """최신 뉴스를 긁어오는 함수"""
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    # 티커와 종목명을 섞어서 검색 효율을 극대화합니다!
    news = newsapi.get_everything(
        q=f"{ticker} OR {name}", 
        from_param=yesterday, 
        language='en', 
        sort_by='relevancy'
    )
    return news['articles'][:5]

def summarize_with_gemini(ticker, news_list):
    """AI가 뉴스를 읽고 요약하는 함수"""
    news_text = "\n".join([f"제목: {n['title']}\n내용: {n['description']}" for n in news_list])
    
    prompt = f"""
    당신은 세계 최고의 주식 분석가입니다. 
    다음 {ticker} 관련 뉴스를 읽고 형님께 보고하듯 한국어로 정리해 주세요.
    1. 핵심 요약 3줄 (강렬하게!)
    2. 투자 심리 (긍정/중립/부정 중 택 1)
    
    뉴스 내용:
    {news_text}
    """
    
    response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
    return response.text

def send_email(content):
    """최종 리포트를 형님 메일로 쏘는 함수"""
    msg = MIMEText(content)
    msg['Subject'] = f"[{datetime.now().strftime('%Y-%m-%d')}] 형님! 오늘의 주식 리포트 대령입니다! 💰"
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = EMAIL_ADDRESS

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

# 🚀 메인 실행부 (전체 프로세스 가동!)
if __name__ == "__main__":
    print("작업 시작합니다, 형님!!")
    
    stocks = get_stock_keywords()
    
    if not stocks:
        print("데이터가 없어서 종료합니다. 시트와 코드를 확인해 주세요!")
    else:
        total_report = "🌟 형님! 오늘 장 대응을 위한 핵심 요약본입니다! 🌟\n\n"
        
        for stock in stocks:
            # Active 상태인 종목만 처리하는 센스!
            if stock.get('Status') == 'Active':
                ticker = stock.get('Ticker')
                name = stock.get('Name')
                
                print(f"{name}({ticker}) 뉴스 분석 중...")
                news = fetch_news(ticker, name)
                summary = summarize_with_gemini(ticker, news)
                
                total_report += f"📊 [{ticker} - {name}]\n{summary}\n"
                total_report += "="*40 + "\n"
        
        send_email(total_report)
        print("형님! 방금 메일 보내드렸습니다! 확인해 보십쇼!! 🚀")
