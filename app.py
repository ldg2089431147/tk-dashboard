"""TK + 飞书寄样表 4步同步工具"""
import os, json, sys, csv, io, time
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()

sys.path.insert(0, os.path.dirname(__file__))
from feishu.config import FeishuConfig
from feishu.client import FeishuClient
from feishu.bitable import BitableService
from feishu.csv_sync import (
    read_csv_by_order, build_status_lookup, load_rules,
    sync_csv_to_bitable, CsvSyncConfig, CsvSyncResult,
)

CONFIG_FILE = Path(__file__).parent / "feishu_config.json"
RULES_PATH = Path(__file__).parent / "feishu" / "feishu_csv_update_rules.json"
UPLOAD_DIR = Path("/tmp/feishu_uploads")

def load_profiles():
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if "app_id" in data:
                return {"默认": data}
            return data
        except:
            return {}
    return {}

def save_profiles(p):
    CONFIG_FILE.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")

def get_service(app_id, app_secret):
    try:
        return BitableService(FeishuClient(FeishuConfig(app_id=app_id, app_secret=app_secret)))
    except:
        return None

# ═══════════════ ROUTES ═══════════════

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/profiles")
def api_profiles():
    profiles = load_profiles()
    name_filter = request.args.get("name", "")
    result = {}
    for name, cfg in profiles.items():
        if name_filter and name != name_filter:
            continue
        s = cfg.get("app_secret","")
        result[name] = {
            "name": name,
            "app_id": cfg.get("app_id",""),
            "app_secret": s[:4]+"****" if len(s)>4 else s,
            "app_secret_full": s,
            "app_token": cfg.get("app_token",""),
            "table_id": cfg.get("table_id","tblRWlmlvudYAruS"),
        }
    return jsonify(result)

@app.route("/api/profiles", methods=["POST"])
def api_save_profile():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    aid = (data.get("app_id") or "").strip()
    sec = (data.get("app_secret") or "").strip()
    tok = (data.get("app_token") or "").strip()
    tid = (data.get("table_id") or "").strip()
    if not name or not aid or not sec or not tok:
        return jsonify({"ok": False, "error": "请填写完整信息"})
    profiles = load_profiles()
    profiles[name] = {"name": name, "app_id": aid, "app_secret": sec, "app_token": tok, "table_id": tid or "tblRWlmlvudYAruS"}
    save_profiles(profiles)
    return jsonify({"ok": True})

@app.route("/api/profiles", methods=["DELETE"])
def api_delete_profile():
    name = request.args.get("name","")
    if not name: return jsonify({"ok": False})
    profiles = load_profiles()
    profiles.pop(name, None)
    save_profiles(profiles)
    return jsonify({"ok": True})

@app.route("/api/test", methods=["POST"])
def api_test():
    data = request.get_json() or {}
    srv = get_service(data.get("app_id",""), data.get("app_secret",""))
    if not srv:
        return jsonify({"ok": False, "error": "无法创建飞书连接"})
    try:
        srv.list_tables(data.get("app_token",""), page_size=1)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "files" not in request.files:
        return jsonify({"error": "请选择CSV文件"})
    files = request.files.getlist("files")
    profile_name = request.form.get("profile","")
    profiles = load_profiles()
    if profile_name not in profiles:
        return jsonify({"error": "请先选择飞书接口"})

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved = []
    for f in files:
        if not f.filename.endswith(".csv"):
            continue
        ts = datetime.now().strftime("%Y%m%d%H%M%S%f")
        fpath = UPLOAD_DIR / f"{ts}_{f.filename}"
        f.save(str(fpath))
        saved.append({"name": f.filename, "path": str(fpath), "size": fpath.stat().st_size})
    return jsonify({"ok": True, "files": saved, "count": len(saved)})

@app.route("/api/upload", methods=["DELETE"])
def api_clear_uploads():
    if UPLOAD_DIR.exists():
        for f in UPLOAD_DIR.glob("*.csv"):
            f.unlink()
    return jsonify({"ok": True})

@app.route("/api/preview", methods=["POST"])
def api_preview():
    data = request.get_json() or {}
    profile_name = data.get("profile","")
    file_paths = data.get("files", [])

    profiles = load_profiles()
    cfg = profiles.get(profile_name)
    if not cfg:
        return jsonify({"error": "飞书接口配置未找到"})

    srv = get_service(cfg["app_id"], cfg["app_secret"])
    if not srv:
        return jsonify({"error": "飞书连接失败，请检查配置"})

    # 合并所有CSV到临时文件（与 execute 保持一致的逻辑）
    merged_path = UPLOAD_DIR / f"preview_merged_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.csv"
    headers = set()
    all_rows = []
    for fp in file_paths:
        p = Path(fp)
        if not p.exists():
            return jsonify({"error": f"文件不存在: {p.name}"})
        text = p.read_text(encoding="utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            headers.update(row.keys())
            all_rows.append(row)

    headers = sorted(headers)
    with open(merged_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(all_rows)

    # Dry run
    rules = load_rules(RULES_PATH)
    status_lookup = build_status_lookup(rules)

    config = CsvSyncConfig(
        app_token=cfg["app_token"],
        table_id=cfg["table_id"],
        csv_path=merged_path,
        rules_path=RULES_PATH,
    )

    result = sync_csv_to_bitable(srv, config, dry_run=True)

    # 清理临时文件
    try:
        merged_path.unlink()
    except:
        pass

    return jsonify(result.to_dict())

@app.route("/api/execute", methods=["POST"])
def api_execute():
    data = request.get_json() or {}
    profile_name = data.get("profile","")
    file_paths = data.get("files", [])

    profiles = load_profiles()
    cfg = profiles.get(profile_name)
    if not cfg:
        return jsonify({"error": "飞书接口配置未找到"})

    srv = get_service(cfg["app_id"], cfg["app_secret"])
    if not srv:
        return jsonify({"error": "飞书连接失败"})

    # Merge CSVs
    merged_path = UPLOAD_DIR / f"merged_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
    headers = set()
    all_rows = []
    for fp in file_paths:
        p = Path(fp)
        if not p.exists(): continue
        text = p.read_text(encoding="utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            headers.update(row.keys())
            all_rows.append(row)

    headers = sorted(headers)
    with open(merged_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(all_rows)

    config = CsvSyncConfig(
        app_token=cfg["app_token"],
        table_id=cfg["table_id"],
        csv_path=merged_path,
        rules_path=RULES_PATH,
    )

    result = sync_csv_to_bitable(srv, config, dry_run=False)
    return jsonify(result.to_dict())


# ═══════════════ HTML ═══════════════

HTML = r"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>飞书寄样表同步</title>
<style>
:root{--primary:#4f46e5;--primary-hover:#4338ca;--success:#10b981;--danger:#ef4444;--warning:#f59e0b;--bg:#f1f5f9;--card:#fff;--text:#1e293b;--muted:#94a3b8;--border:#e2e8f0;--radius:12px}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;line-height:1.5;min-height:100vh}
.main{max-width:880px;margin:0 auto;padding:24px 16px 60px}
.header{text-align:center;padding:24px 0 8px}
.header h1{font-size:1.35rem;font-weight:700;letter-spacing:-.3px}
.header p{color:var(--muted);font-size:.85rem;margin-top:4px}
.steps{display:flex;justify-content:center;align-items:center;gap:0;margin:24px 0 28px}
.step{display:flex;align-items:center;gap:8px}
.step-num{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.8rem;font-weight:600;background:var(--border);color:var(--muted);transition:.25s}
.step.active .step-num{background:var(--primary);color:#fff;box-shadow:0 2px 8px rgba(79,70,229,.3)}
.step.done .step-num{background:var(--success);color:#fff}
.step-label{font-size:.8rem;color:var(--muted);font-weight:500}
.step.active .step-label{color:var(--primary)}
.step.done .step-label{color:var(--success)}
.step-line{width:40px;height:2px;background:var(--border);margin:0 8px}
.step.done+.step-line{background:var(--success)}
.card{background:var(--card);border-radius:var(--radius);box-shadow:0 1px 3px rgba(0,0,0,.06),0 1px 2px rgba(0,0,0,.04);padding:24px;margin-bottom:16px}
.card-title{font-size:1rem;font-weight:600;margin-bottom:16px;display:flex;align-items:center;justify-content:space-between}
.btn{display:inline-flex;align-items:center;gap:4px;padding:8px 16px;border-radius:8px;font-size:.85rem;font-weight:500;border:1px solid var(--border);background:var(--card);color:var(--text);cursor:pointer;transition:.15s;white-space:nowrap}
.btn:hover{background:#f8fafc}
.btn-primary{background:var(--primary);color:#fff;border-color:var(--primary)}
.btn-primary:hover{background:var(--primary-hover)}
.btn-success{background:var(--success);color:#fff;border-color:var(--success)}
.btn-success:hover{background:#059669}
.btn-danger{background:var(--danger);color:#fff;border-color:var(--danger)}
.btn-danger:hover{background:#dc2626}
.btn-sm{padding:5px 10px;font-size:.78rem}
.btn:disabled{opacity:.5;cursor:not-allowed}
.form-group{margin-bottom:12px}
.form-label{display:block;font-size:.82rem;font-weight:500;margin-bottom:4px;color:var(--text)}
.form-input{width:100%;padding:8px 12px;border:1px solid var(--border);border-radius:8px;font-size:.85rem;outline:none;transition:.15s}
.form-input:focus{border-color:var(--primary);box-shadow:0 0 0 3px rgba(79,70,229,.12)}
.form-actions{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}
.upload-zone{border:2px dashed var(--border);border-radius:var(--radius);padding:32px 20px;text-align:center;cursor:pointer;transition:.2s}
.upload-zone:hover,.upload-zone.dragover{border-color:var(--primary);background:#f8faff}
.upload-zone-icon{font-size:2.2rem;margin-bottom:8px}
.upload-zone-text{font-size:.9rem;font-weight:500}
.upload-zone-hint{font-size:.8rem;color:var(--muted);margin-top:4px}
.file-list{display:flex;flex-direction:column;gap:6px}
.file-row{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:#f8fafc;border-radius:8px;font-size:.85rem;transition:.1s}
.file-row:hover{background:#f1f5f9}
.file-row-name{display:flex;align-items:center;gap:6px}
.file-row-size{color:var(--muted);font-size:.78rem;margin-left:8px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:20px}
.stat-card{text-align:center;padding:16px 10px;background:#f8fafc;border-radius:10px}
.stat-num{font-size:1.6rem;font-weight:700;line-height:1.2}
.stat-label{font-size:.78rem;color:var(--muted);margin-top:2px}
.table-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:10px;margin-top:12px}
.table-wrap table{width:100%;border-collapse:collapse;font-size:.82rem}
.table-wrap th{background:#f8fafc;padding:10px 12px;text-align:left;font-weight:600;position:sticky;top:0;z-index:1;border-bottom:1px solid var(--border)}
.table-wrap td{padding:9px 12px;border-bottom:1px solid #f1f5f9}
.table-wrap tr:last-child td{border-bottom:none}
.table-wrap tr:hover td{background:#f8fafc}
.old-val{color:var(--danger);max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.new-val{color:var(--success);max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.toast-wrap{position:fixed;top:16px;right:16px;z-index:9999;display:flex;flex-direction:column;gap:6px}
.toast{padding:10px 18px;border-radius:8px;color:#fff;font-size:.85rem;font-weight:500;box-shadow:0 4px 12px rgba(0,0,0,.15);animation:slideIn .2s ease}
@keyframes slideIn{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}
.toast-success{background:var(--success)}
.toast-danger{background:var(--danger)}
.toast-warning{background:var(--warning)}
.toast-info{background:#6366f1}
.badge{display:inline-block;padding:2px 10px;border-radius:20px;font-size:.75rem;font-weight:500;background:#eef2ff;color:var(--primary)}
.loading{text-align:center;padding:40px 20px}
.spinner{width:28px;height:28px;border:3px solid var(--border);border-top-color:var(--primary);border-radius:50%;animation:spin .6s linear infinite;margin:0 auto 12px}
@keyframes spin{to{transform:rotate(360deg)}}
.gap-2{display:flex;gap:8px;align-items:center}
.mt-3{margin-top:16px}
.mb-3{margin-bottom:16px}
.ms-auto{margin-left:auto}
.text-muted{color:var(--muted)}
.text-danger{color:var(--danger)}
.text-center{text-align:center}
.flex-between{display:flex;justify-content:space-between;align-items:center}
.empty-state{text-align:center;padding:24px;color:var(--muted);font-size:.88rem}
</style>
</head>
<body>
<div class="toast-wrap" id="toastContainer"></div>
<div class="main">
<div class="header"><h1>📊 飞书寄样表同步</h1><p>4步完成 CSV → 飞书寄样表更新</p></div>
<div class="steps">
<div class="step active" id="step1"><div class="step-num">1</div><div class="step-label">选择接口</div></div>
<div class="step-line"></div>
<div class="step" id="step2"><div class="step-num">2</div><div class="step-label">上传CSV</div></div>
<div class="step-line"></div>
<div class="step" id="step3"><div class="step-num">3</div><div class="step-label">预览</div></div>
<div class="step-line"></div>
<div class="step" id="step4"><div class="step-num">4</div><div class="step-label">执行</div></div>
</div>
<div id="page"></div>
</div>
<script>
function escHtml(s){if(!s)return '';return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
let S={step:1,profile:null,csvFiles:[],preview:null,editOriginalName:null};
function toast(m,t){let d=document.getElementById('toastContainer');let e=document.createElement('div');e.className='toast toast-'+(t||'info');e.textContent=m;d.appendChild(e);setTimeout(()=>{if(d.firstChild)d.removeChild(d.firstChild)},3000)}
function setStep(n){S.step=n;for(let i=1;i<=4;i++){let s=document.getElementById('step'+i);s.classList.remove('active','done');if(i<n)s.classList.add('done');if(i===n)s.classList.add('active')}}
function showLoading(msg){return`<div class="loading"><div class="spinner"></div><p class="text-muted">${msg||'加载中...'}</p></div>`}
async function api(url,opts){try{let r=await fetch(url,opts);return await r.json()}catch(e){return{error:e.message}}}

// ═══════════════ STEP 1: 选择接口 ═══════════════
function showStep1(){
setStep(1);
api('/api/profiles').then(data=>{
let html=`<div class="card"><div class="card-title"><span>已保存的飞书接口</span><button class="btn btn-primary btn-sm" onclick="showNewProfile()">+ 新建</button></div>`;
let names=Object.keys(data);
if(names.length===0)html+=`<div class="empty-state">还没有保存的接口，点击上方「新建」添加</div>`;
else{
html+=`<div class="file-list">`;
names.forEach(n=>{
let p=data[n];
html+=`<div class="file-row" onclick="selectProfile('${n}')" style="cursor:pointer">
<div class="file-row-name"><strong>${n}</strong><span class="file-row-size">${p.app_id} | ${(p.app_token||'').substring(0,12)}...</span></div>
<div class="gap-2">
<button class="btn btn-sm" onclick="event.stopPropagation();editProfile('${n}')">✎ 编辑</button>
<button class="btn btn-sm btn-danger" onclick="event.stopPropagation();deleteProfile('${n}')">删除</button>
</div>
</div>`;
});
html+=`</div>`;
}
html+=`<div id="newProfileForm" style="display:none" class="mt-3"></div></div>`;
document.getElementById('page').innerHTML=html;
});
}

function showNewProfile(){
S.editOriginalName=null;
let el=document.getElementById('newProfileForm');
el.style.display='block';
el.innerHTML=`
<div class="form-group"><label class="form-label">接口名称 *</label><input class="form-input" id="npName" placeholder="例如：TK店铺A"></div>
<div class="form-group"><label class="form-label">App ID *</label><input class="form-input" id="npAppId"></div>
<div class="form-group"><label class="form-label">App Secret *</label><input type="password" class="form-input" id="npSecret"></div>
<div class="form-group"><label class="form-label">App Token *</label><input class="form-input" id="npToken" placeholder="多维表格token"></div>
<div class="form-group"><label class="form-label">Table ID</label><input class="form-input" id="npTableId" value="tblRWlmlvudYAruS"></div>
<div class="form-actions">
<button class="btn btn-primary btn-sm" onclick="saveProfile()">保存</button>
<button class="btn btn-sm" onclick="testProfile()">测试连接</button>
<button class="btn btn-sm" onclick="el.style.display='none'">取消</button>
</div>
<div id="testResult" class="mt-3"></div>`;
}

async function saveProfile(){
let n=document.getElementById('npName').value.trim();
let sec=document.getElementById('npSecret').value.trim();
let d={name:n,app_id:document.getElementById('npAppId').value.trim(),app_secret:sec,app_token:document.getElementById('npToken').value.trim(),table_id:document.getElementById('npTableId').value.trim()};
if(!n||!d.app_id||!d.app_token){toast('请填写完整信息','warning');return}
if(!sec&&S.editOriginalName){
// 编辑时 secret 留空则保留原值
let old=await api('/api/profiles?name='+encodeURIComponent(S.editOriginalName));
let op=old[S.editOriginalName];
if(op)d.app_secret=op.app_secret_full||'';
}
if(!d.app_secret){toast('请填写 App Secret','warning');return}
let r=await api('/api/profiles',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});
if(r.ok){
// 如果改名了，删掉旧的
if(S.editOriginalName&&S.editOriginalName!==n){
await api('/api/profiles?name='+encodeURIComponent(S.editOriginalName),{method:'DELETE'});
}
S.editOriginalName=null;
toast('已保存: '+n,'success');
showStep1();
}else toast(r.error,'danger');
}

async function testProfile(){
let d={app_id:document.getElementById('npAppId').value.trim(),app_secret:document.getElementById('npSecret').value.trim(),app_token:document.getElementById('npToken').value.trim(),table_id:document.getElementById('npTableId').value.trim()};
if(!d.app_id||!d.app_secret||!d.app_token){toast('请先填写信息','warning');return}
document.getElementById('testResult').innerHTML='<span class="text-muted">测试中...</span>';
let r=await api('/api/test',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});
document.getElementById('testResult').innerHTML=r.ok?'<span class="text-success">✅ 连接成功</span>':'<span class="text-danger">❌ '+r.error+'</span>';
}

async function selectProfile(name){
let r=await api('/api/profiles');
let p=r[name];
if(!p)return;
S.profile=name;
toast('已选择: '+name,'success');
showStep2();
}

async function deleteProfile(name){
if(!confirm('确定删除「'+name+'」？'))return;
let r=await api('/api/profiles?name='+encodeURIComponent(name),{method:'DELETE'});
if(r.ok){toast('已删除','success');showStep1()}
}

async function editProfile(name){
S.editOriginalName=name;
let r=await api('/api/profiles?name='+encodeURIComponent(name));
let p=r[name];
if(!p){toast('未找到接口信息','danger');return}

let el=document.getElementById('newProfileForm');
el.style.display='block';
el.innerHTML=`
<div class="form-group"><label class="form-label">接口名称 *</label><input class="form-input" id="npName" value="${escHtml(name)}"></div>
<div class="form-group"><label class="form-label">App ID *</label><input class="form-input" id="npAppId" value="${escHtml(p.app_id)}"></div>
<div class="form-group"><label class="form-label">App Secret *</label><input type="password" class="form-input" id="npSecret" value="${escHtml(p.app_secret_full||'')}" placeholder="留空则不修改"></div>
<div class="form-group"><label class="form-label">App Token *</label><input class="form-input" id="npToken" value="${escHtml(p.app_token)}"></div>
<div class="form-group"><label class="form-label">Table ID</label><input class="form-input" id="npTableId" value="${escHtml(p.table_id||'tblRWlmlvudYAruS')}"></div>
<div class="form-actions">
<button class="btn btn-primary btn-sm" onclick="saveProfile()">保存</button>
<button class="btn btn-sm" onclick="testProfile()">测试连接</button>
<button class="btn btn-sm" onclick="document.getElementById('newProfileForm').style.display='none';S.editOriginalName=null">取消</button>
</div>
<div id="testResult" class="mt-3"></div>`;
}

// ═══════════════ STEP 2: 上传CSV ═══════════════
function showStep2(){
if(!S.profile){showStep1();return}
setStep(2);
document.getElementById('page').innerHTML=`
<div class="card">
<div class="card-title">
<span>📁 上传CSV文件</span>
<span class="badge">${S.profile}</span>
</div>
<div class="upload-zone" id="uploadZone" onclick="document.getElementById('csvInput').click()">
<div class="upload-zone-icon">📂</div>
<div class="upload-zone-text">点击上传 CSV 文件</div>
<div class="upload-zone-hint">或将文件拖拽到此处 · 支持一次选多个</div>
</div>
<input type="file" id="csvInput" accept=".csv" multiple style="display:none" onchange="uploadFiles(this)">
<div class="mt-3" id="fileList">${S.csvFiles.length===0?'<div class="empty-state">还没有上传文件</div>':renderFileList()}</div>
<div class="gap-2 mt-3">
<button class="btn btn-sm" onclick="showStep1()">← 上一步</button>
<button class="btn btn-primary btn-sm ms-auto" onclick="goPreview()" ${S.csvFiles.length===0?'disabled':''}>下一步：预览 →</button>
</div>
</div>`;
setupDropZone();
}

function renderFileList(){
return `<div class="file-list">${S.csvFiles.map((f,i)=>`
<div class="file-row">
<div class="file-row-name">📄 ${f.name}<span class="file-row-size">${(f.size/1024).toFixed(1)} KB</span></div>
<button class="btn btn-sm btn-danger" onclick="removeFile(${i})">✕</button>
</div>`).join('')}</div>`;
}

function setupDropZone(){
let z=document.getElementById('uploadZone');
if(!z)return;
z.addEventListener('dragover',e=>{e.preventDefault();z.classList.add('dragover')});
z.addEventListener('dragleave',()=>z.classList.remove('dragover'));
z.addEventListener('drop',e=>{e.preventDefault();z.classList.remove('dragover');if(e.dataTransfer.files.length>0)doUpload(e.dataTransfer.files)});
}

function uploadFiles(input){if(input.files.length>0)doUpload(input.files)}

async function doUpload(files){
let fd=new FormData();
let existingNames=new Set(S.csvFiles.map(f=>f.name));
let dupes=[];
for(let f of files){
if(!f.name.endsWith('.csv'))continue;
if(existingNames.has(f.name)){dupes.push(f.name);continue}
fd.append('files',f);
existingNames.add(f.name);
}
if(dupes.length>0)toast(`跳过重复文件: ${dupes.join(', ')}`,'warning');
if([...fd.entries()].filter(e=>e[0]==='files').length===0){toast('没有新文件可上传','warning');return}
fd.append('profile',S.profile);
let r=await api('/api/upload',{method:'POST',body:fd});
if(r.error){toast(r.error,'danger');return}
if(r.files)S.csvFiles=[...S.csvFiles,...r.files];
toast(`已上传 ${r.count} 个文件`,'success');
showStep2();
}

function removeFile(i){S.csvFiles.splice(i,1);showStep2()}

// ═══════════════ STEP 3: 预览 ═══════════════
async function goPreview(){
if(S.csvFiles.length===0){toast('请先上传CSV文件','warning');return}
setStep(3);
document.getElementById('page').innerHTML=showLoading('正在分析数据...');

let r=await api('/api/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile:S.profile,files:S.csvFiles.map(f=>f.path)})});
S.preview=r;

let html=`<div class="card"><div class="card-title"><span>🔍 预览结果</span><span class="badge">${S.profile}</span></div>`;

if(r.error){html+=`<div class="empty-state text-danger">${r.error}</div>`}
else{
html+=`<div class="stats">`;
html+=stat('CSV 行数',r.csv_rows||0,'#64748b');
html+=stat('匹配记录',r.matched_records||0,'#4f46e5');
html+=stat('待更新',r.planned_updates||0,'#f59e0b');
html+=stat('异常状态',(r.unknown_statuses?Object.keys(r.unknown_statuses).length:0)||0,'#ef4444');
html+=`</div>`;

if(r.field_changes&&Object.keys(r.field_changes).length>0){
html+=`<div class="mb-3"><strong style="font-size:.9rem">字段变更统计</strong><div class="table-wrap"><table><thead><tr><th>字段</th><th>变更数</th></tr></thead><tbody>`;
for(let[k,v]of Object.entries(r.field_changes))html+=`<tr><td>${k}</td><td>${v}</td></tr>`;
html+=`</tbody></table></div></div>`;
}
if(r.status_changes&&Object.keys(r.status_changes).length>0){
html+=`<div class="mb-3"><strong style="font-size:.9rem">签收状态变更</strong><div class="table-wrap"><table><thead><tr><th>状态</th><th>变更数</th></tr></thead><tbody>`;
for(let[k,v]of Object.entries(r.status_changes))html+=`<tr><td>${k}</td><td>${v}</td></tr>`;
html+=`</tbody></table></div></div>`;
}
if(r.unknown_statuses&&Object.keys(r.unknown_statuses).length>0){
html+=`<div class="mb-3"><strong style="font-size:.9rem;color:var(--danger)">未知状态</strong><div class="table-wrap"><table><thead><tr><th>状态</th><th>出现次数</th></tr></thead><tbody>`;
for(let[k,v]of Object.entries(r.unknown_statuses))html+=`<tr><td>${k}</td><td>${v}</td></tr>`;
html+=`</tbody></table></div></div>`;
}

// 详细变更列表
if(r.preview_details&&r.preview_details.length>0){
html+=`<div class="mb-3"><div class="flex-between"><strong style="font-size:.9rem">📋 待更新记录详情</strong><span class="text-muted" style="font-size:.8rem">${r.preview_details.length} 条</span></div><div class="table-wrap" style="max-height:480px;overflow-y:auto"><table><thead><tr><th>订单ID</th><th>字段</th><th>旧值</th><th>→ 新值</th></tr></thead><tbody>`;
for(let d of r.preview_details){
let first=true;
for(let[fld,chg]of Object.entries(d.changes)){
let orderId=first?escHtml(d.order_id||d.record_id):'';
html+=`<tr><td>${orderId}</td><td>${escHtml(fld)}</td><td class="old-val" title="${escHtml(chg.old)}">${escHtml(chg.old)||'<span class="text-muted">空</span>'}</td><td class="new-val" title="${escHtml(chg.new)}">${escHtml(chg.new)||'<span class="text-muted">空</span>'}</td></tr>`;
first=false;
}
}
html+=`</tbody></table></div></div>`;
}

if(!r.field_changes&&!r.status_changes&&!r.unknown_statuses&&(!r.preview_details||r.preview_details.length===0))html+=`<div class="empty-state">没有需要更新的内容</div>`;
}

html+=`<div class="gap-2 mt-3">
<button class="btn btn-sm" onclick="showStep2()">← 上一步</button>
<button class="btn btn-success btn-sm ms-auto" onclick="goExecute()" ${!r.planned_updates?'disabled':''}>执行更新 →</button>
</div></div>`;

document.getElementById('page').innerHTML=html;
}
function stat(lbl,num,color){return `<div class="stat-card"><div class="stat-num" style="color:${color}">${num}</div><div class="stat-label">${lbl}</div></div>`}

// ═══════════════ STEP 4: 执行 ═══════════════
async function goExecute(){
setStep(4);
document.getElementById('page').innerHTML=`<div class="card"><div class="card-title">⚠️ 确认执行</div>
<p style="font-size:.9rem;margin-bottom:8px">将更新 <strong>${S.preview.planned_updates}</strong> 条记录到飞书寄样表。</p>
<p style="font-size:.85rem;color:var(--danger);margin-bottom:16px">此操作不可撤销！</p>
<div style="margin-bottom:16px"><label style="font-size:.88rem;display:flex;align-items:center;gap:8px;cursor:pointer"><input type="checkbox" id="confirmExec"> 我确认要执行更新</label></div>
<div class="gap-2">
<button class="btn btn-sm" onclick="goPreview()">← 返回预览</button>
<button class="btn btn-danger btn-sm ms-auto" id="execBtn" onclick="doExecute()" disabled>执行更新</button>
</div>
<div id="execResult" class="mt-3"></div></div>`;

document.getElementById('confirmExec').addEventListener('change',function(){
document.getElementById('execBtn').disabled=!this.checked;
});
}

async function doExecute(){
document.getElementById('execResult').innerHTML=showLoading('正在执行更新...');
let r=await api('/api/execute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile:S.profile,files:S.csvFiles.map(f=>f.path)})});
let html='';
if(r.error)html=`<div class="empty-state text-danger">${r.error}</div>`;
else{
html=`<div style="text-align:center;padding:16px;font-size:1.1rem;font-weight:600;color:var(--success)">✅ 执行完成</div>`;
html+=`<div class="table-wrap"><table><tr><td>更新成功</td><td><strong>${r.updated||0}</strong></td></tr>`;
html+=`<tr><td>错误</td><td>${(r.errors||[]).length}</td></tr></table></div>`;
if(r.errors&&r.errors.length>0){html+=`<div class="mt-3"><strong style="font-size:.85rem;color:var(--danger)">错误详情:</strong><pre style="font-size:.8rem;max-height:180px;overflow:auto;background:#f8fafc;padding:12px;border-radius:8px;margin-top:6px">${JSON.stringify(r.errors.slice(0,20),null,2)}</pre></div>`}
}
document.getElementById('execResult').innerHTML=html;
toast(r.error?'执行失败':'执行完成','success');
}

// Start
document.addEventListener('DOMContentLoaded',showStep1);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
