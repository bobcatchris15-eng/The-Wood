#pragma once

#include <vector>
#include <string>
#include <cstdint>
#include <functional>
#include <array>

#if __has_include("Generation/WoodGeneration.h")
#include "Generation/WoodGeneration.h"
#elif __has_include("WoodGeneration.h")
#include "WoodGeneration.h"
#else
namespace wood {
struct Vec3 { double x = 0, y = 0, z = 0; };
struct Surface {
    double height = 0, forest = 0, moisture = 0, slope = 0, waterHeight = 0, depth = 0;
    std::array<double, 4> biome{};
    double temperature = 0, exposure = 0, shelter = 0, roughness = 0;
};
}
#endif

namespace wood {

enum class DiscoveryType {
    None,
    DryStoneShelter,
    CottageCorner,
    StreamFootbridge,
    RidgeTor,
    SpringSeep,
    MossyRockHollow,
    WindthrowClearing,
    FallenLogColony,
    RidgeOverlook,
    DryStoneWallStub,
    FoundationStrip,
    StonePierStump,
    MonolithStanding,
    StaircaseToNowhere,
    RustedSword,
    StoneChessPiece,
    BrokenCrown
};

struct DiscoveryReservation {
    DiscoveryType type = DiscoveryType::None;
    Vec3 center{};
    double innerRadius = 0.0;
    double outerRadius = 0.0;

    DiscoveryReservation() = default;
    DiscoveryReservation(DiscoveryType inType, Vec3 inCenter, double inInner, double inOuter)
        : type(inType), center(inCenter), innerRadius(inInner), outerRadius(inOuter) {}
    DiscoveryReservation(DiscoveryType inType, double inX, double inY, double inInner, double inOuter)
        : type(inType), center{inX, inY, 0.0}, innerRadius(inInner), outerRadius(inOuter) {}
    DiscoveryReservation(Vec3 inCenter, double inInner, double inOuter)
        : type(DiscoveryType::None), center(inCenter), innerRadius(inInner), outerRadius(inOuter) {}
    DiscoveryReservation(double inX, double inY, double inInner, double inOuter)
        : type(DiscoveryType::None), center{inX, inY, 0.0}, innerRadius(inInner), outerRadius(inOuter) {}

    double x() const { return center.x; }
    double y() const { return center.y; }
    double z() const { return center.z; }
};

struct DiscoveryPiece {
    std::string name;
    std::string mesh;
    Vec3 position{};
    double yaw = 0.0;
    double pitch = 0.0;
    double roll = 0.0;
    double scale = 1.0;

    DiscoveryPiece() = default;
    DiscoveryPiece(std::string inName, Vec3 inPos, double inYaw = 0.0, double inScale = 1.0)
        : name(std::move(inName)), mesh(), position(inPos), yaw(inYaw), pitch(0.0), roll(0.0), scale(inScale) {}
    DiscoveryPiece(std::string inName, std::string inMesh, Vec3 inPos, double inYaw = 0.0, double inScale = 1.0)
        : name(std::move(inName)), mesh(std::move(inMesh)), position(inPos), yaw(inYaw), pitch(0.0), roll(0.0), scale(inScale) {}
    DiscoveryPiece(std::string inName, std::string inMesh, Vec3 inPos, double inYaw, double inPitch, double inRoll, double inScale)
        : name(std::move(inName)), mesh(std::move(inMesh)), position(inPos), yaw(inYaw), pitch(inPitch), roll(inRoll), scale(inScale) {}
};

struct DiscoveryPlan {
    DiscoveryType type = DiscoveryType::None;
    Vec3 position{};
    double yaw = 0.0;
    DiscoveryReservation reservation{};
    std::vector<DiscoveryPiece> pieces{};
    bool valid = false;

    DiscoveryPlan() = default;
    DiscoveryPlan(DiscoveryType inType, Vec3 inPos, double inYaw = 0.0)
        : type(inType), position(inPos), yaw(inYaw), reservation{inType, inPos, 0.0, 0.0}, pieces{}, valid(true) {}

    const Vec3& center() const { return position; }
};

bool isInsideReservation(const std::vector<DiscoveryReservation>& reservations, double x, double y, bool innerOnly = false);
bool isInsideReservation(const DiscoveryReservation& reservation, double x, double y, bool innerOnly = false);

std::uint32_t hashCell(std::uint32_t seed, int q, int r);

DiscoveryPlan planDiscovery(
    std::uint32_t seed,
    int cellQ,
    int cellR,
    const Vec3& cellCenter,
    const Surface& cellClimate,
    const std::function<double(double, double)>& heightFn,
    const std::function<double(double)>& streamXFn,
    const std::function<double(double)>& streamHWFn,
    bool ruins,
    bool unreal = false);

DiscoveryPlan generateDryStoneShelter(
    std::uint32_t seed,
    const Vec3& origin,
    const Surface& climate,
    const std::function<double(double, double)>& heightFn);

DiscoveryPlan generateCottageCorner(
    std::uint32_t seed,
    const Vec3& origin,
    const Surface& climate,
    const std::function<double(double, double)>& heightFn);

DiscoveryPlan generateStreamFootbridge(
    std::uint32_t seed,
    const Vec3& origin,
    const std::function<double(double, double)>& heightFn,
    const std::function<double(double)>& streamXFn,
    const std::function<double(double)>& streamHWFn);

DiscoveryPlan generateRidgeTor(
    std::uint32_t seed,
    const Vec3& origin,
    const Surface& climate,
    const std::function<double(double, double)>& heightFn);

DiscoveryPlan generateSpringSeep(
    std::uint32_t seed,
    const Vec3& origin,
    const std::function<double(double, double)>& heightFn);

DiscoveryPlan generateMossyRockHollow(
    std::uint32_t seed,
    const Vec3& origin,
    const std::function<double(double, double)>& heightFn);

DiscoveryPlan generateWindthrowClearing(
    std::uint32_t seed,
    const Vec3& origin,
    const std::function<double(double, double)>& heightFn);

DiscoveryPlan generateFallenLogColony(
    std::uint32_t seed,
    const Vec3& origin,
    const std::function<double(double, double)>& heightFn);

DiscoveryPlan generateRidgeOverlook(
    std::uint32_t seed,
    const Vec3& origin,
    const std::function<double(double, double)>& heightFn);

DiscoveryPlan generateDryStoneWallStub(
    std::uint32_t seed,
    const Vec3& origin,
    const std::function<double(double, double)>& heightFn);

DiscoveryPlan generateFoundationStrip(
    std::uint32_t seed,
    const Vec3& origin,
    const std::function<double(double, double)>& heightFn);

DiscoveryPlan generateStonePierStump(
    std::uint32_t seed,
    const Vec3& origin,
    const std::function<double(double, double)>& heightFn);

DiscoveryPlan generateMonolithStanding(
    std::uint32_t seed,
    const Vec3& origin,
    const std::function<double(double, double)>& heightFn);

DiscoveryPlan generateStaircaseToNowhere(
    std::uint32_t seed,
    const Vec3& origin,
    const std::function<double(double, double)>& heightFn);

DiscoveryPlan generateRustedSword(
    std::uint32_t seed,
    const Vec3& origin,
    const std::function<double(double, double)>& heightFn);

DiscoveryPlan generateStoneChessPiece(
    std::uint32_t seed,
    const Vec3& origin,
    const std::function<double(double, double)>& heightFn);

DiscoveryPlan generateBrokenCrown(
    std::uint32_t seed,
    const Vec3& origin,
    const std::function<double(double, double)>& heightFn);

} // namespace wood
