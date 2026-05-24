# CODA: Rewriting Transformer Blocks as GEMM-Epilogue Programs — Notes

> **Paper**: CODA: Rewriting Transformer Blocks as GEMM-Epilogue Programs  
> **Authors**: Han Guo, Jack Zhang, Arjun Menon, Driss Guessous, Vijay Thakkar, Yoon Kim, Tri Dao  
> **arXiv**: 2605.19269v1  
> **Mode**: Research Paper Mode

---

## 1. The One-Liner

Transformer 训练中 norm、activation、residual 等非 GEMM 操作是内存带宽瓶颈而非计算瓶颈；将这些操作通过**代数重参数化**嵌入 GEMM 的 tile-local epilogue，可在不牺牲 GEMM 主循环优化的情况下，用寄存器级计算消除对 global memory 的额外 round-trip。

---

## 2. Why Now?

LLM training 的核心算子——矩阵乘和 attention——已经被 Tensor Core 高度优化，但环绕它们的 normalization、activation、residual update、reduction 等操作**移动张量多、计算少**，在 BF16/FP8 场景下成为越来越突出的瓶颈（Figure 1）。

现有编程模型在这个问题上僵住了：
- **框架层**（PyTorch / JAX）：operator boundaries 往往成为 materialization boundaries，autograd 使情况更糟；
- **手写内核**（custom CUDA）：性能好但扩展性差，backward pass 需大量工程；
- **编译器**（Triton / TileLang）：通用调优难以追平专家级 schedule。

**作者的 unique angle**：不是写更好的编译器或更好的手写内核，而是**承认 GEMM 主循环已经是天花板**，转而利用其 epilogue（输出 tile 写回 global memory 前的最后一段逻辑）作为可编程的融合接口——epilogue 天然在 on-chip 执行，tile-local 即可，无需跨 tile 通信。

---

## 3. The Turn

### 3.1 CODA 的编程模型

CODA 是一个 kernel abstraction，核心设计是 **fixed GEMM mainloop + composable epilogue primitives**。

GEMM mainloop 保持专家级优化不变，epilogue 在输出 tile 仍驻留 on-chip 时插入计算。提供的 primitive 分五类：
1. **Elementwise / pairwise maps**：residual update、SwiGLU、RoPE 等；
2. **Vector loads/stores**：行/列向量的 broadcast 与辅助输出；
3. **Tile loads/stores**：residual stream、saved activation；
4. **Tile reductions**：tile-local partial reduction（后续由轻量 auxiliary kernel 组合）；
5. **Stateful transforms**：online max / sum-exp 等 running statistics。

这个接口的关键限制是 **tile-local**：不见 global state、不做跨 tile 通信。所有超出 tile 边界的 reduction 被拆分为 tile partials + lightweight all-reduction。

### 3.2 代数重参数化的两个核心模式

**模式一：GEMM-Residual-RMSNorm-GEMM 链**

Pre-normalized Transformer 中反复出现：
\[y = \text{RMSNorm}(xW_0 + z)W_1\]

RMSNorm 的 row-wise 逆因子 r 似乎需要在两个 GEMM 之间插入一个 standalone normalization kernel。作者利用交换律将其**代数重排**：r 是行标量，与第二个 GEMM 可交换，因此可以从第一个 GEMM 的 residual 之后延迟到第二个 GEMM 的 epilogue 中应用。两次 GEMM 的 epilogue 各承担一部分 tile-local 工作，再加一个读 partials（而非全张量）的轻量 reduction。

**模式二：Pairwise Activation**

RoPE、SwiGLU 等操作消费相邻特征对。作者将特征对安排在输出维度相邻处，匹配 Hopper Tensor Core accumulator 的寄存器布局，epilogue 直接在寄存器级应用 pairwise map，无需 materialize 中间张量。

**Cross-entropy**：被写成 GEMM + epilogue-side online log-sum-exp + 轻量 auxiliary reduction，避开 standalone softmax over full logits。

### 3.3 Backward Pass 的结构保持（Theorem 1）

论文的核心理论结果：如果前向是 "GEMM → tile-local epilogue → GEMM → ..." 的链式结构，则反向传播保持完全相同的结构。前向的 epilogue 附在前一个 GEMM 的输出端，反向的 epilogue 附在后一个 GEMM 的梯度端（Figure 9）。

RMSNorm backward 中，row-wise inner product 可通过一个恒等式将计算点从 "读取 h₂ 和 ∇h₂" 迁移到 "y 与 ∇y 已同时存在的 GEMM 边界"，从而重新暴露给 epilogue fusion。

### 3.4 LLM 辅助的内核编写

CODA 的 epilogue primitives 已经编码了高效实现策略，LLM（Claude Code）只需组合这些 primitives，无需从零合成 CUDA schedule 或发现硬件调度。实验表明 LLM-generated 与 human-written 内核性能接近。

---

## 4. Results at a Glance

| 关键数字 | 解读 |
|---|---|
| **Figure 10: Forward speedup 1.0–1.3x, Backward 1.0–1.8x** | Backward 增益明显高于 forward，因为反向传播中 norm/activation 的 memory traffic 更重，epilogue fusion 的收益更大。 |
| **LLM vs Human: 几乎持平** | CODA (LLM) 与 CODA (Human) 的 kernel-level 性能差距在测量噪声范围内。这说明 epilogue primitive 的约束接口驯服了 LLM 的输出空间，无需人类手工调 schedule。 |
| **Figure 6: 数值误差低于标准 PyTorch 路径** | 延迟应用 RMSNorm scale 没有恶化精度；更精确的 GEMM mainloop（QuACK）还能进一步压低误差。为低精度训练路线（FP8/FP4）扫除了一个顾虑。 |
| **Block-level (Figure 11): 1.0–1.2x layer forward + backward** | 端到端单层收益比单 kernel 略低，因为 attention 和前后胶水代码不在 CODA 范围内。 |

---

## 5. What Remains

- **Attention 仍未被覆盖**。论文明确将 attention 排除在外，CODA 的 benefit 上限受限于 non-attention 操作在总时间中的占比。当 attention 被 flash-attention 类内核优化后，non-GEMM 的相对权重会上升，但 attention 本身不在 CODA 的射程内。
- **Cross-entropy 的 logit materialization**。Footnote 承认 "materialize logits to simplify the backward pass"，即 full logits 仍被写出到 global memory。这与全文 "避免 materialize 中间张量" 的核心主张存在张力，作者将其作为 trade-off 接受，但未量化代价。
- **Epilogue 复杂度与 compile time**。随着 epilogue primitive 的堆叠（如 residual + partial RMS + scale + SwiGLU），生成的 kernel 代码体积和编译时间如何变化？论文未涉及。
- **自动化** 停留在 LLM 辅助编写层面，尚未实现从 PyTorch operator graph 到 CODA epilogue program 的自动重参数化。

---

## 6. Critical Audit

### A. "Nearly all non-attention computation" 的边界被 materialization 削弱

论文的核心主张是 CODA 通过 epilogue fusion 避免 intermediate tensor 的 global memory round-trip。然而 §3.2.3 cross-entropy 的 footnote 明确说明 "materialize logits to simplify the backward pass"，而 §3.3 的 data movement 描述也提到 "saved intermediates" 作为 epilogue store 的目标之一。

这意味着 **并非所有中间张量都被消除了**：至少 full logits 在 cross-entropy 场景中被写出；saved activations（用于 backward）在某些 epilogue 中也被 materialize。论文用 "nearly all" 给自己留了余地，但 "nearly" 的边界没有明确划定，读者无法判断哪些操作仍会产生内存流量。

### B. Theorem 1 的 tile-local 假设在实际中被部分放宽

Theorem 1 假设 "each tile function acts only on its corresponding GEMM output tile"，从而保证 backward 不引入跨 tile 通信。但实际 RMSNorm backward 中，row-wise statistic 的累加虽然被移动到了 GEMM epilogue，却仍需要一个跨 tile 的 lightweight auxiliary reduction（Figure 4）。

这**不是 tile-local** 的：row statistic 依赖于同一行的所有 tile partials。定理的 scope 被 footnote 和 implementation detail 悄悄扩展了。作者没有在 theorem statement 中声明这个 relaxing，使 "preserves the same GEMM-with-epilogue structure" 的精确性打了折扣——实际上结构变成了 "GEMM-with-epilogue + auxiliary reduction"。

### C. Speedup 上限受 raw GEMM ceiling 约束，但实验呈现方式有误导性

Figure 10 中 CODA (LLM) 的 speedup 常以 raw GEMM（无 epilogue）作为 "upper bound" 参考线。问题是 raw GEMM 不做任何 epilogue work，因此 CODA 不可能追上它。将 raw GEMM 标为 "upper bound" 在技术上是正确的，但在视觉上把 CODA 的 bar 压缩到了一个不可能达到的天花板附近，容易让读者低估其实际价值。更公平的对比基线可能是：一个理论上完美 fused 的上限——但这在图中缺失了。

---

## 7. Brainstorm Q&A

### Q1: CODA 延迟应用 RMSNorm scale（从第一个 GEMM 后移到第二个 GEMM epilogue）改变了低精度矩阵乘中的数值路径。BAF16/FP8 下这是否安全？Figure 6 的 BF16 误差比较能推广到 FP8 吗？

> **结论**：Figure 6 仅在 BF16 上验证了相对误差低于标准路径，FP8 的数值路径安全性未被覆盖，且延迟 scale 在低精度下可能放大量化噪声。  
> **锚点**：§3.2.1 Numerics 与 Figure 6。作者使用 Llama-3 8B 层在 BF16 上做了误差比较，CODA 和 QuACK 的误差均低于 PyTorch 路径。但全文未出现 FP8 实验，而 Introduction 明确提到 "formats such as FP8 and FP4" 会进一步放大 data-movement 瓶颈。如果 CODA 要服务于下一代低精度训练，FP8 下的数值稳定性需要独立验证——尤其是 RMSNorm scale 的延迟应用改变了两个 GEMM 之间的 dynamic range。

### Q2: Theorem 1 证明了 tile-local epilogues 在 backward 中保持结构，但 weight gradient \(\nabla W_\ell = x_{\ell-1}^\top \nabla h_\ell\) 仍需要两个大矩阵的 GEMM。这个 GEMM 的输入之一（\(x_{\ell-1}\)）是中间激活，在 PyTorch 中通常需要 materialize。CODA 是否真的消除了所有中间张量 materialization，还是只是把流量从 epilogue 转移到了 weight-gradient GEMM 的输入端？

> **结论**：Theorem 1 的结构保持不等于零 materialization；CODA 的优化焦点是 epilogue-local 计算而非消除保存用于 backward 的激活张量。  
> **锚点**：§3.2.4 Backward Pass。定理只说明 backward **计算结构** 与前向对称，但 \(\nabla W_\ell\) 的 GEMM 需要 \(x_{\ell-1}\) 和 \(\nabla h_\ell\)，而 \(x_{\ell-1}\) 是前向中间结果。论文中 "saved intermediates" 被列为 epilogue store 的目标，说明激活张量**仍被保存**。CODA 消除的是 norm/activation/residual 这类**轻量操作**的 standalone kernel launch 和 round-trip，而非 weight gradient GEMM 所需的激活缓存。这是一个重要的 scope 澄清：CODA 不是 activation-checkpointing 的替代方案。

### Q3: CODA 定位在 "framework-level productivity with hardware-level efficiency" 的中间地带。从长期看，它与编译器自动融合（torch.compile / Triton）是互补还是替代？如果 Triton 未来自动发现同样的重参数化，CODA 的价值是否归零？

> **结论**：短期互补、长期取决于编译器对 Transformer-specific 代数重参数化的覆盖能力。  
> **锚点**：§2.1 Programming Models 与 §3.3.1 LLM-Oriented Authoring。

论文明确指出编译器的挑战在于 "rapidly evolving accelerators make peak performance a moving target"。CODA 的哲学是：**不搜索 schedule，也不让编译器推断 fusion**，而是把 Transformer 特有的代数知识（如 RMSNorm scale 的交换律、cross-entropy 的 LSE 分解）编码成固定的 primitive 模板，只留接口给上层。

这意味着 CODA 的价值 = "Transformer 专家知识" + "GEMM 专家 schedule" 的预组合。如果未来的编译器能自动执行同样的代数重写（如 TASO/Mirage 的扩展），CODA 的前半部分价值会被侵蚀；但只要 GEMM mainloop 的 peak performance 仍需手写专家 schedule，CODA 的后半部分（固定 mainloop + epilogue 接口）仍不可替代。一个更可能的演化路径是：CODA 的**重参数化规则**被吸收进编译器的 rewrite pass，而其**epilogue primitive 接口**成为硬件供应商的标准 kernel contract。

---