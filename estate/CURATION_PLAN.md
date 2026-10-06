# SZL Holdings: a portfolio people can inspect and reuse

**ROADMAP — curation priorities, not completed experiments or release approval.**

The public atlas is a dated repository inventory. GitHub is the source of truth;
Hugging Face distributes model artifacts, datasets, software mirrors and kernel
packages. The company front door is [holdings.a-11-oy.com](https://holdings.a-11-oy.com),
the product is [a-11-oy.com](https://a-11-oy.com), and the proof surface is
[a11oy.net](https://a11oy.net). Each surface has its own evidence boundary.

## Start with three useful contributions

| Priority | Contribution | What a visitor should be able to inspect | Gate before stronger claims |
|---|---|---|---|
| 1 | Receipt verification software | A canonical statement, digest, signature/key binding, and explicit rejection or incomplete outcome | Replay the pinned positive and negative conformance cases; bind the package to source; obtain an independent replay |
| 2 | Formula and kernel software | Named functions, input contracts, tolerances, reference results and exact source/package revisions | Review executable bytes and dependencies; retain a fresh CPU harness; separately establish any proof correspondence or performance result |
| 3 | Proposal-only ReceiptAgent | A bounded proposal, schema/refusal checks and admission by a separate controller | Pin the qualified adapter/base/loader and held-out data; retain applied-weight coverage and independent replay; keep tool execution outside decode |

Browse their revision-bound references and observed source states in the
[research exhibits](./index.html). These exhibits do not establish fresh runtime
or model qualification.

## Make every public asset understandable

Use a consistent card: purpose, artifact type, exact source and Hub revisions,
one reproducible command, declared dependencies, input/output schema, data and
license terms, a failure example, and the scope of the evidence. Separate adapters,
GGUF derivatives, numeric fixtures, embedding tables, recipes and software kernels.
A model repository is not automatically a trained language model.

Kernel Hub distributions are a separate namespace. Their registry retains both
the package revision and the model-mirror revision, with byte parity **UNKNOWN**
unless a separate attestation establishes it. The current loader uses first-class
kernel repositories; a model-mirror URL is not a substitute for a supported loader
binding. See the [official migration guide](https://huggingface.co/docs/kernels/migration).

Dataset cards should identify provenance, terms, schemas, split identities and
limitations. Keep held-out refusal/abstention cases outside training curricula.
Before new SFT training, apply the canonical validator and Nemo R1–R5 gate.
The audit inspects metadata; dataset rows and rights clearance are **NOT RUN**.
See [dataset card guidance](https://huggingface.co/docs/hub/en/datasets-cards).

## Close the published gaps

- **Khipu:** the owner-reported 2/6 abstention denominator remains a release
  blocker. KHIPU-R2's 3/6 is not a pass. Preserve failed evidence and evaluate a
  new candidate against a fresh untouched gate before considering promotion.
- **Chaski:** original 0/5 and 2/6 results remain failed gates. Later candidate
  counts do not override an explicit NOT_PROMOTABLE or publication-ineligible
  declaration.
- **Forge:** repair the recorded failures at the pinned source revision through
  its governed workflow. A successful observation job is not a production release.
- **Kernel software:** publish a conversion/source attestation and byte hashes;
  review remote code before loading it. Measure timings against a matched
  comparator. Joules require a real meter; otherwise keep energy UNAVAILABLE.
- **Formal mathematics:** preserve the eight locked formula IDs, the machine
  749/14/163 floor and open conjectures. New proof counts or implementation
  refinement claims require canonical counted/replayed evidence.

## A focused 30-day sequence

1. **Week 1 — reuse:** finish one verifier tutorial and one pinned reproduction
   bundle. Include a valid case, a tampered case and an incomplete evidence case.
   Record exactly which checks ran and what each result establishes.
2. **Week 2 — outside replay:** invite an independent maintainer to reproduce the
   bundle. Preserve their outcome, environment, hashes and failures. Draft the
   invitation first; no outreach is implied by this roadmap.
3. **Week 3 — one measured improvement:** choose the highest-value failed gate,
   freeze a fresh held-out test, and compare a new candidate with the published
   baseline. Keep candidates separate from signed releases.
4. **Week 4 — clear publication:** publish a short tutorial, release notes,
   reproducibility bundle and honest failure analysis. Curate existing Hugging
   Face collections rather than creating duplicate lists. Collections can group
   models, datasets, Spaces and papers with context; see the
   [official collection guide](https://huggingface.co/docs/hub/en/collections).

## What to say publicly

Suggested launch wording, to revise after independent replay:

> SZL Holdings builds inspectable software for AI proposals, receipt verification
> and formula research. Our source atlas links public repositories and artifacts
> at exact revisions and makes their limits visible. Start with the receipt
> verifier, inspect a failure case, and tell us what you can reproduce.

Recognition should follow useful software, repeatable results and contributions
to other projects. Track independent reproductions, actionable issues, outside
contributors and documented user outcomes. Downloads and stars can help measure
reach; they do not establish scientific quality, safety or authorization.

This plan makes no promise of fame, leaderboard rank, production readiness or
autonomous tool execution. Training, inference, independent evaluations, energy
measurements and qualification were **NOT RUN** in the estate inventory.
