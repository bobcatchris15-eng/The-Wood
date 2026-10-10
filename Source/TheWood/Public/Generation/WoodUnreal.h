#pragma once
#include <cstdint>
#include "Generation/WoodSalts.h"

// Unreal regional overlays. Everything is inline so the standalone core suites, which compile
// WoodGeneration.cpp without this file's .cpp, keep linking.
namespace wood {
// Complete at this declaration (fixed underlying type); defined in WoodGeneration.h with the same type.
enum class Biome : int;
namespace unreal {
// Names are the first five unreal motifs in Docs/BiomeCatalog.md (43-47). None is reserved for ordinary regions.
enum class Overlay : std::uint8_t { None, ExcessivelyFungal, LuminousMoss, UnnaturallyDark, PaleEnchanted, GlassyMineral };

// Multipliers against ordinary generation. featureScale and densityScale multiply habitat feature scale and
// acceptance density (tree, ground cover, rock layers). lightBrightness multiplies cell brightness, lightKelvinShift
// adds to cell colour temperature (K). windScale and tint are presentation hints for the engine adapter.
struct OverlayParams { double featureScale, densityScale, lightBrightness, lightKelvinShift, windScale; float tintR, tintG, tintB; double fungusScale; };

// Documented table. None is the identity in every field.
//  ExcessivelyFungal (43): large fruiting bodies; bigger, slightly denser, warm dim light, shelf-brown tint, fungi x3.
//  LuminousMoss     (44): soft emission light; ordinary scale, sparser cover, dimmer cool-green tint.
//  UnnaturallyDark  (45): light absorbed beneath crowns; denser canopy, markedly darker, slightly cool.
//  PaleEnchanted    (46): ivory bark, subdued wind; brighter, cooler, near-neutral tint.
//  GlassyMineral    (47): translucent forms; slightly larger, sparser, brighter cool light, blue-leaning tint.
constexpr OverlayParams params(Overlay overlay) {
 switch(overlay) {
 case Overlay::ExcessivelyFungal: return {1.9, 1.25, 0.85, -150.0, 0.8, 1.00f, 0.92f, 0.84f, 3.0};
 case Overlay::LuminousMoss:      return {1.0, 0.90, 1.10, 150.0, 1.0, 0.85f, 1.00f, 0.90f, 1.0};
 case Overlay::UnnaturallyDark:   return {1.0, 1.30, 0.55, 100.0, 1.0, 0.85f, 0.85f, 0.90f, 1.0};
 case Overlay::PaleEnchanted:     return {1.05, 0.85, 1.15, 300.0, 0.6, 0.98f, 0.98f, 1.00f, 1.0};
 case Overlay::GlassyMineral:     return {1.15, 0.90, 1.05, 200.0, 1.0, 0.92f, 0.97f, 1.05f, 1.0};
 case Overlay::None:              break;
 }
 return {1.0, 1.0, 1.0, 0.0, 1.0, 1.0f, 1.0f, 1.0f, 1.0};
}

inline std::uint32_t mixBits(std::uint32_t h) { h^=h>>16; h*=0x7feb352du; h^=h>>15; h*=0x846ca68bu; return h^(h>>16); }

// Deterministic overlay for an unreal region, from its per-region identity (not the shared epoch-0 seed) and biome family. Never returns None.
inline Overlay pick(std::uint32_t regionSeed, Biome family) {
 const auto f=static_cast<std::uint32_t>(family);
 const std::uint32_t h=mixBits(regionSeed^mixBits(Salt::RegionOverlay^(f*0x9e3779b9u)));
 return static_cast<Overlay>(1+h%5);
}

// Hex-weighted overlay multipliers at one point. Ordinary cells contribute neutral values, so the field
// fades across the existing blend band. active is false, and every value neutral, unless an unreal cell has weight.
// fungusScale multiplies the fungus ground-cover ceiling; unrealWeight is the unreal-cell share of the blend (0..1), gating unreal-only flora.
struct OverlayField { double featureScale=1, densityScale=1, lightBrightness=1, lightKelvinShift=0, fungusScale=1, unrealWeight=0; bool active=false; };
}
}
