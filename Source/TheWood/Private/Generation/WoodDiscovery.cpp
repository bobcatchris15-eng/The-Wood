#if __has_include("Generation/WoodDiscovery.h")
#include "Generation/WoodDiscovery.h"
#elif __has_include("WoodDiscovery.h")
#include "WoodDiscovery.h"
#endif

#if __has_include("Generation/WoodSalts.h")
#include "Generation/WoodSalts.h"
#elif __has_include("WoodSalts.h")
#include "WoodSalts.h"
#endif

#include <algorithm>
#include <vector>

namespace wood {

bool isInsideReservation(const DiscoveryReservation& reservation, double x, double y, bool innerOnly) {
    const double r = innerOnly ? reservation.innerRadius : reservation.outerRadius;
    if (r <= 0.0) {
        return false;
    }
    const double dx = x - reservation.center.x;
    const double dy = y - reservation.center.y;
    return (dx * dx + dy * dy <= r * r + 1e-9);
}

bool isInsideReservation(const std::vector<DiscoveryReservation>& reservations, double x, double y, bool innerOnly) {
    for (const auto& res : reservations) {
        if (isInsideReservation(res, x, y, innerOnly)) {
            return true;
        }
    }
    return false;
}

static constexpr double kPi = 3.14159265358979323846;

// Structural pieces bed into the terrain by this depth (metres); they never float above it.
static constexpr double kBedMin = 0.10;
static constexpr double kBedMax = 0.25;
// Mesh lengths at grammar scale 1.0 (Tools/Prepare-Art.py KIT_SPECS).
static constexpr double kDryStoneWallLen = 2.0;
static constexpr double kFoundationLen = 1.6;

struct DiscoveryRng {
    std::uint32_t state;
    explicit DiscoveryRng(std::uint32_t inSeed) : state(inSeed ? inSeed : 123456789U) {}

    std::uint32_t next() {
        state = state * 1664525U + 1013904223U;
        return state;
    }

    double nextDouble(double minVal, double maxVal) {
        double t = static_cast<double>(next() & 0xFFFFFFU) / static_cast<double>(0xFFFFFFU);
        return minVal + t * (maxVal - minVal);
    }

    int nextInt(int minVal, int maxVal) {
        if (minVal >= maxVal) return minVal;
        return minVal + static_cast<int>(next() % static_cast<std::uint32_t>(maxVal - minVal + 1));
    }
};

struct Gradient2D {
    double dx = 0.0;
    double dy = 0.0;
    double len = 0.0;
};

static Gradient2D sampleGradient(const std::function<double(double, double)>& heightFn, double x, double y, double step = 0.5) {
    if (!heightFn) return Gradient2D{};
    double zx1 = heightFn(x + step, y);
    double zx0 = heightFn(x - step, y);
    double zy1 = heightFn(x, y + step);
    double zy0 = heightFn(x, y - step);
    double gx = (zx1 - zx0) / (2.0 * step);
    double gy = (zy1 - zy0) / (2.0 * step);
    double len = std::sqrt(gx * gx + gy * gy);
    return Gradient2D{gx, gy, len};
}

std::uint32_t hashCell(std::uint32_t seed, int q, int r) {
    const std::uint32_t uq = static_cast<std::uint32_t>(q);
    const std::uint32_t ur = static_cast<std::uint32_t>(r);
    std::uint32_t h = seed ^ Salt::DiscoveryCell;
    h ^= (uq * 374761393U + ur * 668265263U);
    h = (h ^ (h >> 13)) * 1274126177U;
    return h ^ (h >> 16);
}

// Shelter walls follow an ellipse parameterised by arc length. Gaps are fixed-width
// (one doorway on the leeward side, one collapse breach), and each run is filled
// with butt-jointed SM_DryStone_Wall pieces. Pieces beside a breach are shorter,
// giving a stepped-down top toward the gap. Rubble sits at the breach foot, downslope.
DiscoveryPlan generateDryStoneShelter(
    std::uint32_t seed,
    const Vec3& origin,
    const Surface& climate,
    const std::function<double(double, double)>& heightFn)
{
    DiscoveryRng rng(seed ^ Salt::DryStoneShelterRng);
    const double centerZ = heightFn ? heightFn(origin.x, origin.y) : origin.z;
    const Vec3 shelterOrigin{origin.x, origin.y, centerZ};
    DiscoveryPlan plan(DiscoveryType::DryStoneShelter, shelterOrigin, 0.0);

    const double spanR = rng.nextDouble(6.0, 14.0);
    const double ecc = rng.nextDouble(0.0, 0.4);
    const double semiMajor = spanR;
    const double semiMinor = spanR * (1.0 - ecc);

    const double theta0 = rng.nextDouble(0.0, 2.0 * kPi);
    plan.yaw = theta0 * (180.0 / kPi);

    double windAngle = rng.nextDouble(0.0, 2.0 * kPi);
    if (climate.exposure > 0.1) {
        windAngle = theta0 + kPi * 0.25;
    }
    const double leewardAngle = std::fmod(windAngle + kPi, 2.0 * kPi);
    const double doorWidth = rng.nextDouble(1.0, 1.4);
    const double breachWidth = rng.nextDouble(1.6, 2.6);
    const double breachFrac = rng.nextDouble(0.35, 0.65);

    const Gradient2D centerGrad = sampleGradient(heightFn, origin.x, origin.y, 1.0);
    double downhillX = -centerGrad.dx;
    double downhillY = -centerGrad.dy;
    if (centerGrad.len > 0.01) {
        downhillX /= centerGrad.len;
        downhillY /= centerGrad.len;
    } else {
        downhillX = std::cos(theta0);
        downhillY = std::sin(theta0);
    }

    const double cosTh = std::cos(theta0);
    const double sinTh = std::sin(theta0);

    const double rInner = 0.85 * spanR;
    const double rOuter = 1.30 * spanR;

    // Arc-length table over the ellipse.
    const int kTable = 720;
    std::vector<double> tAt(kTable + 1);
    std::vector<double> arcAt(kTable + 1, 0.0);
    auto ringXY = [&](double t, double& x, double& y) {
        const double lx = semiMajor * std::cos(t);
        const double ly = semiMinor * std::sin(t);
        x = origin.x + lx * cosTh - ly * sinTh;
        y = origin.y + lx * sinTh + ly * cosTh;
    };
    for (int i = 0; i <= kTable; ++i) {
        tAt[i] = 2.0 * kPi * static_cast<double>(i) / static_cast<double>(kTable);
    }
    double prevX = 0.0;
    double prevY = 0.0;
    ringXY(tAt[0], prevX, prevY);
    for (int i = 1; i <= kTable; ++i) {
        double x = 0.0;
        double y = 0.0;
        ringXY(tAt[i], x, y);
        arcAt[i] = arcAt[i - 1] + std::hypot(x - prevX, y - prevY);
        prevX = x;
        prevY = y;
    }
    const double perimeter = arcAt[kTable];
    auto paramAt = [&](double s) {
        double w = std::fmod(s, perimeter);
        if (w < 0.0) w += perimeter;
        const auto it = std::upper_bound(arcAt.begin() + 1, arcAt.end(), w);
        int hi = static_cast<int>(it - arcAt.begin());
        if (hi > kTable) hi = kTable;
        const int lo = hi - 1;
        const double seg = arcAt[hi] - arcAt[lo];
        const double f = seg > 1e-12 ? (w - arcAt[lo]) / seg : 0.0;
        return tAt[lo] + f * (tAt[hi] - tAt[lo]);
    };

    // Doorway sits at the leeward point of the ring.
    double sLee = 0.0;
    double bestDiff = 1e9;
    for (int i = 0; i < kTable; ++i) {
        double x = 0.0;
        double y = 0.0;
        ringXY(tAt[i], x, y);
        double a = std::atan2(y - origin.y, x - origin.x);
        if (a < 0.0) a += 2.0 * kPi;
        double d = std::abs(a - leewardAngle);
        if (d > kPi) d = 2.0 * kPi - d;
        if (d < bestDiff) {
            bestDiff = d;
            sLee = arcAt[i];
        }
    }

    const double walkStart = sLee + doorWidth * 0.5;
    const double walkEnd = sLee + perimeter - doorWidth * 0.5;
    const double run1Len = (perimeter - doorWidth - breachWidth) * breachFrac;
    const double breachStart = walkStart + run1Len;
    const double breachEnd = breachStart + breachWidth;
    const double run2Len = walkEnd - breachEnd;

    const double taperNear = 0.55;
    const double taperFar = 0.8;

    // Scale sequence for one run. Length budget: each piece spans kDryStoneWallLen * scale.
    // taperFirst: the run starts at a breach (taper leads). Otherwise the taper closes the run.
    auto buildRun = [&](double runLen, bool taperFirst) {
        const double taperTotal = kDryStoneWallLen * (taperNear + taperFar);
        const double bodyTotal = runLen - taperTotal;
        const int n = std::max(1, static_cast<int>(std::lround(bodyTotal / kDryStoneWallLen)));
        const double bodyScale = bodyTotal / (kDryStoneWallLen * static_cast<double>(n));
        std::vector<double> seq;
        if (taperFirst) {
            seq.push_back(taperNear);
            seq.push_back(taperFar);
        }
        for (int k = 0; k < n; ++k) {
            seq.push_back(bodyScale);
        }
        if (!taperFirst) {
            seq.push_back(taperFar);
            seq.push_back(taperNear);
        }
        return seq;
    };

    auto placeRun = [&](double startS, const std::vector<double>& seq) {
        double s = startS;
        for (double sc : seq) {
            const double len = kDryStoneWallLen * sc;
            const double t = paramAt(s + 0.5 * len);

            const double tlx = -semiMajor * std::sin(t);
            const double tly = semiMinor * std::cos(t);
            const double tx0 = tlx * cosTh - tly * sinTh;
            const double ty0 = tlx * sinTh + tly * cosTh;
            const double tlen = std::hypot(tx0, ty0);
            const double tx = tx0 / tlen;
            const double ty = ty0 / tlen;
            const double nx = -ty;
            const double ny = tx;

            double x = 0.0;
            double y = 0.0;
            ringXY(t, x, y);
            const double off = rng.nextDouble(-0.03, 0.03);
            const double wx = x + nx * off;
            const double wy = y + ny * off;
            const double wz = (heightFn ? heightFn(wx, wy) : 0.0) - rng.nextDouble(kBedMin, kBedMax);
            const double wYaw = std::atan2(ty, tx) * (180.0 / kPi) + rng.nextDouble(-3.0, 3.0);

            const bool lowCourse = sc < 0.9;
            plan.pieces.emplace_back(lowCourse ? "shelter_wall_low" : "shelter_wall_base", "SM_DryStone_Wall",
                Vec3{wx, wy, wz}, wYaw, 0.0, 0.0, sc);
            s += len;
        }
    };

    placeRun(walkStart, buildRun(run1Len, false));
    placeRun(breachEnd, buildRun(run2Len, true));

    double bx = 0.0;
    double by = 0.0;
    ringXY(paramAt(breachStart + 0.5 * breachWidth), bx, by);
    const int rubbleCount = rng.nextInt(2, 3);
    for (int r = 0; r < rubbleCount; ++r) {
        const double dist = 0.6 + 0.6 * static_cast<double>(r) + rng.nextDouble(0.0, 0.3);
        const double jit = rng.nextDouble(-0.5, 0.5);
        double rx = bx + downhillX * dist - downhillY * jit;
        double ry = by + downhillY * dist + downhillX * jit;

        const double dx = rx - origin.x;
        const double dy = ry - origin.y;
        const double rdist = std::sqrt(dx * dx + dy * dy);
        if (rdist > rOuter - 0.2) {
            const double factor = (rOuter - 0.4) / (rdist > 1e-4 ? rdist : 1.0);
            rx = origin.x + dx * factor;
            ry = origin.y + dy * factor;
        }

        const double rz = heightFn ? heightFn(rx, ry) : 0.0;
        const double rYaw = rng.nextDouble(0.0, 360.0);
        const double rScale = rng.nextDouble(0.45, 0.75);
        plan.pieces.emplace_back("shelter_rubble", "SM_DryStone_Rubble",
            Vec3{rx, ry, rz}, rYaw, 0.0, 0.0, rScale);
    }

    plan.reservation = DiscoveryReservation(DiscoveryType::DryStoneShelter, shelterOrigin, rInner, rOuter);
    plan.valid = true;
    return plan;
}

DiscoveryPlan generateCottageCorner(
    std::uint32_t seed,
    const Vec3& origin,
    const Surface& climate,
    const std::function<double(double, double)>& heightFn)
{
    (void)climate;
    DiscoveryRng rng(seed ^ Salt::CottageCornerRng);
    const double centerZ = heightFn ? heightFn(origin.x, origin.y) : origin.z;
    const Vec3 cottageOrigin{origin.x, origin.y, centerZ};
    DiscoveryPlan plan(DiscoveryType::CottageCorner, cottageOrigin, 0.0);

    const double lx = rng.nextDouble(8.0, 16.0);
    const double ly = rng.nextDouble(6.0, 12.0);
    const double theta = rng.nextDouble(0.0, 2.0 * kPi);
    plan.yaw = theta * (180.0 / kPi);

    const double ux = std::cos(theta);
    const double uy = std::sin(theta);
    const double vx = -std::sin(theta);
    const double vy = std::cos(theta);

    const double hx = lx * 0.5;
    const double hy = ly * 0.5;

    const double cx[4] = {
        origin.x - ux * hx - vx * hy,
        origin.x + ux * hx - vx * hy,
        origin.x + ux * hx + vx * hy,
        origin.x - ux * hx + vx * hy
    };
    const double cy[4] = {
        origin.y - uy * hx - vy * hy,
        origin.y + uy * hx - vy * hy,
        origin.y + uy * hx + vy * hy,
        origin.y - uy * hx + vy * hy
    };

    const int survivingCornerA = rng.nextInt(0, 3);
    const int survivingCornerB = (rng.nextDouble(0.0, 1.0) < 0.5) ? ((survivingCornerA + 1) % 4) : -1;

    for (int c = 0; c < 4; ++c) {
        const double bed = rng.nextDouble(kBedMin, kBedMax);
        const double cz = (heightFn ? heightFn(cx[c], cy[c]) : 0.0) - bed;
        const double cornerYaw = (theta + static_cast<double>(c) * (kPi * 0.5)) * (180.0 / kPi);

        if (c == survivingCornerA || c == survivingCornerB) {
            plan.pieces.emplace_back("cottage_corner_pier_base", "SM_StonePier",
                Vec3{cx[c], cy[c], cz}, cornerYaw, 0.0, 0.0, 1.2);
            plan.pieces.emplace_back("cottage_corner_pier_mid", "SM_StonePier",
                Vec3{cx[c], cy[c], cz}, cornerYaw + 5.0, 0.0, 0.0, 1.05);
            plan.pieces.emplace_back("cottage_corner_pier_top", "SM_StonePier",
                Vec3{cx[c], cy[c], cz}, cornerYaw - 5.0, 0.0, 0.0, 0.9);
        } else {
            plan.pieces.emplace_back("cottage_corner_pier_ruined", "SM_StonePier_Ruined",
                Vec3{cx[c], cy[c], cz}, cornerYaw, 0.0, 0.0, 0.95);
        }
    }

    // Each wall is n butt-jointed foundation courses spanning corner to corner.
    // Piece scale is set so the mesh length equals the centre spacing exactly.
    for (int wall = 0; wall < 4; ++wall) {
        const int nextCorner = (wall + 1) % 4;
        const double wx0 = cx[wall];
        const double wy0 = cy[wall];
        const double wx1 = cx[nextCorner];
        const double wy1 = cy[nextCorner];
        const double wallLen = (wall % 2 == 0) ? lx : ly;
        const int courseCount = std::max(2, static_cast<int>(std::lround(wallLen / kFoundationLen)));
        const double spacing = wallLen / static_cast<double>(courseCount);
        const double courseScale = spacing / kFoundationLen;
        const double wallYaw = std::atan2(wy1 - wy0, wx1 - wx0) * (180.0 / kPi);
        const double tx = (wx1 - wx0) / wallLen;
        const double ty = (wy1 - wy0) / wallLen;
        const double nx = -ty;
        const double ny = tx;

        for (int s = 0; s < courseCount; ++s) {
            const double frac = (static_cast<double>(s) + 0.5) / static_cast<double>(courseCount);
            const double off = rng.nextDouble(-0.03, 0.03);
            const double sx = wx0 + frac * (wx1 - wx0) + nx * off;
            const double sy = wy0 + frac * (wy1 - wy0) + ny * off;
            const double sz = (heightFn ? heightFn(sx, sy) : 0.0) - rng.nextDouble(kBedMin, kBedMax);

            plan.pieces.emplace_back("cottage_foundation_course", "SM_FoundationCourse",
                Vec3{sx, sy, sz}, wallYaw, 0.0, 0.0, courseScale);
        }
    }

    const int rubbleCount = rng.nextInt(3, 5);
    for (int r = 0; r < rubbleCount; ++r) {
        const double roffU = rng.nextDouble(-hx * 0.7, hx * 0.7);
        const double roffV = rng.nextDouble(-hy * 0.7, hy * 0.7);
        const double rx = origin.x + ux * roffU + vx * roffV;
        const double ry = origin.y + uy * roffU + vy * roffV;
        const double rz = heightFn ? heightFn(rx, ry) : 0.0;
        const double rYaw = rng.nextDouble(0.0, 360.0);
        const double rScale = rng.nextDouble(0.5, 0.9);
        plan.pieces.emplace_back("cottage_internal_rubble", "SM_MasonryDebris",
            Vec3{rx, ry, rz}, rYaw, 0.0, 0.0, rScale);
    }

    const int fernCount = rng.nextInt(2, 4);
    for (int f = 0; f < fernCount; ++f) {
        const double foffU = rng.nextDouble(-hx * 0.6, hx * 0.6);
        const double foffV = rng.nextDouble(-hy * 0.6, hy * 0.6);
        const double fx = origin.x + ux * foffU + vx * foffV;
        const double fy = origin.y + uy * foffU + vy * foffV;
        const double fz = heightFn ? heightFn(fx, fy) : 0.0;
        const double fYaw = rng.nextDouble(0.0, 360.0);
        const double fScale = rng.nextDouble(0.7, 1.1);
        plan.pieces.emplace_back("cottage_internal_fern", "SM_FernPatch",
            Vec3{fx, fy, fz}, fYaw, 0.0, 0.0, fScale);
    }

    const double diagHalf = std::sqrt(hx * hx + hy * hy);
    const double rInner = diagHalf + 1.5;
    const double rOuter = diagHalf + 4.0;
    plan.reservation = DiscoveryReservation(DiscoveryType::CottageCorner, cottageOrigin, rInner, rOuter);
    plan.valid = true;
    return plan;
}

DiscoveryPlan generateStreamFootbridge(
    std::uint32_t seed,
    const Vec3& origin,
    const std::function<double(double, double)>& heightFn,
    const std::function<double(double)>& streamXFn,
    const std::function<double(double)>& streamHWFn)
{
    DiscoveryRng rng(seed ^ Salt::StreamFootbridgeRng);

    const double yc = origin.y;
    const double xc = streamXFn ? streamXFn(yc) : origin.x;
    double hw = streamHWFn ? streamHWFn(yc) : 5.0;
    if (hw < 2.0) hw = 2.0;

    const Vec3 bridgeCenter{xc, yc, heightFn ? heightFn(xc, yc) : 0.0};
    DiscoveryPlan plan(DiscoveryType::StreamFootbridge, bridgeCenter, 0.0);

    double streamDx = 0.0;
    if (streamXFn) {
        streamDx = (streamXFn(yc + 1.0) - streamXFn(yc - 1.0)) * 0.5;
    }
    const double tangentLen = std::sqrt(streamDx * streamDx + 1.0);
    const double tx = streamDx / tangentLen;
    const double ty = 1.0 / tangentLen;

    const double nx = -ty;
    const double ny = tx;

    const double bridgeYaw = std::atan2(ny, nx) * (180.0 / kPi);
    plan.yaw = bridgeYaw;

    const double bankDist = hw + 1.2;
    const double leftX = xc - nx * bankDist;
    const double leftY = yc - ny * bankDist;
    const double leftZ = (heightFn ? heightFn(leftX, leftY) : 0.0) - rng.nextDouble(kBedMin, kBedMax);

    const double rightX = xc + nx * bankDist;
    const double rightY = yc + ny * bankDist;
    const double rightZ = (heightFn ? heightFn(rightX, rightY) : 0.0) - rng.nextDouble(kBedMin, kBedMax);

    plan.pieces.emplace_back("bridge_abutment_left_base", "SM_BridgeAbutment",
        Vec3{leftX, leftY, leftZ}, bridgeYaw, 0.0, 0.0, 1.35);

    const double leftInX = xc - nx * (hw * 0.65);
    const double leftInY = yc - ny * (hw * 0.65);
    const double leftInZ = (heightFn ? heightFn(leftInX, leftInY) : 0.0) - rng.nextDouble(kBedMin, kBedMax);
    plan.pieces.emplace_back("bridge_abutment_left_inward", "SM_BridgeAbutment",
        Vec3{leftInX, leftInY, leftInZ}, bridgeYaw, 0.0, 0.0, 1.1);

    plan.pieces.emplace_back("bridge_abutment_right_base", "SM_BridgeAbutment",
        Vec3{rightX, rightY, rightZ}, bridgeYaw + 180.0, 0.0, 0.0, 1.35);

    const double rightInX = xc + nx * (hw * 0.65);
    const double rightInY = yc + ny * (hw * 0.65);
    const double rightInZ = (heightFn ? heightFn(rightInX, rightInY) : 0.0) - rng.nextDouble(kBedMin, kBedMax);
    plan.pieces.emplace_back("bridge_abutment_right_inward", "SM_BridgeAbutment",
        Vec3{rightInX, rightInY, rightInZ}, bridgeYaw + 180.0, 0.0, 0.0, 1.05);

    const int stepCount = rng.nextInt(3, 5);
    for (int s = 0; s < stepCount; ++s) {
        const double frac = (static_cast<double>(s) + 0.5) / static_cast<double>(stepCount);
        const double dSpan = (frac - 0.5) * (hw * 1.0);
        const double dTang = ((s % 2 == 0) ? 0.35 : -0.35);

        const double stepX = xc + nx * dSpan + tx * dTang;
        const double stepY = yc + ny * dSpan + ty * dTang;
        const double stepZ = heightFn ? heightFn(stepX, stepY) : 0.0;
        const double stepYaw = bridgeYaw + static_cast<double>(s) * 20.0;
        const double stepScale = rng.nextDouble(0.75, 0.95);

        plan.pieces.emplace_back("bridge_stepping_stone", "SM_RiverSteppingStone",
            Vec3{stepX, stepY, stepZ}, stepYaw, 0.0, 0.0, stepScale);
    }

    const double rInner = bankDist + 2.5;
    const double rOuter = bankDist + 5.0;
    plan.reservation = DiscoveryReservation(DiscoveryType::StreamFootbridge, bridgeCenter, rInner, rOuter);
    plan.valid = true;
    return plan;
}

DiscoveryPlan generateRidgeTor(
    std::uint32_t seed,
    const Vec3& origin,
    const Surface& climate,
    const std::function<double(double, double)>& heightFn)
{
    (void)climate;
    DiscoveryRng rng(seed ^ Salt::RidgeTorRng);
    const double centerZ = heightFn ? heightFn(origin.x, origin.y) : origin.z;
    const Vec3 torOrigin{origin.x, origin.y, centerZ};
    DiscoveryPlan plan(DiscoveryType::RidgeTor, torOrigin, 0.0);

    const Gradient2D centerGrad = sampleGradient(heightFn, origin.x, origin.y, 1.0);
    double strikeYaw = 45.0;
    if (centerGrad.len > 0.01) {
        strikeYaw = std::atan2(centerGrad.dx, -centerGrad.dy) * (180.0 / kPi);
    } else {
        strikeYaw = rng.nextDouble(0.0, 180.0);
    }
    plan.yaw = strikeYaw;

    const int monolithCount = rng.nextInt(3, 6);
    for (int m = 0; m < monolithCount; ++m) {
        const double angle = (static_cast<double>(m) * 2.0 * kPi / static_cast<double>(monolithCount)) + rng.nextDouble(-0.2, 0.2);
        const double dist = rng.nextDouble(1.0, 3.0);
        const double mx = origin.x + dist * std::cos(angle);
        const double my = origin.y + dist * std::sin(angle);
        const double mz = heightFn ? heightFn(mx, my) : 0.0;

        const double mPitch = rng.nextDouble(-18.0, 18.0);
        const double mRoll = rng.nextDouble(-12.0, 12.0);
        const double mYaw = strikeYaw + rng.nextDouble(-25.0, 25.0);
        const double mScale = rng.nextDouble(2.4, 3.8);

        plan.pieces.emplace_back("tor_monolith", "SM_GraniteMonolith",
            Vec3{mx, my, mz}, mYaw, mPitch, mRoll, mScale);
    }

    const double sMax = 2.0;
    const double r0 = 7.5;
    const double ringDistances[3] = { 5.5, 9.5, 14.0 };
    const int ringCounts[3] = { 6, 8, 10 };

    for (int ring = 0; ring < 3; ++ring) {
        const double r = ringDistances[ring];
        const double baseScale = sMax * std::exp(-r / r0);
        const int count = ringCounts[ring];

        for (int k = 0; k < count; ++k) {
            const double kAngle = (static_cast<double>(k) * 2.0 * kPi / static_cast<double>(count)) + rng.nextDouble(-0.2, 0.2);
            const double kDist = r + rng.nextDouble(-0.6, 0.6);
            const double kx = origin.x + kDist * std::cos(kAngle);
            const double ky = origin.y + kDist * std::sin(kAngle);
            const double kz = heightFn ? heightFn(kx, ky) : 0.0;

            const double kYaw = strikeYaw + rng.nextDouble(-30.0, 30.0);
            const double kScale = baseScale * rng.nextDouble(0.85, 1.15);

            plan.pieces.emplace_back("tor_talus_rock", "SM_TalusRock",
                Vec3{kx, ky, kz}, kYaw, 0.0, 0.0, kScale);
        }
    }

    const double rInner = 12.0;
    const double rOuter = 18.0;
    plan.reservation = DiscoveryReservation(DiscoveryType::RidgeTor, torOrigin, rInner, rOuter);
    plan.valid = true;
    return plan;
}

DiscoveryPlan planDiscovery(
    std::uint32_t seed,
    int cellQ,
    int cellR,
    const Vec3& cellCenter,
    const Surface& cellClimate,
    const std::function<double(double, double)>& heightFn,
    const std::function<double(double)>& streamXFn,
    const std::function<double(double)>& streamHWFn,
    bool ruins)
{
    const bool isHighlands = (cellClimate.biome[2] > 0.25) || (cellClimate.slope > 0.25) || (cellClimate.roughness > 0.5);

    // Guaranteed site (0, 0): produces CottageCorner or DryStoneShelter
    if (cellQ == 0 && cellR == 0) {
        if (cellClimate.forest >= 0.4 || cellClimate.biome[0] >= 0.4 || cellClimate.biome[3] >= 0.4) {
            return generateCottageCorner(seed, cellCenter, cellClimate, heightFn);
        } else {
            return generateDryStoneShelter(seed, cellCenter, cellClimate, heightFn);
        }
    }

    // Guaranteed site (1, 1) in highlands: produces RidgeTor
    if (cellQ == 1 && cellR == 1 && isHighlands) {
        return generateRidgeTor(seed, cellCenter, cellClimate, heightFn);
    }

    // Evaluate stream proximity
    const bool hasStream = (streamXFn && streamHWFn);
    double sx = 0.0;
    double hw = 0.0;
    double dStream = 1e9;
    if (hasStream) {
        sx = streamXFn(cellCenter.y);
        hw = streamHWFn(cellCenter.y);
        dStream = std::abs(cellCenter.x - sx);
    }
    const bool isStreamCrossing = hasStream && (dStream <= hw + 8.0);

    // Constructed Discovery Allocation: owning region's independent ruins flag (p=1/3)
    if (!ruins) {
        return DiscoveryPlan{};
    }

    // Grammar suitability qualification for allocated cells
    if (isStreamCrossing) {
        const Vec3 streamCenter{sx, cellCenter.y, heightFn ? heightFn(sx, cellCenter.y) : cellCenter.z};
        return generateStreamFootbridge(seed, streamCenter, heightFn, streamXFn, streamHWFn);
    } else if (isHighlands) {
        return generateRidgeTor(seed, cellCenter, cellClimate, heightFn);
    } else if (cellClimate.forest >= 0.4 || cellClimate.biome[0] >= 0.4 || cellClimate.biome[3] >= 0.4) {
        return generateCottageCorner(seed, cellCenter, cellClimate, heightFn);
    } else {
        return generateDryStoneShelter(seed, cellCenter, cellClimate, heightFn);
    }
}

} // namespace wood
