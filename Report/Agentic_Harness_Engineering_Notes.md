# Agentic Harness Engineering (AHE) — Notes

> **Paper**: Agentic Harness Engineering: Observability-Driven Automatic Evolution of Coding-Agent Harnesses  
> **Authors**: Jiahang Lin, Shichun Liu, Chengjun Pan, Lizhi Lin, Shihan Dou, Zhiheng Xi, Xuanjing Huang, Hang Yan, Zhenhua Han, Tao Gui, Yu-Gang Jiang  
> **arXiv**: 2604.25850v4  
> **Mode**: Research Paper Mode

---

## 1. The One-Liner

Coding-agent harness 的自动进化瓶颈不在 agent 智能，而在 **可观测性（observability）**：只有把 harness 解耦为文件级可编辑组件、把百万 token 的原始轨迹蒸馏为可钻取的分层证据、并把每次 edit 绑定为下一轮可验证的预测合同，进化才能稳定收敛，而非沦为不可归因的试错。

---

## 2. Why Now?

Coding agent 在长程软件工程任务上的进展不仅取决于 base model，更取决于环绕它的 **harness**（系统提示+工具+中间件+记忆等可编辑组件的集合）。base model 迭代越来越快，手动适配 harness 成为瓶颈。已有自动优化方法（ACE、Training-Free GRPO）只改 prompt 或强化成功轨迹序列，**未触及 tools / middleware / memory 等承载真正协调逻辑的层**。

_joint evolution_ 面临两道结构性障碍：
1. 原始轨迹动辄数百万 token，有效信号被淹没；
2. 现有 harness 框架将组件紧密耦合，改 prompt 可能连带改工具描述，导致失败模式不可定位。

**作者的 unique angle**：别人把问题当成「agent 不够聪明、需要更强优化器」，作者发现真正卡壳的是 **observability gap** —— 只要进化 agent 能获得结构化的上下文与清晰的 action space，它就能可靠收敛。

---

## 3. The Turn

AHE 通过三个可观测性支柱把 harness 优化变成一个无人值守的闭环（Algorithm 1），base model 全程冻结。

### 3.1 Component Observability — NexAU 解耦基底

NexAU 框架将 harness 拆为 **7 种正交文件级组件**：system prompt、tool description、tool implementation、middleware、skill、sub-agent config、long-term memory。松散耦合意味着新增 middleware 无需碰 prompt，新增 skill 无需碰 tool。

关键设计是 **H₀ 最小种子** —— 仅给一个 shell-execution tool，无 middleware / skill / memory。这强制后续每个新增组件都必须靠 measured rollout 证明显值，否则即被回滚。

### 3.2 Experience Observability — Agent Debugger 分层蒸馏

Agent Debugger 将原始 rollout（~10M tokens）蒸馏为分层证据语料：
- per-task root-cause analysis report
- benchmark-level overview（~10K tokens）

原始 trace 以文件形式保留，支持 **progressive disclosure** —— agent 在需要时逐层下钻验证。

### 3.3 Decision Observability — 可审计、可回滚的 Edit

Evolve Agent 的每次 edit 附带一份 **change manifest entry**，记录：
- 失败证据
- 推断根因
- 目标修复
- 预测影响（预期修复集 + 风险回归集）

下一轮 **attribute** 将预测集与 observed task-level delta 求交，产生 per-edit verdict。无效 edit 在下一轮被回滚到文件粒度。

两个硬约束确保可信归因：
1. **Controllability**：evolve agent 只能写 harness workspace，verifier / tracer / LLM config 只读，seed prompt 不可删；
2. **Evidence-driven**：无预测的 edit 不被接受。

---

## 4. Results at a Glance

| 关键数字 | 解读 |
|---|---|
| **Terminal-Bench 2: 69.7% → 77.0%** | 10 次迭代超越人工设计的 Codex (71.9%) 与自进化基线 ACE (68.9%)、TF-GRPO (72.3%)。 |
| **SWE-bench-verified: 75.6%** | 不重新进化直接迁移，aggregate success 最高，且 token 仅 461k（比 seed 少用 12%，比 ACE 少用 32%）。 |
| **Cross-model +10.1 pp** | deepseek-v4-flash 上增益最大。作者解释：离饱和越远的 base 越依赖 AHE 固化的协调模式。 |
| **Table 3 单组件 ablation** | memory only +5.6 pp（Hard 上甚至优于 full AHE），tool only +3.3 pp，middleware only +2.2 pp；唯独 system_prompt only **−2.3 pp**。说明 harness 的结构层（工具/中间件/记忆）可跨任务/模型迁移，而 prompt 层面的 prose-level 策略不可迁移。 |
| **Fix precision 33.7% vs Regression precision 11.8%** | Fix 预测是随机基线的 5×，证明 edit 确实落在真实目标上；Regression 预测仅 2× 随机基线，意味着 agent 能 justify 为什么 edit 会帮助，但无法 foresee 哪些任务会被破坏。 |

---

## 5. What Remains

- **组件间的非加性交互**（§4.4.1）：三个正单组件增益之和 +11.1 pp 超过 full AHE 的 +7.3 pp，且 memory-only 在 Hard 上优于 full AHE。这说明有效 edit 堆叠时存在冗余抵消，但当前 evolve agent 以 Medium 任务为主导优化，未做 interaction-aware 规划。

- **回归预测盲区**（§4.4.2）：~89% 的 upcoming regressions 未被预见。rollback 只能事后补救，无法事前防御。作者将此列为「未来自进化循环最清晰的方向」。

- **Timeout-budget 耦合**：evolution 在 GPT-5.4 high 的 per-task timeout 和 step budget 下拟合，transfer 到 xhigh reasoning tier 时非单调（+2.3 pp），因为更多 trial 超时而被判失败。

---

## 6. Critical Audit

### A. Hard 层级劣势归因的替代解释未被排除

作者将 AHE 在 Hard（30 tasks）略输 Codex（53.3% vs 56.7%）归因于「组件间干扰」，并以「memory-only swap into NexAU₀ 在 Hard 上 surpasses Codex」作为支撑（§4.2, §4.4.1）。

但该验证的逻辑是测试 memory 的独立效果，而非在全 AHE 中系统性地 ablate 掉被指控的干扰源。Table 3 显示 middleware-only 在 Hard 上为 50.0%，而 full AHE 为 53.3% —— full AHE 实际上并未被 middleware 拖累。Hard 仅 30 个样本，2–3 个任务波动即可造成百分比上的可见差距，作者未汇报显著性检验或置信区间，「干扰」解释可能只是小样本噪声的 post-hoc narrative。

### B. 并发 Edit 归因的因果链缺口

Algorithm 1 第 6–7 行：
\[ V_t \leftarrow \text{ATTRIBUTE}(C_{t-1}, T_{t-1}, T_t) \]

论文声称「each edit becomes falsifiable by the next evaluation」，但归因机制是「将 predicted-fix / predicted-regression 集合与 observed task-level deltas 求交」。当单次迭代提交多个 manifest entries 时，它们的 predicted impact 集合必然重叠，而论文**未讨论如何处理并发 edit 的归因混淆**。这导致 edit 贡献可能被系统性地高估或低估，「可证伪合同」的归因精度存在结构性缺口。

### C. Cross-model Transfer 的 Timeout-budget 替代假设

作者将 cross-family 增益优势（deepseek +10.1 pp > GPT-5.4 xhigh +2.3 pp）归因于「离饱和越远越依赖固化协调模式」。但 GPT-5.4 xhigh 的低迷增益同时被归因于「timeout-budget 耦合」（xhigh 推理更慢，更多 trial 超时）。

如果 timeout-budget 耦合足以抹平 within-family 的饱和度差异，那么它同样可能**结构性放大** cross-family 增益：deepseek-v4-flash 与 GPT-5.4 high 在推理速度/开销上的差异可能导致 deepseek 在固定 timeout 下获得相对更多的有效 step，而非纯粹因为「协调模式泛化」。作者未控制不同 model 的 per-step latency，也未报告各 model 的 timeout 触发率。

---

## 7. Brainstorm Q&A

### Q1: Table 3 中 memory-only 在 Easy 上从 seed 的 87.5% 暴跌至 50.0%（−37.5 pp），但 full AHE 在 Easy 上保持 100%。是什么抵消了 memory 在简单任务上的毒性？

> **结论**：是 middleware 的 finish-hook 与 tool 的 publish-state guard 共同填补了 memory 的过度验证开销。  
> **锚点**：§4.4.1。

作者指出 memory 在 Easy 上引入「superfluous re-verification」，而 middleware-only 在 Easy 上获得 100.0%（Table 3）。这说明 middleware 的单 evaluator-isomorphic closure check 恰好覆盖了 Easy 任务所需的验证，而 memory 的 12 条边界 lessons（性能边际、排队超限取消等）对 4 个简单任务纯属冗余。full AHE 通过 middleware 和 tool 的强制执行来「矮化」memory 的干预，使其不介入简单路径。这也反向说明：若仅把 AHE 的组件视为「additive 增益堆叠」，会误判 memory 的价值。

### Q2: 论文将 AHE 定位为「model-side training 的互补轴」，但如果 base model 持续 Scaling，harness-level evolution 的收益是否会收敛到零？

> **结论**：存在结构性分工上限，不会收敛到零，但收益分布会迁移。  
> **锚点**：§4.3 cross-model。

GPT-5.4 high 上 +7.3 pp，xhigh 仅 +2.3 pp，而 deepseek（更远离饱和）+10.1 pp。这意味着 **harness 收益与 base model 的「协调重推导能力」成反比**。当 base model 足够强，它能在 prompt 内实时重推导出 AHE 固化的协调模式（如 publish guard、closure check），此时 harness 的结构层收益被压缩。

但 prompt 层面的 prose-level 策略已被证明不可迁移（system_prompt only −2.3 pp），因此即便模型变强，**可执行的结构（工具/中间件/记忆）仍承担「跨模型复用」的角色**，只是收益从「提升 pass@1」转向「降低 token 开销」—— SWE-bench-verified 上 AHE 比 seed 少用 12% token 即是信号。

### Q3: Decision Observability 声称把每次 edit 变成「可证伪合同」，但 regression recall 仅 11.1%（~89% 回归未被预见）。这是否意味着该机制实质上是「fix-only 正向选择」，而非真正的 falsification？

> **结论**：是的，「合同」的约束力被过度声称，当前机制更接近于 **有监督的正向筛选** 而非 Popper 意义上的 falsification。  
> **锚点**：§3.3 与 §4.4.2。

Fix precision 33.7%（5× 随机基线）证明 edit 确实落在真实靶点上，但 regression precision 11.8% 仅 2× 随机基线，说明 agent **能 justify 为何 edit 会帮助，却无法 foresee 哪些任务会被破坏**。真正的 falsification 要求预测既能被证实也能被证伪；当回归预测几乎等同于随机猜测时，rollback 只能作为事后纠错，而不能作为事前防御。

Algorithm 1 第 7 行的 `ROLLBACK` 只在观察到负向 delta 后才触发，这意味着 loop 在每一步都承受「不可预见的破坏」风险。作者坦诚这一点是「clearest direction for future work」，但用语中仍保留「each edit becomes a falsifiable contract」，这在修辞上弱化了机制的实际不对称性。

---