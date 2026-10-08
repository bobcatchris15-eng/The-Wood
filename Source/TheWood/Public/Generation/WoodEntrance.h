#pragma once
#include <vector>
#include "Generation/WoodGeneration.h"

// Fixed, seed-independent trailhead entrance. Active only while World::entered() is false.
// All coordinates are metres. Feature z is zero here; World fills it from terrain when it places them.
namespace wood::entrance {
// Gravel lot: 44 x 28 m centred at (LotX,LotY).
inline constexpr double LotX=0, LotY=-560, LotHalfW=22, LotHalfH=14;
// Terrain blend skirts: lot flattening 12 m, zone edge 40 m.
inline constexpr double LotSkirt=12, ZoneSkirt=40;
// Adapter-only: visual lot overlay fade-out skirt beyond the pad edge (metres).
inline constexpr double LotPadSkirt=6;
// Path is 2.4 m wide, sunk 0.08 m, with a 3 m tree-free margin beyond its edges.
inline constexpr double PathHalfWidth=1.2, PathSink=0.08, PathMargin=3;
// Zone = lot rectangle union 60 m around the path, cut off at y = ZoneEndY.
inline constexpr double ZoneMargin=60, ZoneEndY=-200;

// Distance from (x,y) to the lot rectangle; zero inside.
double lotDistance(double x,double y);
// Distance from (x,y) to the path centreline polyline.
double pathDistance(double x,double y);
// True inside the entrance zone.
bool inZone(double x,double y);
// 1 inside the zone, falling smoothly to 0 over ZoneSkirt metres outside it.
double blend(double x,double y);
// Entrance surface height: path sink and flat lot pad at lotHeight, blended over the base wilderness height.
// No zone weighting here; callers multiply by blend().
double shapedHeight(double x,double y,double base,double lotHeight);
// Approximate line of sight in the xy plane: the passage screen circles (trees and outcrops) occlude.
bool lineOfSightBlocked(Vec3 from,Vec3 to);
// Constant-seed entrance features: path forest, understory, rocks, passage screen, lot bollards and props.
std::vector<Feature> fixedFeatures();
}
