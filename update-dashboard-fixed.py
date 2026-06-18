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

# Download echarts if not present
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
df.columns = ['date', 'uid', 'nickname', 'member_tier', 'mobile', 'publish', 'quote', 'match']
df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
df['month'] = pd.to_datetime(df['date']).dt.to_period('M').astype(str)
df['mobile'] = df['mobile'].astype(str).str.replace('.0', '', regex=False)
df['publish'] = pd.to_numeric(df['publish'], errors='coerce').fillna(0).astype(int)
df['quote'] = pd.to_numeric(df['quote'], errors='coerce').fillna(0).astype(int)
df['match'] = pd.to_numeric(df['match'], errors='coerce').fillna(0).astype(int)

daily = df.groupby('date').agg(
    publishers=('uid', 'nunique'),
    publish=('publish', 'sum'),
    quote=('quote', 'sum'),
    match=('match', 'sum')
).reset_index().sort_values('date')

latest = daily.iloc[-1]
latest_date = latest['date']
rr = round(latest['quote'] / latest['publish'] * 100, 1) if latest['publish'] > 0 else 0
mr = round(latest['match'] / latest['quote'] * 100, 1) if latest['quote'] > 0 else 0
print(f"Latest: {latest_date}, publishers={latest['publishers']}, publish={latest['publish']}")

daily_list = []
for _, row in daily.tail(30).iterrows():
    r = row['quote']
    p = row['publish']
    m = row['match']
    daily_list.append({
        "date": row['date'],
        "publishers": int(row['publishers']),
        "publish": int(p),
        "quote": int(r),
        "match": int(m),
        "response_rate": round(r / p * 100, 1) if p > 0 else 0,
        "match_rate": round(m / r * 100, 1) if r > 0 else 0
    })

# Build arrays for JS
dates_js = json.dumps([d['date'][5:] for d in daily_list])
pubs_js = json.dumps([d['publishers'] for d in daily_list])
pubs2_js = json.dumps([d['publish'] for d in daily_list])
matches_js = json.dumps([d['match'] for d in daily_list])
resp_js = json.dumps([d['response_rate'] for d in daily_list])
daily_js = json.dumps(daily_list)

CSS = """
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0f0f1a;color:#e0e0e0;padding:20px;font-size:14px}
h1{color:#fff;margin-bottom:20px;font-size:20px}
.kpi{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:20px}
.kpi-card{background:#1a1a2e;border-radius:10px;padding:16px;border:1px solid #2a2a3a}
.label{font-size:11px;color:#888;margin-bottom:6px;text-transform:uppercase}
.value{font-size:24px;font-weight:700;color:#4fc3f7}
.blue .value{color:#4fc3f7}.green .value{color:#66bb6a}.orange .value{color:#ffb74d}.purple .value{color:#ba68c8}.red .value{color:#ef5350}
.sub{font-size:11px;color:#666;margin-top:2px}
.card{background:#1a1a2e;border-radius:10px;padding:16px;border:1px solid #2a2a3a;margin-bottom:16px}
.section{margin-bottom:28px}
.section-title{font-size:15px;color:#fff;margin-bottom:12px;padding-left:10px;border-left:3px solid #4fc3f7}
.chart{background:#1a1a2e;border-radius:10px;padding:16px;height:320px;margin-bottom:16px}
table{width:100%;border-collapse:collapse;font-size:12px}
th{text-align:left;padding:8px 6px;color:#888;border-bottom:1px solid #2a2a3a;font-weight:500}
td{padding:8px 6px;border-bottom:1px solid #1e1e2e;color:#ccc}
tr:hover{background:#1e1e2e}
.date-cell{color:#fff;font-weight:500}
.up{color:#66bb6a}.down{color:#ef5350}
</style>
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>发布者监控看板</title>
<script src="./echarts.min.js"></script>
""" + CSS + """
</head><body>
<h1>📊 发布者监控看板 <span style="font-size:12px;color:#888;font-weight:normal">更新: """ + latest_date + """</span></h1>

<div class="kpi" id="kpi"></div>

<div class="section">
<div class="section-title">每日趋势</div>
<div class="chart" id="chart"></div>
<div id="table-wrap"></div>
</div>

<div class="section">
<div class="section-title">近7日明细</div>
<div id="detail-table"></div>
</div>

<script>
var DAILY = """ + daily_js + """;
var latest = DAILY[DAILY.length - 1];
var prev = DAILY.length > 1 ? DAILY[DAILY.length - 2] : latest;

document.getElementById("kpi").innerHTML =
  '<div class="kpi-card blue"><div class="label">发布人数</div><div class="value">' + latest.publishers + '</div><div class="sub">' + (latest.publishers >= prev.publishers ? '↑' : '↓') + Math.abs(latest.publishers - prev.publishers) + '</div></div>' +
  '<div class="kpi-card green"><div class="label">发布量</div><div class="value">' + latest.publish + '</div><div class="sub">' + (latest.publish >= prev.publish ? '↑' : '↓') + Math.abs(latest.publish - prev.publish) + '</div></div>' +
  '<div class="kpi-card orange"><div class="label">报价量</div><div class="value">' + latest.quote + '</div></div>' +
  '<div class="kpi-card purple"><div class="label">匹配量</div><div class="value">' + latest.match + '</div></div>' +
  '<div class="kpi-card"><div class="label">响应率</div><div class="value">' + latest.response_rate + '%</div></div>' +
  '<div class="kpi-card red"><div class="label">匹配率</div><div class="value">' + latest.match_rate + '%</div></div>';

var dates = """ + dates_js + """;
var pubs = """ + pubs_js + """;
var pubs2 = """ + pubs2_js + """;
var matches = """ + matches_js + """;
var resp = """ + resp_js + """;

var chart = echarts.init(document.getElementById("chart"));
chart.setOption({
  backgroundColor: "transparent",
  tooltip: {trigger: "axis", backgroundColor: "#1a1a2e", textStyle: {color: "#ccc"}},
  legend: {data: ["发布人数", "发布量", "匹配量", "响应率"], top: 0},
  xAxis: {type: "category", data: dates, axisLine: {lineStyle: {color: "#2a2a3a"}}},
  yAxis: [
    {type: "value", name: "人数/量", axisLine: {lineStyle: {color: "#2a2a3a"}}},
    {type: "value", name: "%", axisLine: {lineStyle: {color: "#2a2a3a"}}}
  ],
  series: [
    {name: "发布人数", type: "line", data: pubs, smooth: true, itemStyle: {color: "#4fc3f7"}},
    {name: "发布量", type: "line", data: pubs2, smooth: true, itemStyle: {color: "#66bb6a"}},
    {name: "匹配量", type: "line", data: matches, smooth: true, itemStyle: {color: "#ff9800"}},
    {name: "响应率", type: "line", yAxisIndex: 1, data: resp, smooth: true, itemStyle: {color: "#ef5350"}}
  ]
});

var tableHtml = "<table><thead><tr><th>日期</th><th>发布人数</th><th>发布量</th><th>报价量</th><th>匹配量</th><th>响应率</th><th>匹配率</th></tr></thead><tbody>";
DAILY.slice(-14).reverse().forEach(function(d) {
  var rr = d.publish > 0 ? (d.quote / d.publish * 100).toFixed(1) : "0";
  var mr = d.quote > 0 ? (d.match / d.quote * 100).toFixed(1) : "0";
  tableHtml += "<tr><td class='date-cell'>" + d.date + "</td><td>" + d.publishers + "</td><td>" + d.publish + "</td><td>" + d.quote + "</td><td>" + d.match + "</td><td>" + rr + "%</td><td>" + mr + "%</td></tr>";
});
tableHtml += "</tbody></table>";
document.getElementById("table-wrap").innerHTML = tableHtml;

var detailHtml = "<table><thead><tr><th>日期</th><th>发布人数</th><th>发布量</th><th>报价量</th><th>匹配量</th><th>响应率</th><th>匹配率</th><th>发布环比</th><th>匹配环比</th></tr></thead><tbody>";
DAILY.slice(-7).forEach(function(d, i) {
  var prevDay = DAILY[DAILY.length - 8 + i] || d;
  var pubChg = d.publish - prevDay.publish;
  var pubPct = prevDay.publish > 0 ? ((pubChg / prevDay.publish * 100).toFixed(1) + "%") : "-";
  var matChg = d.match - prevDay.match;
  var matPct = prevDay.match > 0 ? ((matChg / prevDay.match * 100).toFixed(1) + "%") : "-";
  var rr = d.publish > 0 ? (d.quote / d.publish * 100).toFixed(1) : "0";
  var mr = d.quote > 0 ? (d.match / d.quote * 100).toFixed(1) : "0";
  detailHtml += "<tr><td class='date-cell'>" + d.date + "</td><td>" + d.publishers + "</td><td>" + d.publish + "</td><td>" + d.quote + "</td><td>" + d.match + "</td><td>" + rr + "%</td><td>" + mr + "%</td><td class='" + (pubChg >= 0 ? "up" : "down") + "'>" + (pubChg >= 0 ? "↑" : "↓") + " " + pubPct + "</td><td class='" + (matChg >= 0 ? "up" : "down") + "'>" + (matChg >= 0 ? "↑" : "↓") + " " + matPct + "</td></tr>";
});
detailHtml += "</tbody></table>";
document.getElementById("detail-table").innerHTML = detailHtml;
</script>
</body></html>"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(HTML_TEMPLATE)
print(f"index.html written: {len(HTML_TEMPLATE)} bytes")
print("Done!")
