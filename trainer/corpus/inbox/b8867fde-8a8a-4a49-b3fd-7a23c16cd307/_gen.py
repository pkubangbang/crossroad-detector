# -*- coding: utf-8 -*-
import json, re
SID = "b8867fde-8a8a-4a49-b3fd-7a23c16cd307"
SID8 = SID[:8]
OUT = "C:/Proj/mycc/tools/crossroad-trainer/corpus/inbox/b8867fde-8a8a-4a49-b3fd-7a23c16cd307/batch.jsonl"
CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
def cwc(text):
    no_ws = re.sub(r"\s", "", text)
    if not no_ws: return 0, "en"
    c = len(CJK.findall(no_ws))
    if c/len(no_ws) >= 0.5: return len(no_ws), "zh"
    return len([t for t in re.split(r"\s+", text) if t]), "en"
POS=[]; NEG=[]
def pos(t,s,tt,tid): POS.append((t,s,tt,tid))
def neg(t,s,tid,cj): NEG.append((t,s,tid,cj))
# ---------- English positives ----------
pos("Short and balanced restatements are easy to fold together, so let me just reuse one helper for both. Actually, no. @@The two paths have different failure semantics, so they must stay separate no matter how similar the call sites look.","coding","strong-phrase","en-pos-strong-helper")
pos("The retry loop looks solid and the backoff seems reasonable for the traffic we see today. On second thought @@we should not retry write operations at all, because a duplicate write silently corrupts the ledger.","coding","strong-phrase","en-pos-strong-retry")
pos("Wait. @@That config value is not a timeout at all; it is a concurrency limit, so passing milliseconds there is simply wrong and will crash the worker pool.","debugging","interjection","en-pos-interj-timeout")
pos("Hold on, @@the stack trace actually points at the parser, not the network layer we have been chasing for the better part of an hour.","debugging","interjection","en-pos-interj-trace")
pos("Your plan to cache the whole permission tree will make reads very fast, but @@it will also serve stale grants for up to a minute, which fails our security review outright.","planning","clausal-adversative","en-pos-clause-cache")
pos("Adopting the managed message queue removes a lot of operational work, but @@it locks us to one vendor and makes local development painful for every new hire.","planning","clausal-adversative","en-pos-clause-queue")
pos("I said parse the header synchronously before the handshake, and I still stand by that ordering, though @@the parsing itself must run async or the event loop stalls under load.","coding","self-correction","en-pos-self-parse")
pos("Earlier I told you to delete that index, but @@that was wrong; without it the nightly background job turns into a full table scan and never finishes.","debugging","self-correction","en-pos-self-index")
pos("The migration script seems harmless enough at first glance. Then again, @@it drops the old column before the backfill commits, so a mid-run crash loses everything.","debugging","hedged-return","en-pos-hedge-migrate")
pos("That naming convention feels consistent and the internal docs match it, though @@the public API names now disagree with every example we shipped last year.","analysis","hedged-return","en-pos-hedge-naming")
pos("Teaching this with a single worked example is fast and keeps the lesson moving nicely. Actually, no. @@Students who only ever see one case cannot generalize the underlying rule.","teaching","strong-phrase","en-pos-strong-teach")
# ---------- Chinese positives ----------
pos("这个合并方案听起来挺顺手，把两边当作一个函数就行，其实不对。@@两边的失败语义完全不同，强行合并迟早会在线上出事，必须先拆开。","coding","strong-phrase","zh-pos-strong-merge")
pos("等等。@@那个参数根本不是超时时间，它是并发上限，往里填毫秒只会让工作线程池直接崩掉，这个结论得马上纠正。","debugging","interjection","zh-pos-interj-param")
pos("不过，@@刚才那个结论下得太早了，我们追了半天的网络层其实是无辜的，日志里早就写明是解析器崩的。","debugging","interjection","zh-pos-interj-log")
pos("加一层缓存确实能让读取速度变快很多，但@@它会让你拿到的权限数据最多滞后一分钟，安全审查这一关根本过不了。","planning","clausal-adversative","zh-pos-clause-cache")
pos("用现成的消息队列能省下不少运维工作，不过@@它会把我们绑死在一个厂商身上，新同事本地调试也会变得很麻烦。","planning","clausal-adversative","zh-pos-clause-queue")
pos("我先前说要在握手前同步读配置，那个说法本身有问题，@@配置读取必须异步，否则并发一上来事件循环就会被卡死。","coding","self-correction","zh-pos-self-config")
pos("刚才让你删掉那个索引，其实错了。@@没有它，每晚的批处理会退化成一整夜的全表扫描，根本跑不完。","debugging","self-correction","zh-pos-self-index")
pos("这个迁移脚本乍看挺安全，不过仔细想想也不对。@@它在回填提交前就删了旧列，中途一崩所有数据就全没了。","debugging","hedged-return","zh-pos-hedge-migrate")
pos("这套变量命名读起来很统一，内部文档也能对得上，然而@@对外暴露的名字和去年发出去的示例全都不一样，用户会懵。","analysis","hedged-return","zh-pos-hedge-naming")
# ---------- English negatives ----------
neg("We should wait for the lock to be released before touching the shared buffer, otherwise two writers collide and the file ends up half-written on disk.","coding","en-neg-wait-lock","wait for")
neg("The worker must wait for the parent to signal readiness; polling too early just burns CPU cycles and logs a misleading timeout that confuses everyone.","debugging","en-neg-wait-parent","wait for")
neg("Please wait for the build to finish before you publish the artifact, because a partial bundle will break every downstream consumer that pulls it.","planning","en-neg-wait-build","wait for")
neg("This serializer is fast but also very compact on disk, which is exactly why we picked it over the alternatives for the long-term storage format in the first place, since disk is our scarcest resource.","coding","en-neg-but-add","but")
neg("The service is reliable but also cheap to run at our current volume, so it comfortably fits both the early prototype budget and the production spending plan we all agreed on last quarter.","planning","en-neg-but-cheap","but")
neg("The compiler is strict but also surprisingly helpful in practice, and its detailed error messages have already saved the whole team a great deal of tedious debugging time over the past month.","coding","en-neg-but-helpful","but")
neg("However, there is also a Python version of the same client library if your team happens to prefer working in that ecosystem instead.","coding","en-neg-however-aside","however")
neg("However, a short appendix at the end lists the optional flags; the main usage flow described above needs none of those extras at all.","teaching","en-neg-however-appendix","however")
neg("Here is the rollout plan we agreed on: first we freeze the schema and announce it, second we backfill all historical rows in batches, and third we flip the read path over in one clean cut.","planning","en-neg-first-second","first/second")
neg("First measure the baseline carefully, then apply exactly one change, then measure again so you can attribute the effect to that one change.","analysis","en-neg-first-measure","first/second")
neg("The approach is probably fine as written and it very likely scales well enough for the modest traffic we expect over the next two quarters, so I would not over-engineer it now.","analysis","en-neg-hedge-fine","hedged")
neg("This design might work and it seems broadly consistent with all the constraints we carefully listed at the start of the meeting.","planning","en-neg-hedge-might","hedged")
neg("To summarize: the cache reduces latency, the batch job reduces cost, and we keep the existing schema completely unchanged.","analysis","en-neg-summary-same","summary")
neg("In short, the current implementation is correct, has solid test coverage, and is safe to ship to production at some point later this week once review is done.","coding","en-neg-summary-ship","summary")
neg("It is important to note that this index does measurably speed up lookups along the primary key path, which is by far the hottest query path in the entire service today.","debugging","en-neg-note-index","aside")
neg("Note that the timeout is configured in whole seconds, while the concurrency value is a plain positive integer with no suffix.","coding","en-neg-note-units","aside")
# ---------- Chinese negatives ----------
neg("在改动共享缓冲区之前，我们必须先等待锁释放，否则两个写线程会撞在一起，把文件写成半截的损坏状态。","coding","zh-neg-wait-lock","等待")
neg("工人线程要一直等待父线程发出就绪信号，过早轮询只会白白浪费 CPU 时间，还会打出一条误导性的超时日志让人误判。","debugging","zh-neg-wait-parent","等待")
neg("发布产物之前请务必等待构建全部完成，否则一个半截的包会拖垮所有依赖它的下游使用方，回滚都很麻烦。","planning","zh-neg-wait-build","等待")
neg("这个序列化器的速度很快但占用的体积也很小，正是我们当初把它选来做磁盘存储格式的核心原因。","coding","zh-neg-but-add","但")
neg("这个服务运行起来很稳定但维护成本也便宜，早期原型阶段的预算和正式上线的开销它都能撑得住。","planning","zh-neg-but-cheap","但")
neg("不过，附件里还额外列了几个可选参数，上面描述的那条主流程其实一个都用不到，先忽略即可。","teaching","zh-neg-however-aside","不过")
neg("不过，这个项目其实还有一个 Python 版本的实现，如果你更习惯那个生态可以直接拿来用。","coding","zh-neg-however-python","不过")
neg("水果、蔬菜、肉类等各类食材都放在冷藏区，米面干货则统一集中在左侧靠墙的那排货架上。","teaching","zh-neg-deng-etc","等")
neg("接口、配置、日志等文件都放在仓库的根目录下，并且按照模块名字的字母顺序整整齐齐地排列。","coding","zh-neg-deng-files","等")
neg("这不过是个无关紧要的小问题，随手改一行代码就能修好，完全不必为它去重构整个模块的架构。","debugging","zh-neg-buguo-merely","不过")
neg("这不过是团队历史遗留的一套命名习惯，大家早就约定好不再去动它，以免引入额外风险。","analysis","zh-neg-buguo-legacy","不过")
neg("其实是这样的：我们先把表结构冻结，再把历史数据完整回填，最后才把读路径切换过去。","planning","zh-neg-qishi-fact","其实")
neg("其实这个工具函数只做一件事，就是把传进来的入参统一规范化之后，再原样交给下游的处理流程。","coding","zh-neg-qishi-only","其实")
neg("总体来说，加一层缓存降低了读取延迟，增加批处理降低了运行成本，而底层表结构保持完全不变。","analysis","zh-neg-summary-same","总结")
neg("总之，当前这一套实现是正确的、并且有完整的测试覆盖，本周之内就可以安全地上线运行了。","coding","zh-neg-summary-ship","总之")
neg("需要说明的是，这个索引确实能明显加快主键路径上的查询速度，这一点已经被压测验证过了。","debugging","zh-neg-note-index","说明")

# ---------- extra English negatives (longer, for length parity) ----------
neg("The connection pool sizes look reasonable and the idle timeout is generous enough, but please also keep an eye on the queue depth during the migration window next week.","planning","en-neg-but-also","but")
neg("This lookup table is small but also cheap to keep fully in memory, so loading it once at startup and never evicting it is a perfectly fine design for our scale.","coding","en-neg-but-cheap2","but")
neg("However, the fallback path only triggers when the primary region is entirely unreachable, which in practice has not happened once in the last two years of operation.","debugging","en-neg-however-fallback","however")
neg("First we confirm the regression on the staging cluster, second we bisect the commits until we find the culprit, and third we write a test that would have caught it.","debugging","en-neg-first-bisect","first/second")
neg("We should wait for all in-flight requests to drain before we restart the node, otherwise a handful of users will see a hard error page during the rolling deploy.","debugging","en-neg-wait-drain","wait for")
neg("The caching layer is effective but also introduces one more moving part that someone on call will eventually have to debug at three in the morning.","analysis","en-neg-but-movingpart","but")
neg("To summarize the discussion: we keep the current sharding key, we postpone the schema split, and we revisit the caching question after the next release.","analysis","en-neg-summary-keep","summary")
neg("The library is probably stable enough for our purposes and its API surface has not changed in a meaningful way across the last several minor releases.","coding","en-neg-hedge-stable","hedged")
# ---------- extra Chinese negatives (longer, for length parity) ----------
neg("连接池的大小看起来挺合理，空闲超时也留得足够宽，不过下周迁移窗口期间还是要盯一下队列深度，别让它堆积起来。","planning","zh-neg-but-queue","但")
neg("这张小查找表体积不大但常驻内存的成本也很低，所以启动时一次性加载进来、之后一直不淘汰，在我们这个规模下完全够用。","coding","zh-neg-but-memory","但")
neg("不过，回退路径只有在主区域彻底不可达时才会触发，而过去两年的实际运行中这种情况一次都没有发生过。","debugging","zh-neg-however-fallback","不过")
neg("我们先在预发集群上确认这个回归，再用二分法一路缩小到具体提交，最后补一个本来就能抓住它的测试用例。","debugging","zh-neg-first-bisect","先")
neg("重启节点之前，请等待所有正在处理的请求都排空，否则滚动发布期间会有一小批用户看到硬错误页面。","debugging","zh-neg-wait-drain","等待")
neg("缓存层很有效但同时也引入了一个新的活动部件，早晚会有人在凌晨三点被叫起来专门调试它。","analysis","zh-neg-but-movingpart","但")
neg("总结一下这次讨论的结论：分片键保持不变，表结构拆分往后放，缓存这个问题留到下一个版本再重新评估。","analysis","zh-neg-summary-keep","总结")
neg("这个库对我们来说大概已经足够稳定了，而且它的对外接口在最近好几个小版本里都没有出现过实质性的变化。","coding","zh-neg-hedge-stable","hedged")

records=[]
for t,s,tt,tid in POS:
    i=t.index("@@"); records.append(("pos", t.replace("@@",""), i, s, tt, tid, None))
for t,s,tid,cj in NEG:
    records.append(("neg", t.replace("@@",""), -1, s, "none", tid, cj))
seen=set(); lines=[]; p=n=1
for kind,text,fpos,sc,tt,tid,cj in records:
    wc,lang=cwc(text)
    assert len(text)>=40, (len(text), text)
    assert text not in seen, "dup "+text[:40]
    seen.add(text)
    if kind=="pos":
        rid=f"{lang}-{SID8}-P{p:04d}"; p+=1; has,ine,fv=True,False,fpos
        assert 0<=fv<len(text)
    else:
        rid=f"{lang}-{SID8}-N{n:04d}"; n+=1; has,ine,fv=False,True,-1
    rec={"id":rid,"text":text,"has_turn":has,"first_turn_pos":fv,"scenario":sc,"turn_type":tt,"is_negative":ine,"lang":lang,"word_count":wc,"topic_id":tid,"source_model":"deepseek-v4-flash:cloud","peer_session":SID,"provenance":"generated","conjunction":cj,"verified_by":[],"verdict":"pending"}
    lines.append(json.dumps(rec, ensure_ascii=False))
with open(OUT,"w",encoding="utf-8",newline="\n") as f:
    f.write("\n".join(lines)+"\n")
def st(kind,lang):
    vs=[]
    for t in records:
        if t[0]==kind:
            wc,lg=cwc(t[1])
            if lg==lang: vs.append(wc)
    return len(vs), (sum(vs)/len(vs) if vs else 0)
for lg in ("en","zh"):
    for k in ("pos","neg"):
        c,a=st(k,lg); print(f"{lg} {k}: n={c} avg={a:.1f}")
print("total:",len(lines))