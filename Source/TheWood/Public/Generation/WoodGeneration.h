#pragma once
#include <cstdint>
#include <array>
#include <vector>
#include <functional>
#include <optional>

// Engine-independent generation coordinates are metres; the Unreal adapter converts to cm.
namespace wood {
struct DiscoveryPlan;
struct Vec3 { double x=0, y=0, z=0; };
struct Settings { std::uint32_t seed=12345; double chunkSize=128; int cells=64; };
enum class Biome { TemperateForest, DryGrassland, RockyHighlands, Taiga };
// A stable regional identity on a warped 950m-radius hex lattice; extent is influence diameter.
struct Region {
 Vec3 origin; double moisture=0, roughness=0, phase=0;
 Biome family=Biome::TemperateForest;
 double extent=3100, temperature=0, canopy=0, exposure=0, shelter=0;
 std::uint32_t identity=0;
 int q=0,r=0;
 // Independent per-region flags: unreal p=0.10, ruins p=1/3.
 bool unreal=false, ruins=false;
};
struct Surface {
 double height=0, forest=0, moisture=0, slope=0, waterHeight=0, depth=0;
 // Weights follow Biome's enum order and sum to one; temperature is Celsius.
 std::array<double,4> biome{};
 double temperature=0, exposure=0, shelter=0, roughness=0;
};
enum class Kind { Tree, Fern, Grass, Rock };
struct Feature { Kind kind; Vec3 position; double yaw=0, scale=1; bool young=false; bool prairie=false; };
struct Chunk { int x=0, y=0, cells=0; std::vector<Vec3> vertices; std::vector<std::uint32_t> triangles; std::vector<Feature> features; };
struct Lighting { double brightness=0, kelvin=0; };
class World {
public:
 explicit World(Settings settings);
 Surface sample(double x, double y) const;
 Region region(int latticeX, int latticeY) const;
 std::vector<Region> regions(double x, double y) const;
 // Height of the realized grid triangles, using chunkSize/cells resolution.
 double terrainHeight(double x, double y) const;
 double streamX(double y) const;
 // Logical water half-width; runtime ribbon uses 0.92 of this value.
 double streamHalfWidth(double y) const;
 // Smooth bank weight: 1 at the bed centre, 0 at and beyond the waterline.
 static double bankProfile(double d01);
 // Water depth below the surface at (x,y); zero where dry.
 double streamDepth(double x,double y) const;
 // Terrain-only generation skips ecological work but produces identical geometry.
 Chunk generate(int x, int y, bool includeFeatures=true) const;
 // Centre of the discovery reservation nearest (x,y) whose centre lies within radius metres; empty if none.
 std::optional<Vec3> nearestDiscovery(double x, double y, double radius) const;
 // Nearest 25 m grid point within radius metres of (x,y) whose biome[family] weight is at least minWeight; empty if none.
 std::optional<Vec3> nearestBiomeCore(Biome family, double x, double y, double radius, double minWeight) const;
 Lighting lighting(double x, double y, double seconds) const;
 const Settings& settings() const { return config; }
private:
 Settings config;
 // Visits every valid discovery plan of the cells within two lattice steps of the owner cell.
 void forEachDiscoveryNear(int ownerQ, int ownerR, const std::function<void(const DiscoveryPlan&)>& fn) const;
};
struct Observation {
 bool seated=false, accelerated=false;
 double seconds=0;
 void sit(bool value);
 void accelerate(bool value);
 void advance(double realSeconds);
 double rate() const;
};
}
