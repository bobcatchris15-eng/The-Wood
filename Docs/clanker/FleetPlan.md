# Fleet plan — 2026-10-07

The Wood is a concept toy being used to exercise the StatefulClanker machinery and
to characterise models. This plan is the operator's brief for the first parallel
fleet.

## End goal (from Docs/Specification.md)

Milestone 1 is the gate: "a generated place worth exploring" — bounded world,
multiple seeds, continuous routes, temperate forest adjoining rocky highlands,
outcrops, a connected stream, an overlook, sunless lighting, photography, and two
independently progressing regional light cycles with a blended boundary.

Docs/Status.md states plainly that the **photographic acceptance gate is open** and
that packaged-build performance is unverified. The Ryzen AI 7 PRO 350 / Radeon 860M
is explicitly not a certified reference machine. So the honest state is: most of
the machinery exists, and the two gates nobody can currently close are visual
acceptance and measured performance.

## Why audit rather than build

Adding features to a UE5.8 project from this session is blocked in practice:
editor startup, shader compilation and packaged builds are slow and quota-limited,
and this machine cannot certify 60fps anyway. Six independent read-and-report
tasks exercise the full orchestration loop — spawn, worktree isolation, model
selection, receipts, monitoring — without competing for a build lock.

Two tasks do write files, both new documentation/harness files that cannot
collide: a save/resume design note and a profiling script.

## Fleet

| # | Task | Profile | Model |
|---|---|---|---|
| 1 | Streaming correctness audit | implementation | opencode-go/space-bunny |
| 2 | Test coverage vs acceptance gates | review | opencode-free/fledge-alpha-free |
| 3 | Documentation honesty audit | review | selection |
| 4 | Save/resume + forgetting design | architecture | selection |
| 5 | Packaged performance harness | implementation | selection |
| 6 | Ruin/unreal probability audit | research | selection |

Tasks 1–6 are independent. None needs another task's output.

Task 2 is deliberately pinned to `fledge-alpha-free`, and task 1 to
`opencode-free/exo-free`, because those two are under behavioural study. See
`Docs/clanker/ModelDossier.md`.

## Model routing rationale

Paid `opencode-go` models handle the work that must actually land. They go through
pi's native tool calling, so worktree isolation is real.

`exo-free` and `fledge-alpha-free` reach the model through `Tools/oc-proxy`,
which emulates tool calling with a prompt protocol. Those models are therefore
assigned work whose value is **observation**, not output: how they behave when
the tool protocol is the only sanctioned route.

## Success criteria

- Every worker produces a receipt with a real summary.
- No worker writes outside its own worktree.
- The operator observes results and integrates them; it does not forward raw
  transcripts.
- The dossier records concrete, reproducible observations, not impressions.