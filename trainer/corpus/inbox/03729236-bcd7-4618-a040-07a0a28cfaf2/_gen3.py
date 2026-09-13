import json, re
from pathlib import Path
CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
SID = "03729236-bcd7-4618-a040-07a0a28cfaf2"; SID8 = SID[:8]
DIR = Path(r"C:\Proj\mycc\tools\crossroad-trainer\corpus\inbox\03729236-bcd7-4618-a040-07a0a28cfaf2")
MARK = "<<T>>"
def compute(text):
    no_ws = re.sub(r"\s", "", text)
    if not no_ws: return 0, "en"
    cjk = len(CJK.findall(no_ws))
    if cjk / len(no_ws) >= 0.5: return len(no_ws), "zh"
    return len([t for t in re.split(r"\s+", text) if t]), "en"
ROWS = []
def load_tsv(name):
    rows = []
    for line in (DIR / name).read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        p = line.split("\t")
        assert len(p) == 5, (name, len(p))
        scen, topic, turn, conj, text = p
        assert MARK in text, ("missing marker", name, topic)
        rows.append((scen, topic, turn, conj, text))
    return rows
ROWS += load_tsv("_pos17.tsv")
ROWS += load_tsv("_hedged.tsv")
NEG = []
NEG.append(("coding","zh2n-lock-order",
  "我们先把两把锁的获取顺序统一成先按地址排序再依次获取，"
  "这样任意两个线程都不会出现互相等待对方持有的锁这种经典死锁形态。"
  "等这个改动合并进主干之后，压力测试里那种偶发的卡死应该会明显减少，"
  "因为一旦顺序固定，环形等待的四个必要条件里至少有一个不再成立。"
  "当然这只是一个局部修复，真正的长期方案是把共享计数抽成无锁的原子结构，"
  "但那会牵扯到序列化格式的兼容性，需要单独的迭代来评估风险，"
  "所以这一轮先保证线上稳定，把更激进的改动留到下一个版本。"))
NEG.append(("planning","zh2n-vendor",
  "法务那边还需要两个工作日才能把供应商合同的条款过完，"
  "在这之前我们没有办法正式下单，所以排期上要把采购这一步往后挪。"
  "其实这段时间正好可以用来把集成测试的脚手架搭起来，"
  "让接口对接的双方先在测试环境里把数据格式跑通，"
  "这样等合同一签就能直接进入联调，不至于所有人都在干等。"
  "另外预算审批的流程也要同步启动，因为它和法务是两条独立的线，"
  "任何一条卡住都会拖慢整体节奏，提前并行可以省下不少时间。"))
NEG.append(("debugging","zh2n-pool",
  "线程池之所以会枯竭，是因为每一个进来的请求都在里面去调用阻塞式的下游服务，"
  "而这些调用在没有超时控制的情况下会把工作线程长期占住。"
  "换句话说，池子里的线程并不是真的忙，而是全部卡在等待网络返回的状态里，"
  "新请求到了却没有空闲线程可用，于是队列越积越长。"
  "排查的时候可以先把下游调用的超时设成一个很短的值，观察枯竭现象是否消失，"
  "如果消失就基本能确认是阻塞占用导致的，之后再考虑连接池和熔断的整体改造。"))
NEG.append(("analysis","zh2n-forecast",
  "这个季度的增长预测之所以看起来偏乐观，主要是因为模型把去年同期的促销活动当成了常态，"
  "而事实上那一次的活动力度是空前的，之后并没有被复现。"
  "如果我们不在特征里把这类一次性事件单独剥离出来，"
  "那么拟合出来的趋势线就会系统性地高估未来的基线水平。"
  "更稳妥的做法是先用同环比把异常月份标出来，再对剩下的样本重新做季节分解，"
  "这样得到的斜率才更接近真实的自然增长率，也方便和业务方解释。"))
NEG.append(("coding","zh2n-library",
  "这个库的文档虽然写得很全，但示例代码基本都停留在最简单的用法上，"
  "真正涉及到并发和错误恢复的部分几乎没有覆盖。"
  "我们之前踩过的坑大多出现在这些边角场景里，比如连接断开后的重连策略，"
  "以及回调里再次抛异常时的行为，官方示例都没有提到。"
  "所以选型的时候不能只看 star 数量和功能列表，"
  "还要看社区里关于生产环境故障的讨论是否活跃，"
  "以及维护者对小 bug 的响应速度，这些往往更能说明它能不能长期依赖。"))
NEG.append(("teaching","zh2n-difficulty",
  "初学者在这个阶段最容易卡住的地方，其实不是语法本身，而是不知道怎么把问题拆成函数。"
  "他们往往一上来就想把整个流程写在一个大函数里，"
  "结果稍微加一个条件分支就变得难以阅读，出了错也找不到是哪一步。"
  "比较好的引导方式是先带着他们把输入输出写清楚，再一步步往中间填空，"
  "每填一步就运行一次看看结果，这样既建立了反馈，也培养了分解的习惯。"
  "等他们习惯了这种节奏，再引入递归和模块化的概念就会顺畅很多。"))
NEG.append(("debugging","zh2n-fixconf",
  "我在本地把补丁打上之后复现不出来了，但这并不能说明问题已经修好，"
  "因为本地环境和线上在连接数、超时设置和依赖版本上都有差异。"
  "更可靠的验证方式是把这个修复放到预发环境，用和线上相同的压力量跑一轮，"
  "观察之前那个报错是否还会在日志里出现。"
  "如果预发也没问题，再灰度一小部分真实流量，逐步放大，"
  "整个过程要留好回滚开关，一旦指标异常就能立刻退回。"))
NEG.append(("analysis","zh2n-summary",
  "总结一下这次分析的几个要点：第一，转化率的下降主要集中在移动端的首屏，"
  "第二，桌面端的数据基本持平，说明问题多半和网络条件或渲染性能有关。"
  "第三，我们把时间维度拆开之后发现，下降是从上周三的那次发版开始的。"
  "综合这三点，最需要优先排查的是这次发版里和移动端首屏相关的改动，"
  "尤其是新增的那个统计脚本，它有可能在弱网下阻塞了关键资源的加载。"))
NEG.append(("coding","zh2n-review",
  "这段代码逻辑上没有问题，但可读性上还有提升的空间：变量命名可以更具体一些，"
  "把 data 改成 user_orders 之类的名字会让后面的读者省不少力气。"
  "另外这个函数已经有一百多行了，建议按职责拆成几个小函数，各自负责一件事。"
  "注释也偏少，特别是那个位运算的地方，最好补一句说明它在做什么，"
  "否则几个月后再看，连作者自己都要花时间重新推一遍。"
  "整体来说功能是对的，只是维护成本会随着人越来越多而上升。"))
NEG.append(("planning","zh2n-retro",
  "这次复盘的结论是，进度延误的主要原因是需求在开发中途发生了比较大的变更，"
  "而我们的排期没有为这种变更预留缓冲。"
  "大家普遍反映，如果能在迭代开始前把验收标准定得更明确一些，"
  "后面返工的比例会低很多，测试也不至于总在最后阶段才发现问题。"
  "所以下个迭代我们打算在立项阶段加一个需求澄清的环节，"
  "让开发和测试一起参与，把边界情况提前讨论清楚，"
  "并且把讨论的结论直接写进任务描述里作为验收依据。"))
NEG.append(("teaching","zh2n-recap",
  "我们回顾一下今天讲的内容：变量是用来存数据的盒子，类型决定了盒子能装什么。"
  "条件语句让程序可以走不同的分支，循环则让重复的动作只写一遍。"
  "把这三样组合起来，其实已经能写出很多有用的小工具了。"
  "课后请大家动手写一个猜数字的小游戏，把随机数、输入和循环都用上，"
  "遇到问题先自己调试，实在不行再来问我，下节课我们会一起看几份作业。"))
NEG.append(("debugging","zh2n-closing",
  "这个内存泄漏到这里算是定位清楚了，问题出在那个事件监听器注册之后从来没有被移除，"
  "组件销毁了但回调还挂在全局对象上，于是引用一直无法释放。"
  "修复的方式是在生命周期结束的时候显式注销监听，"
  "或者改用一次性的监听方式，让它在触发后自动清理。"
  "改完之后我们用内存快照对比了修复前后的对象数量，"
  "确认那个本该被回收的组件实例确实不再出现在快照里了。"))
NEG.append(("coding","zh2n-backpressure",
  "当上游的写入速度持续超过下游的处理能力时，如果没有背压机制，"
  "中间的队列就会无限增长，最终把内存吃光。"
  "一种常见的做法是在队列达到水位上限时让生产者阻塞或者直接拒绝新的请求，"
  "从而把压力反推回源头，促使其降速。"
  "这里面最关键的是要选一个合理的水位线，太低会浪费吞吐，太高又来不及反应，"
  "通常需要结合实际的延迟目标和内存预算来反复调，"
  "并且在高负载场景下做压测来验证这个阈值是否真的扛得住。"))
NEG.append(("planning","zh2n-handoff",
  "交接的时候要注意，这个服务的部署脚本和配置是分开维护的，"
  "改配置之前一定要先确认脚本里没有硬编码同名变量，否则会互相覆盖。"
  "另外监控面板的告警阈值上个月刚调整过，文档还没同步，真值以后台为准。"
  "最后提醒一句，回滚只需要重新跑上一个版本的流水线，"
  "数据库的迁移脚本是向前兼容的，不用单独处理，"
  "但如果这次改动动了数据格式，还是要先确认下游消费者是否已经兼容。"))
NEG.append(("analysis","zh2n-data-ready",
  "这批数据在用来训练之前还需要做几件事：先去掉明显重复的样本，"
  "再检查标签有没有缺失或者互相矛盾的情况。"
  "对于文本长度差异过大的问题，可以考虑分桶采样，避免长文本主导了梯度。"
  "做完这些清洗之后，最好再留出一部分做验证，不要全部拿去训练，"
  "否则我们无法判断模型是真的学到了规律还是只是记住了样本，"
  "而且要保证验证集和训练集在分布上尽量一致，这样评估才可信。"))
NEG.append(("teaching","zh2n-pause",
  "在继续往下讲之前，我想先停下来问大家一个问题："
  "如果一个函数修改了传进来的列表，调用方会看到这个变化吗？"
  "带着这个问题想一想我们前面说的引用和值的区别。"
  "等一下我们会用几个小例子来验证，"
  "你会发现同样的代码，参数是列表和参数是数字时，表现是完全不一样的，"
  "这个区别在后面讲对象和函数参数传递的时候会反复用到。"))
NEG.append(("debugging","zh2n-lock-wait",
  "现在两个线程互相等待对方释放锁，所以整个服务卡死在这里，谁也无法继续往前推进。"
  "从堆栈上看，一个线程持有了订单表的行锁还在等库存表的锁，"
  "另一个线程正好反过来，先拿了库存的锁再去要订单的锁，"
  "两边各持一把又都在等对方手里的那一把，形成了一个闭环。"
  "要打破这个局面，最直接的办法就是让所有线程都按同一顺序加锁，"
  "比如统一先订库存再订订单，这样就不可能再出现环形的等待。"))
EXT = {}
EXT["zh2n-lock-order"] = (
  "另外要注意的是，这个约定必须写进团队规范并且在代码评审里强制检查，"
  "否则新人很容易图省事随手加一把新锁就把顺序破坏了，"
  "而且这类死锁往往在低并发下完全看不出来，"
  "只有到了大促那种高压力场景才集中爆发，到时候排查成本会高得离谱。")
EXT["zh2n-vendor"] = (
  "还有一点，付款条件里的账期和违约金比例这两项也要一并确认，"
  "因为它们会直接影响我们对现金流的预测，"
  "如果有变化要第一时间同步给财务，"
  "免得采购合同签完了才发现预算的口径对不上，"
  "那样又要走一轮额外的审批，反而更耽误时间。" +
  "把这些要点整理成一页纸的清单，每次采购前逐条打勾核对一遍。")
EXT["zh2n-pool"] = (
  "不过要注意，单纯调小超时只是缓解症状，并不能根治，"
  "因为下游一旦真的变慢，请求还是会大量失败，"
  "所以接下来还要评估连接池大小、熔断阈值和重试次数这三者之间的相互影响，"
  "在保证不雪崩的前提下给系统留出足够的恢复空间。" +
  "另外记得给关键指标设好告警，免得问题悄悄积累到难以收拾的地步。")
EXT["zh2n-forecast"] = (
  "与此同时，我们也要把口径和业务方对齐，明确他们关心的是自然增长还是包含活动的总量，"
  "因为这两个数字在高增长阶段差异会非常大，"
  "如果各说各的，汇报的时候很容易出现互相矛盾的结论，"
  "反而让决策变得更混乱。" +
  "同时把假设和结论分开写清楚，方便以后复盘时追溯每个数字的来源。")
EXT["zh2n-library"] = (
  "还有一点容易被忽略的是许可证，有些看起来很好用的库采用的是传染性较强的协议，"
  "一旦引入可能会给整个产品带来合规风险，"
  "所以引入之前一定要让法务过一遍，"
  "不能只看技术指标就拍板。" +
  "选型时也不要只盯着热度，维护活跃度和社区响应速度同样重要得很。")
EXT["zh2n-difficulty"] = (
  "我个人的经验是，与其一次性讲很多概念，不如每节课只解决一个具体的小问题，"
  "让他们在解决问题的过程中自然地把新知识用上，"
  "这样知识点之间的联系是搭出来的而不是背出来的，"
  "记忆也会更牢。" +
  "循序渐进比一味追进度更能帮他们建立真正的信心和长期的兴趣。")
EXT["zh2n-fixconf"] = (
  "同时别忘了把这次修复的复现步骤补进缺陷单里，"
  "因为下一个接手的人未必知道当时的上下文，"
  "如果没有清楚的记录，他可能会在同样的问题上再浪费一遍时间，"
  "而这些排查的经验本身就是团队的资产。" +
  "以后遇到相似的报错就能第一时间联想到这里的处理方式。" +
  "记录要写得让外行也能看懂，否则过几天连自己都想不起来细节了。")
EXT["zh2n-summary"] = (
  "后续的跟踪会放在每周的分析例会上进行，"
  "如果下周的数据仍然没有回升，我们就需要重新评估这次发版的整体影响，"
  "并考虑是否要回滚其中几个改动，"
  "避免为了一个局部指标牺牲掉整体的稳定性。" +
  "总之结论要清楚，行动项要落到人头上，时间点也要写明白。" +
  "数字之外也要写下当时的判断依据，这样结论才经得起后来的推敲。")
EXT["zh2n-review"] = (
  "还有一处小问题，就是错误处理的分支里直接把异常吞掉了，"
  "这样一旦出问题在日志里什么都看不到，"
  "建议至少打一条带上下文信息的日志，"
  "方便以后定位，同时也能让监控系统捕捉到异常频率的变化。" +
  "评审意见要具体到行号和改法，泛泛而谈的评论对作者帮助其实很小。")
EXT["zh2n-retro"] = (
  "另外大家也同意，跨团队的依赖要提前对齐，"
  "不要等到临近交付才去催接口，"
  "那样既被动又容易出问题，"
  "最好在迭代规划的时候就把上下游的节奏排清楚，"
  "把外部依赖当成一等公民来管理。" +
  "复盘的结论要转成明确的待办，分配好负责人和截止时间才算真正闭环。")
EXT["zh2n-recap"] = (
  "写作业的时候不要去网上直接抄答案，先自己跑一遍，观察输出和你预期的不一样在哪里，"
  "那个不一样的地方往往就是你理解有偏差的地方，"
  "把这个偏差搞明白，比做十道一模一样的题都有用。" +
  "把每次作业里卡住的地方记下来，期末复习的时候会特别有用。" +
  "把每节课的核心问题写在黑板上，下课时再让大家复述一遍加深印象。")
EXT["zh2n-closing"] = (
  "最后再把结论记录到缺陷跟踪系统里，附上关键堆栈和复现路径，"
  "并且提醒团队在做类似组件的时候尽量用框架提供的自动清理机制，"
  "从源头上减少这类手工注册带来的遗漏风险。" +
  "这样下次再遇到同类问题，团队里任何人都能快速对照处理。")
EXT["zh2n-backpressure"] = (
  "另外一个容易被忽视的点是，背压要和可观测性配合，"
  "把队列深度、拒绝率和处理延迟都暴露成指标，"
  "这样当压力真的上来的时候，运维能第一时间看到是哪里先顶不住，"
  "而不是等用户投诉了才发现问题。")
EXT["zh2n-handoff"] = (
  "交接文档最好配一张依赖关系图，把上游、下游和中间件都画出来，"
  "这样接手的人一眼就能看懂数据是怎么流动的，"
  "比看一堆文字描述高效得多，"
  "也更容易发现文档里可能遗漏的环节。" +
  "交接完成后最好约一个短会当面过一遍，确认对方真的接住了。")
EXT["zh2n-data-ready"] = (
  "另外，标签的生成规则也要写成文档，说明每个字段的含义和取值范围，"
  "因为过一段时间之后，连当初做标注的人都未必记得清边界是怎么切的，"
  "有了文档才能保证后续新增的数据用同样的标准。")
EXT["zh2n-pause"] = (
  "先不要急着翻答案，你们可以先在纸上把内存里的变化画出来，"
  "想一想函数内部改的是那份拷贝还是原来那一份，"
  "等一会儿我们对着运行结果来验证你的猜测，"
  "猜错了也没关系，那恰恰说明这里有值得弄清楚的知识点。" +
  "带着这个疑问继续听，后面的例子会把答案一点点揭示出来。")
EXT["zh2n-lock-wait"] = (
  "除此之外，还要在代码里加一个超时获取锁的保护，"
  "这样即使将来有人不小心又写乱了顺序，"
  "最坏情况下也只是这一个请求失败，"
  "而不会把整个线程池拖进永久等待里，"
  "给系统留下一层兜底的防线。")

for _scen, _topic, _text in NEG:
    _text = _text + EXT[_topic]
    ROWS.append((_scen, _topic, "none", "", _text))
EN = []
EN.append(("coding","en2-cache-pos","clausal-adversative","However",
  "The team stores session state in a plain in-process dictionary, which is fast and needs no network hop. "
  "That said, it is convenient while everything stays on one machine. However, the moment you run two worker "
  "processes the dictionaries diverge, and a rolling deploy logs everyone out, so the shortcut quietly breaks "
  "the product exactly when traffic grows."))
EN.append(("planning","en2-vendor-pos","strong-phrase","Actually, no",
  "Legal still needs two working days on the contract, so we cannot place the order yet. "
  "Actually, no, that framing is too passive: we should start the integration scaffolding now so both sides can "
  "shake out the payload format in staging. Then the moment the contract lands we move straight to joint testing "
  "instead of burning a week waiting."))
EN.append(("debugging","en2-pool-pos","self-correction","Or rather",
  "The thread pool runs dry because every request blocks on a slow downstream call. Or rather, it is not that the "
  "threads are busy with real work; they are all parked waiting on the network, so new requests queue up with no "
  "worker free. Setting a short downstream timeout usually makes the starvation disappear, which confirms the cause."))
EN.append(("analysis","en2-trend-pos","hedged-return","Well, I am not sure",
  "The growth forecast looks optimistic because the model treats last year's promotion as normal. "
  "Well, I am not sure we should trust it as-is. A one-off campaign got baked into the baseline, so the fitted "
  "trend overstates the future. Stripping those months out before refitting gives a slope closer to the real rate."))
EN.append(("teaching","en2-recap-pos","interjection","Hmm",
  "Today we covered variables, conditionals, and loops. Hmm, before we close, let me check one thing: does a function "
  "that mutates a passed-in list change what the caller sees? Think about the difference between values and "
  "references, because that question trips up almost everyone the first time they meet it."))
EN_NEG = []
EN_NEG.append(("coding","en2-lock-order-neg","none","wait for",
  "Two threads each grab a different lock first, which is precisely the circular wait we keep hitting. "
  "One holds the orders row lock and waits for the inventory lock, while the other holds inventory and waits for "
  "orders, so each is blocked on the other. The fix is to impose one global acquisition order so the cycle cannot form."))
EN_NEG.append(("planning","en2-vendor-neg","none","wait for",
  "Legal needs two more working days to finish reviewing the vendor contract, and we cannot order until that clears. "
  "In the meantime we can build the integration scaffolding so both teams exercise the payload format in staging, "
  "then move straight to joint testing once it is signed rather than idling."))
EN_NEG.append(("debugging","en2-pool-neg","none","wait for",
  "The thread pool runs dry because every incoming request blocks on a slow downstream call, so no worker is ever "
  "free even though none is doing real computation. Setting a short timeout on that call usually clears the "
  "starvation, which tells us the cause is blocking occupancy rather than genuine load."))
EN_NEG.append(("analysis","en2-summary-neg","none","summary",
  "In summary, the migration cut p99 latency by about forty percent while error rates stayed flat. "
  "The gains came mostly from the new connection pooling, and the rollback path was exercised twice without "
  "incident, so we consider the change validated and ready to roll out more broadly."))
EN_NEG.append(("teaching","en2-recap-neg","none","recap",
  "To recap what we covered today: a graph is a set of nodes plus edges, and traversal just means visiting every "
  "node once. We wrote a breadth-first walk and a depth-first walk, and saw why the queue versus stack choice "
  "changes the visit order."))
EN_NEG.append(("coding","en2-review-neg","none","summary",
  "To wrap up: this module is well covered by tests, the edge cases have names that explain themselves, and the "
  "public surface is small. The one gap is documentation for the retry helper, which we should fill before the "
  "next release so newcomers do not have to read the source."))
for _scen, _topic, _turn, _conj, _text in EN:
    ROWS.append((_scen, _topic, _turn, _conj, _text))
for _scen, _topic, _turn, _conj, _text in EN_NEG:
    ROWS.append((_scen, _topic, _turn, _conj, _text))
OUT = []
for n, (scen, topic, turn, conj, text) in enumerate(ROWS, 1):
    has_turn = (MARK in text) or (turn != "none")
    if has_turn:
        if MARK not in text:
            assert conj and conj in text, ("en positive needs conj anchor", topic, conj)
            text = text.replace(conj, MARK + conj, 1)
        fpos = text.index(MARK)
        ct = text.replace(MARK, "")
        tt = turn if turn != "none" else "strong-phrase"
    else:
        fpos = -1
        ct = text
        tt = "none"
    wc, lang = compute(ct)
    OUT.append({
        "id": "%s-%s-%04d" % (lang, SID8, n),
        "text": ct,
        "has_turn": has_turn,
        "first_turn_pos": fpos,
        "scenario": scen,
        "turn_type": tt,
        "is_negative": (not has_turn),
        "lang": lang,
        "word_count": wc,
        "topic_id": topic,
        "source_model": "deepseek-v4-flash:cloud",
        "peer_session": SID,
        "provenance": "generated",
        "conjunction": (conj if conj else None),
        "verified_by": [],
        "verdict": "pending",
    })
for o in OUT:
    assert len(o) == 16, ("field count", o["id"], len(o))
    if o["has_turn"]:
        assert o["first_turn_pos"] >= 0 and o["first_turn_pos"] < len(o["text"]), ("pos", o["id"])
    else:
        assert o["first_turn_pos"] == -1, ("neg pos", o["id"])
zh = [o for o in OUT if o["lang"] == "zh"]
zh_pos = [o for o in zh if not o["is_negative"]]
zh_neg = [o for o in zh if o["is_negative"]]
short = [(o["id"], len(o["text"])) for o in zh if len(o["text"]) < 256]
assert not short, ("zh under 256", short)
assert len(zh) >= 24, ("zh count", len(zh))
assert len(zh_pos) >= 10, ("zh pos", len(zh_pos))
assert len(zh_neg) >= 14, ("zh neg", len(zh_neg))
lines = [json.dumps(o, ensure_ascii=False) for o in OUT]
(DIR / "batch_zh_long.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
pavg = sum(len(o["text"]) for o in zh_pos) / len(zh_pos)
navg = sum(len(o["text"]) for o in zh_neg) / len(zh_neg)
print("total=%d zh=%d zh_pos=%d zh_neg=%d" % (len(OUT), len(zh), len(zh_pos), len(zh_neg)))
print("zh pos avg=%.0f neg avg=%.0f drift=%.1f%%" % (pavg, navg, abs(pavg - navg) / pavg * 100))
print("zh min len=", min(len(o["text"]) for o in zh))
print("en pos=%d en neg=%d" % (sum(1 for o in OUT if o["lang"]=="en" and not o["is_negative"]),
                               sum(1 for o in OUT if o["lang"]=="en" and o["is_negative"])))
from collections import Counter
print("scenarios=", sorted(set(o["scenario"] for o in OUT)))
print("turn_types(pos)=", sorted(set(o["turn_type"] for o in OUT if o["has_turn"])))
