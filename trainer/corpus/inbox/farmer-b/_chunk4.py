RAW = []
A = RAW.append

# --- self-correction positives: 6 short (turn early), 4 medium ---
A(("fb-an-growth-rate", "analysis", "self-correction", "Actually,", None,
   "Growth is compounding at eight percent a month. Actually, that is the week-over-week figure annualized by mistake; the true monthly rate is nearer three percent."))
A(("fb-coding-null-guard", "coding", "self-correction", "Actually,", None,
   "The crash is a null dereference on the parser's field access, so guard there. Actually, the field is never null; the object is unset because the constructor throws earlier. Trace the constructor."))
A(("fb-dbg-cpu-attribution", "debugging", "self-correction", "Actually,", None,
   "The CPU spike comes from the log filter's regex. Actually, the profiler attributes four percent to that; the spike is the JSON encoder allocating on every line."))
A(("fb-an-definition-drift", "analysis", "self-correction", "Actually,", None,
   "Active users fell for the third month running. Actually, the drop is definitional: the SDK now emits session starts where it used to emit logins."))
A(("fb-pln-estimate-basis", "planning", "self-correction", "Actually,", None,
   "The migration will take six weeks at two engineers. Actually, that estimate assumes the schema is frozen, and it is not, so six weeks is a floor rather than an estimate."))
A(("fb-coding-cache-key", "coding", "self-correction", "Actually,", None,
   "The cache miss rate is high because the key includes the locale. Actually, it includes a session id that changes on every request, so nothing ever hits the cache at all."))

A(("fb-pln-team-topology", "planning", "self-correction", "Actually,", None,
   "I argued for splitting the team along frontend and backend lines so each group could specialise and hire against a clear profile. That is the textbook structure and it scales cleanly as headcount grows. Actually, our last three features each required one person to touch both ends, so the split added handoffs without adding expertise. I now think a feature-aligned split is right for a team our size."))
A(("fb-coding-pool-size", "coding", "self-correction", "Actually,", None,
   "I set the connection pool to fifty because that matched the old deployment's concurrency and the numbers looked healthy in staging. It was a safe carry-over from a system that ran fine for years. Actually, staging never sees more than five concurrent requests, so the fifty was never exercised, and in production it exhausts the database's connection limit. I need to size it from max_connections, not from habit."))
A(("fb-an-slide-definition", "analysis", "self-correction", "Actually,", None,
   "My first slide defines active users as anyone who logged in during the week, which is the definition the dashboards have always used. It keeps the series consistent with prior reporting. Actually, prior reporting counted logins while the new SDK emits session starts, so the two numbers are not comparable and part of the apparent growth is definitional. I will restate the series on one definition before anyone quotes it."))
A(("fb-teach-variables-references", "teaching", "self-correction", "Actually,", None,
   "I tell students a variable is a named box that holds a value, because it is a friendly first picture and it fits on a whiteboard. It works well for the first two weeks. Actually, in languages with references the box holds a pointer and the value lives elsewhere, so the picture breaks the moment they assign one variable to another. I now say a name refers to a value and then show two names sharing one."))

# --- hedged-return positives: 3 short (turn early), 2 medium ---
A(("fb-coding-ttl-cap", "coding", "hedged-return", "That said,", None,
   "The caching layer is worth keeping even now. That said, cap the TTL so stale data never outlives an order. I want the cache, just bounded."))
A(("fb-an-forecast-horizon", "analysis", "hedged-return", "That said,", None,
   "Planning on a twelve-month horizon is still right. That said, pair it with a three-month operating view for hiring. The long frame stays the spine."))
A(("fb-teach-lab-first", "teaching", "hedged-return", "That said,", None,
   "Opening the course with the lab is deliberate. That said, give them a ten-minute reading beforehand so nobody arrives cold. The lab still comes first."))
A(("fb-pln-free-tier", "planning", "hedged-return", "That said,", None,
   "Keeping a generous free tier is strategically right, because it is our main acquisition channel and the paid conversion from it is real. The numbers support the strategy and I would defend it. That said, I would cap it at a level that blocks obvious abuse, since a handful of heavy users currently cost more than they return. Generous stays; unmetered does not."))
A(("fb-dbg-rollback-decision", "debugging", "hedged-return", "That said,", None,
   "Rolling back the deploy is the right immediate move, because the errors started within minutes of it and a clean revert takes one command. Stabilise first, diagnose later. That said, the previous version is only two hours old and might carry the same fault, so I would glance at the error graph before trusting the revert. Revert unless the graph says otherwise."))
