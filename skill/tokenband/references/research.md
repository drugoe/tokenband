# Research, analysis and experiments

Read the usage/context section only for that experiment type; ordinary source work uses the research rules below.

Start from a concrete question, intended decision, scope, assumptions, permitted
data/tools, acceptance criterion and stopping condition. Separate exploration
from implementation and product decisions. Reuse existing evidence before
launching new work. Basic source lookup can be done directly; a separate agent
needs a bounded verifiable result, not an automatic assignment for every query.

Use [communication](communication.md) for selective source reads and compact evidence packets. A tool-limited analyst receives the necessary verified excerpts/source bytes, provenance, dates/versions and coverage limits. Paths alone are not inputs for a text-only worker. Supplied sources permit analysis of those sources, not a claim of independent exhaustive lookup; use an authorized capable route or report the missing capability when independent retrieval is required.

Prefer primary sources and record provenance, publication/event dates and the
version actually inspected. Verify changeable or uncertain claims at execution
time. Distinguish observation, calculation, inference, hypothesis and unknown.
Document conflicting evidence and material uncertainty; do not present agreement
between models as empirical proof. Keep confidential data and credentials under
the actual authorization and permission boundaries.

For an experiment, specify the hypothesis, method, inputs/sample, controls,
metrics, confounders, environment/version and limits before interpreting results.
Keep commands, settings, seeds where applicable and artifacts sufficient to
reproduce material findings. Test the actual boundary and scenario needed for
the claim. A local simulation cannot establish external, production or real-user
behavior. Respect authorized run volume, costs and folder-specific restrictions;
do not split work to evade them. Stop at the agreed question/criterion instead
of inventing another research phase.

Substantive research conclusions/recommendations receive the [independent gate](routing.md):
check sources, method, calculations, alternatives, reproducibility and claim strength.
Map each material question/claim to inspected source/version, substantive result,
calculation/check and verified/failed/unknown evidence. [Lifecycle](lifecycle.md#engineering-and-acceptance)
owns finding dispositions and focused rechecks; routing owns counts, actual
independence and top consent. Source hashes identify content, not authority/truth.

Deliver the answer, supporting evidence, limitations, unresolved questions and
practical implication. A finished research report does not authorize deployment,
publication, changing live systems or accepting untested software. Implementation
becomes a separate authorized task with engineering and review gates.

## Usage and context experiments

Freeze baseline/candidate snapshots, matched tasks, model/effort, data/tools, cache conditions, review rubric, target metrics, tolerances, trial volume and stopping criteria before trials. Required safeguards and explicitly required behavior are accepted against correctness/quality/control criteria; report their overhead separately. Optional optimization needs measured benefit within the declared tolerances; no benefit may justify rejection. Do not call transferred primary work total-token savings.

Count setup, coordination, dispatch, retries, correction, verification and review. Report primary-family and all-model input/output, cache/reasoning subsets where disclosed, per-model usage, calls, latency and context loaded/peak context separately. Tokenizer estimates, actual counters, API-equivalent prices and subscription-limit consumption are different measures. Unknown is not zero; bytes are not tokens. Document whether cache/reasoning counts are already included, normalize cumulative counters/resets/fork replays without double-counting, and disclose heterogeneous tokenizers. Cache pricing does not shrink a context window.

Retain failed runs and reproducible settings. Report sample size, per-task variability, cold/warm cache strata and run order; include initial and stated amortized setup cost. A smoke test is not a universal savings claim. Real paid/bulk volume and qualified-host trials require their own authorization; mocks cannot establish real-host behavior. Compression formats, cache-prefix schemes and other optional machinery need measured semantic retention plus conversion/instruction overhead against plain prose/JSON. Do not add hidden-reasoning word caps or broad private-history scanning.
