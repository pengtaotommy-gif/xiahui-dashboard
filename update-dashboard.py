import imaplib, email, socket, os, json, urllib.request
import pandas as pd
from email.header import decode_header

DATA_FILE = "latest_data.xlsx"

def ds(s):
    if not s: return ""
    parts = decode_header(s)
    out = []
    for part, enc in parts:
        if isinstance(part, bytes):
            out.append(part.decode(enc or 'utf-8', errors='replace'))
        else:
            out.append(part)
    return ''.join(out)

print("Connecting to mailbox...")
socket.setdefaulttimeout(20)
mail = imaplib.IMAP4_SSL("imap.sina.com", 993)
mail.login(os.environ.get("PENGUIN_EMAIL"), os.environ.get("PENGUIN_PASSWORD"))
mail.select("INBOX")
status, messages = mail.search(None, 'ALL')
all_ids = messages[0].split()
print(f"Total {len(all_ids)} emails")
target_att = None
for mid in reversed(all_ids):
    try:
        status, msg_data = mail.fetch(mid, '(RFC822)')
        if not msg_data or not msg_data[0]: continue
        raw = msg_data[0][1]
        if not isinstance(raw, bytes): continue
        msg = email.message_from_bytes(raw)
        subj = ds(msg.get("Subject", ""))
        if "发布者日发布监控" in subj or "发布者监控" in subj:
            for part in msg.walk():
                fn = part.get_filename()
                fn_dec = ds(fn) if fn else ""
                if '.xlsx' in fn_dec.lower() or 'xlsm' in fn_dec.lower():
                    target_att = part.get_payload(decode=True)
                    print(f"Found: {subj}")
                    break
        if target_att: break
    except: continue
mail.logout()

if not target_att:
    print("No attachment found!"); exit(1)

with open(DATA_FILE, 'wb') as f:
    f.write(target_att)
print(f"Downloaded: {DATA_FILE}")

try:
    if not os.path.exists("echarts.min.js"):
        print("Downloading echarts.min.js...")
        urllib.request.urlretrieve(
            "https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js",
            "echarts.min.js")
        print("echarts.min.js downloaded")
except Exception as e:
    print(f"Warning: echarts download failed: {e}")

df = pd.read_excel(DATA_FILE)
df.columns = ['date','uid','nickname','member_tier','mobile','publish','quote','match']
df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
df['month'] = pd.to_datetime(df['date']).dt.to_period('M').astype(str)
df['mobile'] = df['mobile'].astype(str).str.replace('.0','',regex=False)
df['publish'] = pd.to_numeric(df['publish'], errors='coerce').fillna(0).astype(int)
df['quote'] = pd.to_numeric(df['quote'], errors='coerce').fillna(0).astype(int)
df['match'] = pd.to_numeric(df['match'], errors='coerce').fillna(0).astype(int)

daily = df.groupby('date').agg(
    publishers=('uid','nunique'),
    publish=('publish','sum'),
    quote=('quote','sum'),
    match=('match','sum')
).reset_index().sort_values('date')

latest = daily.iloc[-1]
latest_date = latest['date']
rr = round(latest['quote']/latest['publish']*100,1) if latest['publish']>0 else 0
mr = round(latest['match']/latest['quote']*100,1) if latest['quote']>0 else 0
print(f"Latest: {latest_date}, publishers={latest['publishers']}, publish={latest['publish']}")

compact = {"latest_date": latest_date, "latest": {
    "publishers": int(latest['publishers']),
    "publish": int(latest['publish']),
    "quote": int(latest['quote']),
    "match": int(latest['match']),
    "response_rate": rr,
    "match_rate": mr
}}
with open("dashboard_data_compact.json", "w", encoding="utf-8") as f:
    json.dump(compact, f, ensure_ascii=False, indent=2)

daily_list = []
for _, row in daily.tail(30).iterrows():
    r = row['quote']; p = row['publish']; m = row['match']
    daily_list.append({
        "date": row['date'],
        "publishers": int(row['publishers']),
        "publish": int(p), "quote": int(r), "match": int(m),
        "response_rate": round(r/p*100,1) if p>0 else 0,
        "match_rate": round(m/r*100,1) if r>0 else 0
    })

with open("dashboard_daily.json", "w", encoding="utf-8") as f:
    json.dump(daily_list, f, ensure_ascii=False, indent=2)

dates = json.dumps([d['date'][5:] for d in daily_list])
pubs = json.dumps([d['publishers'] for d in daily_list])
pubs2 = json.dumps([d['publish'] for d in daily_list])
matches = json.dumps([d['match'] for d in daily_list])
resp = json.dumps([d['response_rate'] for d in daily_list])
daily_js = json.dumps(daily_list)

CSS = """
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0f0f1a;color:#e0e0e0;padding:20px;font-size:14px}
h1{color:#fff;margin-bottom:20px}
.kpi{display:flex;gap:16px;margin-bottom:20px;flex-wrap:wrap}
.card{background:#1a1a2e;border-radius:10px;padding:16px;flex:1;min-width:140px}
.card .label{color:#888;font-size:12px;margin-bottom:4px}
.card .value{font-size:24px;font-weight:700;color:#4fc3f7}
.card .sub{color:#666;font-size:11px}
.chart{background:#1a1a2e;border-radius:10px;padding:16px;height:360px;margin-bottom:20px}
table{width:100%;border-collapse:collapse;font-size:12px}
th{text-align:left;padding:8px 6px;color:#888;border-bottom:1px solid #2a2a3a}
td{padding:8px 6px;border-bottom:1px solid #1e1e2e}
tr:hover{background:#1e1e2e}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600}
.V5{background:#ffd700;color:#000}.V4{background:#c0c0c0;color:#000}
.V3{background:#cd7f32;color:#fff}.V2{background:#4a4a6a;color:#ccc}
.V1{background:#2a2a4a;color:#888}
</style>
"""

html = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>发布者监控看板</title>
<script src="./echarts.min.js"></script>
""" + CSS + """
</head><body>
<h1>📊 发布者监控看板 <span style="font-size:12px;color:#666;font-weight:normal">更新: """ + latest_date + """</span></h1>
<div class="kpi">
  <div class="card"><div class="label">发布人数</div><div class="value">""" + str(latest['publishers']) + """</div></div>
  <div class="card"><div class="label">发布量</div><div class="value">""" + str(latest['publish']) + """</div></div>
  <div class="card"><div class="label">报价量</div><div class="value">""" + str(latest['quote']) + """</div></div>
  <div class="card"><div class="label">匹配量</div><div class="value">""" + str(latest['match']) + """</div></div>
  <div class="card"><div class="label">响应率</div><div class="value">""" + str(rr) + """%</div></div>
  <div class="card"><div class="label">匹配率</div><div class="value">""" + str(mr) + """%</div></div>
</div>
<div class="chart" id="chart"></div>
<div id="table-wrap"></div>
<script>
var DAILY = """ + daily_js + """;
var chart = echarts.init(document.getElementById('chart'));
chart.setOption({
  backgroundColor:'transparent',
  tooltip:{trigger:'axis',backgroundColor:'#1a1a2e',textStyle:{color:'#ccc'}},
  legend:{data:['发布人数','发布量','匹配量','响应率'],top:0},
  xAxis:{type:'category',data:""" + dates + """,axisLine:{lineStyle:{color:'#2a2a3a'}}}},
  yAxis:[
    {type:'value',name:'人数/量',axisLine:{lineStyle:{color:'#2a2a3a'}}},
    {type:'value',name:'%',axisLine:{lineStyle:{color:'#2a2a3a'}}}
  ],
  series:[
    {name:'发布人数',type:'line',data:""" + pubs + """,smooth:true,itemStyle:{color:'#4fc3f7'}},
    {name:'发布量',type:'line',data:""" + pubs2 + """,smooth:true,itemStyle:{color:'#66bb6a'}},
    {name:'匹配量',type:'line',data:""" + matches + """,smooth:true,itemStyle:{color:'#ff9800'}},
    {name:'响应率',type:'line',yAxisIndex:1,data:""" + resp + """,smooth:true,itemStyle:{color:'#ef5350'}}
  ]
});
var html='<table><thead><tr><th>日期</th><th>发布人数</th><th>发布量</th><th>报价量</th><th>匹配量</th><th>响应率</th><th>匹配率</th></tr></thead><tbody>';
DAILY.slice(-14).reverse().forEach(function(d){
  var r=d.quote,p=d.publish,m=d.match;
  html+='<tr><td>'+d.date+'</td><td>'+d.publishers+'</td><td>'+p+'</td><td>'+r+'</td><td>'+m+'</td><td>'+(p>0?(r/p*100).toFixed(1):'0')+'%</td><td>'+(r>0?(m/r*100).toFixed(1):'0')+'%</td></tr>';
});
html+='</tbody></table>';
document.getElementById('table-wrap').innerHTML=html;
</script></body></html>"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)
print(f"index.html written: {len(html)} bytes")
print("Done!")
