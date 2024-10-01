from flask import Flask, request, abort
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import *
import os
import requests
import traceback
from groq import Groq  # 確保正確引入 Groq 客戶端

app = Flask(__name__)

# Channel Access Token
line_bot_api = LineBotApi(os.getenv('CHANNEL_ACCESS_TOKEN'))
# Channel Secret
handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))

# 初始化 Groq API client
client = Groq()  # 初始化 Groq 客戶端

# 初始化對話歷史
conversation_history = []
# 設定最大對話記憶長度
MAX_HISTORY_LEN = 10

def Groq_response(messages):
    try:
        # 呼叫 Groq API 來進行 Chat Completion
        chat_completion = client.chat.completions.create(
            messages=messages,
            model="llama3-8b-8192",  # 根據你的模型選擇
            temperature=0.5,  # 設置溫度來控制隨機性
            max_tokens=1024,  # 設定最大 tokens
        )
        # 擷取回應中的文字
        reply = chat_completion.choices[0].message.content
        return reply
    except Exception as e:
        return f"GROQ API 呼叫失敗: {str(e)}"

# 要檢查 LINE Webhook URL 的函數
def check_line_webhook():
    url = "https://api.line.me/v2/bot/channel/webhook/endpoint"
    headers = {
        "Authorization": f"Bearer {os.getenv('CHANNEL_ACCESS_TOKEN')}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        current_webhook = response.json().get("endpoint", "無法取得 Webhook URL")
        print(f"當前 Webhook URL: {current_webhook}")
        return current_webhook
    else:
        print(f"檢查 Webhook URL 失敗，狀態碼: {response.status_code}, 原因: {response.text}")
        return None

# 更新 LINE Webhook URL 的函數
def update_line_webhook():
    new_webhook_url = "https://linebot-qroq.onrender.com/callback"  # 替換為您的新 Webhook URL
    current_webhook_url = check_line_webhook()
    
    if current_webhook_url != new_webhook_url:
        url = "https://api.line.me/v2/bot/channel/webhook/endpoint"
        headers = {
            "Authorization": f"Bearer {os.getenv('CHANNEL_ACCESS_TOKEN')}",
            "Content-Type": "application/json"
        }
        payload = {
            "endpoint": new_webhook_url
        }

        response = requests.put(url, headers=headers, json=payload)
        if response.status_code == 200:
            print(f"Webhook URL 更新成功: {new_webhook_url}")
        else:
            print(f"更新失敗，狀態碼: {response.status_code}, 原因: {response.text}")
    else:
        print("當前的 Webhook URL 已是最新，無需更新。")

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
    global conversation_history
    msg = event.message.text
    
    # 將訊息加入對話歷史
    conversation_history.append({"role": "user", "content": msg + ", 請以繁體中文回答我問題"})
    
    # 限制對話歷史長度
    if len(conversation_history) > MAX_HISTORY_LEN * 2:
        conversation_history = conversation_history[-MAX_HISTORY_LEN * 2:]
    
    # 傳送最新對話歷史給 Groq
    messages = conversation_history[-MAX_HISTORY_LEN:]
    
    try:
        Groq_answer = Groq_response(messages)  # 呼叫 Groq API 取得回應
        print(Groq_answer)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(Groq_answer))
        
        # 將 GPT 的回應加入對話歷史
        conversation_history.append({"role": "assistant", "content": Groq_answer})
    except:
        print(traceback.format_exc())
        line_bot_api.reply_message(event.reply_token, TextSendMessage('GROQ API 呼叫失敗，請檢查 API Key 或查詢 Log 了解更多細節'))

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

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    try:
    # update_line_webhook()  # 啟動時自動更新 Webhook URL
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        print(f"伺服器啟動失敗: {e}")

