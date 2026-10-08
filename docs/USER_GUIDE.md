# FinPilot 完整使用教程

这份教程对应仓库当前版本，目标是让第一次接触 FinPilot 的人能够先完成一次完整体验，再让有金融研究经验的人导入自己的数据。FinPilot 默认离线运行；内置演示数据是合成数据或公开案例快照，不是实时行情，也不构成投资建议。

## 一、第一次体验：不启动服务

最简单的方式是直接打开仓库根目录的 `index.html` 或 `FinPilot演示工作台.html`。

第一次打开后，顶部会看到“视图”选择：

```text
新手引导
专业工作台
```

先选择“新手引导”。

左侧主要入口包括“投资研究”“信用风险”“固收与期权”“案例与评测”。新手第一次只需要使用“投资研究”。

### 1. 选择一个内置时期

投资研究页有“研究截止日”选项：

```text
2025-12-31 · 最新快照
2022-12-31 · 加息周期
2020-12-31 · 疫情后恢复
```

这些时期用于演示 point-in-time 研究逻辑。它们使用本地固定种子合成股票池，不代表真实公司。

选择一个时期后，点击“运行投资研究”。静态页面会直接回放对应的内置结果，不会联网，也不会要求你先启动 Python 服务。

### 2. 选择组合预设

可以选择三个预设：

“均衡研究”使用均衡评分和等权方式，最容易解释；“稳健起步”更强调质量、已观察到的波动和较低单票上限；“价值敏感”更强调估值敏感性和得分权重。

预设改变的是筛选偏好和组合规则，不是未来收益预测。

### 3. 阅读股票池

股票池表格会展示代码、行业、PE、增长、质量/成长/价值评分、价格风险、状态和原因。

看到“排除”时，要区分两类情况。第一类是数据问题，例如披露日在研究日之后、价格历史不足或数据过期；第二类是规则问题，例如 PE 超过上限、EPS 不为正、利润率不为正或债务/权益比过高。

“排除”表示不符合当前研究条件，不表示公司永远没有研究价值；“通过”表示值得继续研究，不表示买入建议。

### 4. 阅读组合草案

组合草案会展示每个候选的行业、权重、原始分数和证据 ID。单票上限是硬约束，如果通过的公司数量不足以在不违反上限的情况下满仓，系统会保留现金。

这意味着：

```text
权重之和 + 现金比例 = 100%
```

### 5. 阅读压力诊断

压力诊断包括一日参数压力、最差 20 日历史回放和相关性压力。每个情景都显示损失、期限和假设。

这些数字不是校准 VaR，不是完整回测，也不是未来收益预测。共同日期收益不足时，系统会显示“不可计算”或“insufficient”，不会用缺失数据补齐。

## 二、第一次专业体验：专业工作台

在顶部把“视图”切换到“专业工作台”。

专业模式会增加估值敏感性、证据账本和配置/再平衡草案。

### 估值敏感性

系统使用当前 EPS 乘不同假设 PE，展示 10x、20x、30x、40x 等隐含价格。它的用途是帮助你提出问题：当前价格隐含了多少倍数？如果估值回落，价格如何变化？

它不是目标价，也不是 DCF，不应该单独用于投资决策。

### 证据账本

证据账本保存来源字符串、披露时间、价格时间、原始输入 hash 和计算定位。来源字段是血缘信息，不等于独立核验。

### 配置与再平衡草案

配置草案展示参考资金、目标权重、金额、参考股数、目标与当前持仓差额、换手率和手续费估算。

它不会连接交易所，不会提交订单，也没有税费、滑点、最小交易单位和流动性模型。参考股数只是便于研究讨论的数量换算。

## 三、使用内置公开案例

点击左侧“案例与评测”。

### 1. 公共历史参考案例

页面包含 S&P 500 和美国 10 年期国债的公共历史参考点位。案例包括：

2020 年疫情冲击与恢复；2022 年加息周期与股市回撤；2022 年美国 10 年期国债收益率重定价。

历史页面会展示来源链接、区间变化、起点、终点、峰值回撤或收益率 bp 变化。数据是稀疏快照，不是完整每日价格序列。

### 2. 官方公开财务案例

页面包含 Apple FY2024、Microsoft FY2024、NVIDIA FY2024 和 WTI 2020 负油价案例。

Apple 案例适合练习一次性税项与利润质量；Microsoft 案例适合练习收入、营业利润和经营利润率；NVIDIA 案例适合练习高增长、高利润率、集中度和估值正常化；WTI 案例适合练习期货到期、存储约束、流动性、保证金和展期。

每个案例都有来源链接、研究问题和限制。案例中的派生指标是 FinPilot 计算，不是来源原文中的投资结论。

### 3. 公共宏观数据库

仓库的 `data/public/` 包含 World Bank 的小型宏观数据快照：GDP 增长、CPI 增长、出口占 GDP 比例，覆盖美国、中国、日本和德国。

它们用于宏观背景和国家比较，不是股票行情，也不是投资信号。每一行包含来源 URL、指标代码和快照日期。

## 四、启动本地 Web 服务

如果你需要导入自己的 CSV、修改任意参数或调用本机 API，在项目目录执行：

```bash
cd "/Users/xiaziliang/Desktop/实习/FinPilot"
python -m pip install -e .
python -m finpilot serve
```

打开：

```text
http://127.0.0.1:8765
```

本机服务只绑定 loopback，不是公网服务。

当前主要 API 包括：

```text
GET  /health
POST /api/investment
POST /api/construct
POST /api/advisor/preview
POST /api/advisor/test
POST /api/advisor/enhance
```

请求需要本机 header：

```text
Content-Type: application/json
X-FinPilot: local
```

## 五、导入自己的股票数据

### stocks.csv

表头必须完全一致：

```csv
symbol,name,sector,currency,price_as_of,price,eps_ttm,revenue_growth,operating_margin,fcf_margin,debt_to_equity,period_end,filed_at,source
```

示例：

```csv
AAPL,Apple Inc.,Technology,USD,2024-12-31,250.00,6.50,0.08,0.31,0.27,1.50,2024-09-28,2024-11-01,https://www.apple.com/newsroom/
```

### prices.csv

表头必须完全一致：

```csv
date,symbol,adj_close
```

示例：

```csv
date,symbol,adj_close
2024-01-02,AAPL,185.64
2024-01-03,AAPL,184.25
2024-01-04,AAPL,181.91
```

比例必须使用小数：

```text
0.08 = 8%
0.31 = 31%
1.50 = 1.5x
```

价格必须为正；同一 CSV 只能使用一种币种；报告期末不能晚于披露日。

### 使用 data doctor

先检查：

```bash
python -m finpilot data doctor \
  --provider user_snapshot \
  --stocks /path/to/stocks.csv \
  --prices /path/to/prices.csv \
  --as-of 2024-12-31
```

再运行：

```bash
python -m finpilot research \
  --stocks /path/to/stocks.csv \
  --prices /path/to/prices.csv \
  --as-of 2024-12-31 \
  --method equal \
  --output reports/research
```

输出包括：

```text
reports/research/research.json
reports/research/input-manifest.json
```

真实导入数据会被标记为“用户提供，未独立核验”。FinPilot 不替用户核实数据授权、会计定义、复权方法或财报修订。

## 六、专业用户的 provider 使用方式

### yfinance

默认不安装。需要用户自己评估来源条款，并主动安装：

```bash
python -m pip install -e ".[market-data]"
```

检查：

```bash
python -m finpilot data doctor --provider yfinance
```

显式抓取：

```bash
python -m finpilot fetch \
  --provider yfinance \
  --ticker AAPL \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --allow-network \
  --accept-terms \
  --output /tmp/aapl-provider.json \
  --prices-output /tmp/aapl-prices.csv
```

缺依赖、网络失败、没有 Adj Close、日期越界或响应异常都会明确失败，不会回退到合成数据。

### SEC companyfacts

需要明确 CIK 和真实联系邮箱：

```bash
python -m finpilot fetch \
  --provider sec_edgar \
  --ticker AAPL \
  --cik 0000320193 \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --user-agent "Research Team contact@your-domain.example" \
  --allow-network \
  --accept-terms \
  --output /tmp/sec-facts.json
```

SEC 入口只返回 raw companyfacts，不自动完成 ticker/CIK 推断、TTM、EPS、FCF、单位统一、修订处理或 stocks.csv 生成。

## 七、LLM 使用方式

FinPilot 的本地核心不需要大模型。

没有 LLM 时，系统仍能完成：

```text
数据检查
股票筛选
组合构建
现金约束
压力测试
估值敏感性
案例分析
证据账本
研究备忘录
```

如果要接入 OpenAI-compatible 模型：

```bash
export FINPILOT_LLM_ENDPOINT=http://127.0.0.1:11434/v1
export FINPILOT_LLM_MODEL=你的本地模型名
export FINPILOT_LLM_API_KEY=
python -m finpilot agent \
  --live-model \
  --question "为什么这些公司被排除？我还需要核查哪些风险？"
```

LLM 可以做问题理解、研究追问、finding 相关性排序和摘要；不能修改 PE、收益率、组合权重、Expected Loss、点时判断或证据 ID。

## 八、金融小白的推荐顺序

第一次只做以下步骤：

```text
1. 打开 index.html
2. 选择新手引导
3. 选择均衡研究
4. 运行 2025 最新快照
5. 阅读通过与排除原因
6. 查看组合现金比例
7. 切换 2022 加息周期
8. 查看 S&P 500 历史案例
9. 阅读 Apple 财务案例
```

先理解三个概念：筛选条件、组合约束、风险情景。

不要一开始就看协方差、ECE、MCP 或 JSON-RPC。

## 九、金融专业用户的推荐顺序

```text
1. 启动本机服务
2. 专业工作台
3. data doctor
4. 导入授权 CSV
5. 修改 PE / 增长 / 杠杆条件
6. 对比均衡/质量/价值预设
7. 输入资金和现金底线
8. 审阅单票/行业 cap
9. 进行再平衡费用估算
10. 导出 research.json 与 input-manifest.json
11. 用案例库做公开事实核对
```

## 十、常见误解

“通过”不等于买入；“排除”不等于公司没有价值；合成回测不等于 alpha；公开历史点位不等于实时数据；provider fetch 成功不等于独立验证；LLM 说得流畅不等于数字正确；组合草案不等于交易指令。

## 十一、重要边界

FinPilot 当前是一个高完成度本地金融研究作品集原型，不是已完成应用商店审核的正式金融产品。正式商业发布前仍需要数据授权、隐私政策、用户协议、风险披露、账号权限、密钥管理、审计日志、真实用户验收、合规评估和商店审核。
