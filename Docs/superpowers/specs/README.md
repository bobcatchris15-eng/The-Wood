# Save/resume design — three candidates

`2026-10-06-save-resume-design.md` is **W12**, chosen as primary. Two alternates
are kept here because they contain material the primary does not, and because
discarding a reviewer's work without reading it is exactly the failure mode this
repository's specification warns about.

All three came from the same assignment. They are **competing designs, not
revisions** — they disagree on mechanism, not on requirements.

## Why W12 is primary

- Longest and most complete coverage of the four areas `Specification.md` §11
  requires: save format, fresh identity for a forgotten region, journalling
  pending generation jobs, and landmark stability on resume.
- Opens with §2 *"What the code does today (evidence)"*, so every later claim is
  anchored to an actual line rather than an assumption.
- §4.5 *"Retirement must be exact, not radius-based"* identifies a failure mode the
  other two do not discuss.

## What the alternates have that W12 does not

**`save-resume-W05-alt.md`** (412 lines)
- §2.2 **epoch-based identity** — a concrete mechanism for fresh identity, framed
  against why the current cell identity cannot express forgetting.
- §2.5 **the forget ledger** — an explicit durable record of retired cells,
  which is the thing that makes "cannot be regenerated from the same seed"
  enforceable rather than aspirational.
- §4.3 specifies a **32-byte file header**. W12 specifies a container and size but
  not a byte layout.
- §2.4 is deliberate and worth preserving: *warp stays seed-only*. Warping must
  not change when a cell is forgotten, or forgetting would alter the terrain
  *around* the forgotten place and break landmark recognition.

**`save-resume-W10-alt.md`** (381 lines)
- §2 **what must and must not be saved** — the negative case, stated as a rule.
  Useful as a review checklist.
- §3.3 a **record grammar** and §3.4 an in-memory shape, i.e. a concrete parser
  target rather than prose.
- §5 explicitly separates the journal of pending generation jobs, matching §11's
  wording most literally.

## Open decision

None of the three has been reviewed against each other by a human. Before this
becomes implementation guidance, someone needs to choose:

1. **Identity mechanism** — W12's `wood::Identities` derivation, or W05's epoch
   counter plus forget ledger. W05's ledger is the stronger guarantee that a
   forgotten cell cannot be regenerated; W12's is simpler.
2. **On-disk shape** — W05's fixed binary header, W12's two-layer container, or
   W10's line format with a grammar.
3. **Whether a forget ledger is mandatory.** If forgetting must be provable, a
   durable retired-cell record is not optional, which argues for W05's approach
   regardless of which identity scheme wins.

## Provenance

Produced by StatefulClanker workers in isolated worktrees; uncommitted until
this integration. Branch names: `clanker/w-12/save-resume-and-forgetti` (primary),
`clanker/w-05/...` and `clanker/w-10/...` (alternates).