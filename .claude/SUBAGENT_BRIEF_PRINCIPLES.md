# Subagent Brief Principles

Patterns for writing effective parallel-subagent briefs for orchestration tasks (literature processing, matrix verification, log analysis, manuscript review). Applies to any task where an orchestrator spawns N read-only subagents and merges their structured output.

**Scope**: these are the principles that matter for the *brief* the orchestrator sends to each subagent. Claim/spawn/merge scaffolding belongs in the specific command's instructions (e.g. `.claude/commands/lit-orchestrate.md`); this file is about how to write the prompt that goes INTO the subagent.

Derived from observed quality differences across sessions, codified 2026-04-14.

---

## Core principles

### 1. Structured vocabulary for any graded/enumerated field

If the merge target contains values from a discrete set (relevance ratings, cell values in a capability matrix, priority tiers), **give the subagent the canonical list of allowed values in the brief**. Subagents will produce mergeable output; main-agent context isn't burned on translating synonyms.

**Bad**: "Rate relevance as HIGH/MEDIUM/LOW/NONE with a brief reason."

**Good**: "Rate relevance using these values: `HIGH` (must-cite or primary benchmark), `MEDIUM` (directly informs argument), `LOW` (contextual only), `NONE` (irrelevant). For each rating include a one-sentence reason cross-referencing the paper's Methods section."

If the vocabulary has sub-cases ("omitted" vs "conflated with X"), enumerate each case. If it's likely to grow, say so: "if the paper uses a treatment that doesn't fit the existing vocabulary, propose a new vocabulary entry and justify it."

### 2. Explicit `❌` vs `❓` rule

For any cell that might be `not addressed` vs `unclear`, separate them:
- **`❌`** — paper doesn't discuss the topic at all. Default for silence.
- **`❓`** — paper *does* discuss the topic but treatment is unclear after a careful read.

Without this rule, subagents drift toward one pole or the other and the merged output becomes unreliable.

### 3. Write vs. no-write decision per brief

State explicitly: **"Do not write to any files"** or **"Write the following files: ..."**. Hybrid batches (some subagents write, some don't) cause concurrency bugs.

- **Verification/analysis tasks** → no writes. Subagent returns structured markdown; orchestrator merges.
- **Ingestion tasks (full paper processing, log processing)** → writes typically allowed, but subagent should still return all structured output in chat so orchestrator can validate before commit. If the subagent writes AND returns output, orchestrator can diff if needed.

**Never** let multiple parallel subagents write to the same shared file (HUMAN_TODO.md, PROCESSING_QUEUE.md, topic files, matrices). Race conditions are silent failures.

### 4. Forced output format with required sections

Give the subagent an exact output skeleton with **required section markers**. The orchestrator's validation step should treat missing sections as failure (revert paper to `pending`, skip merge).

**Example**:
```
Output format:

## Matrix Row
[one markdown table row with cells in exactly this order: col1 | col2 | col3 ...]

## Notes
[3-6 bullets per paper, covering: (a) source used, (b) conflations, (c) hedges, (d) flag-for-personal-read if applicable]

## Queue Status
paper: {filename}
status: complete | skipped | failed
notes: [any blockers]
```

The orchestrator can then parse these deterministically without LLM re-interpretation.

### 5. Word/length cap

Include a word limit (e.g. "under 1000 words" or "under 200 words"). Caps force concision, prevent token-spend on framing prose, and cap per-subagent context on the orchestrator during merge.

Calibrate to task: verification briefs ≈ 1000 words; full paper-summary briefs ≈ 2000 words; small lookups ≈ 200 words.

### 6. Kill meta-narration explicitly

Include the line: **"Do not narrate your search process"** or **"Do not describe what you're about to do — just do it and report"**. Without this, subagents spend 15-30% of their output budget on "I'll now check X, then Y, then Z" framing that the orchestrator doesn't need.

### 7. Degenerate-case escalation

Tell subagents what to do when expected input is missing or degraded:

- **"If the extracted markdown is empty/garbled, fall back to the paper summary at `papers/{name}.md` and flag clearly in output."**
- **"If no Methods section exists, report which cells remain `❓` because of the missing source rather than guessing."**

Silent quality loss is the worst failure mode. Explicit escalation paths prevent it.

### 8. Flag-for-personal-read as a structured output field

For any research-synthesis task where the user may want to read primary sources firsthand, include a **"flag for personal read"** section with criteria:

- **Nearest-neighbour**: paper is within N feature-differences of the method being positioned.
- **Methodologically distinctive**: paper introduces a mechanism no other row uses.
- **Summary-resistant**: paper has ambiguity that a summary can't resolve.

Subagents marking this field explicitly (yes/no + criterion + one-sentence reason) gives the user a triage-ready list without main-agent post-processing.

### 9. Shared context block, not per-agent derivation

If all subagents in a batch need the same background (framework definitions, paper-class context, prior findings), put it in a **shared context block** at the top of each brief, not each subagent's own derivation. Consistency + saves tokens.

**Example**: "The four observation types and their *correct* likelihoods are: [table]. A naive `S(g)` for From-t₀ misses the 1/μ factor — flag it as such."

### 10. Paper paths, not paper content

When spawning, give **file paths** (`extracted/{name}.md`, `papers/{name}.md`), not the file content itself. The subagent will read what it needs. Passing content is a common anti-pattern that wastes orchestrator context and couples spawn to read-latency.

---

## Brief skeleton (copy-paste template)

```
You are {role/task in one sentence}.

**Working dir**: /workspaces/phd-research/{relevant-subtree}/

**Papers to cover** (read `{extracted-path}` for each):
1. {paper-1}
2. {paper-2}
...

**Shared context** (framework, definitions, rules):
{shared block — the stuff every subagent needs to know, written once}

**Your task for each paper**:
1. {step 1}
2. {step 2}
...

**Output format**:

## {Required section 1}
[specific structure — table row, matrix cells, bullet list, ...]

## {Required section 2}
[...]

## Queue Status (or equivalent)
{paper: name, status: complete|skipped|failed, notes: ...}

**Rules**:
- {Use ❌ for not-addressed, ❓ only for addressed-but-unclear}
- {Do not write to any files | Write these specific files: ...}
- {Under N words}
- {Do not narrate your search process}
- {If extraction is missing or degraded, fall back to {X} and flag in output}
```

---

## What goes WRONG without these principles

Observed failure modes from sessions where principles weren't applied:

- **Vocabulary drift**: three subagents return three different phrasings for the same cell value ("yes, but partial", "partially implemented", "⚠️ partial") — orchestrator has to translate.
- **Concurrent-write corruption**: two subagents edit HUMAN_TODO.md simultaneously; one overwrites the other's append.
- **Cell silence**: subagent marks `❌` for a cell it never checked, indistinguishable from a cell it checked and found unaddressed.
- **Meta-rambling**: subagent spends 400 words describing its planned search before reading anything.
- **Guessed cells**: subagent returns a confident value for a cell the source doesn't actually address, because the brief didn't authorise it to say `❓`.
- **Nearest-neighbour buried in prose**: user has to re-read every subagent report to find which papers are worth reading firsthand.

---

## Orchestrator responsibilities (not covered here)

This doc is about brief quality. The orchestrator's job — which belongs in the command instructions, not here — includes:

1. **Pre-claim duplicate check**: before spawning for a paper, `Glob papers/{surname}-*.md` to catch existing summaries under variant filenames.
2. **Serialised writes**: process subagent results sequentially during the merge phase, never in parallel.
3. **Validation gate**: require all Required Sections present before writing; revert to `pending` if missing.
4. **Crash-recovery**: filesystem-based claim markers (`.claimed` files) are more robust than in-queue status edits, at the cost of a third state file.
5. **Post-run checklist**: explicit "all valid summaries written, no stuck `in_progress`, no unhandled failures" before reporting complete.

For literature review specifically, see [manuscript/literature_review/workflow/AGENT_INSTRUCTIONS.md](../manuscript/literature_review/workflow/AGENT_INSTRUCTIONS.md) and `.claude/commands/lit-orchestrate.md`.

---

## Cross-references

- `.claude/commands/lit-orchestrate.md` — reference implementation of claim-spawn-merge for paper ingestion
- `.claude/commands/log-orchestrate.md` — same pattern for chat log processing (uses filesystem `.claimed` marker)
- `manuscript/literature_review/workflow/AGENT_INSTRUCTIONS.md` — lit-review task specifics
- Proposed: `.claude/commands/lit-matrix-sweep.md` — cell-verification variant of lit-orchestrate (scaffold pending)
