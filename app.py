"""TikTok Shop + 飞书寄样表 管理后台"""
import os
import json
import csv
import io
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template_string, jsonify, request, session
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()

# ── 飞书模块 ──
sys.path.insert(0, os.path.dirname(__file__))
from feishu.config import load_config as load_feishu_config
from feishu.client import FeishuClient
from feishu.bitable import BitableService
from feishu.exceptions import FeishuError

# ── HTML 模板 ──
HTML = r"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TK + 飞书 管理后台</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: #f5f6fa; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
        .sidebar {
            background: #1a1a2e;
            min-height: 100vh;
            padding-top: 20px;
        }
        .sidebar .nav-link {
            color: #a0a0b8;
            padding: 12px 20px;
            border-radius: 8px;
            margin: 2px 10px;
            transition: all 0.2s;
        }
        .sidebar .nav-link:hover, .sidebar .nav-link.active {
            color: #fff;
            background: rgba(255,255,255,0.1);
        }
        .sidebar .brand {
            color: #fff;
            font-size: 1.1rem;
            font-weight: 600;
            padding: 0 20px 20px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            margin-bottom: 15px;
        }
        .card {
            border: none;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }
        .main-content { padding: 30px; }
        .page-title { margin-bottom: 25px; }
        .page-title h2 { font-weight: 600; }
        .badge-status { font-size: 0.8rem; padding: 4px 10px; }
        .upload-zone {
            border: 2px dashed #ccc;
            border-radius: 12px;
            padding: 40px;
            text-align: center;
            background: #fff;
            cursor: pointer;
            transition: all 0.3s;
        }
        .upload-zone:hover { border-color: #0d6efd; background: #f0f7ff; }
        .upload-zone.dragover { border-color: #0d6efd; background: #e8f0fe; }
        .result-box {
            background: #fff;
            border-radius: 12px;
            padding: 20px;
            margin-top: 20px;
        }
        .result-box pre {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            max-height: 400px;
            overflow: auto;
        }
        .image-box {
            background: #fff;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            padding: 20px;
            margin-bottom: 20px;
        }
        .image-box img { max-width: 100%; height: auto; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <!-- 侧边栏 -->
            <div class="col-md-2 sidebar p-0 d-none d-md-block">
                <div class="brand">📊 TK 后台</div>
                <nav class="nav flex-column">
                    <a class="nav-link active" href="#" onclick="return loadPage('dashboard')">🏠 首页</a>
                    <a class="nav-link" href="#" onclick="return loadPage('feishu_tables')">📋 飞书表格</a>
                    <a class="nav-link" href="#" onclick="return loadPage('feishu_records')">📝 寄样表记录</a>
                    <a class="nav-link" href="#" onclick="return loadPage('feishu_sync')">🔄 CSV 同步</a>
                    <a class="nav-link" href="#" onclick="return loadPage('feishu_config')">⚙️ 飞书配置</a>
                </nav>
            </div>

            <!-- 主内容 -->
            <div class="col-md-10 main-content" id="mainContent">
                <!-- 由 JS 动态加载 -->
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let currentPage = 'dashboard';

        function loadPage(page) {
            currentPage = page;
            const navLinks = document.querySelectorAll('.nav-link');
            navLinks.forEach(l => l.classList.remove('active'));
            if (event && event.target) event.target.classList.add('active');
            else {
                const links = document.querySelectorAll('.nav-link');
                links.forEach(l => {
                    if (l.getAttribute('onclick')?.includes(page)) l.classList.add('active');
                });
            }

            const el = document.getElementById('mainContent');
            switch(page) {
                case 'dashboard': renderDashboard(el); break;
                case 'feishu_tables': renderFeishuTables(el); break;
                case 'feishu_records': renderFeishuRecords(el); break;
                case 'feishu_sync': renderFeishuSync(el); break;
                case 'feishu_config': renderFeishuConfig(el); break;
            }
            return false;
        }

        // ═══════════════ 首页 ═══════════════
        function renderDashboard(el) {
            el.innerHTML = `
                <div class="page-title">
                    <h2>🏠 首页</h2>
                    <p class="text-muted">TK 小工具 · 飞书寄样表管理</p>
                </div>
                <div class="image-box">
                    <img src="{{ url_for('static', filename='show.png') }}" alt="展示图片">
                </div>
                <div class="row g-4 mt-2">
                    <div class="col-md-4">
                        <div class="card p-4 text-center">
                            <h5>📋 飞书表格</h5>
                            <p class="text-muted">查看和管理飞书多维表格</p>
                            <button class="btn btn-primary" onclick="loadPage('feishu_tables')">进入</button>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="card p-4 text-center">
                            <h5>📝 寄样表记录</h5>
                            <p class="text-muted">查看寄样表数据</p>
                            <button class="btn btn-primary" onclick="loadPage('feishu_records')">进入</button>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="card p-4 text-center">
                            <h5>🔄 CSV 同步</h5>
                            <p class="text-muted">上传 CSV 同步物流状态</p>
                            <button class="btn btn-primary" onclick="loadPage('feishu_sync')">进入</button>
                        </div>
                    </div>
                </div>
                <p class="text-muted mt-4"><small>服务器时间：{{ time }}</small></p>
            `;
        }

        // ═══════════════ 飞书表格列表 ═══════════════
        function renderFeishuTables(el) {
            el.innerHTML = `
                <div class="page-title d-flex justify-content-between align-items-center">
                    <div>
                        <h2>📋 飞书多维表格</h2>
                        <p class="text-muted">查看当前飞书账号下的数据表</p>
                    </div>
                    <button class="btn btn-primary btn-sm" onclick="loadFeishuTables()">🔄 刷新</button>
                </div>
                <div class="card p-3">
                    <div id="tablesContent"><p class="text-muted">加载中...</p></div>
                </div>
            `;
            loadFeishuTables();
        }

        async function loadFeishuTables() {
            const el = document.getElementById('tablesContent');
            if (!el) return;
            el.innerHTML = '<p class="text-muted">加载中...</p>';
            try {
                const res = await fetch('/api/feishu/tables');
                const data = await res.json();
                if (data.error) {
                    el.innerHTML = '<div class="alert alert-warning">' + data.error + '</div>';
                    return;
                }
                const items = data.data?.items || [];
                if (items.length === 0) {
                    el.innerHTML = '<p class="text-muted">暂无数据表，请先配置飞书凭证</p>';
                    return;
                }
                let html = '<div class="table-responsive"><table class="table table-hover"><thead><tr><th>表名</th><th>表 ID</th><th>操作</th></tr></thead><tbody>';
                items.forEach(t => {
                    html += '<tr><td>' + (t.name || '-') + '</td><td><code>' + (t.table_id || '-') + '</code></td>';
                    html += '<td><button class="btn btn-sm btn-outline-primary" onclick="alert(\'查看记录功能开发中\')">查看记录</button></td></tr>';
                });
                html += '</tbody></table></div>';
                el.innerHTML = html;
            } catch(e) {
                el.innerHTML = '<div class="alert alert-danger">加载失败: ' + e.message + '</div>';
            }
        }

        // ═══════════════ 寄样表记录 ═══════════════
        function renderFeishuRecords(el) {
            el.innerHTML = `
                <div class="page-title d-flex justify-content-between align-items-center">
                    <div>
                        <h2>📝 寄样表记录</h2>
                        <p class="text-muted">查看寄样表中的数据</p>
                    </div>
                    <div>
                        <input type="text" class="form-control form-control-sm d-inline-block w-auto" id="recordLimit" placeholder="条数" value="20" style="width:80px">
                        <button class="btn btn-primary btn-sm" onclick="loadFeishuRecords()">🔄 加载</button>
                    </div>
                </div>
                <div class="card p-3">
                    <div id="recordsContent"><p class="text-muted">点击加载查看寄样表记录</p></div>
                </div>
            `;
        }

        async function loadFeishuRecords() {
            const el = document.getElementById('recordsContent');
            if (!el) return;
            const limit = document.getElementById('recordLimit')?.value || 20;
            el.innerHTML = '<p class="text-muted">加载中...</p>';
            try {
                const res = await fetch('/api/feishu/records?page_size=' + limit);
                const data = await res.json();
                if (data.error) {
                    el.innerHTML = '<div class="alert alert-warning">' + data.error + '</div>';
                    return;
                }
                const items = data.items || [];
                if (items.length === 0) {
                    el.innerHTML = '<p class="text-muted">暂无记录</p>';
                    return;
                }
                let html = '<div class="table-responsive"><table class="table table-sm table-hover"><thead><tr>';
                // 取第一条的字段名作为表头
                const fields = items[0].fields || {};
                const headers = Object.keys(fields).slice(0, 10);
                headers.forEach(h => { html += '<th>' + h + '</th>'; });
                html += '<th>操作</th></tr></thead><tbody>';
                items.forEach(item => {
                    const f = item.fields || {};
                    html += '<tr>';
                    headers.forEach(h => {
                        let val = f[h];
                        if (val === null || val === undefined) val = '-';
                        else if (typeof val === 'object') val = JSON.stringify(val);
                        else val = String(val).substring(0, 30);
                        html += '<td><small>' + val + '</small></td>';
                    });
                    html += '<td><button class="btn btn-sm btn-outline-secondary">详情</button></td></tr>';
                });
                html += '</tbody></table></div>';
                html += '<p class="text-muted">共 ' + data.total + ' 条记录，显示前 ' + items.length + ' 条</p>';
                el.innerHTML = html;
            } catch(e) {
                el.innerHTML = '<div class="alert alert-danger">加载失败: ' + e.message + '</div>';
            }
        }

        // ═══════════════ CSV 同步 ═══════════════
        function renderFeishuSync(el) {
            el.innerHTML = `
                <div class="page-title">
                    <h2>🔄 CSV 同步寄样表</h2>
                    <p class="text-muted">上传 CSV 文件，自动更新飞书寄样表的签收状态</p>
                </div>
                <div class="card p-4">
                    <div class="upload-zone" id="uploadZone" onclick="document.getElementById('csvFile').click()">
                        <h3>📁 点击上传 CSV 文件</h3>
                        <p class="text-muted">或将文件拖拽到此处</p>
                    </div>
                    <input type="file" id="csvFile" accept=".csv" style="display:none" onchange="uploadCSV(this)">
                    <div class="mt-3">
                        <label class="me-3"><input type="checkbox" id="dryRun" checked> 预览模式（不修改飞书数据）</label>
                    </div>
                    <div id="syncResult" class="result-box" style="display:none"></div>
                </div>
            `;
            // 拖拽支持
            const zone = document.getElementById('uploadZone');
            if (zone) {
                zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
                zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
                zone.addEventListener('drop', e => {
                    e.preventDefault();
                    zone.classList.remove('dragover');
                    if (e.dataTransfer.files.length > 0) {
                        const file = e.dataTransfer.files[0];
                        if (file.name.endsWith('.csv')) uploadCSVFile(file);
                        else alert('请上传 CSV 文件');
                    }
                });
            }
        }

        function uploadCSV(input) {
            if (input.files.length > 0) uploadCSVFile(input.files[0]);
        }

        async function uploadCSVFile(file) {
            const resultEl = document.getElementById('syncResult');
            resultEl.style.display = 'block';
            resultEl.innerHTML = '<p>上传中...</p>';

            const formData = new FormData();
            formData.append('csv', file);
            formData.append('dry_run', document.getElementById('dryRun').checked ? '1' : '0');

            try {
                const res = await fetch('/api/feishu/sync', { method: 'POST', body: formData });
                const data = await res.json();
                if (data.error) {
                    resultEl.innerHTML = '<div class="alert alert-danger">' + data.error + '</div>';
                    return;
                }
                const mode = data.dry_run ? '🔍 预览模式' : '✅ 执行模式';
                let html = '<h5>' + mode + '</h5>';
                html += '<table class="table table-sm"><tr><td>CSV 行数</td><td>' + (data.csv_rows || 0) + '</td></tr>';
                html += '<tr><td>匹配记录</td><td>' + (data.matched_records || 0) + '</td></tr>';
                html += '<tr><td>计划更新</td><td>' + (data.planned_updates || 0) + '</td></tr>';
                html += '<tr><td>已更新</td><td>' + (data.updated || 0) + '</td></tr>';
                html += '<tr><td>错误</td><td>' + (data.errors?.length || 0) + '</td></tr></table>';

                if (data.field_changes && Object.keys(data.field_changes).length > 0) {
                    html += '<h6>字段变更统计：</h6><ul>';
                    for (const [k, v] of Object.entries(data.field_changes)) {
                        html += '<li>' + k + ': ' + v + ' 次</li>';
                    }
                    html += '</ul>';
                }
                if (data.status_changes && Object.keys(data.status_changes).length > 0) {
                    html += '<h6>签收状态变更：</h6><ul>';
                    for (const [k, v] of Object.entries(data.status_changes)) {
                        html += '<li>' + k + ': ' + v + ' 条</li>';
                    }
                    html += '</ul>';
                }
                if (data.errors && data.errors.length > 0) {
                    html += '<h6 class="text-danger">错误详情：</h6><pre>' + JSON.stringify(data.errors, null, 2) + '</pre>';
                }
                resultEl.innerHTML = html;
            } catch(e) {
                resultEl.innerHTML = '<div class="alert alert-danger">同步失败: ' + e.message + '</div>';
            }
        }

        // ═══════════════ 飞书配置 ═══════════════
        function renderFeishuConfig(el) {
            el.innerHTML = `
                <div class="page-title">
                    <h2>⚙️ 飞书配置</h2>
                    <p class="text-muted">配置飞书开放平台 API 凭证</p>
                </div>
                <div class="card p-4">
                    <p>在 Railway 后台设置以下环境变量：</p>
                    <table class="table">
                        <tr><td><code>FEISHU_APP_ID</code></td><td>飞书应用的 App ID</td></tr>
                        <tr><td><code>FEISHU_APP_SECRET</code></td><td>飞书应用的 App Secret</td></tr>
                        <tr><td><code>FEISHU_APP_TOKEN</code></td><td>寄样表的 app_token</td></tr>
                        <tr><td><code>FEISHU_TABLE_ID</code></td><td>寄样表的 table_id（当前：<code>tblRWlmlvudYAruS</code>）</td></tr>
                    </table>
                    <div id="configStatus"></div>
                    <button class="btn btn-primary mt-3" onclick="checkFeishuConfig()">🔍 检查配置状态</button>
                </div>
            `;
        }

        async function checkFeishuConfig() {
            const el = document.getElementById('configStatus');
            el.innerHTML = '<p>检查中...</p>';
            try {
                const res = await fetch('/api/feishu/check');
                const data = await res.json();
                if (data.ok) {
                    el.innerHTML = '<div class="alert alert-success">✅ 飞书配置正常，连接成功</div>';
                } else {
                    el.innerHTML = '<div class="alert alert-warning">⚠️ ' + (data.error || '配置不完整') + '</div>';
                }
            } catch(e) {
                el.innerHTML = '<div class="alert alert-danger">检查失败: ' + e.message + '</div>';
            }
        }

        // ── 启动 ──
        document.addEventListener('DOMContentLoaded', () => renderDashboard(document.getElementById('mainContent')));
    </script>
</body>
</html>
"""


# ── 飞书 API 辅助 ──

def get_feishu_service():
    """获取飞书服务实例，失败返回 None"""
    try:
        config = load_feishu_config()
        client = FeishuClient(config)
        return BitableService(client)
    except Exception as e:
        return None


def get_feishu_app_token():
    return os.getenv("FEISHU_APP_TOKEN", "")


def get_feishu_table_id():
    return os.getenv("FEISHU_TABLE_ID", "tblRWlmlvudYAruS")


# ── 页面路由 ──

@app.route("/")
def index():
    return render_template_string(HTML, time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


# ── API 路由 ──

@app.route("/api/feishu/check")
def api_feishu_check():
    """检查飞书配置"""
    try:
        service = get_feishu_service()
        if not service:
            return jsonify({"ok": False, "error": "飞书配置不完整，请设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET"})
        app_token = get_feishu_app_token()
        if not app_token:
            return jsonify({"ok": False, "error": "缺少 FEISHU_APP_TOKEN"})
        # 测试连接
        service.list_tables(app_token, page_size=1)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/feishu/tables")
def api_feishu_tables():
    """获取飞书表格列表"""
    try:
        service = get_feishu_service()
        if not service:
            return jsonify({"error": "飞书配置不完整"})
        app_token = get_feishu_app_token()
        if not app_token:
            return jsonify({"error": "缺少 FEISHU_APP_TOKEN"})
        result = service.list_tables(app_token)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/feishu/records")
def api_feishu_records():
    """获取寄样表记录"""
    try:
        service = get_feishu_service()
        if not service:
            return jsonify({"error": "飞书配置不完整", "items": [], "total": 0})
        app_token = get_feishu_app_token()
        table_id = get_feishu_table_id()
        if not app_token or not table_id:
            return jsonify({"error": "缺少 FEISHU_APP_TOKEN 或 FEISHU_TABLE_ID", "items": [], "total": 0})
        page_size = request.args.get("page_size", 20, type=int)
        result = service.list_records(app_token, table_id, page_size=page_size)
        data = result.get("data") or {}
        items = data.get("items") or []
        total = data.get("total", 0)
        return jsonify({"items": items, "total": total})
    except Exception as e:
        return jsonify({"error": str(e), "items": [], "total": 0})


@app.route("/api/feishu/sync", methods=["POST"])
def api_feishu_sync():
    """上传 CSV 并同步寄样表"""
    try:
        if "csv" not in request.files:
            return jsonify({"error": "请上传 CSV 文件"})

        file = request.files["csv"]
        if not file.filename.endswith(".csv"):
            return jsonify({"error": "请上传 CSV 文件"})

        dry_run = request.form.get("dry_run", "1") == "1"

        # 保存上传的 CSV
        upload_dir = Path("/tmp/feishu_uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        csv_path = upload_dir / f"upload_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
        file.save(str(csv_path))

        # 加载配置
        service = get_feishu_service()
        if not service:
            return jsonify({"error": "飞书配置不完整"})

        app_token = get_feishu_app_token()
        table_id = get_feishu_table_id()

        from feishu.csv_sync import (
            CsvSyncConfig, CsvSyncResult, sync_csv_to_bitable
        )

        rules_path = Path(__file__).parent / "feishu" / "feishu_csv_update_rules.json"

        config = CsvSyncConfig(
            app_token=app_token,
            table_id=table_id,
            csv_path=csv_path,
            rules_path=rules_path,
        )

        result = sync_csv_to_bitable(service, config, dry_run=dry_run)

        return jsonify(result.to_dict())
    except Exception as e:
        return jsonify({"error": str(e)})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
