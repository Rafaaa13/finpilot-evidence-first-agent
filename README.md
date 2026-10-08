# FinPilot

> Screen a synthetic equity universe, build a capped long-only portfolio, stress it on common-date returns, and export an evidence-linked research memo — locally, reproducibly, without an LLM.

FinPilot 是一个本地优先的金融研究与风险工作台。它不是“会聊天的选股机器人”，而是一条可以被复核的研究流程：输入研究截止日和数据，先做点时与口径检查，再筛选候选、配置组合、做风险压力诊断，最后导出研究备忘录。LLM 只作为可选的自然语言增强，不参与金融算术、权重计算或风险门禁。

当前默认演示使用固定种子的合成数据。`DEMO01`—`DEMO08` 不是现实证券，演示中的收益、评分和压力数值不能用于投资决策。

## 你可以用它做什么

FinPilot 适合演示和训练四类金融任务。投资研究入口根据 PE、收入增长、经营利润率、自由现金流率、债务/权益比和数据完整性筛选候选；组合入口支持等权、得分权重和低波倒数权重，设置单票上限后将剩余部分保留为现金；风险入口用共同日期日收益计算一日参数压力、最差 20 日历史回放和相关性压力；信用与固收入口分别展示 EAD 加权 Expected Loss、PD/LGD 压力、AUC/Brier/ECE、债券久期/凸性/DV01 和期权定价交叉核对。

工作台支持“新手引导”和“专业工作台”两种视图。新手模式先看候选/组合/压力四步流程，并可直接回放内置的 2025、2022 加息周期、2020 疫情后恢复三个合成投资案例和公开 S&P 500 月度市场案例；专业模式展开估值敏感性、证据账本和配置/再平衡草案，包括资金、现金底线、单票/行业约束、换手和手续费估算。组合草案不会连接交易所或下单。

它的关键用途不是替你得出“买什么”，而是让你能清楚回答：候选为什么入选或被排除？组合规则是什么？现金为什么没有被强行配置？压力情景用的是什么日期和假设？数据是否由用户核验？哪些地方必须交给研究员复核？

## 5 分钟上手

环境要求 Python 3.10+。在仓库根目录运行：

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python -m finpilot research --as-of 2025-12-31 --method equal
python -m finpilot export --output FinPilot演示工作台.html
python -m finpilot serve
```

不启动服务也能完整体验内置案例：双击 `index.html` 或 `FinPilot演示工作台.html`，选择“新手引导”，点击“运行投资研究”，切换 2025 最新快照、2022 加息周期、2020 疫情后恢复，查看候选、组合、压力与公开 S&P 500 月度案例。静态页面的参数只使用内置可复现快照，不会显示“已重算”的假结果；需要上传自己的 CSV、修改任意参数或运行 doctor 时，再启动本机服务。

然后打开 `http://127.0.0.1:8765`。建议第一次按这个顺序演示：
```text
投资研究 → 运行研究
         → 股票池：看通过/排除原因
         → 组合：看权重上限与现金
         → 压力：看三种风险情景
         → 导出 JSON / 查看证据账本
信用风险 → 拖动压力参数，解释 EAD 加权 EL
评测与边界 → 注入失败案例，说明系统为什么拒绝
```

也可以导出一个不需要启动 Python 服务的静态页面：

```bash
python -m finpilot export --output /tmp/FinPilot演示工作台.html
open /tmp/FinPilot演示工作台.html
```

## 岗位能力训练工作台

仓库还包含一个独立的中文训练工具 [`金融风险能力训练工作台.html`](金融风险能力训练工作台.html)。它把风险管理、金融工程、SQL/Python 练习、项目证据包和面试演练串成八周训练路线，使用离线合成数据，不需要联网即可双击打开。工作台会明确区分“练习结果”和“真实生产经验”，并提供本机 SQLite starter 练习与进度 JSON 导入/导出。

建议使用顺序：风险实验室 → 金工计算台 → SQL 数据练习 → 本机练习 → 项目证据包 → 面试演练。合成数据和训练结果不能写成真实金融机构生产项目或投资业绩。

## 导入自己的研究快照

本地服务支持 `POST /api/investment`，工作台提供 CSV 文件入口。股票财务 CSV 的表头必须是：

```text
symbol,name,sector,currency,price_as_of,price,eps_ttm,revenue_growth,operating_margin,fcf_margin,debt_to_equity,period_end,filed_at,source
```

日线价格 CSV 的表头必须是：

```text
date,symbol,adj_close
```

所有比例用小数，例如 `0.18` 表示 18%；`adj_close` 要明确是用户选择的复权价格。系统限制 CSV 体积、行数、代码格式、重复日期、正价格、单币种和披露日期口径。未来披露或价格不会被偷偷用于历史截止日；缺失字段会进入排除或风险不可计算，而不是补 0。

用户导入的数据标签是“用户提供，未独立核验”。`source` 字段用于血缘记录，不代表 FinPilot 已经替用户验证来源真实性、供应商许可或财务口径。

## 可选真实数据方式（默认不联网）

FinPilot 现在支持三种数据方式，但默认仍是安全、离线、可复现：

1. **本地授权 CSV**：沿用上面的 `stocks.csv` / `prices.csv` 合同，推荐先运行 `data doctor`，再用 `research --stocks ... --prices ...`。真实输入仍标记为未独立核验。
2. **显式 provider fetch**：`yfinance` 与 SEC raw companyfacts 适配器只在 `fetch` 命令中延迟导入/请求；必须明确 `--allow-network` 和 `--accept-terms`。缺依赖、网络失败、日期/单位/响应错误都会清晰失败，绝不静默回退为合成数据。输出是 `real_user_fetch`，不是 `verified`。
3. **版本化案例包**：`examples/real_cases/` 只有案例元数据模板，没有精确行情数字。四个案例都标记 `data_status=user_snapshot_required`，需要研究者提供有权使用的快照。

离线检查和显式 fetch 示例见 [`docs/data-sources.md`](docs/data-sources.md)。普通安装不安装 `yfinance`；如自行安装，使用可选依赖 `market-data`。本次仓库验证不下载任何外部数据。

## LLM：锦上添花，不是依赖

不配置 LLM 时，本地确定性核心仍可完成数据校验、候选筛选、组合权重、现金保留、共同日期压力、风险门禁和研究备忘录。这样设计是为了让金融数字可重复、让用户不必上传敏感数据，也让面试官能看到产品价值不依赖“模型说得像不像”。

接入自己的 OpenAI-compatible endpoint：

```bash
export FINPILOT_LLM_ENDPOINT=http://127.0.0.1:11434/v1
export FINPILOT_LLM_MODEL=你的本地模型名
export FINPILOT_LLM_API_KEY=
python -m finpilot agent --live-model --question "请解释为什么有些公司被排除，并列出人工核查问题"
```

LLM 允许做自然语言问题理解、工具路由、候选 finding 相关性排序、研究追问和摘要润色；LLM 不允许计算或修改 PE、收益、Expected Loss、组合权重、压力损失、点时判断或 evidence ID。工作台中的“LLM 可选增强”先展示发送摘要，用户确认后才调用模型；默认不发送 CSV 原文、私有文件或密钥。

## 最小产品架构

```text
本地 CSV / 合成 fixture
        ↓
字段、币种、日期、披露时点校验
        ↓
投资筛选：PE / 增长 / 利润率 / FCF / 杠杆 / 数据完整性
        ↓
组合构建：等权 / 得分 / 低波倒数 + 单票上限 + 现金
        ↓
共同日期风险：参数压力 / 历史20日 / 相关性压力
        ↓
证据账本 + 研究备忘录 + 可复现 JSON
        ↑
可选 LLM：只做问题理解、相关性排序和表达增强
```

核心模块包括：`investment.py` 负责用户数据入口与股票研究；`portfolio.py` 负责长仓权重、硬性 cap、现金、行业集中度和共同日期压力；`data.py` 与 `analytics.py` 负责原始观察、点时可见性和确定性指标；`risk.py` 负责信用/固收/期权算例；`integrations.py` 负责受限 MCP 与 OpenAI-compatible 边界；`advisor.py` 负责 LLM 发送前预览和相关性增强；`workbench.html` 是用户演示界面。

## 数据与风险口径

报告期结束日不等于数据可用日。财务字段必须带 `period_end` 与 `filed_at`；研究系统只允许使用截止日已经披露的数据。日线风险必须使用真实日期交集，不能把不同标的的第 1 行、第 2 行机械拼在一起。共同样本不足 40 个观测时，参数压力会返回 `insufficient`。

组合压力是当前权重的风险诊断：参数情景用共同日期日收益协方差，历史情景用同一实际日期区间逐日应用当前权重并复合，不模拟调仓成本或成交可行性。它不是校准 VaR，不是历史可交易回测，也不证明策略未来收益。

信用模块的 EL 是 `sum(EAD × stressed_PD × stressed_LGD) / sum(EAD)`；固收模块的 DV01 是收益率上移 1bp 的价格变化；这些模块用于能力训练和模型治理讨论，不是 IFRS 9、资本计量或监管审批系统。

## AI 产品岗位映射

这个项目能展示的问题拆解是：把“请分析一下这批公司”拆成数据合同、筛选门禁、组合约束、风险情景、证据展示和人工复核。可展示的产品能力包括用户流程设计、结构化工具合同、可观察 trace、失败态、LLM 权限边界、成本/时延入口、离线评测和用户数据隐私。

面试中不要只讲“我用了 Agent”。应该讲：我有意把金融数字从模型输出中拿出来，让模型只能引用已存在的 finding；如果数据缺失、日期未来、来源不明或风险样本不足，系统宁可返回 review/insufficient，也不制造完整但不可靠的答案。

## 金融岗位映射

申请风险管理/模型验证：讲 EAD 加权 EL、PD/LGD 压力、时间切分、AUC/Brier/ECE 以及“合成指标不等于真实校准”。申请金融基础设施/数据治理：讲单位、币种、`filed_at`、`price_as_of`、来源 hash、CSV 行级错误和 fail-closed。申请 ALM/固收/金融市场：讲现金流折现、duration、convexity、DV01 和利率冲击的适用边界。申请金融科技/风险产品：讲筛选→组合→压力的任务闭环、解释性 UI、人工复核和证据导出。

## STAR 叙事

**Situation：** 金融研究工具常把检索、数字计算、组合配置和叙述混在一起，用户难以判断一个候选是因为真的不符合条件，还是因为数据不足；同时，直接依赖 LLM 会带来数字、日期和引用不可审计的问题。

**Task：** 我希望做一个本地可运行、无需大模型也能完成核心研究任务的金融 Agent 产品，并让它同时能够训练 AI 产品、风险管理、数据治理和固收岗位需要的能力。

**Action：** 我设计了点时数据合同和 CSV 入口；使用固定规则做 PE、收入增长、利润率、自由现金流率和杠杆筛选；把评分定义为可解释的绝对阈值组合，不把它包装成预测概率；用长仓、单票上限和现金保留规则构建组合；用共同日期收益做参数、历史和相关性压力；将每个结论绑定到 evidence ledger；加入 MCP/LLM 的白名单、输出 schema、调用预算和发送前预览；用手算基准、本地回归测试（含 provider mock）和失败样本验收关键边界。

**Result：** 当前版本可以在本地完成“股票池→筛选→组合→压力→备忘录”的可演示闭环，也保留信用风险、固收和期权模块；不需要 LLM 或外部数据服务即可运行。当前 demo 使用合成数据，外部用户验证、真实模型效果和 live provider 联调仍未完成（适配器仅经 mock 验收），因此不能把它写成真实投资业绩、alpha、监管验证或用户增长结果。

## 当前可核验状态

| 能力 | 当前状态 | 不能宣称 |
| --- | --- | --- |
| 投资研究 | 本地 CSV/合成数据、筛选、组合、共同日期压力和 memo 已实现 | 真实证券推荐、alpha、未来收益 |
| 风险管理 | 合成贷款、PD/LGD/EAD、EL、时间切分指标 | IFRS 9、真实校准、监管审批 |
| 固收/期权 | 价格、duration、convexity、DV01、BS/MC | 实盘定价、完整 ALM |
| LLM | 可选受限路由和研究追问；默认不调用 | LLM 金融准确率、生产 Agent |
| 数据连接 | 本地授权 CSV；可选 yfinance/SEC 显式 fetch；结果带 provenance 且未独立核验 | 已连接实时数据、数据许可、独立验证 |
| 用户研究 | 协议和指标定义存在 | 外部用户、留存、节省时间 |

## 开发与验证

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
python -m finpilot research --as-of 2025-12-31
python -m finpilot eval --output /tmp/finpilot-eval.json
python -m finpilot export --output /tmp/FinPilot演示工作台.html
```

当前本地测试覆盖确定性市场/财务、回测、信用/固收/期权、MCP/LLM schema、CSV 导入、投资筛选、组合压力与 provider 的 mock 验收（延迟依赖、授权、日期边界、失败不回退和来源合同）。测试通过表示代码路径通过离线验收，不表示真实业务有效或已完成 live 联调。

## 安全与隐私

不要提交真实 API key、原始个人简历、客户数据、未公开访谈材料或私人金融 Agent 文档。不要把真实数据供应商的受限下载打包进仓库。工作台只绑定 loopback；工具调用只读、有限、显式 opt-in。

## 参考文档

- [`docs/product-v03.md`](docs/product-v03.md)：产品定位、使用场景、快速上手和功能边界
- [`docs/data-contract.md`](docs/data-contract.md)：CSV 字段、点时规则、缺失与来源标签
- [`docs/data-sources.md`](docs/data-sources.md)：离线 doctor、显式 fetch、provider 输出合同与复现边界
- [`examples/real_cases/historical_reference_snapshots.md`](examples/real_cases/historical_reference_snapshots.md)：带来源的公共历史参考快照与案例边界
- [`examples/real_cases/financial_casebook.md`](examples/real_cases/financial_casebook.md)：Apple、Microsoft、NVIDIA、WTI 财务/市场案例
- [`docs/architecture.md`](docs/architecture.md)：数据、计算、Agent 和失败策略
- [`docs/interview-playbook.md`](docs/interview-playbook.md)：AI 产品与金融岗位回答
- [`docs/interview-v03.md`](docs/interview-v03.md)：投资研究主线的演示话术与深挖问题
- [`docs/capability-map.md`](docs/capability-map.md)：岗位能力映射与 SQL/实验模板
- [`docs/resume.md`](docs/resume.md)：当前可用和条件式简历版本
- [`docs/integrations.md`](docs/integrations.md)：MCP/LLM 接入与安全边界
- [`docs/advisor.md`](docs/advisor.md)：LLM 可选增强、发送内容和模型边界
- [`docs/model-card.md`](docs/model-card.md)：数据、方法和限制

参考入口：

- [SEC EDGAR API documentation](https://www.sec.gov/edgar/sec-api-documentation)
- [Model Context Protocol specification](https://modelcontextprotocol.io/specification/latest)
- [TradingAgents](https://github.com/TauricResearch/TradingAgents)
- [OpenBB](https://github.com/OpenBB-finance/OpenBB)
- [Qlib](https://github.com/microsoft/qlib)

## License

MIT License。许可证不改变数据提供商条款、模型服务条款或使用者对金融决策的责任。
