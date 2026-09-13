RAW = []
A = RAW.append

# --- clausal-adversative positives: 7 short (turn early), 8 medium ---
A(("fb-an-linear-forecast", "analysis", "clausal-adversative", "But ", None,
   "A linear forecast is defensible for the next quarter. But the series has a clear seasonal shape the line ignores, so it will miss every peak. Fit a seasonal model first."))
A(("fb-coding-global-lock", "coding", "clausal-adversative", "But ", None,
   "Start with a global lock; it is the quickest correct fix. But six workers share it, so throughput drops to one job at a time. Shard the lock by account instead."))
A(("fb-pln-poll-push", "planning", "clausal-adversative", "But ", None,
   "Keep the polling loop, it is simple and already tested. But the broker now supports push subscriptions, so polling is pure waste. Switch to push and drop the latency."))
A(("fb-teach-search-assumptions", "teaching", "clausal-adversative", "But ", None,
   "Show binary search on a sorted array first. But students then apply it to linked lists, where it is useless without random access. State the access-cost assumption up front."))
A(("fb-dbg-timeout-bump", "debugging", "clausal-adversative", "But ", None,
   "The obvious fix is to raise the client timeout from two to ten seconds. But the dependency's p99 is already nine seconds, so that just hides a sick service. Profile the downstream call first."))
A(("fb-an-classifier-shift", "analysis", "clausal-adversative", "But ", None,
   "Sentiment looks like it improved this month. But the classifier was upgraded mid-month, so the shift may be in the model rather than the users. Re-score last month with the new model."))
A(("fb-coding-env-secrets", "coding", "clausal-adversative", "But ", None,
   "Storing the secrets in the repo is convenient for local runs. But the repo is cloned onto every contractor laptop, so the convenience is the whole leak. Move them to a vault and inject at deploy time."))

A(("fb-coding-composite-index", "coding", "clausal-adversative", "But ", None,
   "I would add a composite index on tenant and created_at, because the tenant-scoped listing query is the slowest thing on the dashboard and a single-column index only helps tiny tenants. The planner would use the leading column and filter the rest, which is what we want. But the write path inserts a million rows an hour and every index taxes that, so I want the insert regression measured on a staging copy before shipping it."))
A(("fb-pln-roadmap-cut", "planning", "clausal-adversative", "But ", None,
   "My recommendation is to cut the reporting module from this quarter, since it is the least requested item and the team is already carrying a slipped migration. That frees two engineers for the billing work, which is what the roadmap actually needs. But reporting is the one feature the two largest accounts asked for by name, and losing them costs more than a slipped migration. I want that tradeoff priced before we cut anything."))
A(("fb-an-sample-bias", "analysis", "clausal-adversative", "Yet ", None,
   "The experiment sample should be representative because we randomize at the account level and the assignment buckets were balanced at the start. That is a clean design and I would defend it in review. Yet the analysis only includes accounts that stayed active for the whole window, which drops the churned ones and biases the result upward. I need an intention-to-treat read instead."))
A(("fb-teach-threads-channels", "teaching", "clausal-adversative", "But ", None,
   "Threads are the right first model for concurrency, because they map onto the hardware and the mental picture is intuitive. Students can watch parallelism happen on their own laptop. But threads also make shared state the default, and beginners lose weeks to races that a message-passing model would never create. I now teach channels first and bring threads in as an optimization."))
A(("fb-dbg-replica-lag", "debugging", "clausal-adversative", "But ", None,
   "The read replica is lagging, so I planned to route reads back to the primary until it catches up. That is the safe move in the middle of an incident and it needs no code change. But the primary is already at eighty percent CPU and carries all the writes, so pulling reads over will tip it. Throttling the bulk import that caused the lag is the better lever."))
A(("fb-coding-api-version", "coding", "clausal-adversative", "Yet ", None,
   "I want to add v2 endpoints alongside v1 so clients can migrate at their own pace and we never break anyone. Additive versioning is the least disruptive path and it is what we promised at the last review. Yet maintaining two shapes doubles the surface for bugs, and the team is six people, not sixty. A single version with a deprecation window and a thin compatibility shim is more realistic for us."))
A(("fb-pln-build-buy", "planning", "clausal-adversative", "But ", None,
   "Building the scheduler in house gives us exactly the semantics our workflow needs and removes a vendor from the critical path. That control is worth real money and the two engineers want to do it. But the maintenance burden of a cron subsystem never ends, and those same two engineers would own it forever. The hosted option is cheaper than that even at three times the licence fee."))
A(("fb-teach-tdd", "teaching", "clausal-adversative", "But ", None,
   "Test-first is the discipline I would teach, because it forces the design conversation before the code exists and it guarantees the tests are runnable. The pedagogy is sound and employers ask for it. But beginners write tests that merely restate the implementation, which locks in the same misunderstanding twice. I now teach example-driven development and introduce test-first once they can name a behaviour."))
