from flask import Flask, render_template_string
import os
from datetime import datetime

app = Flask(__name__)

HTML = """
<html>
<head>
    <meta charset="utf-8">
    <title>TK 小工具</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            max-width: 800px;
            margin: 30px auto;
            text-align: center;
            background: #f5f6fa;
            padding: 20px;
        }
        h1 { color: #1a1a2e; margin-bottom: 10px; }
        .info { color: #666; margin-bottom: 30px; }
        .image-box {
            background: #fff;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            padding: 20px;
            margin-bottom: 20px;
        }
        .image-box img {
            max-width: 100%;
            height: auto;
            border-radius: 8px;
        }
        .status {
            color: #999;
            font-size: 0.85rem;
            margin-top: 30px;
        }
    </style>
</head>
<body>
    <h1>🎯 TK 小工具</h1>
    <p class="info">服务器时间：{{ time }}</p>
    
    <div class="image-box">
        <img src="{{ url_for('static', filename='show.png') }}" alt="展示图片">
    </div>
    
    <p class="status">✅ 运行正常</p>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML, time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
