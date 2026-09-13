RAW = []
A = RAW.append

A(("fb-dbg-auth-token", "debugging", "interjection", "Wait —", None,
   "I was about to raise the access token lifetime from fifteen minutes to an hour, since the refresh churn is generating a lot of noise in the logs. Longer tokens would cut that traffic roughly in half. Wait — the noise is coming from one client that ignores the expiry field entirely and refreshes on every request, so lengthening the token would just hide a bug and widen the blast radius if one leaks. Fix the client first."))

A(("fb-coding-module-split", "coding", "interjection", "Hold on,", None,
   "Let me pull the billing logic out of the monolith into its own service so it can scale and deploy independently. That decoupling is overdue and the team keeps tripping over shared migrations. Hold on, billing writes and order writes share a transaction today, and splitting them means introducing a saga for something that is currently atomic. The migration risk outweighs the deployment convenience; I would modularize in place instead."))

A(("fb-an-market-sizing", "analysis", "interjection", "Wait —", None,
   "Trying the top-down approach first, I take the reported industry revenue and apply our historical share to get a target of roughly forty million. That gives the board a number they can anchor on. Wait — the reported revenue double counts resellers, so our share of the true addressable market is nearly twice that estimate. The bottom-up build from customer counts is the number I would actually present."))

A(("fb-pln-on-call-rotation", "planning", "interjection", "Hmm —", None,
   "I would move us to a weekly on-call rotation, because a full week gives each person enough context to handle the pager without constant handoffs. Shorter rotations are notoriously disruptive. Hmm — the last time we tried weekly, two engineers burned out within a month and we quietly reverted. A four-day rotation with a dedicated shadow seems to fit our team size better."))

A(("fb-teach-pointers", "teaching", "interjection", "Oh —", None,
   "I usually introduce pointers by drawing boxes and arrows on the whiteboard, because the visual makes aliasing concrete for students who have never thought about memory. It works well for a first pass. Oh — that same drawing convinces them a pointer is a separate object that holds an address, when in C it is just a typed integer. I should redraw it as an offset into one flat array of bytes."))

A(("fb-dbg-ci-failure", "debugging", "interjection", "Wait —", None,
   "The build started failing right after we bumped the base image, so my first move is to pin the old image and confirm the failure disappears. That isolates the change cleanly. Wait — pinning the image did not fix it, which means the real difference is the dependency resolution that ran at the same time. I need to diff the lockfile before touching the image again."))

A(("fb-coding-pagination", "coding", "interjection", "Hold on,", None,
   "I will implement cursor pagination for the activity feed, since offset pagination drifts when new rows arrive and users see duplicates. Cursors are the standard fix. Hold on, our feed is sorted by a mutable score, so a cursor over the score is just as unstable as an offset when scores change. I need a stable tie-breaker like the row id in the sort key, or the cursor will skip items too."))

A(("fb-an-cohort-retention", "analysis", "interjection", "Wait —", None,
   "The cohort table says week-four retention improved to 34 percent, and I was ready to credit the new onboarding checklist. That is a six-point jump, which is large for a single change. Wait — the cohort sizes shrank sharply that month because we changed the signup source filter. The improvement is a sampling artifact, not a product win."))

A(("fb-pln-office-lease", "planning", "interjection", "Hmm —", None,
   "I recommend renewing the office lease for another three years, because the rate is locked and moving costs would exceed the savings of a smaller space. Stability matters for recruiting too. Hmm — our badge data shows peak occupancy is under a third of capacity, and hybrid is not reversing. Downsizing now, even with the moving costs, pays back in about eighteen months."))

A(("fb-teach-floating-point", "teaching", "interjection", "Oh —", None,
   "I teach floating point by showing that 0.1 plus 0.2 is not 0.3, because the surprise makes the representation stick. Students remember that demo. Oh — they walk away thinking the problem is only about decimal fractions, when the deeper lesson is that any fixed-width binary format has gaps. I should also show a case where two different computations round to the same value."))

A(("fb-dbg-deadlock", "debugging", "interjection", "Wait —", None,
   "The deadlock graph points at two queries updating the same row, so I planned to add a retry wrapper around the transaction and move on. Retries usually clear this class of problem. Wait — the graph shows a consistent lock-order inversion between the accounts and ledgers tables, which retries will not fix, just make rarer. I need to enforce a single lock ordering across both code paths."))

A(("fb-coding-cache-layer", "coding", "interjection", "Hold on,", None,
   "Adding a Redis cache in front of the product service should absorb the read spike and buy us months. It is the standard scaling lever and low risk. Hold on, the spike is on a per-user personalized endpoint, so the hit rate would be near zero and we would just add a network hop plus a new failure mode. The real fix is denormalizing the two joins that dominate those queries."))

A(("fb-an-pricing-test", "analysis", "interjection", "Wait —", None,
   "The pricing test shows the higher tier converts better than expected, so raising the price looks like free revenue. I would apply it to new signups immediately. Wait — the lift comes entirely from annual plans, and monthly plans dropped by a similar amount. Net revenue is flat, so what we learned is about plan mix, not price sensitivity."))

A(("fb-pln-vendor-choice", "planning", "interjection", "Hmm —", None,
   "Between the two vendors, I lean toward the one with the richer API, because our integration work is the biggest cost and their docs are far better. Developer velocity should decide this. Hmm — their pricing scales with events, and our volume grows superlinearly, so the richer API gets expensive fast. The cheaper vendor with a thinner API costs less over three years even including integration."))

A(("fb-teach-git-branching", "teaching", "interjection", "Oh —", None,
   "I start the branching lesson with feature branches off main, because it is the workflow most teams use and students need it for their first job. It is a practical default. Oh — that framing makes merge conflicts look like failures, when they are normal and resolving them is the actual skill. I should demonstrate a conflict deliberately and walk through the resolution."))
