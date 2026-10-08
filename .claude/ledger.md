# Spec v1.1 roadmap — orchestrator ledger
Updated: 2026-10-08 | HEAD: ebdd6c6 | Graph: 58f0e77

## Objective
Take The Wood from current prototype to Docs/Specification.md v1.1 (M1–M5) via the roadmap at
~/.claude/plans/alright-look-around-the-validated-snowglobe.md. Doubles as an evaluation of Haiku as Clanker.

## Decisions
- D1 2026-10-08: ALL dispatch = impl-worker, model haiku, effort medium (user directive; Haiku eval). Plan's [S] tasks still go to Haiku with tighter packets. Revisit only on user say-so.
- D2: Existing code is agent-built; structural change is allowed. Assets may be looted from this repo and C:\Misc\Vivarium.
- D3: Mode S (serial) by default. Mode P per-tree seed ≈ 323 MB zig + 704 MB Content/.
- D4: Orchestrator re-runs Test-Core.ps1 itself before each commit (cheap, 26 s) instead of a validate-runner.
- Prior effort (Soundscape, 2026-10-06) DONE; its open assumption carried below.

## Tasks
| id | targets | status | attempts | last return line |
|----|---------|--------|----------|------------------|
| P0.1 | CLAUDE.md | DONE f9385c9 | 1 | PASS; Fast 26s, UE build 5s incr, UE tests 4/4 30s |
| P0.2 | docs | DONE 8d9964c | 1 | PASS; 10 boxes ticked (biome-art tick = judgement) |
| P0.3 | WoodSalts.h + Generation/Discovery.cpp | DONE ebdd6c6 | 1 | PASS; pure move, also named noise seed offsets |
| P0.4 | ledger | DONE 58f0e77 | - | - |
| P0.5 | graphify | DONE | - | AST-only, 626 nodes, 37 communities, built_at 58f0e77 |

## Unverified assumptions
- Soundscape never heard in a running game (S1 closes this).

- CLAUDE.md claims "adapter in cm" — not checked against source.
