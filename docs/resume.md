# Resume language for FinPilot

## Current accurate version

Use this version before personal acceptance is complete:

**FinPilot｜证据优先的金融风险与研究工作台｜个人项目**

- 设计并实现离线优先的金融研究流程，将带 `filed_at/effective_at` 的数据观察、公式化金融计算、point-in-time 检查、证据账本和可复现运行记录串联；默认使用固定种子的合成数据，不宣称真实证券数据或投资结果。
- 构建确定性计算模块，覆盖市场特征、EAD 加权 PD/LGD/EAD 预期损失、压力情景、债券久期/凸性/DV01、Black–Scholes 与种子化 Monte Carlo；通过独立手算基准和离线单元测试核对边界条件。
- 设计可观察的金融 Agent 状态机，将数据审阅、基本面/市场分析、风险审查、质疑和证据化写作分离；模型若接入仅可引用既有 evidence ID，不能修改数值、替代时间门禁或执行任意代码。
- 通过明确的下一时点执行、交易成本、基准、泄漏检查和严格 JSON 输出构建可复现 demo；AI 辅助搭建代码，个人负责需求拆解、公式核对、参数修改、失败案例复核和发布边界。

## Conditional stronger version

Only use after you personally complete the corresponding run log, hand calculation, failure review and peer/user review:

- 在 [实际验证日期] 完成 [n] 个冻结案例验收，引用覆盖率为 [x]、结构化输出通过率为 [x]、未知单位/未来财报注入均进入 review；这些是离线评测结果，不是外部用户效果。
- 与 [受访角色/人数] 完成去标识任务访谈和 [n] 次 UAT，观察到 [准确、可核实的结果]；原始材料不进入公开仓库。

Do not fill the brackets from planning assumptions. Do not claim a user study, live model, real data, production deployment, alpha, regulatory validation or cross-functional leadership without evidence.

## Interview one-line version

我把金融 Agent 设计成“确定性计算 + 证据账本 + 受限解释”的工作台：模型可以帮助组织研究，但不能替代财务算术、点时校验和风险门禁。

## Finance-specific variants

For risk/model validation applications, emphasize the synthetic chronological split, EAD-weighted expected loss, AUC/Brier/ECE definitions and caveats. For data governance roles, emphasize source lineage, units, filed/effective dates, raw hashes and fail-closed behavior. For ALM/fixed-income roles, emphasize cash-flow discounting, duration/convexity/DV01 and shock approximation. For fintech/risk product roles, emphasize review states, user tasks, evidence UX and acceptance tests.
