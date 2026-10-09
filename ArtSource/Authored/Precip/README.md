# Precipitation and wet-ground textures

Self-authored procedural art by `Tools/Author-Precip.py`. CC0 1.0. No third-party
inputs. Regenerate with `python Tools/Author-Precip.py` (needs Pillow, numpy).
Output is deterministic (seeded).

| File | Size | Layout | Notes |
|---|---|---|---|
| rain_streak_atlas.png / .svg | 512x512 | 4x4 grid of 128x128, index = row*4+col (16 variants) | White RGB, alpha = streak coverage. Straight alpha, no dark fringe. Premultiply on import if the material expects it. |
| snowflake_atlas.png / .svg | 512x512 | 4x4 grid of 128x128 (0-5 dendritic, 6-15 soft) | White RGB, straight alpha. Dendritic = 6 arms with 2 branch pairs. |
| rain_splash_flipbook.png / .svg | 1024x256 | 8 frames in one row, each 128x256, frame 0 = impact, frame 7 = dissipated | Ground contact at (64,236) in each frame. Ring plus droplets. |
| ripple_normal_flipbook.png | 1024x1024 | 4x4 grid of 256x256, index = row*4+col, 16 frames loop | Tangent-space normals, flat = (128,128,255). Seamless tile (integer wavevectors). Seamless loop over 16 frames. Peak slope 0.5. No SVG: procedural. |

SVG files are editable layout sources. Their PNG is the raster of record; the
script renders PNGs analytically from the same primitives, so edges may differ
by sub-pixel antialiasing if the SVG is edited and re-rasterised elsewhere.

Provenance: generated here from seeded random parameters. No external images,
fonts, or traced artwork.
