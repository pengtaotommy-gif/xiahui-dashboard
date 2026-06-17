# 发布者监控看板 — Vercel + GitHub 自动部署指南

## 整体流程

```
每天 10:00（我定时触发）
    ↓
我：拉取邮箱 → 解析 Excel → 生成最新 HTML/JSON
    ↓
我：git push 到 GitHub 仓库
    ↓
Vercel：检测到新 commit → 自动部署 → 公网可访问
```

**零成本，零服务器，永久自动**

---

## 第一步：创建 GitHub 私有仓库

1. 打开 https://github.com/new
2. Repository name: `xiahui-dashboard`（私有）
3. 不要勾选任何初始化选项 → Create repository
4. 记下仓库地址，格式如：`https://github.com/你的用户名/xiahui-dashboard`

---

## 第二步：本地初始化 Git 仓库

在终端执行（替换 `你的用户名` 为你的 GitHub 用户名）：

```bash
cd /Users/boni/Desktop/鹅鹅鹅的小龙虾/vercel_deploy

git init
git remote add origin https://github.com/你的用户名/xiahui-dashboard.git

# 忽略大文件
echo "dashboard_user_detail.json" >> .gitignore
echo "latest_data.xlsx" >> .gitignore
git remote -v
```

---

## 第三步：首次推送

```bash
git add .
git commit -m "Initial publish"
git branch -M main
git push -u origin main
```

---

## 第四步：连接 Vercel

1. 打开 https://vercel.com
2. 用 GitHub 账号登录
3. "Add New" → "Project"
4. 选择 `xiahui-dashboard` 仓库
5. Framework Preset: **Other**（不用改任何配置）
6. 点击 **Deploy**
7. 等待 30 秒 → 获得永久公网 URL，如：`https://xiahui-dashboard.vercel.app`

---

## 第五步：设置每日自动更新

我来处理这一步。仓库创建并首次推送后，告诉我一声，我配置每天定时：

1. 拉取邮箱最新附件
2. 重新生成 `dashboard_simple.html`
3. `git add . && git commit && git push`

Vercel 检测到 push，自动部署新版本。

---

## 部署后访问

| 环境 | URL |
|:---|:---|
| 正式版 | `https://xiahui-dashboard.vercel.app` |
| 完整版 | `https://xiahui-dashboard.vercel.app/final` |

---

## 目录结构

```
vercel_deploy/
├── dashboard_simple.html        # 主看板（简洁版）
├── 发布者监控看板_最终版.html    # 完整版
├── dashboard_data.json          # 主数据
├── dashboard_data_compact.json  # 紧凑数据
├── dashboard_newold.json        # 新老用户数据
├── dashboard_user_detail.json   # 用户明细
├── echarts.min.js              # 图表库
└── README.md                    # 本文件
```

---

## 手动更新（可选）

如果某天想立刻更新数据，在终端执行：

```bash
cd /Users/boni/Desktop/鹅鹅鹅的小龙虾
python3 update_dashboard_full.py
cd vercel_deploy
cp ../dashboard_simple.html .
cp ../dashboard_data.json .
cp ../dashboard_data_compact.json .
cp ../dashboard_newold.json .
cp ../dashboard_user_detail.json .
git add .
git commit -m "Update: $(date '+%Y-%m-%d %H:%M')"
git push
```

Vercel 会在 30 秒内自动部署新版本。
