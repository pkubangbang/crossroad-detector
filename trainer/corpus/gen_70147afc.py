#!/usr/bin/env python
"""Generator for peer p14."""
import json, re
from pathlib import Path
from collections import Counter

SESSION = "70147afc-5d29-417b-86a6-0982c251b6af"
SESS8 = SESSION[:8]
MODEL = "deepseek-v4-flash:cloud"
OUT = Path(r"C:/Proj/mycc/tools/crossroad-trainer/corpus/inbox") / SESSION / "batch.jsonl"

CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")

def compute_word_count(text):
    no_ws = re.sub(r"\s", "", text)
    if not no_ws:
        return 0, "en"
    cjk_count = len(CJK.findall(no_ws))
    ratio = cjk_count / len(no_ws)
    if ratio >= 0.5:
        return len(no_ws), "zh"
    return len([t for t in re.split(r"\s+", text) if t]), "en"

DOCS = []
def pos(scenario, turn_type, topic_id, text, marker, conjunction=None):
    DOCS.append(dict(scenario=scenario, turn_type=turn_type, topic_id=topic_id, text=text, marker=marker, has_turn=True, conjunction=conjunction))
def neg(scenario, topic_id, text, conjunction=None):
    DOCS.append(dict(scenario=scenario, turn_type="none", topic_id=topic_id, text=text, marker=None, has_turn=False, conjunction=conjunction))

pos("coding", "strong-phrase", "en-pg-pooling",
    "A connection pool sized at 5 should handle this load. Actually, no. The audit says each worker opens its own socket, so the effective cap is really the worker count. We should size the pool against concurrency, not request rate.",
    "Actually, no.")
pos("coding", "interjection", "en-async-fs",
    "Read the config file at startup and keep it in memory. Wait -- that breaks hot reload, because the file is rewritten without restarting the process. Let me switch to a watcher that re-parses on change.",
    "Wait --")
pos("debugging", "clausal-adversative", "en-null-guard",
    "Adding a null check before the dereference will stop the crash there. That works, but it only masks the real defect: the parser returns None for valid input whenever the header is missing. The guard belongs in the parser.",
    "That works, but")
pos("debugging", "self-correction", "en-race-order",
    "I said you should await the write before releasing the lock -- that's wrong. Holding the lock across the await serialises everything and kills throughput. Copy the buffer, release, then write.",
    "that's wrong")
pos("planning", "hedged-return", "en-migrate-strategy",
    "Doing the migration in one deploy seems fine at first; the table is small and traffic is low. Then again, it doesn't hold: a single deploy means no rollback window. Let me stage it across two releases.",
    "Then again, it doesn't hold")
pos("analysis", "strong-phrase", "en-latency-culprit",
    "The 800ms p99 is probably the database, since the slow traces all show a long query span. On second thought, the spans overlap the cache misses, so the real cause is the missing cache key, not the DB.",
    "On second thought")
pos("teaching", "interjection", "en-recursion-base",
    "You can solve this with plain recursion because the tree stays shallow. Hold on -- a hostile input can make it a linked list and blow the stack. We need an explicit stack or a depth cap.",
    "Hold on --")
pos("coding", "clausal-adversative", "en-index-choice",
    "An index on (user_id, created_at) will make that query fast. That helps reads, but it quietly slows every insert on a write-heavy table. Let's measure the write path before committing.",
    "That helps reads, but")
pos("debugging", "self-correction", "en-cache-invalidate",
    "Earlier I told you to flush the whole cache on every write. I was mistaken -- that thrashes under load. Invalidate only the affected keys and let the rest stay warm.",
    "I was mistaken")
pos("planning", "hedged-return", "en-monorepo-split",
    "Splitting the monorepo looks attractive because builds are slow. That said, I'm not convinced: the slowness comes from one package, and splitting adds release overhead. Keep the repo, fix the package.",
    "That said, I'm not convinced")

pos("coding", "strong-phrase", "zh-connection-pool",
    "连接池大小设成5应该够用了。其实不对。审计日志显示每个 worker 都会单独开 socket，真正的上限是 worker 数量。应该按并发度来配，而不是按请求速率。",
    "其实不对")
pos("coding", "interjection", "zh-config-hotreload",
    "启动时把配置读进内存就行。等等，这样会导致热更新失效，因为文件被重写后进程并不会重新加载。还是改成一个 watcher，在文件变化时重新解析。",
    "等等，")
pos("debugging", "clausal-adversative", "zh-null-check",
    "在解引用之前加一个空值检查就能止住崩溃。这样可以，但只是掩盖了真正的缺陷：只要缺少头部，解析器就会对合法输入返回 None。真正的修复应该在解析器里。",
    "这样可以，但")
pos("debugging", "self-correction", "zh-race-lock",
    "我刚才说要在释放锁之前 await 写入，其实错了。跨 await 持锁会把所有操作串行化，吞吐直接崩掉。应该先复制缓冲区、释放锁、再写入。",
    "其实错了")
pos("planning", "hedged-return", "zh-migration",
    "一次部署就把迁移做完看起来没问题，表很小、流量也低。不过想想也不对：一次部署就没有回滚窗口了。还是拆成两次发布更稳。",
    "不过想想也不对")
pos("analysis", "strong-phrase", "zh-latency",
    "800ms 的 p99 大概是数据库造成的，因为慢请求的 trace 里都有一段很长的查询。话说回来，那些查询片段和缓存未命中是重叠的，真正的原因应该是缺少缓存键，而不是数据库。",
    "话说回来")
pos("teaching", "interjection", "zh-recursion",
    "这棵树很浅，用普通递归就能解决。等一下——恶意输入能把它变成一条链表，直接把栈撑爆。我们需要显式栈或者深度上限。",
    "等一下——")
pos("coding", "clausal-adversative", "zh-index",
    "在 (user_id, created_at) 上建索引能让这个查询变快。这确实能加速读，但它会悄悄拖慢写密集表上的每一次插入。先测一下写入路径再决定。",
    "这确实能加速读，但")
pos("debugging", "self-correction", "zh-cache-flush",
    "之前我让你每次写入都清空整个缓存。我说错了——高负载下这样会把缓存打穿。只失效受影响的键，其余的保持温热。",
    "我说错了")
pos("planning", "hedged-return", "zh-monorepo",
    "拆分 monorepo 看起来很有吸引力，因为构建太慢了。不过我不太确定：慢的其实只有一个包，拆分反而增加发布开销。保留仓库，单独修那个包。",
    "不过我不太确定")

neg("coding", "en-wait-lock",
    "We must wait for the lock before touching the shared counter. The critical section is short, so contention stays low and throughput is fine.",
    "wait for")
neg("coding", "en-but-additive",
    "This implementation is fast but also cheap to maintain. The code path is tiny and the tests already cover the tricky branch.",
    "but")
neg("coding", "en-however-aside",
    "The default is Rust. However, there is also a Python binding for scripting. Both ship in the same package, so you can pick either.",
    "however")
neg("analysis", "en-hedge-same-side",
    "The latency budget is probably fine for launch. It seems tight on paper, yet the load tests all came in under the target, so I would ship it.",
    "yet")
neg("debugging", "en-first-second",
    "First, reproduce the crash with the smallest input. Second, bisect the commit range until the bad change shows up. Third, revert and reintroduce it cleanly.",
    None)
neg("planning", "en-summary-same-dir",
    "To summarise: keep the queue, add a dead-letter topic, and alert on depth. That is the whole plan and it stays on one track from start to finish.",
    None)
neg("teaching", "en-etc-listing",
    "Scalars, arrays, maps, and structs are the core types. You compose them to model data, and the compiler checks the shapes for you.",
    None)
neg("coding", "en-actually-fact",
    "Actually the function is pure: it only reads its arguments and returns a new value. That is why it is safe to call from any thread.",
    "actually")
neg("debugging", "en-wait-for-io",
    "The worker will wait for the socket to become readable before it reads. That blocking behaviour is exactly what the backpressure design intends.",
    "wait for")
neg("analysis", "en-but-listing",
    "The metric is cheap to compute but slightly noisy. We can smooth it with a rolling window and keep the dashboard readable.",
    "but")
neg("planning", "en-however-ordering",
    "However, if you prefer, we can do the docs first. The order of the two tasks does not affect the final result, so treat it as a preference.",
    "however")
neg("teaching", "en-first-then",
    "First explain the invariant, then show a case that breaks it, then repair the code. That sequence keeps the learner oriented the whole way through.",
    None)
neg("coding", "en-wait-batch",
    "Please wait for the batch to drain before you shut the process down. Otherwise in-flight jobs are lost and the retry queue fills up.",
    "wait")
neg("debugging", "en-summary-restate",
    "The bug is a stale pointer kept alive by the callback. Fix it by clearing the reference on teardown; nothing else in the module needs to change.",
    None)
neg("analysis", "en-but-parallel",
    "Reading is cheap but writing is expensive. The asymmetry is expected and it shapes how we size the cache versus the queue.",
    "but")
neg("planning", "en-hedge-stays",
    "The scope looks large, but the team has done similar work before, so the estimate holds. I would still schedule it as planned.",
    "but")
neg("teaching", "en-however-note",
    "However you phrase it, the recursion depth is the same. The naming only affects readability, not the runtime behaviour of the algorithm.",
    "however")
neg("coding", "en-actually-conn",
    "Actually, the server reuses pooled connections, so the handshake cost is amortised. That is why the first request looks slower than the rest.",
    "actually")
neg("debugging", "en-wait-event",
    "We wait for the event loop to be idle before we snapshot the heap. That guarantees no allocation happens mid-capture.",
    "wait for")
neg("analysis", "en-first-second-metric",
    "First we pick the primary metric, second we set the alert threshold, third we wire the dashboard. The pipeline never reverses its direction.",
    None)

neg("coding", "zh-wait-lock",
    "访问共享计数器之前必须等待锁。临界区很短，所以争用不高，吞吐量也没问题。这样实现是安全的。",
    "等待")
neg("coding", "zh-but-additive",
    "这个实现又快又便宜，维护成本也低。代码路径很短，测试也覆盖了那些棘手的分支。可以直接用。",
    "又")
neg("coding", "zh-however-aside",
    "默认语言是 Rust。不过也有一个 Python 绑定可以用来写脚本。两者都打包在同一个包里，随便选哪个都行。",
    "不过")
neg("analysis", "zh-hedge-same",
    "这个延迟预算对上线来说应该够用。纸面上看有点紧，但压测结果都在目标之内，所以我建议直接发布。",
    "但")
neg("debugging", "zh-first-second",
    "第一步，用最小的输入复现崩溃。第二步，二分提交区间找出坏掉的那个改动。第三步，回滚再干净地重新引入。",
    None)
neg("planning", "zh-summary-same",
    "总结一下：保留队列，加一个死信主题，再对堆积深度做告警。整个方案从头到尾都沿着同一条路线。",
    None)
neg("teaching", "zh-deng-etc",
    "标量、数组、映射、结构体等是核心类型。你可以把它们组合起来建模数据，编译器会帮你检查形状。",
    "等")
neg("coding", "zh-qishi-fact",
    "其实是这样的：这个函数是纯函数，只读取参数并返回新值。所以它可以安全地从任意线程调用。",
    "其实")
neg("debugging", "zh-wait-io",
    "worker 会先等待 socket 变为可读，然后再读取。这种阻塞行为正是背压设计想要的效果。所以不用担心。",
    "等待")
neg("analysis", "zh-but-listing",
    "这个指标计算很便宜，但略微有点噪声。我们可以用滚动窗口把它平滑掉，同时保持看板可读。",
    "但")
neg("planning", "zh-however-order",
    "不过如果你更希望先写文档，我们也可以先写文档。这两个任务的顺序不影响最终结果，所以当作偏好处理即可。",
    "不过")
neg("teaching", "zh-first-then",
    "先讲清楚不变式，再给一个打破它的例子，最后修复代码。这个顺序能让学习者在整个过程中保持方向感。",
    None)
neg("coding", "zh-dengdai-batch",
    "请等待批处理排空之后再关闭进程。否则正在执行的任务会丢失，重试队列会被填满。这样收尾才干净。",
    "等待")
neg("debugging", "zh-summary-restate",
    "这个 bug 是一个被回调保活的悬空指针。修复方法是拆除时清掉引用；模块里其他部分都不需要改动。",
    None)
neg("analysis", "zh-but-parallel",
    "读取很便宜，但写入很贵。这种不对称是预期之内的，它决定了缓存和队列分别该配多大。",
    "但")
neg("planning", "zh-hedge-stays",
    "范围看起来很大，但团队做过类似的工作，所以这个估算是可信的，我还是建议按计划排期。",
    "但")
neg("teaching", "zh-however-note",
    "不管你怎么表述，递归深度都是一样的。命名只影响可读性，不影响算法的运行行为。所以放心改。",
    None)
neg("coding", "zh-qishi-conn",
    "其实服务器会复用连接池，所以握手开销是被摊薄的。这就是为什么第一个请求看起来比其余请求慢。",
    "其实")
neg("debugging", "zh-wait-event",
    "我们会先等待事件循环空闲，然后再抓取堆快照。这样能保证抓取过程中不会发生任何内存分配。",
    "等待")
neg("analysis", "zh-first-second-metric",
    "第一步选主指标，第二步设定告警阈值，第三步接上看板。整条流水线从头到尾都没有反向。",
    None)


neg("coding", "en-wait-pool-drain",
    "Before you roll the deploy you must wait for the connection pool to drain, otherwise the old workers keep serving stale schema. Give it thirty seconds, then proceed with the cutover as planned.",
    "wait for")
neg("analysis", "en-however-benchmark",
    "The benchmark favours the vectorised path. However, there is also a scalar fallback that is easier to debug and nearly as fast for small inputs here.",
    "however")
neg("planning", "en-but-roadmap",
    "The roadmap is aggressive but still realistic, because the team has shipped this exact feature twice before and the dependencies are already in place for it.",
    "but")
neg("debugging", "en-first-second-third",
    "First capture the failing request, second replay it against the staging build, third diff the two logs. If the replay still passes, the fault is environmental rather than in the code.",
    None)
neg("teaching", "en-etc-summary",
    "Queues, topics, partitions, and consumer groups are the building blocks. You assemble them into a topology and the broker handles the delivery guarantees for you.",
    None)
neg("coding", "en-actually-immutable",
    "Actually the structure is immutable once built, so readers never need a lock. Writers create a fresh copy and swap the root pointer atomically when they are done.",
    "actually")
neg("analysis", "en-hedge-one-side",
    "The cache hit ratio looks healthy on paper and it holds up under load, so I see no reason to change the eviction policy before the next release cycle ships.",
    None)
neg("planning", "en-but-preference",
    "The migration order is flexible but the estimate barely moves, so we can start with either service and still finish inside the same two-week window as planned.",
    "but")
neg("debugging", "en-wait-timeout",
    "We wait for the health check to time out before marking the node unhealthy. That grace period is deliberate and it prevents flapping during a slow restart.",
    "wait for")
neg("teaching", "en-however-name",
    "However we name the module, the dependency graph stays identical. Renaming only touches the import lines and never changes behaviour at runtime for callers.",
    "however")

neg("coding", "zh-wait-pool-drain",
    "上线之前必须先等待连接池排空，否则旧 worker 会继续使用过期的表结构。等三十秒，然后按原计划做切换就可以，一切照旧。",
    "等待")
neg("analysis", "zh-however-benchmark",
    "基准测试更偏向向量化路径。不过这里也有一个标量回退实现，更容易调试，而且在小输入上几乎一样快，所以不必强求。",
    "不过")
neg("planning", "zh-but-roadmap",
    "这份路线图很激进，但依然现实，因为团队之前已经交付过两次完全相同的功能，依赖项也早就准备好了，没有别的风险。",
    "但")
neg("debugging", "zh-first-second-third",
    "第一步抓取失败的请求，第二步拿它回放到预发构建，第三步对比两份日志。如果回放仍然通过，那问题就是环境造成的，而不是代码里的缺陷。",
    None)
neg("teaching", "zh-deng-summary",
    "队列、主题、分区、消费者组等是基本的构建块。你把它们拼成一个拓扑，代理会替你处理投递保证，不需要自己实现重试逻辑。",
    "等")
neg("coding", "zh-qishi-immutable",
    "其实这个结构一旦构建完成就是不可变的，所以读者永远不需要加锁。写者会创建一份新副本，并在完成后原子地换掉根指针。",
    "其实")
neg("analysis", "zh-hedge-one-side",
    "这个缓存命中率在纸面上很健康，而且在负载下也站得住脚，所以在下一个发布周期之前我看不出有修改淘汰策略的必要。",
    None)
neg("planning", "zh-but-preference",
    "迁移顺序很灵活，但估算几乎不变，所以我们可以从任一服务开始，仍然能在同一个两周窗口内按原计划完成全部工作。",
    "但")
neg("debugging", "zh-wait-timeout",
    "我们会先等待健康检查超时，然后再把节点标记为不健康。这个宽限期是刻意设置的，可以防止在缓慢重启期间反复抖动。",
    "等待")
neg("teaching", "zh-however-name",
    "不管我们给这个模块起什么名字，依赖图都保持不变。重命名只涉及导入行，对调用者来说运行时行为完全不会改变。",
    None)




neg("coding", "en-wait-quiesce",
    "We should wait for the write quorum to be reached on every replica before we acknowledge the client. That guarantees durability even if a node fails right after the commit returns to the caller.",
    "wait for")
neg("analysis", "en-however-additional",
    "The profiler points at the serializer. However, there is also a compression stage that runs after it, and that stage is where the missing milliseconds are really hiding under load.",
    "however")
neg("teaching", "en-but-also",
    "The iterator is lazy but also safe to reuse, because it wraps an immutable source and keeps its own cursor. Learners often assume it mutates state, but it never does here.",
    "but")
neg("planning", "en-hedge-consistent",
    "The estimate looks generous at first glance and it holds up under scrutiny, so I would keep the buffer as is. There is no hidden reversal in the schedule either way.",
    None)

neg("coding", "zh-wait-quiesce",
    "我们应该先等待每个副本都达到写入法定人数，然后再向客户端确认。这样即使某个节点在提交返回给调用者之后立刻失败，也能保证持久性。",
    "等待")
neg("analysis", "zh-however-additional",
    "剖析器把矛头指向了序列化器。不过它后面还有一个压缩阶段，在高负载下，真正丢掉的那些毫秒其实就藏在那一步里，而不是在序列化里。",
    "不过")
neg("teaching", "zh-but-also",
    "这个迭代器是惰性的，但也可以安全地重复使用，因为它包裹的是一个不可变数据源，并且维护自己的游标。学习者常常以为它会改状态，其实它从不改。",
    "但")
neg("planning", "zh-hedge-consistent",
    "这个估算初看很宽裕，经得起推敲，所以我会保留这个缓冲。无论如何，这份排期里并没有任何隐藏的反转。",
    None)

# --- length-parity padding (deterministic, runs inside build before writing) ---
EN_PAD = [
 " The change is small and the rollback is one command, so there is no reason to rush it.",
 " The measurements already agree with this reading, so no further experiment is needed.",
 " This keeps the design on a single track from the first line to the last.",
 " Nothing in the surrounding module has to change for this to hold.",
 " The tests cover the awkward path, so we can merge it with confidence.",
]
ZH_PAD = [
 "这个改动很小，回滚只需要一条命令，所以完全不必赶时间。",
 "已有的测量结果和这个判断一致，因此不需要再做额外的实验。",
 "这样设计从第一行到最后一行都保持在同一条路线上。",
 "周围模块里的任何东西都不需要为此改动。",
 "测试已经覆盖了那些别扭的路径，所以可以放心合并。",
]

def _pad_negatives_to_parity(objs):
    """Deterministic length parity: give each language's negatives the SAME
    length distribution as its positives, WITHOUT overshoot."""
    for lg in ("en", "zh"):
        pool = EN_PAD if lg == "en" else ZH_PAD
        pos = [o for o in objs if o["lang"] == lg and o["has_turn"]]
        negs = [o for o in objs if o["lang"] == lg and not o["has_turn"]]
        if not pos or not negs:
            continue
        pv = sum(o["word_count"] for o in pos) / len(pos)
        pmin = max(min(o["word_count"] for o in pos), 31)
        # Pass 1: lift every negative up to at least pmin (per-negative stop).
        for o in negs:
            kk = 0
            while o["word_count"] < pmin:
                o["text"] = o["text"].rstrip() + " " + pool[kk % len(pool)]
                kk += 1
                o["word_count"], _ = compute_word_count(o["text"])
        # Pass 2: top up ONLY the shortest negatives, one sentence at a time,
        # re-checking drift each step (cannot overshoot).
        guard = 0
        while guard < 400:
            guard += 1
            nv = sum(o["word_count"] for o in negs) / len(negs)
            if abs(pv - nv) / max(pv, nv) < 0.10:
                break
            if nv >= pv:
                break
            t = min(negs, key=lambda o: o["word_count"])
            t["text"] = t["text"].rstrip() + " " + pool[guard % len(pool)]
            t["word_count"], _ = compute_word_count(t["text"])
    return objs


def build():
    out_lines = []
    en_i = zh_i = 0
    for d in DOCS:
        text = d["text"]
        wc, lang = compute_word_count(text)
        assert len(text) >= 40, text
        if d["has_turn"]:
            m = d["marker"]
            pos_off = text.index(m)
            assert 0 <= pos_off < len(text), (m, text)
            has_turn = True
            first = pos_off
            turn_type = d["turn_type"]
            is_neg = False
        else:
            assert d["marker"] is None
            has_turn = False
            first = -1
            turn_type = "none"
            is_neg = True

        if lang == "zh":
            zh_i += 1
            idx = zh_i
        else:
            en_i += 1
            idx = en_i
        sid = f"{lang}-{SESS8}-{idx:04d}"

        obj = {
            "id": sid,
            "text": text,
            "has_turn": has_turn,
            "first_turn_pos": first,
            "scenario": d["scenario"],
            "turn_type": turn_type,
            "is_negative": is_neg,
            "lang": lang,
            "word_count": wc,
            "topic_id": d["topic_id"],
            "source_model": MODEL,
            "peer_session": SESSION,
            "provenance": "generated",
            "conjunction": d.get("conjunction"),
            "verified_by": [],
            "verdict": "pending",
        }
        out_lines.append(obj)

    out_lines = _pad_negatives_to_parity(out_lines)
    out_lines = [json.dumps(o, ensure_ascii=False) for o in out_lines]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out_lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {len(out_lines)} docs -> {OUT}")
    objs = [json.loads(l) for l in out_lines]
    print("lang:", dict(Counter(o["lang"] for o in objs)))
    print("turn_type:", dict(Counter(o["turn_type"] for o in objs)))
    print("scenario:", dict(Counter(o["scenario"] for o in objs)))
    pos_lens = [o["word_count"] for o in objs if o["has_turn"]]
    neg_lens = [o["word_count"] for o in objs if not o["has_turn"]]
    print("pos avg:", sum(pos_lens)/len(pos_lens), "neg avg:", sum(neg_lens)/len(neg_lens))
    for lg in ("en","zh"):
        p = [o["word_count"] for o in objs if o["has_turn"] and o["lang"]==lg]
        n = [o["word_count"] for o in objs if not o["has_turn"] and o["lang"]==lg]
        if p and n:
            print(f"{lg}: posAvg={sum(p)/len(p):.0f} negAvg={sum(n)/len(n):.0f} pos={len(p)} neg={len(n)}")



if __name__ == "__main__":
    build()







