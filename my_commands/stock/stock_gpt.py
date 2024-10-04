import os
import re
import pandas as pd
import yfinance as yf
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import PostbackEvent, TextSendMessage, MessageEvent, TextMessage
from linebot.models import *
from groq import Groq, GroqError
import requests
from my_commands.stock_price import stock_price
from my_commands.stock_news import stock_news
from my_commands.stock_value import stock_fundamental

# 設定 API 金鑰
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# 讀取 CSV 檔案並將其轉換為 DataFrame
stock_data_df = pd.read_csv('name_df.csv')

# 根據股號查找對應的股名
def get_stock_name(stock_id):
    result = stock_data_df[stock_data_df['股號'] == stock_id]
    if not result.empty:
        return result.iloc[0]['股名']
    return None

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

# 建立 GPT 模型
def get_reply(messages):
    try:
        response = groq_client.chat.completions.create(
            model="llama3-70b-8192",
            messages=messages,
            max_tokens=2000,
            temperature=1.2
        )
        reply = response.choices[0].message.content
        return reply
    except GroqError as groq_err:
        reply = f"GROQ API 發生錯誤: {groq_err.message}"
        return reply

# 建立訊息指令(Prompt)
def generate_content_msg(stock_id):
    # 檢查是否為美盤
    if stock_id == "美盤" or stock_id == "美股":
        stock_id = "^GSPC"  # 標普500指數的代碼
        stock_name = "美國大盤"
    else:
        # 使用 pandas 根據股號查找對應的股名
        stock_name = get_stock_name(int(stock_id))
        if not stock_name:
            stock_name = stock_id

    # 取得價格資訊
    price_data = stock_price(stock_id)
    # 取得新聞資料並移除全形空格字符及截取
    news_data = remove_full_width_spaces(stock_news(stock_name))
    news_data = truncate_text(remove_full_width_spaces(news_data), 1024)

    # 組合訊息
    content_msg = '你現在是一位專業的證券分析師, \
      你會依據以下資料來進行分析並給出一份完整的分析報告:\n'
    content_msg += f'近期價格資訊:\n {price_data}\n'

    if stock_id not in ["大盤", "^GSPC"]:
        stock_value_data = stock_fundamental(stock_id)
        if stock_value_data:
            content_msg += f'每季營收資訊：\n {stock_value_data}\n'
        else:
            content_msg += '每季營收資訊無法取得。\n'

    content_msg += f'近期新聞資訊: \n {news_data}\n'
    content_msg += f'請給我{stock_name}近期的趨勢報告。請以詳細、嚴謹及專業的角度撰寫此報告，並提及重要的數字，請使用台灣地區的繁體中文回答。'

    return content_msg

# StockGPT
def stock_gpt(stock_id):
    content_msg = generate_content_msg(stock_id)

    msg = [{
        "role": "system",
        "content": "你現在是一位專業的證券分析師, 你會統整近期的股價\
      、基本面、新聞資訊等方面並進行分析出買入區間: ??區間,預計停利: ??%，可?線?碼獲利,資金水位: ?張左右，做多還是多空?, 然後生成一份專業的趨勢分析報告。如果有要回連結格式範例： https://tw.stock.yahoo.com/quote/{{stock_id}}}}, reply in 繁中, Markdown格式"
    }, {
        "role": "user",
        "content": content_msg
    }]

    reply_data = get_reply(msg)

    return reply_data

# stock_value.py 內的 stock_fundamental 函數增加錯誤處理
def stock_fundamental(stock_id):
    if stock_id == "^GSPC":
        print("美國大盤無需營收資料分析")
        return None  # 大盤無需營收資料

    stock = yf.Ticker(stock_id)
    try:
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

    if "Reported EPS" in earnings_dates.columns:
        reported_eps = earnings_dates["Reported EPS"]
        return reported_eps
    else:
        print("Column 'Reported EPS' not found in the data")
        return None