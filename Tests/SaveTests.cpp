#include "Generation/WoodSave.h"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <optional>
#include <string>
#include <vector>

using namespace wood::save;

namespace {

int failures = 0;
int checks = 0;

#define CHECK(cond) do { ++checks; if (!(cond)) { std::fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #cond); ++failures; } } while (0)

bool sameBits(double a, double b) { return std::memcmp(&a, &b, sizeof a) == 0; }

bool sameState(const SaveState& a, const SaveState& b) {
 if (a.version != b.version || a.seed != b.seed) return false;
 if (!sameBits(a.playerX, b.playerX) || !sameBits(a.playerY, b.playerY) || !sameBits(a.playerZ, b.playerZ)) return false;
 if (!sameBits(a.yaw, b.yaw) || !sameBits(a.pitch, b.pitch) || !sameBits(a.clockSeconds, b.clockSeconds)) return false;
 if (a.seated != b.seated || a.accelerated != b.accelerated || a.enteredWild != b.enteredWild) return false;
 if (a.retainedChunks.size() != b.retainedChunks.size() || a.epochs.size() != b.epochs.size()) return false;
 for (std::size_t i = 0; i < a.retainedChunks.size(); ++i)
  if (!(a.retainedChunks[i] == b.retainedChunks[i])) return false;
 for (std::size_t i = 0; i < a.epochs.size(); ++i)
  if (!(a.epochs[i].first == b.epochs[i].first) || a.epochs[i].second != b.epochs[i].second) return false;
 return true;
}

SaveState sampleState() {
 SaveState s;
 s.version = 1;
 s.seed = 4294967295u;
 s.playerX = -123456.789012345;
 s.playerY = 1e-300;
 s.playerZ = -0.0;
 s.yaw = 3.141592653589793;
 s.pitch = -1.5707963267948966;
 s.clockSeconds = 1.0e15 + 0.5;
 s.seated = true;
 s.accelerated = false;
 s.enteredWild = true;
 s.retainedChunks = {{-3, -4}, {0, 0}, {2147483647, -2147483647 - 1}};
 s.epochs = {{wood::memory::RegionKey{-7, 12}, 4294967295u},
             {wood::memory::RegionKey{0, 0}, 0u},
             {wood::memory::RegionKey{1, -1}, 1000000u}};
 return s;
}

void testRoundTripExact() {
 const SaveState s = sampleState();
 const std::string json = toJson(s);
 const auto back = fromJson(json);
 CHECK(back.has_value());
 if (back) {
  CHECK(sameState(*back, s));
  CHECK(toJson(*back) == json);   // stable under a second round trip
 }
}

void testEmptyVectors() {
 SaveState e;
 const std::string json = toJson(e);
 CHECK(json.find("\"retainedChunks\":[]") != std::string::npos);
 CHECK(json.find("\"epochs\":[]") != std::string::npos);
 const auto back = fromJson(json);
 CHECK(back.has_value());
 if (back) CHECK(sameState(*back, e));
}

void testRandomDoublesExact() {
 std::uint64_t state = 0x9E3779B97F4A7C15ull;
 auto next = [&state]() {
  state ^= state << 13;
  state ^= state >> 7;
  state ^= state << 17;
  return state;
 };
 auto fromBits = [](std::uint64_t bits) {
  double d;
  std::memcpy(&d, &bits, sizeof d);
  return d;
 };
 int tested = 0;
 for (int i = 0; i < 2000; ++i) {
  SaveState s;
  double v[8];
  for (int k = 0; k < 8; ++k) {
   double d = fromBits(next());
   while (!std::isfinite(d)) d = fromBits(next());
   v[k] = d;
  }
  s.playerX = v[0]; s.playerY = v[1]; s.playerZ = v[2]; s.yaw = v[3];
  s.pitch = v[4]; s.clockSeconds = v[5];
  s.seed = static_cast<std::uint32_t>(next());
  const auto back = fromJson(toJson(s));
  if (!back || !sameState(*back, s)) { CHECK(false); break; }
  ++tested;
 }
 CHECK(tested == 2000);
 // Denormal and negative-zero edges.
 SaveState edge;
 edge.playerX = 4.9406564584124654e-324;
 edge.playerY = -0.0;
 edge.clockSeconds = 2.2250738585072014e-308;
 const auto back = fromJson(toJson(edge));
 CHECK(back.has_value());
 if (back) CHECK(sameState(*back, edge));
}

void testMalformedRejected() {
 const char* bad[] = {
  "", " ", "{", "}", "[]", "[1]", "\"s\"", "null", "42",
  "{\"version\":1", "{\"version\":1,}", "{,}", "{\"seed\" 1}", "{\"seed\":1,,\"yaw\":2}",
  "{\"seed\":-1}", "{\"seed\":4294967296}", "{\"seed\":1.5}", "{\"seed\":1e3}",
  "{\"version\":01}", "{\"version\":\"1\"}", "{\"playerX\":\"1.0\"}", "{\"seated\":1}",
  "{\"yaw\":1e999}", "{\"yaw\":-}", "{\"yaw\":1.}", "{\"yaw\":.5}", "{\"yaw\":+1}",
  "{\"retainedChunks\":[{\"x\":1}]}", "{\"retainedChunks\":{}}", "{\"retainedChunks\":[1]}",
  "{\"epochs\":[{\"q\":1,\"r\":2}]}", "{\"epochs\":[{\"q\":1,\"r\":2,\"epoch\":-1}]}",
  "{\"seated\":true} x", "{}}", "{\"a\":\"unterminated}", "{\"a\":\"bad\\q\"}",
  "{\"a\":\"ctl\x01x\"}", "{\"a\":[1,2}", "{\"a\":\"\\u12\"}",
  "{\"version\":2}", "{\"version\":0}", "{\"version\":-1}",
 };
 for (const char* b : bad) {
  if (fromJson(b).has_value()) {
   std::fprintf(stderr, "FAIL accepted malformed: %s\n", b);
   CHECK(false);
  } else {
   ++checks;
  }
 }
 const std::string deep(100, '[');
 CHECK(!fromJson(deep).has_value());
}

void testFutureVersionRejected() {
 CHECK(!fromJson("{\"version\":2}").has_value());
 CHECK(!fromJson("{\"version\":99,\"seed\":1}").has_value());
 SaveState future;
 future.version = kSupportedVersion + 1;
 CHECK(!fromJson(toJson(future)).has_value());
 SaveState current;
 CHECK(fromJson(toJson(current)).has_value());
}

void testExtraKeysTolerated() {
 const std::string json =
  "{\"extra\":{\"a\":[1,2.5e-3,{\"b\":null,\"c\":true}],\"s\":\"x\\u00e9\\n\"},"
  "\"seed\":7,\"playerX\":-2.5,\"version\":1,\"unknown\":false,"
  "\"epochs\":[{\"q\":3,\"r\":-4,\"epoch\":9,\"note\":\"ok\"}]}";
 const auto st = fromJson(json);
 CHECK(st.has_value());
 if (st) {
  CHECK(st->version == 1);
  CHECK(st->seed == 7u);
  CHECK(sameBits(st->playerX, -2.5));
  CHECK(sameBits(st->playerY, 0.0));
  CHECK(st->retainedChunks.empty());
  CHECK(st->epochs.size() == 1);
  if (st->epochs.size() == 1) {
   CHECK(st->epochs[0].first == (wood::memory::RegionKey{3, -4}));
   CHECK(st->epochs[0].second == 9u);
  }
 }
}

void testReorderedKeys() {
 const std::string json =
  "{ \"enteredWild\": true, \"clockSeconds\": 12.5, \"pitch\": 0.25, \"yaw\": 1,\n"
  "  \"playerZ\": 3, \"playerY\": 2, \"playerX\": 1, \"accelerated\": true,\n"
  "  \"seated\": false, \"retainedChunks\": [ {\"y\": 2, \"x\": 1} ],\n"
  "  \"epochs\": [ {\"epoch\": 5, \"r\": 1, \"q\": 0} ], \"seed\": 42, \"version\": 1 }";
 const auto st = fromJson(json);
 CHECK(st.has_value());
 if (st) {
  CHECK(st->version == 1);
  CHECK(st->seed == 42u);
  CHECK(sameBits(st->playerX, 1.0) && sameBits(st->playerY, 2.0) && sameBits(st->playerZ, 3.0));
  CHECK(sameBits(st->yaw, 1.0) && sameBits(st->pitch, 0.25) && sameBits(st->clockSeconds, 12.5));
  CHECK(!st->seated && st->accelerated && st->enteredWild);
  CHECK(st->retainedChunks.size() == 1);
  if (!st->retainedChunks.empty()) CHECK((st->retainedChunks[0] == wood::streaming::Coord{1, 2}));
  CHECK(st->epochs.size() == 1);
  if (!st->epochs.empty()) CHECK(st->epochs[0].second == 5u);
 }
}

void testMissingKeysDefault() {
 const auto st = fromJson("{}");
 CHECK(st.has_value());
 if (st) {
  SaveState def;
  CHECK(sameState(*st, def));
  CHECK(st->version == 1);
 }
 const auto ws = fromJson("  {\n\t}\n ");
 CHECK(ws.has_value());
}

} // namespace

int main() {
 testRoundTripExact();
 testEmptyVectors();
 testRandomDoublesExact();
 testMalformedRejected();
 testFutureVersionRejected();
 testExtraKeysTolerated();
 testReorderedKeys();
 testMissingKeysDefault();
 if (failures != 0) {
  std::fprintf(stderr, "Save: FAIL (%d of %d checks)\n", failures, checks);
  return 1;
 }
 std::printf("Save: PASS (%d checks)\n", checks);
 return 0;
}
