RAW = []
A = RAW.append

A(("fb-pln-release-window", "planning", "strong-phrase", "However,", None,
   "I would schedule the release for Thursday evening, when traffic is lowest and the on-call rotation is fully staffed. The migration is small, so a quiet window should absorb any hiccup without paging anyone. However, checking the holiday calendar I see Thursday is a regional holiday in our largest market, which means support coverage is thinner than usual. A Tuesday morning deploy with everyone at their desks is the safer bet, and the slightly higher traffic is manageable if we watch the error budget."))

A(("fb-coding-config-loader", "coding", "strong-phrase", "Having said that,", None,
   "I will keep the YAML config loader as the single source of truth so operators only have one file to edit. That keeps onboarding simple and avoids drift between formats. Having said that, the loader silently ignores unknown keys, which is exactly how the last outage started when a typo in a key name went unnoticed for two weeks. I want strict schema validation that fails loudly on unrecognized fields before we ship this."))

A(("fb-an-churn-metric", "analysis", "strong-phrase", "On the other hand,", None,
   "My initial read of the dashboard says monthly churn is improving, because the headline number dropped from 4.1 to 3.6 percent. That looks like the onboarding changes are finally paying off. On the other hand, the improvement is entirely in the free tier, while the paid cohort churns faster than it did before. If revenue is the real question, the metric we should be watching is paid retention, not the blended rate."))

A(("fb-teach-recursion", "teaching", "strong-phrase", "Nevertheless,", None,
   "The cleanest way to explain recursion to beginners is with the factorial function, because the base case and the recursive step are both obvious. Most students grasp it in a single lecture that way. Nevertheless, I have watched too many of them leave believing recursion is only about arithmetic, so they freeze when they later meet a tree traversal. I now start with directory walking instead, where the self-similar structure is visible in the problem itself."))

A(("fb-dbg-latency-spike", "debugging", "strong-phrase", "However,", None,
   "I was ready to blame the new search feature for the latency spike, since it landed the same morning the p99 doubled. The timing is too neat to be a coincidence. However, the trace data shows the spike is concentrated in writes, and search is a read-only path. The real regression is in the write-ahead log flush, which started batching more aggressively after a config change that nobody linked to this incident."))

A(("fb-coding-orm-choice", "coding", "strong-phrase", "However,", None,
   "Let me standardize the team on the existing ORM rather than introduce a query builder, since everyone already knows its escaping rules and the migration cost is zero. Consistency has real value here. However, profiling the reporting endpoints shows the ORM generates N+1 queries that no amount of eager loading fixes, and those endpoints are our slowest. We should adopt a thin SQL layer just for reporting and keep the ORM everywhere else."))

A(("fb-pln-hiring-plan", "planning", "strong-phrase", "However,", None,
   "The hiring plan should focus on two senior backend engineers, because our queue of infrastructure work is deep and needs people who can own it end to end. Juniors would need too much mentoring right now. However, looking at the last two quarters, our seniors are already at capacity mentoring the mid-level hires we made in spring. A senior plus two strong mid-level hires spreads the load better."))

A(("fb-an-ab-test", "analysis", "strong-phrase", "On the other hand,", None,
   "The A/B test looks like a clear win: the variant lifts conversion by 2.3 percent with a p-value under 0.01. I would roll it out to everyone this week. On the other hand, the lift is concentrated in returning desktop users, and the sample is only eleven days long. That pattern usually means novelty rather than a durable effect, so I would extend the test two more weeks before committing."))

A(("fb-teach-indexing", "teaching", "strong-phrase", "Nevertheless,", None,
   "For teaching indexes, I like the phone book analogy, because it maps directly onto a B-tree lookup and students remember it. It has served me well for years. Nevertheless, the analogy quietly teaches that an index always makes reads fast, which is false for low-selectivity columns, and I keep having to unteach it. I now pair it with a counterexample where the index makes the planner slower."))

A(("fb-dbg-memory-leak", "debugging", "strong-phrase", "Having said that,", None,
   "My best guess is that the memory leak lives in the image thumbnail cache, because RSS climbs steadily only on pages that render galleries. Nothing else correlates as tightly. Having said that, I disabled the cache on staging and the leak persisted, just more slowly. That pushes me toward the upload pipeline holding decoded bitmaps alive, which I will test by dropping the queue size to one worker."))

A(("fb-coding-error-taxonomy", "coding", "strong-phrase", "However,", None,
   "I plan to model failures with a single generic error type and a string code, because it is easy to serialize and the surface area stays small. That keeps the client simple. However, callers keep branching on those strings, which is brittle and untestable. Typed error variants with exhaustive matching would remove the guesswork, so I am switching the design before anyone depends on the codes."))

A(("fb-pln-data-backfill", "planning", "strong-phrase", "However,", None,
   "I would run the backfill as one long transaction so the table is never in a half-migrated state and readers see a consistent snapshot. That is the simplest correctness story. However, it will hold locks on the hottest table for hours, which we cannot afford during business hours. Chunked batches with a resumable cursor are worth the extra bookkeeping."))

A(("fb-an-user-survey", "analysis", "strong-phrase", "On the other hand,", None,
   "The survey responses suggest users love the new navigation, with 78 percent rating it easy to find things. I would double down on the same layout for the mobile app. On the other hand, the survey only reached people who completed onboarding, which quietly excludes exactly the users who got lost. Session recordings from the drop-off cohort suggest the opposite conclusion, so I would not redesign mobile yet."))

A(("fb-teach-big-o", "teaching", "strong-phrase", "Nevertheless,", None,
   "Big-O is best introduced as counting operations rather than timing them, because it isolates growth from hardware noise. Students get the idea quickly with nested loop examples. Nevertheless, they then treat the notation as a precise prediction and are shocked when an n log n sort loses to insertion sort on small arrays. I now spend a full session on constants and cache effects."))

A(("fb-dbg-flaky-test", "debugging", "strong-phrase", "Having said that,", None,
   "The flaky integration test is almost certainly a race between the fixture teardown and the background job it triggers, since the failure only appears when the suite runs in parallel. Serial runs pass every time. Having said that, I ran the suite serially ten times overnight and it failed twice, so the race is not the whole story. There is also a hardcoded timestamp that breaks after midnight, which I will fix first because it is cheap."))
