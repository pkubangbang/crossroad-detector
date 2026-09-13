# -*- coding: utf-8 -*-
import json, re, sys, os

CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")

def compute(text):
    no_ws = re.sub(r"\s", "", text)
    cjk = len(CJK.findall(no_ws))
    ratio = cjk / len(no_ws) if no_ws else 0.0
    if ratio >= 0.5:
        return len(no_ws), "zh"
    return len(text.split()), "en"

# Each row: (topic_id, scenario, turn_type, conjunction, text)
# Positives mark the turn with <<T>>. Negatives must not contain <<T>>.
ROWS = []

def add(topic, scen, turn, conj, text):
    ROWS.append((topic, scen, turn, conj, text))

# ---- ZH POSITIVES (turn mid-text) ----
add("tzh2p-01","coding","strong-phrase","其实",">我在重构这个缓存层的写入路径的时候，先量了一下不同实现的命中率和内存占用，确认瓶颈确实在序列化这一步上。其实我的看法是，与其继续在序列化格式上抠那几个百分点，不如先把调用方的并发模型理清楚，因为真正拖慢整体吞吐的是锁的竞争，而不是编码本身。之后再回头看缓存淘汰策略，你会发现前面的判断会完全不一样，所以我打算先停一停，把并发这块彻底搞清楚再继续往下改。")
add("tzh2p-02","coding","strong-phrase","说白了",">这个模块的接口设计我先看了半小时，越看越觉得不对劲，因为每个函数都在偷偷修改共享状态，调用顺序稍有变化结果就会不一样。说白了问题不在具体实现，而在这套接口把副作用藏得太深，导致测试和推理都变得非常困难。我倾向的方案是把纯计算和不纯的副作用彻底分开，让上层用一个明确的执行器来编排顺序，这样既能保证可复现，也方便单独替换任何一段逻辑，代价是要多写一层胶水代码。")
add("tzh2p-03","coding","strong-phrase","关键是",">刚才那段日志把我卡了很久，因为报错信息只显示了一个模糊的超时，没告诉我到底是哪个下游服务慢。关键是这里的可观测性太差了，超时被一路包装，原始上下文早就丢了，所以排查只能靠猜。我建议在每一层转发的时候都带上一个请求标记，并把每跳耗时单独打点，这样一旦变慢就能立刻定位到具体环节，而不是像现在这样在几个服务之间来回翻日志，浪费大量时间。")
add("tzh2p-04","coding","strong-phrase","说到底",">我原本以为这个性能问题出在数据库查询上，结果加了索引以后几乎没变化，这才意识到方向找错了。说到底瓶颈在应用层的对象转换上，每一行数据都要经过三四次拷贝才最终返回，量一大开销就非常可观。所以接下来不是继续优化那条查询，而是先把转换链路上多余的那几层去掉，直接映射成最终结构，同时用流式处理避免一次性把全部结果读进内存，这样再压测应该能看到明显的改善。")
add("tzh2p-05","coding","strong-phrase","回过头看",">我把这块的部署流程重新梳理了一遍，之前每次上线都要手动改好几个配置文件，稍不留神就会漏掉一个环境。回过头看，真正的问题不是流程有多复杂，而是配置散落得到处都是，根本没有单一事实来源。我打算把所有环境差异抽到一个集中管理的文件里，用模板渲染出各环境的最终配置，这样既能避免手改出错，也方便审计每次变更，前面那些踩过的坑基本都能被这套机制堵住。")
add("tzh2p-06","planning","interjection","嗯",">我们下周要开始做这个迁移项目，我先把几个关键节点列了出来，包括数据双写、灰度切流和回滚演练这三个阶段。嗯，我觉得还有一个被忽略的点，就是监控和告警必须提前就位，否则切流的时候如果出问题，我们可能要过很久才能发现。所以我准备把可观测性作为第一阶段的一部分，而不是等迁移快结束才补上，这样即使中途出现异常，也能第一时间感知并快速回退到原来的路径。")
add("tzh2p-07","planning","interjection","那个",">关于这个季度的目标，我列了三条：性能提升、稳定性加固、以及文档补齐。那个，我想补充一点，这三条之间其实是有依赖关系的，性能优化往往要先有足够的监控数据支撑，而稳定的系统又离不开清晰的文档来传递上下文。所以我建议调整一下顺序，先做稳定性加固和可观测性，等基础扎实了再集中做性能，最后再补文档，这样每一项都能站在前一项的成果上，而不是互相拖累。")
add("tzh2p-08","planning","interjection","话说",">我看了下团队的排期，发现下周有两个人同时请假，正好赶上关键模块的联调窗口。话说回来，这个问题其实早就该预见到，因为我们从来没把人员可用性纳入排期模型，都是按理想情况排的。我的想法是接下来引入一个简单的缓冲机制，给每个里程碑留出百分之二十左右的浮动时间，并且在排期评审时明确标出高风险的时间段，这样即使有人临时缺席，也不至于让整个计划崩盘。")
add("tzh2p-09","planning","interjection","唔",">这个方案的评审意见我整理了一下，主要是担心它引入的复杂度超过了收益。唔，我自己其实也有类似的顾虑，因为这套抽象虽然灵活，但会让新人上手变得很慢，而且调试链路会拉长。所以我倾向于先做一个最小版本，只覆盖当前最痛的两个场景，用真实数据验证一段时间，确认收益确实对得起复杂度以后再考虑扩展，而不是一上来就把所有可能性都设计进去。")
add("tzh2p-10","debugging","clausal-adversative","不过",">我把线上那个间歇性的错误跟踪了两天，日志里偶尔会冒出一条连接被重置的记录，频率很低但一直存在。不过，我并不认为这是网络本身的抖动，因为同一时间其他服务都好好的，只有这个下游会偶发。更可能的原因是我们这边的连接池配置不合理，空闲连接超时和对方的关闭超时对不上，导致复用了已经被对端关掉的连接。接下来我会调大健康检查频率并缩短空闲回收时间，观察这个错误是否消失来验证判断。")
add("tzh2p-11","debugging","clausal-adversative","然而",">这个内存泄漏排查了很久，堆快照显示对象数量在缓慢增长，但一直没找到明确的持有者。然而，我注意到增长曲线只在特定的请求类型出现时才加速，其他流量下几乎平稳。这说明泄漏点和那条特定路径强相关，而不是全局性的缓存问题。顺着这个线索往下查，我发现有个回调注册以后从来没被注销，每次请求都会累积一份，这正好解释了为什么只有那类请求会触发。")
add("tzh2p-12","debugging","clausal-adversative","可是",">复现这个崩溃花了我大半天，本地怎么都重现不了，直到我换了一台内存更小的机器才稳定复现。可是，这并不单纯是内存不够的问题，因为报错发生在栈很浅的地方，不像是耗尽导致的。真正的原因其实是我们依赖的一个库在小内存环境下走了不同的分配分支，那个分支里有个边界判断写反了。所以修复要针对这个条件分支，而不是简单地增加内存了事。")
add("tzh2p-13","debugging","clausal-adversative","话虽如此",">这个接口偶尔会返回空数据，我一开始以为是上游还没准备好，加了重试以后好了一阵子。话虽如此，重试只是掩盖了症状，因为根因是我们的查询在事务提交之前就发出去了，存在一个很短的可见性窗口。重试能提高概率命中，但永远无法彻底消除。真正该做的是把读取放到提交之后，或者用一致性读来保证能看到刚写入的数据，这样才能从根上解决这个问题。")
add("tzh2p-14","analysis","self-correction","等等",">我在分析这个用户留存下降的原因，初步看是新增用户在第三天流失得特别厉害，所以第一反应是新手引导出了问题。等等，我可能搞错了，因为把数据按渠道拆开以后发现，只有某一个渠道的用户有这个特征，其他渠道的曲线是正常的。这就意味着问题多半不在产品本身，而在那个渠道带来的用户质量或者承诺不一致上。所以我准备换一个方向，先对比各渠道的留存差异，再判断要不要改引导流程。")
add("tzh2p-15","analysis","self-correction","不对",">这个收入预测的模型我看了一下，输入特征里包含了当月的一些行为指标，预测出来的曲线非常漂亮。不对，这里肯定有数据泄漏，因为那些当月指标在预测时点根本拿不到，等于是用结果去预测结果。所以我得把特征的时间窗口严格限制在预测点之前，重新训练一遍再看真实的泛化能力。审慎起见，还应该做一次时间序列的交叉验证，避免随机切分带来的乐观偏差。")
add("tzh2p-16","analysis","self-correction","我收回前面的话",">刚才我说这个功能没什么人用，判断依据是页面访问量很低。我收回前面的话，因为访问量低很可能是入口藏得太深导致的，并不能证明用户不需要这个功能。要判断真实需求，应该看有多少人主动搜索过相关关键词，或者通过其他路径绕过去使用类似能力。所以我打算换几个指标交叉验证，而不是拿一个容易被入口影响的数字就下结论。")
add("tzh2p-17","teaching","self-correction","准确地说",">同学们可以先把这个算法理解成一个不断缩小搜索范围的过程，每次比较都能排除掉一半的候选。准确地说，只有在数据已经有序的前提下才能这样排除，否则每次只能排除一个，复杂度会退化得很厉害。所以我们在讲解它的时候，一定要把有序这个前提反复强调，因为很多初学者记住了步骤却忘了条件，用错场景以后反而觉得这个方法不可靠，实际上是前提没满足。")

# ---- ZH POSITIVES (hedged-return) ----
add("tzh2h-queue-choice","coding","hedged-return","这个嘛",">关于消息队列的选型，团队里一直有两种声音，一派主张用成熟的重量级方案，另一派觉得我们量级不大，用轻量的就够了。这个嘛，我本来倾向于后者，因为运维成本确实低很多，而且上手快。但是仔细想想，我们明年的写入量预计要翻好几倍，轻量方案在积压和顺序保证上可能会撑不住，到时候再迁移代价更大。所以是不是应该一步到位，直接上能水平扩展的那套，虽然前期投入高，但省去了未来的迁移阵痛，你们觉得呢。")
add("tzh2h-remote-policy","planning","hedged-return","老实说",">最近关于远程办公的政策讨论得很激烈，管理层的初步想法是要求每周至少到岗三天，理由是协作效率和团队凝聚力。老实说，我对这个方向拿不准，因为一方面线下沟通确实能减少很多误解，尤其是新人的融入速度明显更快；另一方面，强制到岗会让一部分表现很好的同事感到不被信任，甚至可能因此流失。也许更好的做法是按团队的实际协作需求来定，而不是一刀切。我不太确定哪种更合适，想听听大家的实际经验再决定。")
add("tzh2h-retry-backoff","debugging","hedged-return","我有点犹豫",">在排查这个重试风暴的时候，我最初的想法是把退避上限调大，这样能减少同时重试造成的冲击。我有点犹豫，因为单纯加大退避虽然能缓解瞬时压力，但如果下游是持续不可用，请求会长时间挂在队列里，反而拖垮上游的线程池。另一种思路是引入熔断，连续失败后就快速拒绝，给下游恢复的时间，但这样又会牺牲一部分本来可能成功的请求。我还没想清楚哪种权衡更适合我们的场景，想先做个小实验对比一下再定。")

# ---- ZH NEGATIVES (confusable: contain trigger-ish words but NO actual turn) ----
add("tzh2n-wait","debugging","none","none",">这个接口偶尔会超时，排查的时候我注意到很多请求其实是在等待数据库返回，等待时间随着并发升高明显变长。为了确认等待到底花在哪里，我抓了一段慢查询日志，发现大部分时间耗在锁竞争上，而不是磁盘或网络。目前的结论是线程池配置偏小，导致请求排队，接下来我打算把连接数调大并观察等待时间是否下降，然后再决定要不要拆分这个热点表以减少锁的粒度。")
add("tzh2n-but","planning","none","none",">这次迭代的排期我重新算了一遍，把测试和联调的时间都算了进去，不过整体还是偏紧。主要原因是第三方接口的对接文档迟迟没到位，我们只能先按假设开发，等文档来了再回填。为了降低风险，我准备把依赖外部接口的部分放到最后，优先完成内部闭环的模块。这样一来即使外部接口延期，我们也能保证大部分功能按时交付，剩下的部分单独跟进度即可。")
add("tzh2n-actually","analysis","none","none",">我重新核对了这份月度报告的原始数据，发现上个月的增长率其实被重复计算了一次，因为两个数据源的时间口径不一样。修正以后环比是有小幅下滑的，主要拖累来自华东区域，其他区域基本持平。基于这个修正后的结果，我调整了接下来的分析重点，准备先把华东的渠道结构拆开看，弄清楚是哪个渠道贡献了大部分下滑，再针对性地制定挽回策略。")
add("tzh2n-summary","teaching","none","none",">这节课我们主要讲了三个概念，分别是复杂度、稳定性和可维护性。总结一下，复杂度决定了系统的推理难度，稳定性决定了它在异常情况下的表现，可维护性则决定了团队能不能持续演进它。这三者往往是相互制约的，提升其中一个经常要以另一个为代价。课后请大家找一个小项目，尝试识别其中这三者的取舍，下节课我们会结合具体案例来讨论如何做平衡。")
add("tzh2n-think","coding","none","none",">在写这段代码之前，我想先把边界条件想清楚，比如输入为空、数字溢出、以及并发修改等情况。想清楚以后就可以按最简的实现来写，不需要提前引入复杂的抽象，因为需求本身很简单。写完之后我会补上对应的单元测试，覆盖刚才列出的每一种边界，确保后续有人改动时能第一时间发现回归。这样整个开发过程就比较稳妥，不会留下太多隐患。")
add("tzh2n-however","analysis","none","none",">整体来看这个季度的用户增长是达标的，新增和活跃都超过了目标。不过在质量维度上还有一些隐忧，比如七日留存比上个季度低了两个百分点，说明拉新带来的用户和产品匹配度有所下降。因此下个季度的重点会从拉新转向提留存，先把新用户的引导路径打磨好，再考虑扩大投放，否则拉来的用户很快流失，投入产出比会越来越差。")
add("tzh2n-well","planning","none","none",">关于这个季度要不要扩招，我列了一些判断依据，包括当前的人均产出、待办需求的积压量，以及未来半年的业务预期。从数据上看，团队已经接近满负荷，积压的需求还在增加，所以适度扩充是有必要的。但我倾向于先招关键岗位，比如架构和测试，其余岗位通过流程优化和工具提升来缓解，而不是一次性把编制打满，避免后续业务波动时又要裁员。")
add("tzh2n-nomeantime","debugging","none","none",">这个报错在高峰期才会出现，平时很难复现。我对比了高峰和低谷两次的调用链，发现高峰期多了一次对配置中心的远程读取，而那次读取偶尔会返回旧版本，导致行为不一致。所以问题并不在业务代码，而在配置同步的延迟上。接下来我会给配置读取加本地缓存和版本校验，确保拿到的始终是最新值，同时缩短同步间隔来降低窗口。")
add("tzh2n-hold","coding","none","none",">重构之前我先梳理了一下现有的调用关系，画了一张依赖图，发现有几个核心模块被十几处引用，改动风险很高。为了控制风险，我决定采用逐步替换的方式，先在新路径上实现同样的功能，用影子流量对比结果，确认一致以后再切换调用方。整个过程会分几次提交完成，每次都能独立回滚，这样即使中间出问题也不会影响线上的稳定性。")
add("tzh2n-turnfrom","teaching","none","none",">讲算法之前，我想先强调一下分析问题的基本方法，就是要先明确输入输出的范围和约束。拿到任何一个问题，第一步都是把条件和目标写清楚，第二步是找出可行的思路，第三步才是比较它们的代价。很多同学恰恰跳过了前两步，直接背解法，结果换个场景就不会用了。所以这门课我更希望你们掌握的是分析框架，而不是记住某一个具体答案。")
add("tzh2n-anyway","planning","none","none",">这次评审的结论是把方案拆成两期来做，第一期只解决最核心的性能问题，第二期再考虑架构上的统一。之所以这样安排，是因为当前最紧的是线上卡顿，其他问题虽然也存在但不影响交付。第二期的重构会涉及多个团队的接口，需要更长的协调周期，不适合和性能优化捆在一起。这样分阶段推进，既能尽快缓解线上压力，也能给重构留出充分的沟通时间。")
add("tzh2n-onething","analysis","none","none",">关于这次的转化率下降，我做了初步归因。落地页的改版只影响了一部分流量，而且那部分流量的转化其实还略有上升，所以可以排除改版因素。真正的下滑集中在移动端，且和一次应用商店的版本更新时间点高度吻合。因此我判断是那个版本引入的某个交互改动影响了转化，下一步会对比新旧版本的关键路径埋点，定位到具体的页面和步骤。")
add("tzh2n-lookback","debugging","none","none",">回顾这次故障，从告警到恢复一共花了四十分钟，其中大部分时间用在定位上，因为监控只覆盖了入口的错误率，没有覆盖内部各环节。复盘的时候大家一致认为，最该补的是链路的可观测性，也就是让每一次请求的每一跳都能被单独度量。除此之外，我们还需要把应急预案写得更具体，明确每个角色在故障时该做什么，避免像这次一样在沟通上浪费宝贵的时间。")
add("tzh2n-deepdown","coding","none","none",">深入看这套依赖注入的实现，它其实是通过反射在运行时解析依赖关系，灵活但代价是启动变慢、报错也不直观。对小项目来说这没什么问题，可一旦依赖图变大，排查一个循环依赖就会非常痛苦。所以是否采用它，取决于项目规模和团队对启动性能的敏感程度，不能一概而论。我们当前的项目启动时间还能接受，暂时保留，但会记录这个潜在的技术债。")

# ---- EN docs (needed for --strict lang coverage) ----
add("ten2-lock-order-neg","debugging","none","none",">I spent the afternoon chasing a deadlock that only showed up under load. Two transactions were grabbing the same pair of rows but in opposite orders, so under contention they would each hold one lock and wait forever for the other. The fix is to impose a global ordering on lock acquisition so every transaction takes the same sequence. I also want to add a timeout that aborts and retries, but the ordering alone removes the root cause rather than just papering over it.")
add("ten2-vendor-neg","planning","none","none",">We evaluated three vendors for the managed queue and scored them on cost, throughput, and operational burden. The cheapest option had the weakest durability guarantees, and the most robust one would roughly double our monthly spend. My recommendation is to start with the middle option, since it meets our current throughput target with acceptable durability, and revisit the decision once we have real production numbers instead of estimates from a benchmark that may not match our workload.")
add("ten2-pool-neg","coding","none","none",">The connection pool was sized by copying a number from an old service, which turned out to be far too small for our traffic. Requests were queuing for a connection even though the database itself was mostly idle. I raised the limit and shortened the idle timeout so stale connections get recycled before the server closes them. Early results look promising, but I want to run a longer soak test before calling it fixed, since the original bug was intermittent.")
add("ten2-summary-neg","analysis","none","none",">This month the top line grew modestly while margins compressed, mainly because support costs rose faster than revenue. The growth came almost entirely from a single region, which is a concentration risk worth watching. My read is that we should invest in automation for the support workflow before adding more headcount, because the cost curve is driven by volume, and volume is not going to fall on its own anytime soon.")
add("ten2-recap-neg","teaching","none","none",">Today we covered the three stages of compilation: parsing, optimization, and code generation. Parsing turns source text into a tree, optimization rewrites that tree to be more efficient, and code generation lowers it to the target instruction set. The key takeaway is that each stage has a clear contract with the next, and bugs are easiest to isolate when you can dump the intermediate representation and inspect exactly what each pass produced.")
add("ten2-review-neg","planning","none","none",">The design review surfaced two concerns: the new abstraction leaks storage details into the domain layer, and the migration path assumes downtime we cannot afford. Both are fixable. We can hide the storage behind a repository interface, and we can run a dual-write phase so the switch is seamless. I will revise the proposal with these changes and bring it back next week rather than pushing the current version forward with known gaps.")

# ---- EN positive (clears en single-class warning) ----
add("ten2-cache-pos","coding","clausal-adversative","However",">I profiled the cache layer and found hit rates were lower than expected, so the obvious move was to enlarge the cache. However, the misses were almost all cold-start lookups for keys that are only requested once, so a bigger cache would not help at all. The real problem is that we are caching the wrong thing; the expensive part is the upstream fan-out, not the lookup. I will cache the aggregated result instead and leave the raw entries uncached, which should cut upstream traffic far more than resizing ever could.")

# ---- Emit ----
def has_cjk_ratio_zh(text):
    no_ws = re.sub(r"\s", "", text)
    if not no_ws:
        return False
    return len(CJK.findall(no_ws)) / len(no_ws) >= 0.5

errors = []
turn_types_seen = set()
scenarios_seen = set()
langs_seen = set()
zh_pos_lens, zh_neg_lens = [], []
en_pos_lens, en_neg_lens = [], []

objs = []
for i, (topic, scen, turn, conj, raw) in enumerate(ROWS):
    has_turn = "<<T>>" in raw
    if has_turn:
        pos_ = raw.index("<<T>>")
        text = raw.replace("<<T>>", "", 1)
        is_neg = False
        if turn not in ("strong-phrase","interjection","clausal-adversative","self-correction","hedged-return"):
            errors.append(f"{topic}: has_turn but turn_type={turn}")
        # turn must be mid-text
        if not (0 < pos_ < len(text) - 1):
            errors.append(f"{topic}: turn not mid-text pos={pos_} len={len(text)}")
    else:
        text = raw
        is_neg = True
        pos_ = -1
        if turn != "none":
            errors.append(f"{topic}: negative but turn_type={turn}")
    wc, lang = compute(text)
    if len(text) < 40:
        errors.append(f"{topic}: text <40")
    if lang == "zh" and len(text) < 256:
        errors.append(f"{topic}: zh text {len(text)} <256")
    turn_types_seen.add(turn)
    scenarios_seen.add(scen)
    langs_seen.add(lang)
    if lang == "zh":
        (zh_pos_lens if has_turn else zh_neg_lens).append(wc)
    else:
        (en_pos_lens if has_turn else en_neg_lens).append(wc)
    objs.append({
        "id": f"{lang}-03729236-{i:04d}",
        "text": text,
        "has_turn": has_turn,
        "first_turn_pos": pos_,
        "scenario": scen,
        "turn_type": turn,
        "is_negative": is_neg,
        "lang": lang,
        "word_count": wc,
        "topic_id": topic,
        "conjunction": conj,
        "source_model": "peer-03729236",
        "peer_session": "03729236-bcd7-4618-a040-07a0a28cfaf2",
    })

# checks
if errors:
    print("BUILD ERRORS:")
    for e in errors:
        print("  -", e)
    sys.exit(1)
REQ_SCEN = {"coding","planning","debugging","analysis","teaching"}
REQ_TURN = {"strong-phrase","interjection","clausal-adversative","self-correction","hedged-return"}
missing_s = REQ_SCEN - scenarios_seen
missing_t = REQ_TURN - turn_types_seen
missing_l = {"en","zh"} - langs_seen
if missing_s or missing_t or missing_l:
    print("COVERAGE GAP:", missing_s, missing_t, missing_l); sys.exit(1)

def avg(x): return sum(x)/len(x) if x else 0
print(f"n={len(objs)} zh_pos={len(zh_pos_lens)} zh_neg={len(zh_neg_lens)} en_pos={len(en_pos_lens)} en_neg={len(en_neg_lens)}")
print(f"zh posAvg={avg(zh_pos_lens):.0f} negAvg={avg(zh_neg_lens):.0f} min={min(zh_pos_lens+zh_neg_lens)}")
print("turn_types:", sorted(turn_types_seen))
print("scenarios:", sorted(scenarios_seen))

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "batch_zh_long.jsonl")
with open(out, "w", encoding="utf-8", newline="\n") as f:
    for o in objs:
        f.write(json.dumps(o, ensure_ascii=False) + "\n")
print("WROTE", out, os.path.getsize(out), "bytes")
