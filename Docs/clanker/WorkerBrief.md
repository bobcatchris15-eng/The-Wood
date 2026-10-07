# Worker environment brief

Read this before planning. It records the tools and sources available on this
machine that are not obvious from the repository itself.

## Authoritative documents

Every task is scoped by these. Read the relevant one before making claims.

| Document | What it governs |
|---|---|
| `Docs/Specification.md` | The intended game, experience pillars, non-goals, milestones, acceptance gates. **Requirements, not claims about the build.** |
| `Docs/Status.md` | What is verified today, and what is explicitly still open. |
| `Docs/BiomeGeneration.md` | Hex cells, warped boundaries, shared edge contracts, streaming and validation rules. **Future specification.** |
| `Docs/BiomeCatalog.md` | Climate families and unreal variants. **Future specification.** |
| `Docs/DiscoveryCatalog.md` | Ruins, structures, artifacts, geological and ecological discoveries, prop kits. **Future specification.** |
| `Docs/Hardware.md` / `Docs/Assets.md` | Machine reference and asset provenance. |
| `Docs/superpowers/plans/` | Dated implementation plans. |
| `Docs/clanker/ModelDossier.md` | Measured behaviour of the models in the pool. |

**The single most important rule in this repository:** it must never overstate
what is built. `Specification.md` §11 and `Status.md` both say so explicitly. A
claim in a document that no test or file supports is a defect, not a summary.

## Toolchain

| Tool | Location | State |
|---|---|---|
| Blender | `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe` | Available |
| Unreal Engine | `C:\Program Files\Epic Games\UE_5.8` | **Reinstalling — the previous install was corrupted. Do not attempt engine builds, editor launches, or automation runs.** |
| Visual Studio 2022 Build Tools | expected at `C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools` | Absent on this machine |
| Git | on PATH | working; project is a git repo on `main` |
| MSVC / clang / gcc | — | **Not available.** `Tools/Test-Core.ps1` needs ziglang via pip |

### What this means right now

- **Engine-independent work only.** C++ source review, standalone algorithm
  reasoning, documentation, PowerShell tooling, and design are all in scope.
- **Do not promise a compile or a test run you cannot perform.** If a task seems to
  need one, say so in `unresolved_questions` and deliver the analysis anyway. A
  worker that honestly reports "no compiler present, findings are from reading the
  code" is far more useful than one that implies verification.
- Blender work is fine and does not need the engine.

## Vivarium — cross-project asset source

`E:\Vivarium` is a sibling project (Godot + .NET simulation). It is a **useful
source of plant forms**, but read this before assuming what is there.

**There are no mesh files to copy.** No FBX, OBJ, BLEND, glTF or USD exists in the
tree. Vivarium's plants are *procedurally generated*:

- `E:\Vivarium\src\Vivarium.Sim\Geometry\OrganismMeshes.cs` — organism mesh synthesis
- `E:\Vivarium\src\Vivarium.Sim\Geometry\OrganismMeshes.VisualBreakFlora.cs`
- `E:\Vivarium\src\Vivarium.Sim\Geometry\FloraLeaf.cs`, `FloraVisualCompiler.cs`
- `E:\Vivarium\src\Vivarium.Sim\Geometry\PropMeshes.cs`, `PilotTreeMeshes.cs`
- `E:\Vivarium\src\Vivarium.Sim\Flora\Flora.cs`, `FloraSystem.cs`, `AmbientGroundCover.cs`, `DeadFlora.cs`

Rendered species references exist as PNGs — 34 distinct species including
`veilfern`, `bogglass_moss`, `floodlace_moss`, `pearl_cushion_moss`,
`velvetweave_moss`, `antlerlace_lichen`, `embercrust_lichen`, `emberfan_fungus`,
`ruffle_lichen`, `spiralvine`, `mooncoin`, `frosttussock`, `dewbonnet`,
`embercrown`, `sunstone_rosette`, `prismstar`, `glassrush`, `glassfinger`,
`ringreed`, `brooklace`, `clinglace`, `ironlace`, `kiteleaf`, `lanternbrush`,
`mirrorleaf`, `shadebell`, `fenbead`, `fenhook`, `fenneedle`, `coinrunner`,
`ambervein`.

Most live under `E:\Vivarium\build\` (many are review/specimen renders, not
clean masters). Check before treating any of them as a source texture.

### So "looting" means one of three things

1. **Lift the approach.** Port the *shape language* of a Vivarium organism into
   The Wood's C++ generator. This is the highest-value option and needs no file
   copying.
2. **Export from Vivarium.** `E:\Vivarium` has a .NET CLI and a `launch-editor.cmd`.
   Determine whether an export path exists before planning around one — do not
   assume it.
3. **Use a species render as a concept reference** for silhouette and habit.

### Licensing

`Specification.md` §10 requires: free assets with suitable redistribution rights,
and **preserved source URLs, licence records and checksums**, recorded in
`Docs/Assets.md`.

Vivarium is the same owner, so redistribution is fine. Provenance is still
mandatory: anything adopted must be recorded in `Docs/Assets.md` with its origin
path. Nothing enters `Content/` undocumented.

## Rules that survive every task

- Stay inside your worktree if you have one. Workers without one are read-only by
  instruction — honour that.
- Do not represent the repository as the finished game or as achieving 60fps.
- `Specification.md` §12 is explicit that a passing compile proves compilation and
  a passing terrain test proves the condition it exercises. Neither proves a
  convincing forest.