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
    old_name = (data.get("old_name") or "").strip()
    if not name or not aid or not tok:
        return jsonify({"ok": False, "error": "请填写完整信息"})
    if not sec and old_name:
        # 编辑时 secret 留空则保留原值
        profiles = load_profiles()
        old_cfg = profiles.get(old_name)
        if old_cfg:
            sec = old_cfg.get("app_secret", "")
    if not sec:
        return jsonify({"ok": False, "error": "请填写 App Secret"})
    profiles = load_profiles()
    # 如果改名了，删掉旧的
    if old_name and old_name != name and old_name in profiles:
        del profiles[old_name]
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
    csv_files = data.get("files", [])  # [{name, content}, ...]

    profiles = load_profiles()
    cfg = profiles.get(profile_name)
    if not cfg:
        return jsonify({"error": "飞书接口配置未找到"})

    srv = get_service(cfg["app_id"], cfg["app_secret"])
    if not srv:
        return jsonify({"error": "飞书连接失败，请检查配置"})

    # 合并所有CSV内容
    merged_path = UPLOAD_DIR / f"preview_merged_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.csv"
    headers = set()
    all_rows = []
    for cf in csv_files:
        text = cf.get("content", "")
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            headers.update(row.keys())
            all_rows.append(row)

    headers = sorted(headers)
    with open(merged_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(all_rows)

    rules = load_rules(RULES_PATH)
    config = CsvSyncConfig(
        app_token=cfg["app_token"],
        table_id=cfg["table_id"],
        csv_path=merged_path,
        rules_path=RULES_PATH,
    )

    try:
        result = sync_csv_to_bitable(srv, config, dry_run=True)
    except Exception as e:
        return jsonify({"error": str(e), "csv_rows": 0, "matched_records": 0, "planned_updates": 0})

    try:
        merged_path.unlink()
    except:
        pass

    return jsonify(result.to_dict())

@app.route("/api/execute", methods=["POST"])
def api_execute():
    data = request.get_json() or {}
    profile_name = data.get("profile","")
    csv_files = data.get("files", [])  # [{name, content}, ...]

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
    for cf in csv_files:
        text = cf.get("content", "")
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

    try:
        result = sync_csv_to_bitable(srv, config, dry_run=False)
    except Exception as e:
        return jsonify({"error": str(e), "updated": 0, "errors": [["<system>", str(e)]]})
    return jsonify(result.to_dict())


# ═══════════════ HTML ═══════════════

HTML = r"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>飞书寄样表同步</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body{background:#f5f6fa;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.steps{display:flex;justify-content:center;margin:20px 0 30px}
.step{display:flex;align-items:center}
.step-circle{width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1rem;background:#dee2e6;color:#6c757d;transition:.3s}
.step.active .step-circle{background:#0d6efd;color:#fff}
.step.done .step-circle{background:#198754;color:#fff}
.step-label{margin:0 8px;font-size:.82rem;color:#6c757d}
.step.active .step-label{color:#0d6efd;font-weight:600}
.step-line{width:50px;height:2px;background:#dee2e6;margin:0 8px}
.step.done .step-line{background:#198754}
.card{border:none;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.06)}
.main-content{max-width:900px;margin:20px auto;padding:0 15px}
.upload-zone{border:2px dashed #ccc;border-radius:12px;padding:25px;text-align:center;cursor:pointer;transition:.3s}
.upload-zone:hover,.upload-zone.dragover{border-color:#0d6efd;background:#f0f7ff}
.toast-container{position:fixed;top:20px;right:20px;z-index:9999}
.profile-item{cursor:pointer;transition:.2s}
.profile-item:hover{background:#f0f7ff}
.file-row{display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:#f8f9fa;border-radius:8px;margin-bottom:6px}
.stat-card{text-align:center;padding:15px}
.stat-card .num{font-size:1.8rem;font-weight:700}
.stat-card .lbl{color:#6c757d;font-size:.85rem}
table td,table th{font-size:.85rem}
</style>
</head>
<body>
<div class="toast-container" id="toastContainer"></div>
<div class="main-content">
<div class="text-center mt-3"><h4>📊 飞书寄样表同步</h4></div>
<div class="steps">
<div class="step active" id="step1"><div class="step-circle">1</div><div class="step-label">选择接口</div></div>
<div class="step-line"></div>
<div class="step" id="step2"><div class="step-circle">2</div><div class="step-label">上传CSV</div></div>
<div class="step-line"></div>
<div class="step" id="step3"><div class="step-circle">3</div><div class="step-label">预览</div></div>
<div class="step-line"></div>
<div class="step" id="step4"><div class="step-circle">4</div><div class="step-label">执行</div></div>
</div>
<div id="page"></div>
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script>
function escHtml(s){if(!s)return '';return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
let S={step:1,profile:null,csvFiles:[],preview:null,editOriginalName:null};
function toast(m,t){let d=document.getElementById('toastContainer'),c={success:'#198754',danger:'#dc3545',warning:'#ffc107',info:'#0dcaf0'},b=c[t]||c.info;let e=document.createElement('div');e.innerHTML=`<div style="background:${b};color:#fff;padding:10px 18px;border-radius:8px;margin-bottom:6px;box-shadow:0 2px 8px rgba(0,0,0,.15)">${m}</div>`;d.appendChild(e.firstElementChild);setTimeout(()=>{if(d.firstChild)d.removeChild(d.firstChild)},3000)}
function setStep(n){S.step=n;for(let i=1;i<=4;i++){let s=document.getElementById('step'+i);s.classList.remove('active','done');if(i<n)s.classList.add('done');if(i===n)s.classList.add('active')}}
async function api(url,opts){try{let r=await fetch(url,opts);return await r.json()}catch(e){return{error:e.message}}}

// ═══════════════ STEP 1: 选择接口 ═══════════════
function showStep1(){
setStep(1);
api('/api/profiles').then(data=>{
let html=`<div class="card p-4"><div class="d-flex justify-content-between align-items-center mb-3"><h5>已保存的飞书接口</h5><button class="btn btn-primary btn-sm" onclick="showNewProfile()">+ 新建</button></div>`;
let names=Object.keys(data);
if(names.length===0)html+=`<p class="text-muted">还没有保存的接口，请点击"新建"</p>`;
else{
html+=`<div class="list-group">`;
names.forEach(n=>{
let p=data[n];
html+=`<div class="list-group-item profile-item" onclick="selectProfile('${n}')" style="cursor:pointer">
<div class="d-flex justify-content-between align-items-center">
<div><strong>${n}</strong><br><small class="text-muted">${p.app_id} | Token: ${(p.app_token||'').substring(0,15)}...</small></div>
<div>
<button class="btn btn-sm btn-outline-primary me-1" onclick="event.stopPropagation();editProfile('${n}')">✎ 编辑</button>
<button class="btn btn-sm btn-outline-danger" onclick="event.stopPropagation();deleteProfile('${n}')">删除</button>
</div>
</div></div>`;
});
html+=`</div>`;
}
html+=`<div id="newProfileForm" style="display:none" class="mt-3 border-top pt-3"></div></div>`;
document.getElementById('page').innerHTML=html;
});
}

function showNewProfile(){
S.editOriginalName=null;
let el=document.getElementById('newProfileForm');
el.style.display='block';
el.innerHTML=`
<h6>新建飞书接口</h6>
<div class="mb-2"><label class="form-label">接口名称 *</label><input class="form-control form-control-sm" id="npName" placeholder="例如：TK店铺A"></div>
<div class="mb-2"><label class="form-label">App ID *</label><input class="form-control form-control-sm" id="npAppId"></div>
<div class="mb-2"><label class="form-label">App Secret *</label><input type="password" class="form-control form-control-sm" id="npSecret"></div>
<div class="mb-2"><label class="form-label">App Token *</label><input class="form-control form-control-sm" id="npToken" placeholder="多维表格token"></div>
<div class="mb-2"><label class="form-label">Table ID</label><input class="form-control form-control-sm" id="npTableId" value="tblRWlmlvudYAruS"></div>
<div class="d-flex gap-2">
<button class="btn btn-sm btn-primary" onclick="saveProfile()">保存</button>
<button class="btn btn-sm btn-outline-secondary" onclick="testProfile()">测试连接</button>
<button class="btn btn-sm btn-outline-secondary" onclick="el.style.display='none'">取消</button>
</div>
<div id="testResult" class="mt-2"></div>`;
}

async function saveProfile(){
let n=document.getElementById('npName').value.trim();
let d={name:n,old_name:S.editOriginalName||'',app_id:document.getElementById('npAppId').value.trim(),app_secret:document.getElementById('npSecret').value.trim(),app_token:document.getElementById('npToken').value.trim(),table_id:document.getElementById('npTableId').value.trim()};
if(!n||!d.app_id||!d.app_token){toast('请填写完整信息','warning');return}
let r=await api('/api/profiles',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});
if(r.ok){S.editOriginalName=null;toast('已保存: '+n,'success');showStep1()}else toast(r.error,'danger');
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
<h6>编辑飞书接口</h6>
<div class="mb-2"><label class="form-label">接口名称 *</label><input class="form-control form-control-sm" id="npName" value="${escHtml(name)}"></div>
<div class="mb-2"><label class="form-label">App ID *</label><input class="form-control form-control-sm" id="npAppId" value="${escHtml(p.app_id)}"></div>
<div class="mb-2"><label class="form-label">App Secret *</label><input type="password" class="form-control form-control-sm" id="npSecret" value="${escHtml(p.app_secret_full||'')}" placeholder="留空则不修改"></div>
<div class="mb-2"><label class="form-label">App Token *</label><input class="form-control form-control-sm" id="npToken" value="${escHtml(p.app_token)}"></div>
<div class="mb-2"><label class="form-label">Table ID</label><input class="form-control form-control-sm" id="npTableId" value="${escHtml(p.table_id||'tblRWlmlvudYAruS')}"></div>
<div class="d-flex gap-2">
<button class="btn btn-sm btn-primary" onclick="saveProfile()">保存</button>
<button class="btn btn-sm btn-outline-secondary" onclick="testProfile()">测试连接</button>
<button class="btn btn-sm btn-outline-secondary" onclick="document.getElementById('newProfileForm').style.display='none';S.editOriginalName=null">取消</button>
</div>
<div id="testResult" class="mt-2"></div>`;
}

// ═══════════════ STEP 2: 上传CSV ═══════════════
function showStep2(){
if(!S.profile){showStep1();return}
setStep(2);
document.getElementById('page').innerHTML=`
<div class="card p-4">
<div class="d-flex justify-content-between align-items-center mb-3">
<h5>📁 上传CSV文件</h5>
<span class="badge bg-info">接口: ${S.profile}</span>
</div>
<div class="upload-zone" id="uploadZone" onclick="document.getElementById('csvInput').click()">
<h5>📂 点击上传 CSV 文件</h5>
<p class="text-muted">或将文件拖拽到此处 | 支持一次选多个</p>
</div>
<input type="file" id="csvInput" accept=".csv" multiple style="display:none" onchange="uploadFiles(this)">
<div class="mt-3" id="fileList">${S.csvFiles.length===0?'<p class="text-muted">还没有上传文件</p>':renderFileList()}</div>
<div class="d-flex gap-2 mt-3">
<button class="btn btn-outline-secondary btn-sm" onclick="showStep1()">← 上一步</button>
<button class="btn btn-primary btn-sm ms-auto" onclick="goPreview()" ${S.csvFiles.length===0?'disabled':''}>下一步：预览 →</button>
</div>
</div>`;
setupDropZone();
}

function renderFileList(){
return S.csvFiles.map((f,i)=>`
<div class="file-row">
<span>📄 ${f.name} <small class="text-muted">(${(f.size/1024).toFixed(1)} KB)</small></span>
<button class="btn btn-sm btn-outline-danger" onclick="removeFile(${i})">✕</button>
</div>`).join('');
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
let newFiles=[];
for(let f of files){
if(!f.name.endsWith('.csv'))continue;
if(S.csvFiles.some(ex=>ex.name===f.name)){toast(`跳过重复: ${f.name}`,'warning');continue}
// 前端读取CSV内容，跳过上传保存步骤
try{
let text=await f.text();
newFiles.push({name:f.name,size:f.size,content:text});
}catch(e){toast(`读取失败: ${f.name}`,'danger')}
}
if(newFiles.length===0){toast('没有新文件','warning');return}
S.csvFiles=[...S.csvFiles,...newFiles];
toast(`已添加 ${newFiles.length} 个文件`,'success');
showStep2();
}

function removeFile(i){S.csvFiles.splice(i,1);showStep2()}

// ═══════════════ STEP 3: 预览 ═══════════════
async function goPreview(){
if(S.csvFiles.length===0){toast('请先上传CSV文件','warning');return}
setStep(3);
document.getElementById('page').innerHTML=`<div class="card p-4 text-center"><div class="spinner-border text-primary"></div><p class="mt-2">正在预览...</p></div>`;

let r=await api('/api/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile:S.profile,files:S.csvFiles.map(f=>({name:f.name,content:f.content}))})});
S.preview=r;

let html=`<div class="card p-4"><div class="d-flex justify-content-between align-items-center mb-3"><h5>🔍 预览结果</h5><span class="badge bg-info">接口: ${S.profile}</span></div>`;

if(r.error){html+=`<div class="alert alert-warning">${r.error}</div>`}
else{
html+=`<div class="row g-3 mb-3">`;
html+=stat('CSV 行数',r.csv_rows||0,'#6c757d');
html+=stat('匹配记录',r.matched_records||0,'#0d6efd');
html+=stat('待更新',r.planned_updates||0,'#ffc107');
html+=stat('异常状态',(r.unknown_statuses?Object.keys(r.unknown_statuses).length:0)||0,'#dc3545');
html+=`</div>`;

if(r.field_changes&&Object.keys(r.field_changes).length>0){
html+=`<h6>字段变更统计</h6><table class="table table-sm"><thead><tr><th>字段</th><th>变更数</th></tr></thead><tbody>`;
for(let[k,v]of Object.entries(r.field_changes))html+=`<tr><td>${k}</td><td>${v}</td></tr>`;
html+=`</tbody></table>`;
}
if(r.status_changes&&Object.keys(r.status_changes).length>0){
html+=`<h6>签收状态变更</h6><table class="table table-sm"><thead><tr><th>状态</th><th>变更数</th></tr></thead><tbody>`;
for(let[k,v]of Object.entries(r.status_changes))html+=`<tr><td>${k}</td><td>${v}</td></tr>`;
html+=`</tbody></table>`;
}
if(r.unknown_statuses&&Object.keys(r.unknown_statuses).length>0){
html+=`<h6 class="text-danger">未知状态</h6><table class="table table-sm"><thead><tr><th>状态</th><th>出现次数</th></tr></thead><tbody>`;
for(let[k,v]of Object.entries(r.unknown_statuses))html+=`<tr><td>${k}</td><td>${v}</td></tr>`;
html+=`</tbody></table>`;
}
if(!r.field_changes&&!r.status_changes&&!r.unknown_statuses)html+=`<p class="text-muted">没有需要更新的内容</p>`;
}

html+=`<div class="d-flex gap-2 mt-3">
<button class="btn btn-outline-secondary btn-sm" onclick="showStep2()">← 上一步</button>
<button class="btn btn-success btn-sm ms-auto" onclick="goExecute()" ${!r.planned_updates?'disabled':''}>执行更新 →</button>
</div></div>`;

document.getElementById('page').innerHTML=html;
}
function stat(lbl,num,color){return `<div class="col-3"><div class="stat-card card p-2"><div class="num" style="color:${color}">${num}</div><div class="lbl">${lbl}</div></div></div>`}

// ═══════════════ STEP 4: 执行 ═══════════════
async function goExecute(){
setStep(4);
document.getElementById('page').innerHTML=`<div class="card p-4"><h5>⚠️ 确认执行</h5>
<p>将更新 <strong>${S.preview.planned_updates}</strong> 条记录到飞书寄样表。</p>
<p class="text-danger">此操作不可撤销！</p>
<div class="mb-3"><label><input type="checkbox" id="confirmExec"> 我确认要执行更新</label></div>
<div class="d-flex gap-2">
<button class="btn btn-outline-secondary btn-sm" onclick="goPreview()">← 返回预览</button>
<button class="btn btn-danger btn-sm ms-auto" id="execBtn" onclick="doExecute()" disabled>执行更新</button>
</div>
<div id="execResult" class="mt-3"></div></div>`;

document.getElementById('confirmExec').addEventListener('change',function(){
document.getElementById('execBtn').disabled=!this.checked;
});
}

async function doExecute(){
document.getElementById('execResult').innerHTML='<div class="text-center"><div class="spinner-border spinner-border-sm"></div> 正在执行...</div>';
let r=await api('/api/execute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile:S.profile,files:S.csvFiles.map(f=>({name:f.name,content:f.content}))})});
let html='';
if(r.error)html=`<div class="alert alert-danger">${r.error}</div>`;
else{
html=`<div class="alert alert-success">✅ 执行完成</div>`;
html+=`<table class="table table-sm"><tr><td>更新成功</td><td><strong>${r.updated||0}</strong></td></tr>`;
html+=`<tr><td>错误</td><td>${(r.errors||[]).length}</td></tr></table>`;
if(r.errors&&r.errors.length>0){html+=`<h6 class="text-danger">错误详情:</h6><pre class="small" style="max-height:200px;overflow:auto">${JSON.stringify(r.errors.slice(0,20),null,2)}</pre>`}
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
