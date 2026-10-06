# FinPilot

FinPilot 是一个**证据优先的金融风险研究工作台原型**。它把点时可见性、单位口径、确定性计算、证据引用、风险闸门和可复现运行记录放在一条可审计链路上。它的目标不是替研究员或风险人员给出交易答案，而是让每一个可复核的结论都能回答：

1. 这条数据在什么时间点已经可见？
2. 数字使用了什么公式、单位和假设？
3. 叙述或结论由哪些证据支持？
4. 在什么情况下系统应该停止并交给人复核？

> 当前项目是离线、合成数据、教育用途的原型。它不是投资建议、生产风控审批系统、交易执行系统、监管模型或商业部署。

## 当前状态：先说清楚已实现与未实现

仓库当前的可信边界如下。**“已测试”只表示仓库中存在对应代码和本地测试，不表示真实业务有效、模型校准或用户认可。**

| 范围 | 当前可核验状态 | 不应据此宣称 |
| --- | --- | --- |
| `data.py` | 固定种子合成 fixture；保留 `effective_at`、`filed_at`、`raw_ref`、单位和来源定位；按 `as_of` 过滤 | 真实 SEC、Yahoo 或其他市场数据 |
| `analytics.py` | 市场特征、财务特征、风险快照和描述性综合分数有确定性代码与单元测试 | alpha、投资建议、经过校准的风险概率 |
| `backtest.py` | 明确的信号日→下一收盘执行模型、交易成本、基准、泄漏检查和小样本测试 | 回测证明 alpha、可交易收益或未来表现 |
| `risk.py` | 合成贷款损失、时间切分的分类指标、债券价格/久期/凸性/DV01、Black–Scholes 和可选种子化 Monte Carlo 有代码与测试 | IFRS 9、监管资本、真实校准、定价意见或审批结论 |
| `pipeline.py` / `agents.py` / `risk.py` | 离线 fixture、确定性分析、证据台账、信用压力、固收/期权工具、风险标记和 trace；有 31 项本地测试 | 已接入实时数据、完整策略引擎、监管模型或生产服务 |
| `ui.py` / `server.py` / `workbench.html` | 可导出独立工作台；本机只读服务提供研究、信用、固收、评测、面试训练和工程边界页 | 已上线的公网 Web 产品或外部用户验证 |
| MCP / LLM / Agent | 有受限 MCP stdio、OpenAI-compatible 客户端和两次调用的工具选择路径；默认仍离线、不连真实服务 | 已安装 MCP、已访问 live data、已完成真实模型质量评测 |
| evaluation / 用户研究 | 24 项离线验收覆盖哈希、点时、数字一致性、负例和手算基准；有访谈协议但尚无外部用户与线上指标 | 已有真实准确率、留存、节省时间、付费或用户验证结果 |

项目借鉴 TradingAgents、OpenBB、Qlib 的公开设计问题，但不依赖它们，也没有抄写其代码。参考过不等于安装过或接通过。

## 为什么做 FinPilot

金融研究工具通常把资料检索、数字计算和叙述生成混在一起，容易出现四类错误：

- 将报告期、披露日和系统可见日混为一谈；
- 将未知单位直接当成可比较的数值；
- 让模型生成或改写数字算术；
- 在回测中用生成信号的同一根 bar 执行交易。

FinPilot 的相反顺序是：**先执行有边界的确定性规则，再让可选的 LLM 处理受限的解释任务；遇到未知单位、未来信息、证据缺失或结构不兼容时 fail-closed。** 数字算术、点时过滤、风险闸门和安全决策不交给 LLM。

项目同时服务两条求职主线：

- **AI 产品线**：把访谈、PRD、埋点 SQL、冻结评测、RAG/agent 工具、成本、安全和跨团队协作变成可验收证据；
- **金融岗位线**：只写已核实的四类岗位族——风险管理/模型验证、金融基础设施/数据治理、ALM/固收/金融市场、金融科技/风险产品。

简历和面试材料会把“代码中已有”“本人已手算验收”“规划中”分开。AI 辅助开发不自动等于本人掌握：只有完成手算、改参数、阅读失败例并留下记录后，才可以使用强化版表述。

## 快速开始

环境要求为 Python 3.10 或更高版本。默认运行路径依赖项目声明的 `numpy` 和 `pandas`，测试使用 Python 标准库 `unittest`。在仓库根目录执行：

```bash
python -m pip install -e .
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
python -m finpilot demo --ticker AAPL --as-of 2025-12-31 --output reports/demo
python -m finpilot eval --output /tmp/finpilot-eval.json
python -m finpilot export --output /tmp/FinPilot演示工作台.html
python -m finpilot agent --question '请分析信用压力下的预期损失和久期风险'
```

`AAPL` 和 `MSFT` 只是兼容 CLI 的输入；fixture 返回的观察值始终标记为内部 `DEMO`，并明确写明是 synthetic。它们不会变成真实证券数据。

一次 demo 会写出 JSON 运行记录和 Markdown 研究备忘录。复核入口包括：

- `source` / `source_locator`：来源与定位；
- `raw_ref`：对原始记录的确定性哈希引用；
- `effective_at` / `filed_at`：可见时间与披露时间；
- `formula_refs`：派生数字所使用的公式说明；
- `evidence_ids` / `evidence_ledger`：叙述 claim 的证据链接；
- `trace`：确定性研究图的节点状态。

这些字段描述合成 fixture，不是 AAPL 的真实市场或财务数据。

## 现有代码路径

```text
FixtureProvider.load(ticker, as_of)
        ↓
frames(observations)
        ↓
market_features + fundamental_features
        ↓
risk_snapshot + composite_score
        ↓
run_momentum_backtest + leakage_check
        ↓
run_research_graph（证据 claim、skeptic flags、trace）
        ↓
run_fixture → JSON / Markdown memo
```

关键约束：

- fixture 使用固定种子，数据先生成完整 corpus，再按截止日过滤；改变 `as_of` 不会改变过去行的数值；
- 市场数据按 `effective_at <= as_of`，财务数据按 `filed_at <= as_of`；
- 市场回测在收盘产生信号，下一收盘执行，新仓位从执行后的下一段收益开始计入；
- Sharpe 使用日收益的算术平均/样本标准差并乘以 `sqrt(252)`，风险自由利率为 0 的教育性假设；
- 信用损失使用 `sum(EAD × PD × LGD) / sum(EAD)`，不是简单平均 PD；
- 未知单位、日期无效、证据缺失、未来观察或不兼容输出应进入 `review`、`blocked` 或 `insufficient_data`，而不是猜测。

### 连接器与服务路径

`integrations.py`、`evaluation.py`、`runtime.py` 和 `server.py` 已实现并有离线测试。`python -m finpilot eval` 运行的是确定性验收，不是模型 benchmark；`python -m finpilot serve` 只绑定 `127.0.0.1`，默认使用合成 fixture。MCP client 与 LLM client 是显式 opt-in 的安全边界，真实 SEC/Yahoo MCP、真实模型和数据条款仍需单独审查、安装、映射和联调。`python -m finpilot agent --question '信用压力下的预期损失'` 默认使用离线规则路由；只有明确传 `--live-model` 且配置本地/远程 endpoint 才会发模型请求。

`risk.py` 的实验函数与 `run_fixture` 主链路已经连接：默认 demo 包含信用压力、固收和期权工具结果；`--no-risk-lab` 可在只需要研究回放时关闭信用组合。

## fail-closed 原则

FinPilot 不以“尽可能给一个答案”为成功标准。以下任一情况都应停止或降级：

- 单位未知、币种不明，或百分比/小数含义无法确认；
- `effective_at`、`filed_at`、`as_of` 无法解析，或观察值在截止日之后；
- 工具返回字段缺失、类型不兼容、来源不可追溯；
- claim 没有 evidence ID，或 LLM 输出没有通过结构校验；
- 回测执行日不严格晚于信号日；
- 结果需要用缺失值填补、隐式重命名或模型猜测才能成立。

fail-closed 的代价是更频繁地要求人工复核；这比在金融语境中制造虚假的确定性更可接受。

## 面试与求职使用边界

推荐把项目讲成“证据优先的金融 AI 产品工程问题”，不要讲成“会选股的机器人”。

- **90 秒**：讲问题、约束、确定性核心、point-in-time 和当前未验证边界；
- **5 分钟**：展开单位口径、回测滞后、fail-closed、证据台账、成本安全和验证计划；
- **深挖**：能手算一个收益/损失/债券价格例子，解释为什么回测不是 alpha 证明，并展示一次改参数或失败例复盘。

若项目使用 AI 辅助开发，基础版简历应明确说明辅助事实，不把未完成的用户访谈、团队领导、商业部署、真实模型结果或外部连接器写成已完成。强化版只有在本人完成验收日志后才能启用。

详细回答、金融算例、14 天证据练习和实验日志见 [`docs/interview-playbook.md`](docs/interview-playbook.md)。岗位族映射见 [`docs/capability-map.md`](docs/capability-map.md)，当前与条件式简历版本见 [`docs/resume.md`](docs/resume.md)。

## 产品与验证边界

当前没有外部用户、没有商业部署、没有真实 live data、没有真实 model key，也没有已验证的留存、准确率、节省时间、收入或付费指标。`docs/user-validation.md` 提供的是**拟执行**的访谈协议、事件字典、指标定义和 SQL 草案，不是已完成研究。

任何实验日志必须至少记录：日期、代码版本、输入 manifest、参数、预期、手算结果、程序结果、差异、失败样本、本人结论和下一步。没有日志就不要把数字写入简历或面试答案。

## 安全与隐私

禁止将以下内容提交到公开仓库：

- 真实模型 key、浏览器凭据和个人访问令牌；
- 原始个人简历、客户数据、未公开访谈记录；
- 私有的 `金融agent.docx` 或其摘录、截图、链接；
- 未经授权的 SEC/Yahoo 原始下载和供应商受限数据。

本项目文档不引用、不上传私有金融 agent 文档。外部模型路径未来只能收到经批准的合成或公开摘要；工具必须是只读白名单，并限制调用次数、返回大小和 token 数，不得授予 LLM 任意 shell、SQL 或网络执行权。

安全问题不要在公开 issue 中粘贴密钥、个人信息或客户材料；请使用维护者的私下安全渠道。普通 bug 和功能建议使用 `.github/ISSUE_TEMPLATE/` 模板。

## 参考入口

以下链接只是公开协议或项目设计的核验入口，不是 FinPilot 的依赖声明，也不保证数据条款、许可或效果：

- SEC EDGAR API 文档：<https://www.sec.gov/edgar/sec-api-documentation>
- Model Context Protocol 规范：<https://modelcontextprotocol.io/specification/latest>
- TradingAgents 公开仓库：<https://github.com/TauricResearch/TradingAgents>
- OpenBB 公开仓库：<https://github.com/OpenBB-finance/OpenBB>
- Qlib 公开仓库：<https://github.com/microsoft/qlib>

## 许可证

项目使用 MIT License，详见 [`LICENSE`](LICENSE)。许可证不改变数据提供商条款、模型服务条款或使用者对金融决策的责任。

更多产品、架构、发布和模型边界说明见：

- [`docs/product.md`](docs/product.md)
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/publish.md`](docs/publish.md)
- [`docs/model-card.md`](docs/model-card.md)
