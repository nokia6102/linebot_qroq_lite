from flask import Flask, request, abort
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import *
import os
import traceback
from groq import GroqClient, GroqError  # 假設這是 Groq 的 Python SDK

app = Flask(__name__)
static_tmp_path = os.path.join(os.path.dirname(__file__), 'static', 'tmp')

# Channel Access Token
line_bot_api = LineBotApi(os.getenv('CHANNEL_ACCESS_TOKEN'))
# Channel Secret
handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))

# 初始化 Groq API client
groq_api_key = os.getenv('GROQ_API_KEY')  # 從環境變數取得 Groq API key
groq_client = GroqClient(api_key=groq_api_key)  # 假設這是正確的 Groq API 客戶端初始化方法

def Groq_response(messages):
    try:
        # 呼叫 Groq API
        response = groq_client.chat.completions.create(
            model="llama3-70b-8192",  # 假設使用 Groq 的 llama 模型
            messages=messages,
            max_tokens=2000,
            temperature=1.2
        )
        # 擷取回應中的文字
        reply = response.choices[0].message.content
        return reply
    except GroqError as groq_err:
        # 如果 Groq API 發生錯誤，回傳錯誤訊息
        return f"GROQ API 發生錯誤: {groq_err.message}"

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
        # 將接收到的訊息轉換為 Groq API 的 message 格式
        messages = [{"role": "user", "content": msg}]
        Groq_answer = Groq_response(messages)  # 改為呼叫 Groq_response 函數
        print(Groq_answer)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(Groq_answer))
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
    app.run(host='0.0.0.0', port=port)

