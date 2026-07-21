// Deploy this as a Google Apps Script Web App attached to your Google Sheet.
// Existing Payment export keeps working. The same /exec URL also serves the mobile dashboard.
const SECRET = 'CHANGE_ME_TO_A_LONG_RANDOM_SECRET';
const SHEET_NAME = 'Payments';
const MOBILE_INBOX_SHEET = 'MobileInbox';
const MOBILE_PAYMENTS_SHEET = 'MobilePayments';
const PROPERTIES = PropertiesService.getScriptProperties();
const COLUMNS = ['Ngày', 'Account name', 'Currency', 'Amount', 'Payment ID'];
const MOBILE_INBOX_COLUMNS = [
  'source_id', 'mail_date', 'account_name', 'account_email', 'from_addr', 'subject',
  'category', 'priority', 'trusted_sender', 'currency', 'amount', 'payment_id',
  'snippet', 'body', 'body_status', 'body_error'
];
const MOBILE_PAYMENT_COLUMNS = ['mail_date', 'account_name', 'account_email', 'currency', 'amount', 'payment_id'];

function json(value) {
  return ContentService.createTextOutput(JSON.stringify(value)).setMimeType(ContentService.MimeType.JSON);
}

function displayDate(value) {
  if (value instanceof Date && !isNaN(value)) return Utilities.formatDate(value, Session.getScriptTimeZone(), 'dd/MM');
  const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})/);
  return match ? `${match[3]}/${match[2]}` : String(value || '');
}

function paymentKey(row) {
  return [displayDate(row[0]), row[1], row[2], row[3], row[4]].join('|');
}

function prepareSheet(sheet) {
  const lastRow = sheet.getLastRow();
  const oldHeader = lastRow > 0 ? sheet.getRange(1, 1, 1, Math.max(sheet.getLastColumn(), 1)).getValues()[0] : [];
  const isLegacy = oldHeader[0] === 'mail_date' && oldHeader[2] === 'account_email';
  if (isLegacy && lastRow > 1) {
    const legacy = sheet.getRange(2, 1, lastRow - 1, Math.max(sheet.getLastColumn(), 6)).getValues();
    const migrated = legacy.map(row => [displayDate(row[0]), row[1], row[3], row[4], row[5]]);
    sheet.getRange(2, 1, migrated.length, COLUMNS.length).setValues(migrated);
  }
  sheet.getRange(1, 1, 1, COLUMNS.length).setValues([COLUMNS]);
  sheet.getRange(2, 1, Math.max(lastRow - 1, 1), 1).setNumberFormat('@');
  if (sheet.getMaxColumns() > COLUMNS.length) sheet.hideColumns(COLUMNS.length + 1, sheet.getMaxColumns() - COLUMNS.length);
}

function getOrCreateSheet(name) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  return ss.getSheetByName(name) || ss.insertSheet(name);
}

function writeSnapshot(name, columns, rows) {
  const sheet = getOrCreateSheet(name);
  sheet.clearContents();
  sheet.getRange(1, 1, 1, columns.length).setValues([columns]);
  if (rows.length) {
    const values = rows.map(row => columns.map(column => row[column] == null ? '' : row[column]));
    sheet.getRange(2, 1, values.length, columns.length).setValues(values);
  }
  sheet.setFrozenRows(1);
  return sheet;
}

function sha256(value) {
  const bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, String(value), Utilities.Charset.UTF_8);
  return bytes.map(byte => ((byte + 256) % 256).toString(16).padStart(2, '0')).join('');
}

function deviceHashes() {
  try { return JSON.parse(PROPERTIES.getProperty('mobile_device_hashes') || '{}'); }
  catch (_) { return {}; }
}

function saveDeviceHashes(value) {
  PROPERTIES.setProperty('mobile_device_hashes', JSON.stringify(value));
}

function configureMobilePin(pin) {
  const value = String(pin || '').trim();
  if (value.length < 4 || value.length > 64) throw new Error('PIN phải có từ 4 đến 64 ký tự.');
  PROPERTIES.setProperty('mobile_pin_hash', sha256(value));
  PROPERTIES.deleteProperty('mobile_device_hashes');
  return { ok: true };
}

function revokeMobileDevices() {
  PROPERTIES.deleteProperty('mobile_device_hashes');
  return { ok: true };
}

function createDeviceToken() {
  return `${Utilities.getUuid()}-${Utilities.getUuid()}`;
}

function requireDevice(token) {
  const tokenHash = sha256(String(token || ''));
  const devices = deviceHashes();
  if (!tokenHash || !devices[tokenHash]) throw new Error('Thiết bị chưa được xác thực.');
  devices[tokenHash] = new Date().toISOString();
  saveDeviceHashes(devices);
}

// Called by the mobile page through google.script.run. The PIN is never stored in the browser source.
function mobileUnlock(pin) {
  const expected = PROPERTIES.getProperty('mobile_pin_hash');
  if (!expected) throw new Error('Chưa đặt PIN. Hãy mở app PC, vào Cài đặt và đặt PIN Mobile Dashboard.');
  if (sha256(String(pin || '').trim()) !== expected) throw new Error('PIN không đúng.');
  const token = createDeviceToken();
  const devices = deviceHashes();
  const keys = Object.keys(devices);
  if (keys.length >= 12) delete devices[keys.sort((a, b) => String(devices[a]).localeCompare(String(devices[b])))[0]];
  devices[sha256(token)] = new Date().toISOString();
  saveDeviceHashes(devices);
  return { token: token };
}

function readRows(name, columns) {
  const sheet = getOrCreateSheet(name);
  if (sheet.getLastRow() < 2) return [];
  const values = sheet.getRange(2, 1, sheet.getLastRow() - 1, columns.length).getValues();
  return values.map(row => {
    const value = {};
    columns.forEach((column, index) => value[column] = row[index]);
    return value;
  });
}

// Called by the mobile page after a device token has been issued.
function mobileSnapshot(token) {
  requireDevice(token);
  let meta = {};
  try { meta = JSON.parse(PROPERTIES.getProperty('mobile_snapshot_meta') || '{}'); }
  catch (_) { meta = {}; }
  return {
    meta: meta,
    messages: readRows(MOBILE_INBOX_SHEET, MOBILE_INBOX_COLUMNS),
    payments: readRows(MOBILE_PAYMENTS_SHEET, MOBILE_PAYMENT_COLUMNS),
  };
}

function saveMobileSnapshot(payload) {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    writeSnapshot(MOBILE_INBOX_SHEET, MOBILE_INBOX_COLUMNS, payload.messages || []);
    writeSnapshot(MOBILE_PAYMENTS_SHEET, MOBILE_PAYMENT_COLUMNS, payload.payments || []);
    PROPERTIES.setProperty('mobile_snapshot_meta', JSON.stringify({
      synced_at: payload.synced_at || new Date().toISOString(),
      range_days: Math.max(Number(payload.range_days || 1), 1),
      message_count: (payload.messages || []).length,
      payment_count: (payload.payments || []).length,
    }));
  } finally {
    lock.releaseLock();
  }
}

function doPost(e) {
  const payload = JSON.parse(e.postData.contents || '{}');
  if (payload.secret !== SECRET) return json({ ok: false, error: 'Unauthorized' });
  if (payload.action === 'mobile_snapshot') {
    saveMobileSnapshot(payload);
    return json({ ok: true, messages: (payload.messages || []).length, payments: (payload.payments || []).length });
  }
  if (payload.action === 'mobile_set_pin') return json(configureMobilePin(payload.pin));
  if (payload.action === 'mobile_revoke_devices') return json(revokeMobileDevices());

  const sheet = getOrCreateSheet(SHEET_NAME);
  prepareSheet(sheet);
  const existing = new Set();
  const lastRow = sheet.getLastRow();
  if (lastRow > 1) sheet.getRange(2, 1, lastRow - 1, COLUMNS.length).getValues().forEach(row => existing.add(paymentKey(row)));
  let appended = 0;
  (payload.rows || []).forEach(row => {
    const values = [displayDate(row.mail_date), row.account_name || '', row.currency || '', row.amount ?? '', row.payment_id || ''];
    const key = paymentKey(values);
    if (existing.has(key)) return;
    sheet.appendRow(values);
    existing.add(key);
    appended += 1;
  });
  const paymentRows = sheet.getLastRow() - 1;
  if (paymentRows > 1) sheet.getRange(2, 1, paymentRows, COLUMNS.length).sort({ column: 2, ascending: true });
  return json({ ok: true, appended: appended });
}

function doGet() {
  return HtmlService.createHtmlOutput(MOBILE_HTML).setTitle('Amazon Mail Reader');
}

const MOBILE_HTML = `<!doctype html>
<html><head><base target="_top"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#1d2024"><meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<style>
:root{color-scheme:dark;--bg:#17191c;--surface:#202428;--surface2:#292e34;--line:#3a4148;--text:#f4f7fa;--muted:#a8b0ba;--blue:#2586d7;--green:#3cc869;--red:#f05252;--orange:#f5a43b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI Variable","Segoe UI",sans-serif}.app{max-width:760px;margin:auto;padding:20px 16px 92px}.top{display:flex;justify-content:space-between;align-items:center;margin:8px 0 4px}.brand{font-size:24px;font-weight:700;letter-spacing:0}.amazon{font-size:17px;font-weight:800;color:#fff;position:relative;padding-bottom:5px}.amazon:after{content:"";position:absolute;left:2px;right:0;bottom:0;height:3px;border-bottom:2px solid #ff9900;border-radius:0 0 70% 70%;transform:skewX(20deg)}.sync{color:var(--muted);font-size:13px;margin:8px 0 18px}.search{width:100%;border:1px solid var(--line);background:var(--surface);color:var(--text);padding:13px 14px;border-radius:12px;font-size:16px;outline:none}.filters{display:flex;gap:8px;overflow:auto;padding:14px 0 10px}.filters button{white-space:nowrap;border:1px solid var(--line);background:transparent;color:var(--text);padding:8px 12px;border-radius:10px;font-size:14px}.filters button.active{background:var(--blue);border-color:var(--blue)}.list{display:grid;gap:10px}.message{width:100%;text-align:left;border:1px solid var(--line);background:var(--surface);border-radius:14px;color:var(--text);padding:14px;display:grid;grid-template-columns:42px 1fr auto;gap:12px;align-items:center}.mark{width:42px;height:42px;display:grid;place-items:center;border-radius:12px;background:#30363d;font-size:21px}.mark.security,.pill.security{background:#52282b;color:#ff8787}.mark.reject,.pill.reject{background:#5c3126;color:#ffac66}.mark.payment,.pill.payment{background:#1c492a;color:#71e895}.mark.update,.pill.update{background:#4a3823;color:#ffc46b}.mark.amazon,.pill.amazon{background:#243d57;color:#82c2ff}.subject{font-size:16px;font-weight:600;line-height:1.35}.meta{font-size:13px;color:var(--muted);margin-top:4px}.pill{display:inline-block;border-radius:6px;padding:3px 6px;font-size:12px;margin-bottom:5px}.amount{color:var(--green);font-weight:700;font-size:14px;text-align:right}.time{color:var(--muted);font-size:12px;text-align:right;margin-top:6px}.empty{color:var(--muted);text-align:center;padding:40px 16px}.bottom{position:fixed;bottom:0;left:0;right:0;background:#202428ee;backdrop-filter:blur(12px);border-top:1px solid var(--line);display:flex;justify-content:center;gap:8px;padding:10px calc(16px + env(safe-area-inset-right)) calc(10px + env(safe-area-inset-bottom)) calc(16px + env(safe-area-inset-left))}.bottom button{min-width:130px;border:0;border-radius:10px;background:transparent;color:var(--muted);padding:10px;font-size:14px}.bottom button.active{background:#263e57;color:#93c9ff}.payment-summary{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}.sum{background:#1e3c2a;color:#82ec9c;padding:7px 10px;border-radius:8px;font-size:13px}.payment-row{background:var(--surface);border-bottom:1px solid var(--line);padding:12px 2px;display:grid;grid-template-columns:55px 1fr auto;gap:10px}.payment-row:first-child{border-top:1px solid var(--line)}.date{color:var(--muted);font-size:13px}.right{text-align:right}.modal{position:fixed;inset:0;background:#0009;display:none;align-items:end;justify-content:center}.modal.open{display:flex}.sheet{width:min(760px,100%);max-height:88vh;overflow:auto;background:#202428;border-radius:18px 18px 0 0;padding:20px 18px calc(26px + env(safe-area-inset-bottom))}.sheet h2{margin:0 0 12px;font-size:18px}.body{white-space:pre-wrap;line-height:1.5;font-size:15px}.close{float:right;border:0;background:#343b43;color:#fff;border-radius:8px;padding:7px 10px}.login{min-height:100vh;display:grid;place-items:center;padding:24px}.login-box{width:min(380px,100%);background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:24px}.login h1{margin:0 0 7px;font-size:24px}.login p{color:var(--muted);line-height:1.45}.login input{width:100%;background:#17191c;border:1px solid var(--line);border-radius:10px;color:#fff;padding:13px;font-size:18px;letter-spacing:3px}.login button{width:100%;margin-top:12px;background:var(--blue);border:0;color:#fff;border-radius:10px;padding:12px;font-size:16px}.error{color:#ff9696;font-size:13px;margin-top:10px;min-height:18px}
</style></head><body><main id="root"></main><script>
const icons={Security:'🛡',Reject:'⊘',Payment:'▣',Update:'↻',Amazon:'amazon',General:'✉'};let snapshot={meta:{},messages:[],payments:[]},tab='inbox',filter='All',query='';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const date=v=>{const m=String(v||'').match(/^(\\d{4})-(\\d{2})-(\\d{2})/);return m?m[3]+'/'+m[2]:String(v||'')};
const money=m=>m.amount===''||m.amount==null?'':esc(m.currency)+' '+Number(m.amount).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
let memoryToken='';
function token(){try{return localStorage.getItem('amz_mobile_token')||memoryToken}catch(_){return memoryToken}}
function saveToken(value){memoryToken=value||'';try{localStorage.setItem('amz_mobile_token',memoryToken)}catch(_){}}
function clearToken(){memoryToken='';try{localStorage.removeItem('amz_mobile_token')}catch(_){}}
function run(name,...args){return new Promise((resolve,reject)=>google.script.run.withSuccessHandler(resolve).withFailureHandler(reject)[name](...args))}
function login(){root.innerHTML='<section class="login"><div class="login-box"><div class="amazon">amazon</div><h1>Amazon Mail Reader</h1><p>Nhập mã PIN đã đặt trong app PC. Bạn chỉ cần làm một lần trên thiết bị này.</p><input id="pin" type="password" inputmode="numeric" placeholder="PIN"><button id="unlock">Mở dashboard</button><div id="error" class="error"></div></div></section>';document.querySelector('#unlock').onclick=async()=>{try{const result=await run('mobileUnlock',document.querySelector('#pin').value);localStorage.setItem('amz_mobile_token',result.token);load()}catch(e){document.querySelector('#error').textContent=e.message||String(e)}}}
function loginSafe(){root.innerHTML='<section class="login"><div class="login-box"><div class="amazon">amazon</div><h1>Amazon Mail Reader</h1><p>Nhap ma PIN da dat trong app PC.</p><input id="pin" type="password" inputmode="numeric" placeholder="PIN"><button id="unlock">Mo dashboard</button><div id="error" class="error"></div></div></section>';document.querySelector('#unlock').onclick=async()=>{try{const result=await run('mobileUnlock',document.querySelector('#pin').value);saveToken(result.token);load()}catch(e){document.querySelector('#error').textContent=e.message||String(e)}}}
async function load(){try{snapshot=await run('mobileSnapshot',token());render()}catch(e){clearToken();loginSafe()}}
function render(){const meta=snapshot.meta||{},sync=meta.synced_at?new Date(meta.synced_at).toLocaleString():'Chưa có dữ liệu';root.innerHTML='<div class="app"><div class="top"><div><div class="brand">Amazon Mail Reader</div><div class="sync">Đồng bộ '+esc(sync)+' · '+esc(meta.range_days||7)+' ngày</div></div><div class="amazon">amazon</div></div><div id="page"></div></div><nav class="bottom"><button id="nav-inbox" class="'+(tab==='inbox'?'active':'')+'">✉&nbsp; Inbox</button><button id="nav-payment" class="'+(tab==='payment'?'active':'')+'">▣&nbsp; Payment</button></nav><div id="modal" class="modal"></div>';document.querySelector('#nav-inbox').onclick=()=>{tab='inbox';render()};document.querySelector('#nav-payment').onclick=()=>{tab='payment';render()};tab==='inbox'?renderInbox():renderPayments()}
function renderInbox(){const page=document.querySelector('#page');const categories=['All','Security','Reject','Update','Amazon','Payment'];page.innerHTML='<input id="search" class="search" placeholder="Tìm kiếm mail"><div class="filters">'+categories.map(c=>'<button data-filter="'+c+'" class="'+(filter===c?'active':'')+'">'+(c==='All'?'Tất cả':c)+'</button>').join('')+'</div><div id="list" class="list"></div>';const input=document.querySelector('#search');input.value=query;input.oninput=()=>{query=input.value;paintInbox()};page.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{filter=b.dataset.filter;renderInbox()});paintInbox()}
function paintInbox(){const q=query.toLowerCase(),rows=snapshot.messages.filter(m=>(filter==='All'||m.category===filter)&&[m.account_name,m.from_addr,m.subject,m.snippet].join(' ').toLowerCase().includes(q));const list=document.querySelector('#list');list.innerHTML=rows.length?rows.map((m,i)=>'<button class="message" data-index="'+i+'"><span class="mark '+String(m.category||'General').toLowerCase()+'">'+(m.category==='Amazon'?'<span class="amazon">amazon</span>':icons[m.category]||icons.General)+'</span><span><span class="pill '+String(m.category||'General').toLowerCase()+'">'+esc(m.category)+'</span><span class="subject">'+esc(m.account_name)+' · '+esc(m.subject||'(Không có tiêu đề)')+'</span><span class="meta">'+esc(m.from_addr)+'</span></span><span>'+(m.amount!==''&&m.amount!=null?'<span class="amount">'+money(m)+'</span>':'')+'<span class="time">'+date(m.mail_date)+'</span></span></button>').join(''):'<div class="empty">Không có mail trong mốc đang đồng bộ.</div>';list.querySelectorAll('[data-index]').forEach(b=>b.onclick=()=>openMessage(rows[Number(b.dataset.index)]))}
function openMessage(m){const modal=document.querySelector('#modal');const body=m.body_status==='error'?'[Không tải được nội dung: '+esc(m.body_error)+']':esc(m.body||'[Không có nội dung text]');modal.innerHTML='<section class="sheet"><button class="close">Đóng</button><h2>'+esc(m.subject||'(Không có tiêu đề)')+'</h2><div class="meta">'+esc(m.account_name)+' · '+esc(m.from_addr)+' · '+date(m.mail_date)+'</div><hr style="border:0;border-top:1px solid #3a4148;margin:16px 0"><div class="body">'+body+(m.body_status==='truncated'?'\n\n[Nội dung đã được rút gọn trên mobile]':'')+'</div></section>';modal.classList.add('open');modal.querySelector('.close').onclick=()=>modal.classList.remove('open');modal.onclick=e=>{if(e.target===modal)modal.classList.remove('open')}}
function renderPayments(){const totals={};snapshot.payments.forEach(p=>{if(p.currency&&p.amount!==''&&p.amount!=null)totals[p.currency]=(totals[p.currency]||0)+Number(p.amount)});document.querySelector('#page').innerHTML='<div class="payment-summary">'+Object.entries(totals).map(([c,a])=>'<span class="sum">'+esc(c)+': '+a.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})+'</span>').join('')+'</div><div>'+snapshot.payments.map(p=>'<div class="payment-row"><span class="date">'+date(p.mail_date)+'</span><span><strong>'+esc(p.account_name)+'</strong><div class="meta">'+esc(p.account_email)+'</div><div class="meta">ID: '+esc(p.payment_id)+'</div></span><span class="right"><strong>'+money(p)+'</strong></span></div>').join('')+'</div>'}
const root=document.querySelector('#root');token()?load():loginSafe();
</script></body></html>`;
