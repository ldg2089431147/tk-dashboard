"""TikTok Shop + 飞书寄样表 管理后台"""
import os
import json
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template_string, jsonify, request
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()

# ── 飞书模块 ──
sys.path.insert(0, os.path.dirname(__file__))
from feishu.config import load_config as load_feishu_config, FeishuConfig
from feishu.client import FeishuClient
from feishu.bitable import BitableService
from feishu.exceptions import FeishuError

# ── 配置存储（多套配置） ──
CONFIG_FILE = Path(__file__).parent / "feishu_config.json"


def load_all_profiles() -> dict:
    """读取所有保存的配置档案"""
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            # 兼容旧格式：单套配置直接转
            if "app_id" in data:
                name = data.get("name", "默认")
                return {name: data}
            return data
        except Exception:
            return {}
    return {}


def save_profile(name: str, data: dict):
    """保存一套配置档案"""
    profiles = load_all_profiles()
    profiles[name] = {
        "name": name,
        "app_id": data.get("app_id", ""),
        "app_secret": data.get("app_secret", ""),
        "app_token": data.get("app_token", ""),
        "table_id": data.get("table_id", "tblRWlmlvudYAruS"),
    }
    CONFIG_FILE.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")


def delete_profile(name: str):
    """删除一套配置档案"""
    profiles = load_all_profiles()
    profiles.pop(name, None)
    CONFIG_FILE.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")


def get_active_config(profile_name: str | None = None):
    """获取指定档案的配置，未指定则用第一个"""
    profiles = load_all_profiles()
    if profile_name and profile_name in profiles:
        return profiles[profile_name]
    # 取第一个
    for name, cfg in profiles.items():
        return cfg
    # 都没有则用环境变量
    return {
        "name": "",
        "app_id": os.getenv("FEISHU_APP_ID", ""),
        "app_secret": os.getenv("FEISHU_APP_SECRET", ""),
        "app_token": os.getenv("FEISHU_APP_TOKEN", ""),
        "table_id": os.getenv("FEISHU_TABLE_ID", "tblRWlmlvudYAruS"),
    }


def get_feishu_service(profile_name: str | None = None):
    """获取飞书服务实例"""
    cfg = get_active_config(profile_name)
    if not cfg.get("app_id") or not cfg.get("app_secret"):
        return None
    try:
        feishu_cfg = FeishuConfig(app_id=cfg["app_id"], app_secret=cfg["app_secret"])
        client = FeishuClient(feishu_cfg)
        return BitableService(client)
    except Exception:
        return None


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
        .config-form label { font-weight: 500; }
        .config-form .form-text { font-size: 0.8rem; }
        .toast-container { position: fixed; top: 20px; right: 20px; z-index: 9999; }
    </style>
</head>
<body>
    <div class="toast-container" id="toastContainer"></div>
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
            <div class="col-md-10 main-content" id="mainContent"></div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function showToast(msg, type) {
            const container = document.getElementById('toastContainer');
            const colors = { success: '#198754', danger: '#dc3545', warning: '#ffc107', info: '#0dcaf0' };
            const bg = colors[type] || colors.info;
            const html = `<div style="background:${bg};color:#fff;padding:12px 20px;border-radius:8px;margin-bottom:8px;box-shadow:0 2px 8px rgba(0,0,0,0.15);min-width:250px">${msg}</div>`;
            const el = document.createElement('div');
            el.innerHTML = html;
            container.appendChild(el.firstElementChild);
            setTimeout(() => { if (container.firstChild) container.removeChild(container.firstChild); }, 3000);
        }

        let currentPage = 'dashboard';
        function loadPage(page) {
            currentPage = page;
            const navLinks = document.querySelectorAll('.nav-link');
            navLinks.forEach(l => l.classList.remove('active'));
            if (event && event.target) event.target.classList.add('active');
            else {
                document.querySelectorAll('.nav-link').forEach(l => {
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
                            <p class="text-muted">查看飞书多维表格</p>
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
                let html = '<div class="table-responsive"><table class="table table-hover"><thead><tr><th>表名</th><th>表 ID</th></tr></thead><tbody>';
                items.forEach(t => {
                    html += '<tr><td>' + (t.name || '-') + '</td><td><code>' + (t.table_id || '-') + '</code></td></tr>';
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
                        <input type="number" class="form-control form-control-sm d-inline-block w-auto" id="recordLimit" value="20" style="width:80px">
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
                const fields = items[0].fields || {};
                const headers = Object.keys(fields).slice(0, 10);
                let html = '<div class="table-responsive"><table class="table table-sm table-hover"><thead><tr>';
                headers.forEach(h => { html += '<th>' + h + '</th>'; });
                html += '</tr></thead><tbody>';
                items.forEach(item => {
                    const f = item.fields || {};
                    html += '<tr>';
                    headers.forEach(h => {
                        let val = f[h];
                        if (val === null || val === undefined) val = '-';
                        else if (typeof val === 'object') val = JSON.stringify(val).substring(0, 20);
                        else val = String(val).substring(0, 30);
                        html += '<td><small>' + val + '</small></td>';
                    });
                    html += '</tr>';
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
                    for (const [k, v] of Object.entries(data.field_changes)) html += '<li>' + k + ': ' + v + ' 次</li>';
                    html += '</ul>';
                }
                if (data.status_changes && Object.keys(data.status_changes).length > 0) {
                    html += '<h6>签收状态变更：</h6><ul>';
                    for (const [k, v] of Object.entries(data.status_changes)) html += '<li>' + k + ': ' + v + ' 条</li>';
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

        // ═══════════════ 飞书配置（多套配置） ═══════════════
        let configProfiles = {};
        let currentProfileName = '';

        function renderFeishuConfig(el) {
            el.innerHTML = `
                <div class="page-title d-flex justify-content-between align-items-center">
                    <div>
                        <h2>⚙️ 飞书配置</h2>
                        <p class="text-muted">管理多套飞书 API 凭证</p>
                    </div>
                    <div>
                        <button class="btn btn-outline-info btn-sm" onclick="showProfileSelector()">📂 加载配置</button>
                        <button class="btn btn-outline-danger btn-sm ms-1" onclick="deleteCurrentProfile()">🗑️ 删除</button>
                    </div>
                </div>
                <div class="card p-4">
                    <div class="mb-3">
                        <label>配置名称 <span class="text-danger">*</span></label>
                        <input type="text" class="form-control" id="cfgName" placeholder="例如：TK店铺A、TK店铺B" value="默认">
                        <div class="form-text">给这套配置起个名字，方便以后切换</div>
                    </div>
                    <form class="config-form" onsubmit="return saveFeishuConfig()">
                        <div class="mb-3">
                            <label>FEISHU_APP_ID <span class="text-danger">*</span></label>
                            <input type="text" class="form-control" id="cfgAppId" placeholder="飞书应用的 App ID" required>
                            <div class="form-text">飞书开放平台 → 应用 → 凭证与基础信息</div>
                        </div>
                        <div class="mb-3">
                            <label>FEISHU_APP_SECRET <span class="text-danger">*</span></label>
                            <input type="password" class="form-control" id="cfgAppSecret" placeholder="飞书应用的 App Secret" required>
                            <div class="form-text">飞书开放平台 → 应用 → 凭证与基础信息</div>
                        </div>
                        <div class="mb-3">
                            <label>FEISHU_APP_TOKEN <span class="text-danger">*</span></label>
                            <input type="text" class="form-control" id="cfgAppToken" placeholder="多维表格的 app_token" required>
                            <div class="form-text">打开寄样表 → URL 中 /base/ 后面的那串字符</div>
                        </div>
                        <div class="mb-3">
                            <label>FEISHU_TABLE_ID</label>
                            <input type="text" class="form-control" id="cfgTableId" placeholder="寄样表的 table_id" value="tblRWlmlvudYAruS">
                            <div class="form-text">默认已填写，一般不需要改</div>
                        </div>
                        <div class="d-flex gap-2">
                            <button type="submit" class="btn btn-primary">💾 保存配置</button>
                            <button type="button" class="btn btn-outline-secondary" onclick="testFeishuConfig()">🔍 测试连接</button>
                        </div>
                    </form>
                    <div id="configStatus" class="mt-3"></div>
                </div>
            `;
            loadProfileList();
        }

        async function loadProfileList() {
            try {
                const res = await fetch('/api/feishu/profiles');
                configProfiles = await res.json();
            } catch(e) {}
        }

        function showProfileSelector() {
            const names = Object.keys(configProfiles);
            if (names.length === 0) {
                showToast('没有已保存的配置', 'warning');
                return;
            }
            let html = '<div class="list-group">';
            names.forEach(name => {
                const p = configProfiles[name];
                const masked = p.app_secret ? p.app_secret.substring(0, 4) + '****' : '';
                html += '<button class="list-group-item list-group-item-action d-flex justify-content-between align-items-center" onclick="applyProfile(\'' + name + '\')">';
                html += '<div><strong>' + name + '</strong><br><small class="text-muted">' + p.app_id + ' | ' + masked + '</small></div>';
                html += '<span class="badge bg-primary rounded-pill">加载</span></button>';
            });
            html += '</div>';

            const el = document.getElementById('configStatus');
            el.innerHTML = '<div class="card p-3"><h6>选择要加载的配置：</h6>' + html + '</div>';
        }

        function applyProfile(name) {
            const p = configProfiles[name];
            if (!p) return;
            document.getElementById('cfgName').value = name;
            document.getElementById('cfgAppId').value = p.app_id || '';
            document.getElementById('cfgAppSecret').value = p.app_secret || '';
            document.getElementById('cfgAppToken').value = p.app_token || '';
            document.getElementById('cfgTableId').value = p.table_id || 'tblRWlmlvudYAruS';
            currentProfileName = name;
            document.getElementById('configStatus').innerHTML = '<div class="alert alert-success">✅ 已加载配置: ' + name + '</div>';
            showToast('已加载: ' + name, 'success');
        }

        async function saveFeishuConfig() {
            const name = document.getElementById('cfgName').value.trim();
            const data = {
                app_id: document.getElementById('cfgAppId').value.trim(),
                app_secret: document.getElementById('cfgAppSecret').value.trim(),
                app_token: document.getElementById('cfgAppToken').value.trim(),
                table_id: document.getElementById('cfgTableId').value.trim(),
            };
            if (!name) { showToast('请输入配置名称', 'warning'); return false; }
            if (!data.app_id || !data.app_secret || !data.app_token) {
                showToast('请填写必填字段', 'warning');
                return false;
            }
            try {
                const res = await fetch('/api/feishu/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: name, ...data }),
                });
                const result = await res.json();
                if (result.ok) {
                    showToast('✅ 配置已保存: ' + name, 'success');
                    await loadProfileList();
                } else {
                    showToast('保存失败: ' + (result.error || '未知错误'), 'danger');
                }
            } catch(e) {
                showToast('保存失败: ' + e.message, 'danger');
            }
            return false;
        }

        async function deleteCurrentProfile() {
            const name = document.getElementById('cfgName').value.trim();
            if (!name || !configProfiles[name]) {
                showToast('当前配置不存在或未保存', 'warning');
                return;
            }
            if (!confirm('确定删除配置「' + name + '」吗？')) return;
            try {
                const res = await fetch('/api/feishu/config?name=' + encodeURIComponent(name), { method: 'DELETE' });
                const result = await res.json();
                if (result.ok) {
                    showToast('已删除: ' + name, 'success');
                    await loadProfileList();
                    document.getElementById('configStatus').innerHTML = '';
                }
            } catch(e) {
                showToast('删除失败: ' + e.message, 'danger');
            }
        }

        async function testFeishuConfig() {
            const el = document.getElementById('configStatus');
            const app_id = document.getElementById('cfgAppId').value.trim();
            const app_secret = document.getElementById('cfgAppSecret').value.trim();
            const app_token = document.getElementById('cfgAppToken').value.trim();
            const table_id = document.getElementById('cfgTableId').value.trim();
            if (!app_id || !app_secret || !app_token) {
                showToast('请先填写 App ID、Secret 和 Token', 'warning');
                return;
            }
            el.innerHTML = '<p>测试连接中...</p>';
            try {
                const res = await fetch('/api/feishu/check', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ app_id, app_secret, app_token, table_id }),
                });
                const data = await res.json();
                if (data.ok) {
                    el.innerHTML = '<div class="alert alert-success">✅ 连接成功！飞书配置正常</div>';
                } else {
                    el.innerHTML = '<div class="alert alert-warning">⚠️ ' + (data.error || '连接失败') + '</div>';
                }
            } catch(e) {
                el.innerHTML = '<div class="alert alert-danger">测试失败: ' + e.message + '</div>';
            }
        }

        document.addEventListener('DOMContentLoaded', () => renderDashboard(document.getElementById('mainContent')));
    </script>
</body>
</html>
"""


# ── 页面路由 ──

@app.route("/")
def index():
    return render_template_string(HTML, time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


# ── 配置 API ──

@app.route("/api/feishu/profiles")
def api_list_profiles():
    """列出所有已保存的配置档案"""
    profiles = load_all_profiles()
    # 隐藏 secret 中间部分
    result = {}
    for name, cfg in profiles.items():
        secret = cfg.get("app_secret", "")
        if len(secret) > 8:
            masked = secret[:4] + "****" + secret[-4:]
        else:
            masked = secret[:2] + "****" if secret else ""
        result[name] = {
            "name": name,
            "app_id": cfg.get("app_id", ""),
            "app_secret": masked,
            "app_token": cfg.get("app_token", ""),
            "table_id": cfg.get("table_id", ""),
        }
    return jsonify(result)


@app.route("/api/feishu/config", methods=["GET"])
def api_get_feishu_config():
    """获取指定配置（含完整 secret，用于加载）"""
    name = request.args.get("name", "")
    profiles = load_all_profiles()
    if name and name in profiles:
        return jsonify(profiles[name])
    # 取第一个
    for n, cfg in profiles.items():
        return jsonify(cfg)
    return jsonify({})


@app.route("/api/feishu/config", methods=["POST"])
def api_save_feishu_config():
    """保存飞书配置"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "无效的请求数据"})

        name = (data.get("name") or "默认").strip()
        app_id = (data.get("app_id") or "").strip()
        app_secret = (data.get("app_secret") or "").strip()
        app_token = (data.get("app_token") or "").strip()
        table_id = (data.get("table_id") or "").strip()

        if not app_id or not app_secret or not app_token:
            return jsonify({"ok": False, "error": "App ID、App Secret、App Token 为必填项"})

        save_profile(name, {
            "app_id": app_id,
            "app_secret": app_secret,
            "app_token": app_token,
            "table_id": table_id or "tblRWlmlvudYAruS",
        })

        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/feishu/config", methods=["DELETE"])
def api_delete_feishu_config():
    """删除一套配置"""
    name = request.args.get("name", "")
    if not name:
        return jsonify({"ok": False, "error": "缺少配置名称"})
    delete_profile(name)
    return jsonify({"ok": True})


# ── 飞书 API ──

@app.route("/api/feishu/check", methods=["GET", "POST"])
def api_feishu_check():
    """检查飞书配置"""
    try:
        if request.method == "POST":
            # 用表单提交的配置测试
            data = request.get_json() or {}
            app_id = data.get("app_id", "")
            app_secret = data.get("app_secret", "")
            app_token = data.get("app_token", "")
            table_id = data.get("table_id", "")
            if not app_id or not app_secret or not app_token:
                return jsonify({"ok": False, "error": "请填写 App ID、App Secret 和 App Token"})
            feishu_cfg = FeishuConfig(app_id=app_id, app_secret=app_secret)
            client = FeishuClient(feishu_cfg)
            service = BitableService(client)
            service.list_tables(app_token, page_size=1)
            return jsonify({"ok": True})
        
        name = request.args.get("name", "")
        service = get_feishu_service(name or None)
        if not service:
            return jsonify({"ok": False, "error": "飞书配置不完整，请填写 App ID 和 App Secret"})
        cfg = get_active_config(name or None)
        if not cfg.get("app_token"):
            return jsonify({"ok": False, "error": "缺少 App Token"})
        service.list_tables(cfg["app_token"], page_size=1)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/feishu/tables")
def api_feishu_tables():
    """获取飞书表格列表"""
    try:
        name = request.args.get("name", "")
        service = get_feishu_service(name or None)
        if not service:
            return jsonify({"error": "飞书配置不完整"})
        cfg = get_active_config(name or None)
        if not cfg.get("app_token"):
            return jsonify({"error": "缺少 App Token"})
        result = service.list_tables(cfg["app_token"])
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/feishu/records")
def api_feishu_records():
    """获取寄样表记录"""
    try:
        name = request.args.get("name", "")
        service = get_feishu_service(name or None)
        if not service:
            return jsonify({"error": "飞书配置不完整", "items": [], "total": 0})
        cfg = get_active_config(name or None)
        if not cfg.get("app_token") or not cfg.get("table_id"):
            return jsonify({"error": "缺少 App Token 或 Table ID", "items": [], "total": 0})
        page_size = request.args.get("page_size", 20, type=int)
        result = service.list_records(cfg["app_token"], cfg["table_id"], page_size=page_size)
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
        profile_name = request.form.get("profile", "")

        upload_dir = Path("/tmp/feishu_uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        csv_path = upload_dir / f"upload_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
        file.save(str(csv_path))

        service = get_feishu_service(profile_name or None)
        if not service:
            return jsonify({"error": "飞书配置不完整"})

        cfg = get_active_config(profile_name or None)

        from feishu.csv_sync import CsvSyncConfig, sync_csv_to_bitable

        rules_path = Path(__file__).parent / "feishu" / "feishu_csv_update_rules.json"

        sync_config = CsvSyncConfig(
            app_token=cfg["app_token"],
            table_id=cfg["table_id"],
            csv_path=csv_path,
            rules_path=rules_path,
        )

        result = sync_csv_to_bitable(service, sync_config, dry_run=dry_run)
        return jsonify(result.to_dict())
    except Exception as e:
        return jsonify({"error": str(e)})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
