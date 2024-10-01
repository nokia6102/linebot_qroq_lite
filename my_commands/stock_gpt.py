import os
import openai
import yfinance as yf
from groq import Groq, GroqError
import pandas as pd
from my_commands.stock_price import stock_price
from my_commands.stock_news import stock_news
from my_commands.stock_value import stock_fundamental
from database import initialize_database  # 從 database.py 引入初始化函數

# 設定 API 金鑰
openai.api_key = os.getenv("OPENAI_API_KEY")
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# 初始化資料庫
initialize_database()  # 呼叫初始化資料庫的函數

# 讀取初始化後的股票資料
df_stock_data = pd.read_csv('existing_data.csv')

# 移除全形空格的函數
def remove_full_width_spaces(data):
    if isinstance(data, list):
        return [remove_full_width_spaces(item) for item in data]
    if isinstance(data, str):
        return data.replace('\u3000', ' ')
    return data

# 截取前1024個字的函數
def truncate_text(data, max_length=1024):
    if isinstance(data, list):
        return [truncate_text(item, max_length) for item in data]
    if isinstance(data, str):
        return data[:max_length]
    return data

# 從資料框取得股票名稱
def get_stock_name(stock_id):
    """根據 stock_id 從資料框中取得對應的股票名稱"""
    stock_row = df_stock_data[df_stock_data['stock_id'] == stock_id]
    if not stock_row.empty:
        return stock_row.iloc[0]['stock_name']
    else:
        return stock_id  # 如果找不到，返回 stock_id 自己

# 建立 GPT 模型回應的函數
def get_reply(messages):
    try:
        # 使用 OpenAI GPT-3.5-turbo 進行回應
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages)
        reply = response["choices"][0]["message"]["content"]
    except openai.OpenAIError as openai_err:
        try:
            # 如果 OpenAI 出錯，使用 Groq API 進行回應
            response = groq_client.chat.completions.create(
                model="llama3-70b-8192",
                messages=messages,
                max_tokens=2000,
                temperature=1.2
            )
            reply = response.choices[0].message.content
        except GroqError as groq_err:
            reply = f"OpenAI API 發生錯誤: {openai_err}，GROQ API 發生錯誤: {groq_err}"
    return reply

# 建立訊息指令 (Prompt)
def generate_content_msg(stock_id):
    # 檢查是否為美盤
    if stock_id == "美盤" or stock_id == "美股":
        stock_id = "^GSPC"  # 標普500指數的代碼
        stock_name = "美國大盤"
    else:
        # 從資料框中取得股票名稱
        stock_name = get_stock_name(stock_id)

    # 取得股票價格資訊
    price_data = stock_price(stock_id)

    # 取得新聞資料並移除全形空格及截取
    news_data = remove_full_width_spaces(stock_news(stock_name))
    news_data = truncate_text(news_data, 1024)

    # 組合訊息
    content_msg = (
        '你現在是一位專業的證券分析師, '
        '你會依據以下資料來進行分析並給出一份完整的分析報告:\n'
        f'近期價格資訊:\n {price_data}\n'
    )

    # 如果不是大盤或美股，加入基本面資料
    if stock_id not in ["大盤", "^GSPC"]:
        stock_value_data = stock_fundamental(stock_id)
        if stock_value_data:
            content_msg += f'每季營收資訊：\n {stock_value_data}\n'
        else:
            content_msg += '每季營收資訊無法取得。\n'

    content_msg += f'近期新聞資訊: \n {news_data}\n'
    content_msg += f'請給我{stock_name}近期的趨勢報告，並以詳細、嚴謹及專業的角度撰寫此報告，請使用台灣地區的繁體中文回答。'

    return content_msg

# StockGPT: 呼叫 GPT 模型來分析股票
def stock_gpt(stock_id):
    content_msg = generate_content_msg(stock_id)

    msg = [
        {
            "role": "system",
            "content": "你是一位專業的證券分析師, "
                       "你會統整近期的股價、基本面、新聞資訊等方面，"
                       "並進行完整的趨勢分析。請使用台灣地區的繁體中文回答。"
        },
        {
            "role": "user",
            "content": content_msg
        }
    ]

    reply_data = get_reply(msg)

    return reply_data

# stock_value.py 內的 stock_fundamental 函數增加錯誤處理
def stock_fundamental(stock_id):
    # 如果是大盤或美盤，不需要取得營收資料
    if stock_id == "^GSPC":
        print("美國大盤無需營收資料分析")
        return None  # 大盤無需營收資料

    stock = yf.Ticker(stock_id)
    try:
        # 取得公司財報資訊
        earnings_dates = stock.get_earnings_dates()
    except Exception as e:
        print(f"Error fetching earnings dates: {e}")
        return None

    if earnings_dates is None:
        print("No earnings dates found for the symbol.")
        return None

    # 確認 'Earnings Date' 列是否存在，避免 KeyError
    if "Earnings Date" not in earnings_dates.columns:
        print("Column 'Earnings Date' not found in the data")
        return None

    # 確認是否有 'Reported EPS' 資料
    if "Reported EPS" in earnings_dates.columns:
        reported_eps = earnings_dates["Reported EPS"]
        return reported_eps
    else:
        print("Column 'Reported EPS' not found in the data")
        return None
