from flask import Flask, request, abort
import requests  # 新增 requests 用於 Groq API 調用
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import *
import os
import traceback

app = Flask(__name__)
static_tmp_path = os.path.join(os.path.dirname(__file__), 'static', 'tmp')

# Channel Access Token
line_bot_api = LineBotApi(os.getenv('CHANNEL_ACCESS_TOKEN'))
# Channel Secret
handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))
# Groq API Key初始化設定
groq_api_key = os.getenv('GROQ_API_KEY')  # 請確保環境變數設置正確

def Groq_response(text):
    url = "https://api.groq.com/v1/completions"  # 假設的 Groq API endpoint
    headers = {
        'Authorization': f'Bearer {groq_api_key}',
        'Content-Type': 'application/json'
    }
    payload = {
        "model": "groq-gpt-model",  # 使用 Groq 的模型名稱
        "prompt": text,
        "temperature": 0.5,
        "max_tokens": 500
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        answer = data['choices'][0]['text'].replace('。','')  # 根據 Groq 的回應結構進行提取
        return answer
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        return "Groq API 呼叫失敗，請檢查 API Key 或查詢 Log 了解更多細節"

# 監聽所有來自 /callback 的 Post Request
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# 處理訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text
    try:
        Groq_answer = Groq_response(msg)  # 改為呼叫 Groq_response 函數
        print(Groq_answer)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(Groq_answer))
    except:
        print(traceback.format_exc())
        line_bot_api.reply_message(event.reply_token, TextSendMessage('你所使用的Groq API key額度可能已經超過，請於後台Log內確認錯誤訊息'))

@handler.add(PostbackEvent)
def handle_postback(event):
    print(event.postback.data)

@handler.add(MemberJoinedEvent)
def welcome(event):
    uid = event.joined.members[0].user_id
    gid = event.source.group_id
    profile = line_bot_api.get_group_member_profile(gid, uid)
    name = profile.display_name
    message = TextSendMessage(text=f'{name}歡迎加入')
    line_bot_api.reply_message(event.reply_token, message)

import os
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
