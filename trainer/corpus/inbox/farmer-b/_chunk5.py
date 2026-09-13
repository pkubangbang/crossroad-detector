RAW = []
A = RAW.append

# ===== confusable negatives: strong-phrase surface form, mid-sentence / balanced, NO turn =====
A(("fb-neg-sp-retry-policy", "coding", "none", None, "however-mid-sentence",
   "The retry policy is generous, however it also masks transient faults that we would rather see in the dashboard. Both properties are real and pull in opposite directions, so I would instrument retry counts and revisit the settings once we have a month of data."))
A(("fb-neg-sp-cost-model", "analysis", "none", None, "however-mid-sentence",
   "The cost model is simple, however it ignores the egress charges that dominate at our scale. The simplicity is a genuine virtue for reasoning and the omissions are a real gap, so the honest move is to document the assumptions and move on."))
A(("fb-neg-sp-hiring-freeze", "planning", "none", None, "on-the-other-hand-balance",
   "A hiring freeze protects the runway. On the other hand, it also freezes the two projects that generate next year's revenue. Both sides matter, and the right level of hiring is somewhere between zero and the current plan."))
A(("fb-neg-sp-typed-config", "coding", "none", None, "however-mid-sentence",
   "Typed config catches mistakes early, however it also slows down the small experiments that make the config worth having. Neither effect is decisive on its own, so we should measure how often the types actually fire before deciding."))
A(("fb-neg-sp-batch-window", "analysis", "none", None, "that-said-continuation",
   "The five-minute batch window keeps the pipeline simple and cheap. That said, it also sets a floor on end-to-end latency that some dashboards would like to beat. Both are true and we should pick the window per consumer rather than globally."))
A(("fb-neg-sp-monorepo", "planning", "none", None, "having-said-that-continuation",
   "A monorepo makes cross-service changes atomic. Having said that, it also means one slow test suite gates every service. The tradeoff is familiar and we should decide it on build times, not on principle."))
A(("fb-neg-sp-readability", "teaching", "none", None, "however-mid-sentence",
   "Readable code reviews faster, however it is not the only thing that matters in a review. Correctness and test coverage carry equal weight, so a review checklist should score all three rather than optimise for readability alone."))

# ===== confusable negatives: instructional "wait", NO turn =====
A(("fb-neg-wait-build", "coding", "none", None, "wait-for",
   "Before running the integration suite, start the local database container. Wait for the health check to report ready, then run the suite. If the container restarts, wait for the log line that says it finished migrating before you continue."))
A(("fb-neg-wait-dns", "debugging", "none", None, "wait-until",
   "To reproduce the DNS failure locally, edit the hosts file and point the service name at a black hole address. Wait until the resolver cache expires, which takes about thirty seconds, then issue the request. The retry behaviour is what we care about here."))
A(("fb-neg-wait-deploy", "planning", "none", None, "wait-until",
   "The release checklist is short. Merge to main, wait until the pipeline publishes the artifact, then promote it to staging. Leave it on staging overnight and promote to production the following morning after the smoke tests pass."))
A(("fb-neg-wait-lab", "teaching", "none", None, "wait-for",
   "For the lab, each student should fork the starter repo and clone it locally. Wait for the dependency install to finish before opening the notebook. If install seems stuck, wait for two more minutes; the native build is slow on the first run."))
A(("fb-neg-wait-index", "analysis", "none", None, "wait-for",
   "To measure the effect of the new index, rebuild it on the staging copy. Wait for the build to complete, then replay the captured query log. Compare the total execution time against the baseline and record the p95 as well as the mean."))
A(("fb-neg-wait-grafana", "debugging", "none", None, "wait-until",
   "Open the latency dashboard and set the window to twelve hours. Wait until the panel finishes loading before you change the filter, because the query is expensive and re-runs on every keystroke. Once it settles, group by endpoint."))
A(("fb-neg-wait-reindex", "coding", "none", None, "wait-to",
   "The search reindex script takes a while. Run it with the low-priority flag and wait to start the next deploy until it reports finished. Nothing else in the pipeline depends on it, so you can keep working meanwhile."))

# ===== confusable negatives: "actually" as mid-sentence clarification, NO turn =====
A(("fb-neg-act-hash", "coding", "none", None, "actually-clarification",
   "The helper looks like it validates the checksum, but the branch is actually a no-op because the comparison target is a constant. The function is otherwise fine and the callers are correct, so the fix is a one-line change to compare against the computed digest."))
A(("fb-neg-act-latency", "debugging", "none", None, "actually-clarification",
   "The endpoint that looks slowest in the trace is actually waiting on a lock the whole time. The work it does when it holds the lock is trivial, so the fix belongs in whatever serialises access rather than in the endpoint itself."))
A(("fb-neg-act-threshold", "analysis", "none", None, "actually-clarification",
   "The alert fires at ninety percent, which sounds tight, but the metric is actually a five-minute average, so brief spikes are already smoothed out. The threshold is reasonable as written and I would leave it alone for another quarter."))
A(("fb-neg-act-copy", "teaching", "none", None, "actually-clarification",
   "Assignment in this language is actually a copy of the reference, not of the object. That detail explains almost every surprising behaviour in the exercises, so it is worth pausing on before moving to collections."))
A(("fb-neg-act-cron", "planning", "none", None, "actually-clarification",
   "The nightly job that we scheduled for midnight is actually running at four in the morning, because the scheduler stores times in UTC and the cluster default is not our local zone. The job itself is healthy and the report it produces is correct."))
A(("fb-neg-act-cache", "coding", "none", None, "actually-clarification",
   "The in-memory cache is actually shared across tenants in this service, which is fine while the keys are namespaced by tenant id. The key builder already does that, so the isolation is intact and no change is needed."))
A(("fb-neg-act-replica", "debugging", "none", None, "actually-clarification",
   "The read that we thought was hitting the primary is actually going to a replica, because the routing hint is set by the transaction middleware. The consistency guarantee we documented is stronger than what the code provides, so the docs should be corrected."))
A(("fb-neg-act-p99", "analysis", "none", None, "actually-clarification",
   "The p99 we quote to customers is actually computed over a rolling day, while the dashboard shows a rolling hour. Both are legitimate, but they answer different questions, so the two numbers can differ without either being wrong."))
A(("fb-neg-act-branch", "planning", "none", None, "actually-clarification",
   "The long-lived branch we are keeping for the partner integration is actually just three commits ahead of main. It is cheap to maintain and the partner's release cycle is slow, so keeping it open costs us almost nothing."))

# ===== confusable negatives: "that said / having said that" continuing same direction, NO turn =====
A(("fb-neg-hs-runner", "coding", "none", None, "that-said-continuation",
   "The self-hosted runner cut our build times by forty percent because it avoids the cold cache that hosted runners start with. That said, the same reasoning applies to the release pipeline, which still uses the hosted pool. Migrating that one too should give us a similar win."))
A(("fb-neg-hs-partition", "analysis", "none", None, "that-said-continuation",
   "Partitioning the events table by month is the right call, since it lets us drop old partitions instantly instead of deleting row by row. That said, the same argument applies to the audit table, which is growing even faster. Include it in the same migration."))
A(("fb-neg-hs-pairing", "teaching", "none", None, "that-said-continuation",
   "Pairing narrows the feedback loop, which is why the labs in this course are all pair-based. That said, the same reasoning supports the review sessions, so those will also run in pairs. The whole course leans on fast feedback."))
A(("fb-neg-hs-budget", "planning", "none", None, "that-said-continuation",
   "Moving the infrastructure spend to a reserved plan saves about a third over on-demand pricing, and the commitment is well inside our forecast. That said, we should also reserve the database spend, where the savings are even larger. The plan extends naturally to both."))
A(("fb-neg-hs-retry", "debugging", "none", None, "that-said-continuation",
   "The retry storm yesterday came from a client that kept retrying a permanently failing request, so we added a circuit breaker at the caller. That said, the same pattern exists in the webhook dispatcher, which has no breaker at all. Apply the same fix there."))
A(("fb-neg-hs-types", "coding", "none", None, "having-said-that-continuation",
   "Adding types to the client library caught three real bugs in the first week, mostly around optional fields being treated as present. Having said that, the same benefit should follow for the CLI, which shares most of the same parsing code. Type it next."))
A(("fb-neg-hs-scope", "planning", "none", None, "that-said-continuation",
   "Cutting the scope to one payment provider for launch is the right call, because each additional provider roughly doubles the reconciliation work. That said, the same logic favours launching with one currency as well, which simplifies the ledger further. Keep trimming until launch."))
A(("fb-neg-hs-threshold", "analysis", "none", None, "that-said-continuation",
   "Lowering the alert threshold worked exactly as intended: the two silent failures last week now page within a minute. That said, the same threshold change should be applied to the queue-depth alert, which has the same blind spot. Treat both alerts together."))

# ===== confusable negatives: bare adversative inside one assessment, NO turn =====
A(("fb-neg-adv-cache-win", "coding", "none", None, "but-mid-sentence",
   "The cache cut the median read from eighty to twelve milliseconds but it also added a class of bug where stale data survives an update. Both facts are part of the same tradeoff, so we should keep the cache and fix the invalidation path rather than remove it."))
A(("fb-neg-adv-plan-speed", "planning", "none", None, "but-mid-sentence",
   "The plan is achievable but it leaves no slack for the audit that always lands in the last month. That is a property of the plan worth stating out loud, and it is why I would sequence the risky items first instead of changing the dates."))
A(("fb-neg-adv-graph", "analysis", "none", None, "yet-mid-sentence",
   "The graph looks flat yet it hides a weekly cycle that the monthly rollup averages away. Both readings are correct at their own resolution, and the honest summary should mention the cycle before anyone draws a conclusion from the trend line."))
A(("fb-neg-adv-docs", "teaching", "none", None, "but-mid-sentence",
   "The documentation is thorough but it assumes you already know the deployment model, which is the one thing the tutorials never explain. That gap is worth fixing, and it does not mean the docs are wrong, only that they start too late in the story."))
A(("fb-neg-adv-license", "analysis", "none", None, "however-mid-sentence",
   "The hosted licence is expensive however it removes an entire on-call rotation from our plate. Both parts of that sentence are doing real work, so the comparison should be priced honestly rather than dismissed as expensive."))
A(("fb-neg-adv-scaling", "coding", "none", None, "but-mid-sentence",
   "The queue decouples the producer but it makes end-to-end failures harder to trace, since the stack unwinds at the broker. That is a cost of the design and not a reason to abandon it; structured correlation ids cover most of the gap."))
A(("fb-neg-adv-vendors", "planning", "none", None, "but-mid-sentence",
   "Consolidating on one vendor saves money but it concentrates our risk in a single contract. Both effects are familiar from the last consolidation, and the mitigation is a documented exit plan rather than a second vendor."))
A(("fb-neg-adv-rewrite", "coding", "none", None, "but-mid-sentence",
   "The rewrite is clean but it will take a year and the old system still has to be maintained throughout. This is the standard shape of a rewrite and it is why I would migrate module by module and keep the old code running beside the new."))
A(("fb-neg-adv-naming", "teaching", "none", None, "yet-mid-sentence",
   "The naming convention is unusual yet it is applied consistently across the whole library. Consistency is what makes it readable, so I would leave the convention in place and simply document the reason it exists."))
A(("fb-neg-adv-verbose", "debugging", "none", None, "but-mid-sentence",
   "Verbose logging helped during the incident but it costs real money in storage every month. Both are true, and the answer is level-based retention rather than turning the logging down and losing the detail when it matters."))
