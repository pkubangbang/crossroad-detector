# Chunker v3 — 段级自适应重叠滑动窗口

> 状态：设计已确认并实现于 `trainer/chunker_v3.py`（训练侧）。
> `chunker_v2.py` 保持不动，v3 是它的后继。本文档解释 v3 的原理、与 v2 的区别、
> 以及为什么这个改动是本次重训的关键改进。

## 1. 背景：为什么需要重叠

crossroad-detector 的任务是**检测 LLM 在响应中途改变方向**（turning word /
crossroad）。检测是**事后**对完整响应做的：把整段文本切成若干**窗口
（chunk）**，每个窗口喂给 DistilBERT，问一个问题——"这段里是否正在发生
方向反转？"

窗口的边界决定了模型能看到什么。这里有一个核心矛盾：

- 一个 turn 可能恰好落在某个窗口的**边缘**。如果窗口之间没有重叠，这个
  turn 只出现在一个窗口里，且那个窗口可能只包含 turn 的一侧上下文，模型
  看不全"反转"的全貌，容易漏检。
- 如果窗口**重叠**，同一个 turn 会出现在**≥2 个相邻窗口**里，每个窗口从
  不同角度提供上下文，模型至少在一个窗口里能看到完整的反转语境。这正是
  设计文档 `plan-crossroad-distilbert-chunks.md` 一直主张的原则：

  > Windows overlap so a turn near a boundary still appears in ≥ 2 windows.

## 2. 历史脉络：v1 → v2 → v3

| 版本 | 文件 | 算法 | 是否重叠 |
|---|---|---|---|
| **v1** | `chunking.py` | 固定字符窗口 `WINDOW=128 / STRIDE=32`，75% 重叠 | ✅ 重叠 |
| **v2** | `chunker_v2.py` | 段级 tile-by-cap，`X_CHARS=448 / SEG_MAX=224`，连续铺盖 | ❌ **不重叠** |
| **v3** | `chunker_v3.py` | 段级**自适应重叠**滑动窗口，`X=224 / 2X=448 / 3X=672` | ✅ 重叠 |

- **v1** 用固定字符步长重叠，简单但窗口边界是硬切字符位置，与语义内容
  （句子/子句）无关。
- **v2** 引入了"段"（segment）概念——先按标点切子句、每段硬上限 224 字符
  ——让窗口边界**对齐语义单元**。但 v2 丢了重叠：相邻 chunk 首尾相接
  （`left = right`），变成连续铺盖（tile-by-cap）。
- **v3** 取两者之长：**保留 v2 的段级语义边界对齐**，**恢复重叠**。相邻
  chunk 共享一段前缀/后缀，turn 出现在 ≥2 个窗口里。重叠的"步长"由段长度
  自适应决定，而不是固定字符数。

## 3. 段切分（与 v2 共享，不变）

v3 复用 v2 的 `build_segments`，保证两者基于**完全相同的段格点**，这样
v3 和 v2 的差异纯粹来自"如何在这些段格点上铺窗口"，而非段定义本身。

1. **子句切分**：按句子结束标点（`.!?,;:\n` + CJK `。！？，；：`）拆分，
   分隔符**粘在前一个子句末尾**（look-behind 正则，不消耗分隔符）。
2. **段硬上限**：每个子句再按 `SEG_MAX = 224` 字符硬切（CJK 安全，不挑
   词边界）。每段 ≤ 224 字符。
3. **尾部吸收**：文档末尾分隔符之后的残留（如空白）并入最后一段，保证
   覆盖到 EOF。

结果是一组覆盖全文档的 `(start, end)` 段偏移，升序、连续、不重叠。

## 4. 核心算法：段级自适应重叠滑动窗口

### 4.1 常量

| 名 | 值 | 含义 |
|---|---|---|
| `X` | 224 | 段最大字符数（= `SEG_MAX`）；`calculateToken(2X) ≤ ctx` |
| `TWO_X` | 448 | 窗口目标上限（chunk "cap"）≈ 454 token < 512 |
| `THREE_X` | 672 | 缓冲区扩展上限（buffer expansion cap） |

`2X = 448` 字符是窗口的"目标"大小：worst-case CJK 约 1.016 tok/char，
`448 × 1.016 ≈ 454 < 512`，安全落在 DistilBERT 的 512-token 位置预算内。

### 4.2 算法步骤（伪代码）

```
segments = build_segments(text)          # 复用 v2 的段格点
if segments 为空: return []

# ---- Step 1: 初始 buffer（开头特殊处理）----
left = 0
right = 从 left 起贪婪增长: 装入尽量多连续段
       条件: segments[right].end - segments[left].start <= TWO_X (448)
# 最多再多装一个段就会超过 TWO_X
emit chunk = (segments[left].start, segments[right-1].end)   # 第一个 chunk

# ---- Step 3: 滑动循环 ----
while right < len(segments):
    # (a) 向后扩展后缀：buffer 长到 <= THREE_X (672)，再多一个就超
    while right < len(segments)
          and segments[right].end - segments[left].start <= THREE_X:
        right += 1

    # (b) 向前缩减前缀：删前缀段直到 span < TWO_X (448)【首次跌破即停】
    while (left + 1 < right)
          and segments[right-1].end - segments[left].start >= TWO_X:
        left += 1

    # (c) 当前 buffer = 下一个 chunk
    emit chunk = (segments[left].start, segments[right-1].end)

# ---- Step 4: 文档末尾（结尾特殊处理）----
# 循环因 right == EOF 退出，最后 buffer 已覆盖到末尾
final = (segments[left].start, segments[-1].end)
if final 未与前一个 chunk 完全重复: emit final
```

### 4.3 两个歧义点的处理（已与用户确认）

1. **缩减前缀的停止条件（Step 3b）**：删前缀段直到 span **首次** `< TWO_X`
   即停（取**第一个**跌破 448 的位置），**不是**继续删到"最短可能的 < 448"。
   理由：每次只删最少的前缀 → 窗口平滑前移 → **重叠最大化**。若删到最短，
   窗口会跳得太快、重叠骤减，退化为接近 v2 的非重叠铺盖。

2. **文档末尾（Step 4）**：循环结束时 `right` 已指向文档末尾段，最后
   buffer 已覆盖到 EOF。只要它的跨度没作为 chunk 输出过（避免与上一块
   完全重复），就补一块。**末尾残余块允许 < 2X**，只要它把文档剩余内容
   完整覆盖。开头同理——首块是"从 segment 0 起尽可能装入到 ≤ 2X"的初始
   buffer，短文档可能整篇就是一个 chunk。

## 5. 与 v2 的对比：重叠从何而来

v2 的滑动是 **`left = right`**——下一个 chunk 的起点 = 上一个 chunk 的
终点，**零重叠**：

```
v2:  [seg0 ───── seg2] [seg3 ───── seg5] [seg6 ─── seg8]
          chunk0          chunk1          chunk2
     (首尾相接，无共享段)
```

v3 的滑动是 **`left` 缓慢前移、`right` 缓慢前移**，两者不同步，中间留出
共享段——**有重叠**：

```
v3:  [seg0 ───── seg2]            (Step 1: 初始 buffer, ≤ 2X)
          [seg1 ───── seg4]       (Step 3: 扩到 ≤3X, 缩到 <2X)
                [seg3 ───── seg6] (继续滑)
                        [seg5 ─── seg8]  (Step 4: 末尾)
     (相邻 chunk 共享 seg1~2 / seg3~4 / seg5~6)
```

重叠量是**自适应的**：它等于"缩减前缀时跳过的段的总长度"。段长可变
（由子句长度决定），所以步长（= 2X − 重叠量）也随之变化，而不是固定
字符数。这让窗口边界**自然落在语义单元边界**，同时保证**重叠覆盖**。

## 6. 为什么这是本次重训的关键改进

本次任务的起因是"chunking 算法错误，应改为重叠 chunking"。重叠的收益
体现在三个方面：

### 6.1 边界 turn 不再漏检

非重叠（v2）下，一个恰好落在 chunk 边界的 turn 只出现在一个窗口里，且
那个窗口可能只看到 turn 的一侧。重叠（v3）下，同一 turn 出现在 ≥2 个
相邻窗口，每个窗口从不同偏移提供上下文。训练时，模型在多个"视角"上
看到同一个 turn 的正例，**泛化更稳**；推理时，边界 turn 至少在一个
窗口里被完整覆盖，**召回更可靠**。

### 6.2 与 doc-level split 配合不泄漏（已验证）

重叠的一个副作用是：同一文档的相邻窗口**高度相似**（共享大量文本）。
如果 train/test split 把同一文档的窗口分到不同 split，等于在测试集上
考训练集见过的文本——**泄漏**，F1 虚高。

上游刚修复的 `train.py`（`split_by_doc`，按 `doc_id`/`topic_id` 连通
分量切分）正是为此而生。我已用 `check_doc_leak.py` 验证 v3 chunks 在
新 split 下**零泄漏**（5 个 seed 全部 0 文档/0 topic 撕裂）：

```
seed   BEFORE(旧topic split)  AFTER(新doc split)
42               11 文档泄漏      0 文档泄漏
7                12              0
123              15              0
2024             12              0
99               16              0
VERDICT: PASS
```

→ **重叠让边界 turn 收益，doc-level split 保证这份收益不靠泄漏造假。**
两者必须同时存在。

### 6.3 长度混淆被消除

v1 的历史失败教训之一是"正例长、负例短"→ 模型学成"长 ⇒ turn"。v3 的
每个 chunk（除首尾特殊处理）都受 `TWO_X`/`THREE_X` 约束，正负 chunk
长度分布接近：

| | pos 平均 | neg 平均 | min | max |
|---|---|---|---|---|
| R4 v3 chunks | 298.9 | 339.4 | 50 | 448 |

正负长度没有系统性差异，长度不携带标签信号。

## 7. 参数选择的依据

- **X = 224**：`2X = 448` 字符 ≈ 454 token，安全 < 512 位置预算。段上限
  取 `X` 保证单段不会过大。
- **2X = 448（窗口 cap）**：与 v2 的 `X_CHARS` 一致，沿用已验证的安全
  字符预算。
- **3X = 672（扩展 cap）**：扩展阶段允许 buffer 临时长到 3X，给"缩减
  前缀"留出操作空间。3X = 1.5 × 2X，是一个平衡：太小则步长接近 0
  （窗口几乎不动，chunk 数爆炸）；太大则重叠骤减（接近非重叠）。

## 8. 已验证的实证数据（R4 语料）

用 v3 处理最新 R4 语料（`r4.balanced.jsonl`，3919 文档）：

```
chunks: 7069   (v2 同语料约 5558 → +27%，重叠产生更多窗口)
pos_chunks: 868  (v2: 638 → +36，turn 边界出现在更多重叠窗口里)
pos/neg 长度: 298.9 / 339.4  (无长度混淆)
doc_leak 检查: PASS (0 泄漏)
```

与 v2 同语料的对比：重叠使 chunk 总数 +27%、正例 chunk +36%——这正是
"边界 turn 出现在 ≥2 窗口"的量化体现。

## 9. 输出 schema（与 v2 完全一致）

v3 的 chunk JSONL 与 v2 逐字段相同，`train.py` / `eval_test` /
`export_misclassified` 无需改动即可消费：

```json
{
  "chunk_id": "<doc_id>#<index>",
  "doc_id": "...",
  "topic_id": "...",
  "lang": "en",
  "scenario": "coding",
  "turn_type": "strong-phrase",
  "text": "...",
  "start": 0,
  "end": 446,
  "label": 1,
  "turn_offset_in_chunk": 312,
  "n_chars": 446,
  "provenance": "generated"
}
```

- `label = 1` 当且仅当文档的 `first_turn_pos` 落在该 chunk 的
  `[start, end)` 区间内。
- `turn_offset_in_chunk = first_turn_pos - start`（turn 在 chunk 内的
  相对偏移），供 `evaluate.py` 做位置桶诊断。

## 10. 限制与后续

- **重叠 chunker 的 chunk 之间有内容重复**，训练样本数比 v2 多 ~27%。
  CPU 训练成本相应上升（max-len 512 尤甚）。这是为召回付出的代价。
- **推理端** `src/chunker.ts` 尚未移植 v3。服务端目前仍是 v2（非重叠）。
  若 v3 模型验证有效，`src/chunker.ts` 必须做 1:1 移植，否则服务端喂给
  v3 模型的窗口分布与训练时不一致（out-of-distribution）。这是下一个
  待办项。
- **`THREE_X`/`TWO_X` 比例**目前固定 1.5。若实测发现重叠过多（chunk
  爆炸）或过少（重叠不足），可调比例重新生成，但需重训。

## 引用

- `trainer/chunker_v3.py` — v3 实现（本任务产出）
- `trainer/chunker_v2.py` — v2 实现（段切分逻辑被 v3 复用）
- `trainer/plan-crossroad-distilbert-chunks.md` — 原始设计文档（主张重叠）
- `trainer/check_doc_leak.py` — doc-level split 泄漏验证工具
- `trainer/train.py` — `split_by_doc`（doc_id/topic_id 连通分量切分）