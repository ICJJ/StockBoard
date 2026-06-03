# StockBoard

一个简洁的美股实时自选股看板，基于 Next.js（App Router）构建，行情数据来自 [Finnhub](https://finnhub.io)。

## 功能

- 自选股网格看板：实时价格、涨跌额/涨跌幅、当日开盘/昨收/最高最低
- 股票搜索并一键加入自选（按代码或公司名）
- 会话内日内迷你走势图（Sparkline）
- 当日价格区间位置标记
- 每 15 秒自动刷新，支持手动刷新
- 自选股保存在浏览器本地（localStorage）
- 美股交易时段状态指示（基于纽约时间）
- API key 完全保存在服务端，不暴露给浏览器

## 本地运行

```bash
npm install
cp .env.example .env.local   # 填入你的 Finnhub API key
npm run dev
```

打开 http://localhost:3000

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `FINNHUB_API_KEY` | Finnhub API key，免费注册：https://finnhub.io/register |

## 部署到 Vercel

1. 在 Vercel 导入此 GitHub 仓库
2. 在 Project Settings → Environment Variables 添加 `FINNHUB_API_KEY`
3. 部署

## 技术栈

- Next.js 14 / React 18
- 服务端 API 路由代理 Finnhub（`/api/quote`、`/api/search`）
- 零额外 UI 依赖，纯 CSS + 内联 SVG 图表

> 数据仅供参考，不构成投资建议。
