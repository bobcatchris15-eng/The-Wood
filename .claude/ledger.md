# Spec v1.1 roadmap — orchestrator ledger
Updated: 2026-10-08 | HEAD: e236f47 | Graph: 58f0e77 (stale: body+API drift)

## Objective
Take The Wood from current prototype to Docs/Specification.md v1.1 (M1–M5) via the roadmap at
~/.claude/plans/alright-look-around-the-validated-snowglobe.md. Doubles as an evaluation of Haiku as Clanker.

## Decisions
- D1 2026-10-08: ALL dispatch = impl-worker, model haiku, effort medium (user directive; Haiku eval). Plan's [S] tasks still go to Haiku with tighter packets. Revisit only on user say-so.
- D2: Existing code is agent-built; structural change is allowed. Assets may be looted from this repo and C:\Misc\Vivarium.
- D3: Mode S (serial) by default. Mode P per-tree seed ≈ 323 MB zig + 704 MB Content/.
- D4: Orchestrator re-runs Test-Core.ps1 itself before each commit (cheap, 26 s) instead of a validate-runner.
- D5 2026-10-08: Haiku halts hard at Target_Nodes edges (good), so packets must list the whole call chain: core → Runtime.h → PreparedChunk → World + WoodWorldStreaming call sites. Under-scoping cost B2b its 3 attempts. Before dispatch, grep consumers of any changed struct.
- D5b: Packets now carry a standing clause: "may edit any other file under Source/, Tests/, Tools/ strictly required; list each". Mode S makes this safe; saves a round trip per scope miss.
- D6: Art reimport skips existing versioned assets; new/changed meshes need forced replace (pattern in BootstrapEditor.py).
- D7 2026-10-08: exposure contract = <=0.25 EV per 10 m (~0.1 EV/s at walk speed); observed 0.18. Original 0.1/10m was arbitrary. Revisit if playtest shows visible brightness swells at boundaries.
- Prior effort (Soundscape, 2026-10-06) DONE; its open assumption carried below.

## Tasks
| id | targets | status | attempts | last return line |
|----|---------|--------|----------|------------------|
| P0.1 | CLAUDE.md | DONE f9385c9 | 1 | PASS; Fast 26s, UE build 5s incr, UE tests 4/4 30s |
| P0.2 | docs | DONE 8d9964c | 1 | PASS; 10 boxes ticked (biome-art tick = judgement) |
| P0.3 | WoodSalts.h + Generation/Discovery.cpp | DONE ebdd6c6 | 1 | PASS; pure move, also named noise seed offsets |
| P0.4 | ledger | DONE 58f0e77 | - | - |
| P0.5 | graphify | DONE | - | AST-only, 626 nodes, 37 communities, built_at 58f0e77 |
| P1 | stream banks, flow water, pine base, prairie, rocks 2K, spec tests | DONE | - | 3956cbf..ef5c51b |
| M1 | gate fixes: ruin/biome-framed views, moss layer | DONE (visual items on human list) | - | 4bbc1d8..e236f47 |
| G1-G9 | flags, climate families, staged pipeline, forgetting, save/resume, docs | DONE | - | 153ab73..G9 |
| E1 | EntranceZone core | IN PROGRESS | | |

## Unverified assumptions
- Soundscape never heard in a running game (S1 closes this).

- CLAUDE.md claims "adapter in cm" — not checked against source.

## Human review list (Gate M1)
- Pine trunk hard pale/dark seam ~1/3 up (Ruins view). Not the UV1 mask. Candidates: bark material slot boundary in the Poly Haven scan, or B1 soil-cut ring. Possibly pre-existing (dusk renders too dark to tell).
- Grassland clumps blend into a sward rather than distinct tussocks; ground tint reads tan not green.
- Playtest per .clanker/HUMAN_HANDOFF.md (movement feel, wading, sit/time, photos) — not doable by agents.
- Ruins read as rubble/boulder rings: no masonry kit yet. Phase 4 D0 must add cut-stone/brick/timber kit meshes (loot ambientCG CC0 rock/brick textures incl. C:\Misc\Vivarium\game\Textures).
- Taiga floor still reads olive-brown gravel; moss carpet layer exists in core (3.6x cover) but small scale barely reads. Changing the taiga tint in BootstrapEditor.py and regenerating M_Ground_BiomeV2 produces heavy contour/chevron banding — the committed .uasset is fine. Treat ground-material regeneration as fragile: diff the graph before editing it.
- HydrologyStage is computed but unused by habitat (off-grid y). Fold real hydrology (drainage, macro-basins) into it in a later task.
- Perf: Test-Core now ~140 s (was 26 s at start; growth from added tests + ~15% from epoch owner lookups). Add a per-chunk generate() time budget test before Phase 6; generation cost matters for streaming.
