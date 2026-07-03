from flask import Flask
import os
from datetime import datetime

app = Flask(__name__)

@app.route("/")
def home():
    return f"""
    <html>
    <head><meta charset="utf-8"><title>TK 小工具</title></head>
    <body style="font-family:sans-serif;max-width:600px;margin:50px auto;text-align:center">
        <h1>✅ TK 小工具跑起来了</h1>
        <p>服务器时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>状态：正常</p>
        <hr>
        <p><small>部署到 Railway 后，这个页面就能在外网访问了</small></p>
    </body>
    </html>
    """

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
