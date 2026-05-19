# Code as Agent Harness: A Survey (2605.18747v1)

## 1. Editorial Thesis

这篇综述的核心翻转是：code 不是 agent 的产出物，而是 agent 与外部世界之间的 harness 接口。

传统认知把 code agent 看作"会写代码的 LLM"——模型输出一段代码，人或其他工具去验收。CodeAgentHarness 的编者彻底颠覆了这一关系：agent 可靠性的瓶颈不在模型生成能力，而在执行闭环的完整性。Code 之所以被选为这个闭环的媒介，不是因为它"方便生成"，而是因为它同时具备三个不可还原的属性——executable（可被外部解释器执行并验证）、inspectable（中间计算暴露为结构化 trace）、stateful（程序状态在跨步交互中持久化）。三者共同把 code 从一个终点 output 转变为循环中的状态载体。

由此，编者把 agent engineering 的核心矛盾从"如何让模型写出更好的代码"迁移到"如何设计一个可执行、可检查、可治理的运行时 substrate"。这个立场宣称：prompt engineering 的天花板已经显现，harness engineering 才是下一代 agent 系统的决定性战场。

---

## 2. Evolution Path

### 2.1 Code 是外部计算器（2022–2023）

最早的问题设定很朴素：语言模型做不好精确的数学/逻辑/符号计算怎么办？**PoT（Program-of-Thought, 2022）**提出——让模型把推理过程写成 Python，丢给外部解释器执行，再把结果拿回来继续下一步推理。**PAL（Program-Aided Language Models, 2023）**进一步把"逻辑推理"和"数值计算"解耦：模型负责高层分解，解释器负责精确执行。同期**Chain of Code（2023）**甚至尝试让模型模拟执行那些"语义上可执行但语法上不合法"的伪代码段。

这个范式填补的 gap 是纯文本 CoT（Chain-of-Thought，链式思维推理）在算术和符号推理上的高错误率。

但它遗留了一个结构性裂缝：执行是一次性的。模型生成代码、拿到结果、继续下一步——中间没有任何持久状态，模型的"下一步"和"上一步的执行"之间是断开的。Code 只是被调用的工具，不是被居住的环境。

### 2.2 Code 是行动接口（2023）

裂缝很快暴露：如果 code 只在"需要计算时"才被调用，那 agent 如何与持续运行的外部世界交互？**Code-as-Policies（CaP, 2023）**第一次把代码当作机器人的控制接口——LLM 生成的 Python 直接变成机械臂的运动策略。**Voyager（2023）**走得更远：它在 Minecraft 中运行，把每一次成功的交互代码段存入一个可增长的技能库，供后续任务复用。此时 code 不再是用完即弃的计算器，而是在环境中积累下来的可执行资产。

同期**SayCan（2022）**和**KnowNo（2023）**从另一个方向逼近：它们不直接让模型生成控制代码，而是让模型从预定义的技能库中选择可执行行为——选择的前提是每个技能都配有物理可行性估计器。这暗示了一个关键张力：模型可以生成任意代码，但环境只能执行其中一部分。Harness 的任务不是放任模型生成，而是筛选、约束、验证。

这个范式填补的 gap 是从一次性计算到与环境持续交互的跨越。

但它暴露了新的瓶颈：单代理的上下文窗口装不下大型代码库的长程推理；"跑通了测试"和"做对了"是两回事（Weak Oracle 问题）。更深层的问题是——谁来管理这个交互循环本身？谁来决定什么代码可以执行、什么不行、失败后怎么修复？

### 2.3 Harness 作为闭环控制系统（2024）

上述瓶颈倒逼出一个结构性回应：把交互循环本身工程化。**SWE-agent（2024）**是这个转折的标志。它不再只是一个在 prompt 里写代码的模型，而是一个拥有结构化 working memory、replayable shell interface、和文件系统状态追踪的完整运行时。编者明确指出：在 SWE-agent 的框架下，相同 base model 在不同 harness 设计下的 repo-level repair 性能差异巨大——这直接证明可靠性不是模型问题，而是 harness 问题。

随后**OpenHands（2024–2025）**把闭环推向完整：stateful edit-exec workspace 让 agent 在一个受控的 sandbox 里持续编辑、执行、观察 diff/log/test/approval 反馈。与此同时，**CodePRM（2025）**和**RLEF（2024）**把执行反馈从"结果对/错"提升为 reasoning trajectory 上的过程奖励信号——模型不是在最后验收时才得到反馈，而是在每一步代码执行后都得到细粒度的优化信号。

这个范式填补的 gap 是从"生成+验证"的单次模式到"Plan-Execute-Verify（PEV）"的闭环控制。

它引入的核心概念是 PEV Loop：Plan 不是简单的 todo list，而是对外部状态的预期变更 contract；Execute 必须在 sandboxed 和 permissioned 的环境中发生；Verify 通过 linter、parser、unit test、static analyzer 等 deterministic sensor 产生独立于模型判断的 ground truth。Harness 从一个被动的前后端连接器，变成了主动控制 agent 行为边界的 cybernetic governor。

但这个闭环在单代理内部走到极限后，又碰到了天花板：一个 agent 同时做规划、编码、测试、安全审计，既不高效也缺乏独立验证通道。

### 2.4 多智能体协作与共享基底（2024–2025）

回应单代理瓶颈的路径是多智能体系统（MAS, Multi-Agent System）。**ChatDev（2023）**和**MetaGPT（2024）**率先引入了软件开发中的角色分工：架构师、程序员、测试员、审查员各司其职。但这个阶段的 MAS 有一个致命缺陷——agents 之间的共享状态仅仅是"当前代码文件"或"对话历史"，没有持久、可查询的共享表示。编者将此命名为 state divergence（状态分歧）：一个 planner 基于旧 repo snapshot 做计划，coder 在更 patch 上修改，tester 验证的又是第三个版本——artifacts 在传递，assumptions 没有同步。

更新的系统开始修复这一缺陷：**L2MAC（2024）**引入 blackboard 结构共享中间状态；**Cogito（2025）**使用三层记忆体系做 hierarchical synchronization；**SyncMind（2025）**尝试 formal synchronization protocol。编者在这个阶段的批判性立场非常明确：synchronization alone does not provide transactional semantics or assumption-level consistency。

这个范式填补的 gap 是单一 agent 的 context/specialization/self-correction 三重瓶颈。

但它提出的挑战比解决的还多：多 agent 的冲突不能只靠文件 diff 检测，而需要语义级的 merge、rollback、dependency-aware locking——这些已经超出了传统版本控制的范畴。

### 2.5 Harness 本身成为研究对象（2025–2026）

当 harness 基础设施的复杂性达到一定程度后，一个元问题自然浮现：谁来设计 harness？**AutoHarness（2026）**尝试自动合成过滤无效动作的 harness 代码。**Meta-Harness（2026）**把 harness 设计形式化为一个优化问题，搜索空间覆盖 prompts、tools、scripts。**Agentic Harness Engineering（AHE, 2025–2026）**提出用 deep telemetry（记录 prompts、tool latency、permission request、test result、human intervention 等全链路轨迹）让 Evolution Agent 诊断 failures 并 propose harness 修订。

但编者随即提出了一个治理红线：AHE 不能等同于无约束的自我修改。每一次 harness mutation 必须携带 change contract——明确说明改了哪个组件、针对哪种 failure mode、预测了什么改进、必须保留哪些 invariants、用什么 evaluation 可以 falsify、以及如何 rollback。这个要求把 harness 进化纳入了和 PEV Loop 同级别的工程纪律。

编者援引 OpenAI、Anthropic、LangChain 的工业共识作为佐证：可靠的 agent 需要 explicit harness loops、tool contracts、trace replay、eval suites、context budgets——这些不是锦上添花，而是运行时的基础设施。

这个范式填补的 gap 是把 harness 从手工配置的 wrapper 提升为可测量、可优化、可演化的系统组件。

---

## 3. Structural Map

综述的五章建立在同一个递进假设之上：agent 可以先定义接口、再叠加机制、最后扩展协作——如果这个假设不成立，后续各章的论述根基都会动摇。

§2（Harness Interface）是整个叙事的压舱石。它把 code 的 roles 划分为 reasoning、acting、environment modeling——三者不是独立分类，而是同一接口的三个投影：reasoning 需要可验证的计算 substrate；acting 需要可执行的物理/数字接口；environment modeling 需要可持久化的状态载体。编者刻意不提 training 和 model capability——这不是疏忽，而是立场声明：无论模型多强，没有 harness 就无法从"会写代码的文本生成器"变成"可操作世界的 agent"。

§3（Harness Mechanisms）只有当接口属性被确认后才成为可能。Planning（如何把长程意图分解为可执行步骤）、Memory（如何在有限 context window 中管理持续膨胀的中间状态）、Tool Use（如何把外部 API/终端/沙箱接入循环）、Control（PEV Loop 如何闭环）、Optimization（AHE 如何持续改进 harness 本身）——这些机制回答的是同一个元问题：有了可执行的接口后，如何保证 agent 在长程交互中的可靠收敛？

§4（Scaling the Harness）的前提是机制层已经建立。当单代理的 context window、角色专精、自我纠错三重限制同时触顶时，多智能体不是可选优化，而是结构性必要。但编者对这一章的论述是有保留的——大量 MAS 工作仍停留在 implicit/file-only 的共享状态阶段，state divergence 问题远未解决。§4.3 实际上是编者对领域的规劝：下一代 MAS 必须建立在 transactional shared program state 之上，否则多代理不是扩展 harness，而是把单代理的不可靠性乘以 N。

---

## 4. Mechanism Deep-Dive

### 4.1 可执行性 vs 可控性 — PEV Loop 是对"放权给模型"的根本纠偏

综述中最具系统论色彩的机制是 Plan-Execute-Verify（PEV）Loop（§3.4）。它的深层意义不是"让 agent 会调试"，而是把控制权从模型手中收回给 harness。

在没有 PEV 的早期范式中，模型既是问题的提出者又是答案的评判者——它生成代码，如果出错，把 error message 塞回 prompt 再试一轮。这个模式下存在双重风险：第一，模型可能生成危险代码（如删除文件、越权访问），没有任何外部约束可以在执行前拦截；第二，模型的自我纠错依赖自身的推理能力，如果它根本不知道自己错在哪（如 silent logic error），反馈循环就是无效的。

PEV Loop 的回应是三层控制结构：
- Plan as Contract：agent 必须在执行前显式声明预期变更和验证标准——这个 contract 可被外部审计，而不只是模型内部的 CoT。
- Permissioned Execution：harness 根据风险等级分配 sandbox 权限（只读 → sandbox 编辑 → 全访问），高危操作必须走 human-in-the-loop gate。
- Deterministic Verification：测试、linter、static analyzer 提供的反馈是确定性的（与模型概率输出不同），这使得 harness 拥有独立于模型判断的 ground truth。

Code 的可执行性既是最强大的能力（能真正改变世界状态），也是最危险的能力（不可逆的错误可以真正破坏系统）。PEV Loop 不是限制可执行性，而是给可执行性装上刹车和仪表盘。

### 4.2 自动化扩展 vs 安全治理 — Harness 自进化不是自由生长，而是受控演进

§3.5 提出的 Agentic Harness Engineering（AHE）触及了一个递归性难题：如果 harness 是控制 agent 的基础设施，那么当 harness 自身需要进化时，谁来控制进化过程？

编者把这个问题分解为三个互补的研究线：
1. AutoHarness（2026）：自动合成 harness 代码——但它只能处理已知模式，无法创造全新的 harness 结构。
2. Meta-Harness（2026）：把 harness 设计形式化为参数搜索问题——搜索空间包括 prompts、tools、scripts，但搜索本身消耗巨大的计算资源。
3. AHE（2025–2026）：通过 deep telemetry 让 Evolution Agent 诊断 failures 并 propose harness 修订。

但编者随即提出了治理红线：AHE 不能等同于无约束的自我修改。每一次 harness mutation 必须携带 change contract——明确说明改了哪个组件、针对哪种 failure mode、预测了什么改进、必须保留哪些 invariants、用什么 evaluation 可以 falsify、以及如何 rollback。这个要求把 harness 进化纳入了和 PEV Loop 同级别的工程纪律。

Agent 系统的自动化程度和治理强度必须同步增长。一个能快速自我改进的 harness 如果不能同时保证 safety invariant，其进化速度本身就是风险源。

---

## 5. Open Problems & Frontiers

§5.2 列出了七个开放问题，但它们的实质性并不均等。以下按与综述核心论点的关联强度排序：

### 5.1 Harness-Level Evaluation & Oracle Adequacy（高度实质性）

编者尖锐地指出：现有 evaluation 几乎只看 end-task success（测试是否通过、问题是否解决），这把模型能力、harness 质量、工具可靠性、环境难度全部混淆了。一个 agent 可能通过了所有可见测试，但利用了 weak oracle（如测试覆盖率低、检查脚本有漏洞）；另一个 agent 可能在 GUI 任务中完成了目标，但中间执行了不安全操作。

编者呼唤的 harness-level metrics 包括：trajectory efficiency（工具调用次数、token 消耗、耗时）、verification strength（测试覆盖、oracle 多样性、false acceptance 率）、recovery ability（失败后能否诊断并修复）、state consistency（memory/repo/execution trace/belief 是否同步）。

这是编者论点（可靠性取决于 harness）的直接推论。如果无法单独测量 harness 的质量，就无法验证"harness engineering > prompt engineering"这一核心主张。

### 5.2 Transactional Shared Program State（高度实质性）

这是 §4.3 Position 的自然延伸。当前 MAS 的同步机制（sequential handoff、shared logs、file-only state）只能同步 artifacts，不能同步 assumptions。编者提出的缺失抽象是 transaction semantics：每个 agent action 应声明 read set、write set、assumptions、version dependencies、verifier obligations；冲突应在 plan、test、evidence、permission、memory entry 的语义层面被检测和解决。

如果这个问题不解决，多智能体系统不是"多个专家协作"，而是"多个盲人各自摸象后互相传递错误信息"。编者的立场是：这是下一代 MAS 从"demo 级"走向"工业级"的临界点。

### 5.3 Semantic Verification Beyond Executable Feedback（高度实质性）

执行反馈会制造"虚假正确感"：green test ≠ full specification。编者提出需要多层验证 artifact（unit test、property-based test、fuzzer、static analyzer、formal spec、human review），每层都应显式声明验证范围和置信度。一个被接受的动作应携带 evidence bundle——包含运行了哪些检查、保留了哪些假设、哪些区域仍然未经测试、剩余风险是什么。

这直接关系到 PEV Loop 的可靠性。如果 verifier 是 weak signal，agent 会在训练中优化到错误的目标——正如 RL 中 reward hacking 的机制。

### 5.4 Self-Evolving Harnesses without Regression（高度实质性）

编者区分了"能不能自动进化 harness"（已有 AutoHarness/Meta-Harness/AHE 证明可以）和"能不能安全地自动进化"（尚未解决）。核心挑战：改进可能带来隐性回归（如新检索策略提升 benchmark accuracy 但增加 hallucinated evidence；新 verifier 提高 pass rate 但接受 underspecified solutions）。

对应可操作性建议：定义 harness mutation operator、建立 telemetry 标准、用 held-out regression suites 做评估、在进化中强制 safety invariants、用 canary deployment 和 rollback semantics。

### 5.5–5.7 Human-in-the-Loop Safety、Multimodal Harness、Science of Harness Engineering

这三个问题的实质性稍弱。
- HITL Safety（中等）：提出了 valuable 的框架（multi-tier permission model、auditable state transitions），但更像是工程实践指南而非未解的研究问题。
- Multimodal Harness（中等）：论述扎实（GUI/embodied/scientific agent 需要视觉/触觉/物理状态的持久表示），但更多是横向扩展而非纵深的结构性裂缝。
- Science of Harness Engineering（偏礼貌性）："需要 benchmark、telemetry、metrics、design principles"——这是正确的但略显笼统的号召。

---

## 6. Brainstorm Q&A

### Q1：code-as-harness 和 code-as-output 的本质区别是什么？

传统 view 把 code agent 看作 LLM 写代码 + 外部工具验收。Harness view 则认为代码是循环中的状态载体——它被执行、被检查、被修订、被持久化，跨越多个交互步。

关键差异不在"写得好不好"，而在"写了之后发生了什么"。没有 harness，代码只是文本；有了 harness，每一次代码生成都是一次可控的状态转移 attempt——harness 决定它是否被执行、在哪个 sandbox 中执行、执行结果如何被验证、验证失败如何被反馈。这个翻转把 agent 的可靠性从模型的单点 accuracy 转移到了系统的闭环稳定性上（§2, §3.4）。

### Q2：为什么从"一次性计算"（PoT/PAL）走向"持续交互"（Voyager/CaP）是必然的？

PoT 解决的是 LLM 在数学计算上的不可靠，它的执行是 stateless 的：模型生成代码、拿到结果、继续下一步——中间没有持久状态。但当 agent 需要操作文件系统、控制机器人、修改代码库时，"下一步"必须依赖"上一步执行后的世界状态"。

Voyager 在 Minecraft 中的技能库存储和 CaP 在机器人控制中的代码即策略，本质上都是在修复 PoT 的同一个结构性裂缝：code 不能只是被调用的 calculator，必须是能持续改变和读取环境状态的 interface。这个转移不是技术升级，而是问题定义的根本扩展——从"LLM 怎么算对一道数学题"变成了"LLM 怎么在一个开放环境中持续做对一系列事"（§2.1→§2.2）。

### Q3：Voyager 的技能库积累和 SWE-agent 的 harness 工程有什么本质差异？

Voyager 的可复用技能库确实是 harness 思想的雏形——它让 code 在环境中积累了下来，供后续任务使用。但这个积累是**被动**的：成功执行的代码段被存起来，失败了就丢弃，没有显式的验证、回滚、或审计机制。

SWE-agent 的 harness 工程是**主动控制**：它引入了 replayable shell interface、working memory 结构、和文件系统状态追踪，把交互循环本身变成了可测量、可调试、可约束的系统。Voyager 问的是"我们能不能记住成功的代码"；SWE-agent 问的是"我们能不能保证每一次交互都在受控范围内收敛"。前者是可复用资产的积累，后者是闭环可靠性的工程化（§2.2→§2.3）。

### Q4：PEV Loop 与 ReAct 的 think-act-observe 循环有何本质差异？

ReAct 是模型层面的推理模式：模型自己想、自己调工具、自己看结果——控制权完全在模型。PEV Loop 是系统层面的控制架构：Plan 是显式 contract（可被外部审计），Execute 在 sandboxed/permissioned 环境中发生（harness 可拦截越权行为），Verify 通过 deterministic sensor 产生信号（不依赖模型的自我评估）。

本质差异：ReAct 对模型的信任是隐性的、无条件的；PEV 对模型的信任是显性的、分级的。当 agent 开始编辑生产级代码库时，这个差异从"设计偏好"变成"安全底线"。相同 base model 在 SWE-agent harness 下的 repo-level repair 性能显著高于裸 ReAct，这证明了控制权转移带来的可靠性增益不来自模型，而来自 harness（§3.4）。

### Q5：单代理的什么瓶颈迫使多智能体成为结构性必需？

三个同时触顶的瓶颈：
1. Context Window：一个 agent 装不下大型 repo 的全局上下文 + 细粒度实现细节 + 测试验证信息。
2. Specialization：让同一个模型同时扮演架构师、程序员、测试员、审查员，等于要求一个大脑同时维持四种互斥的认知模式。
3. Self-Correction：agent 审查自己的代码时，既当被告又当法官——缺乏独立的验证通道。

ChatDev 和 MetaGPT 引入角色分工不是为了拟人，而是为了把这三个瓶颈从单个 agent 迁移到多个 agent 的协作架构中。但编者同时警告：如果多 agent 之间的共享状态没有超越文件级的语义同步，分工只是把单点的不可靠性拆成了多份的不可靠性（§4）。

### Q6：state divergence 的本质是什么？为什么文件级同步不够？

State divergence 不是"多个 agent 改了同一个文件所以冲突了"，而是"agents 在各自心智模型中对外部世界的假设已经不同步了"。

举例：planner 基于旧的 repo snapshot 制定了一个重构计划；coder 在执行时面对的是已经被另一个 agent patch 过的新版本；tester 验证的又是第三个状态。即使三者最终看到的 artifact（代码文件）是相同的，他们的 assumptions（哪些模块是稳定的、哪些接口契约是有效的）已经分叉。

文件级同步（git diff、shared logs）只能检测到 syntactic 冲突，无法检测到 semantic assumption 的不一致。编者提出的 transactional shared program state 要求在 plan、evidence、permission、memory entry 的语义层面声明 read/write sets 和版本依赖——这已经超出了传统版本控制的范畴（§4.3, §5.2）。

### Q7：AHE 的自我进化为什么必须伴随 change contract 和 safety invariant？

AutoHarness 和 Meta-Harness 证明了 harness 可以自动合成和优化，但它们没有回答"谁来保证进化过程本身是安全的"。AHE 的递归性风险在于：如果 harness 是控制 agent 行为的基础设施，那么 harness 的自我修改就是"基础设施修改自己的规则"——没有外部约束时，改进可能带来隐性回归（如新检索策略提升 benchmark accuracy 但增加 hallucinated evidence）。

Change contract（声明改了什么、针对什么 failure mode、预测了什么改进、如何 rollback）和 safety invariant（在进化中不可违背的底线约束）把 harness 的自我进化从"自由生长"转变为"受控演进"。这个要求和 PEV Loop 的 governance 逻辑是一致的：PEV 防止 agent 执行危险代码，change contract 防止 harness 自身产生危险的自我修改（§3.5, §5.4）。

### Q8：综述在大面积讨论 harness engineering 的同时，几乎不谈 model capability 的 hard boundary。这意味着什么？

编者的沉默是一个刻意的 framing 选择。既然核心论点是"可靠性取决于 harness 而非模型"，那么 model capability 就被设定为先验条件——"假设模型足够好，我们怎么通过 harness 把它的能力安全可靠地兑现"。

但这个假设在真实场景中并不总是成立。在某些长尾推理任务上，即使给最完善的 harness，当前模型也难以生成正确的初始 plan。如果把全部研究资源倾斜到 harness engineering，可能忽略了一个并行的关键问题：什么级别的模型能力是 harness 能够"补救"的上限？当模型连基本的 problem decomposition 都做不对时，再完善的 PEV Loop 也只能在错误的地基上迭代。

综述通过 exclusion 把这个张力隐藏了——这是读者在接受其 taxonomy 时必须保持警觉的地方。Harness 不能替代模型能力，它只能在模型能力可触及的范围内做放大和兜底（§1, §5 各处）。
