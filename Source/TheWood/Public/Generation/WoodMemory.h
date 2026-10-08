#pragma once
#include <algorithm>
#include <cstdint>
#include <map>
#include <utility>
#include <vector>
#include "Generation/WoodStreaming.h"

namespace wood::memory {
struct RegionKey {
 int q=0,r=0;
 bool operator==(const RegionKey& other) const {return q==other.q && r==other.r;}
 bool operator!=(const RegionKey& other) const {return !(*this==other);}
 bool operator<(const RegionKey& other) const {return q<other.q || (q==other.q && r<other.r);}
};

// Decides when a region is forgotten. A forgotten region keeps its key but gains
// a new epoch, so regenerated ground is a distinct identity from the original.
// No engine or generation access: callers feed in which regions own retained chunks.
class RegionMemory {
public:
 // Regions that currently own any retained chunk. Input order and duplicates are irrelevant.
 void observe(const std::vector<RegionKey>& touchedByRetainedChunks, double nowSeconds);
 // Regions absent from the last observe() for >= graceSeconds (measured from last seen),
 // seen at least once, not already forgotten for this absence. Increments their epoch.
 // Returned sorted.
 std::vector<RegionKey> forgetDue(double nowSeconds, double graceSeconds=90);
 // 0 if never forgotten.
 std::uint32_t epoch(RegionKey key) const;
 // Serialisation for save/resume. Only regions with epoch>0, sorted by key.
 std::vector<std::pair<RegionKey,std::uint32_t>> epochs() const;
 // Replaces all epochs with the given set; visibility/absence state is not restored.
 void restore(const std::vector<std::pair<RegionKey,std::uint32_t>>& saved);
private:
 struct Record {
  double lastSeen=0;
  std::uint32_t epoch=0;
  bool seen=false;
  bool touched=false;
  bool forgotten=false;
 };
 std::map<RegionKey,Record> records_;
};

// Samples each chunk's four corners and centre through ownerFn(xMeters, yMeters).
// Chunk {x,y} spans [x*chunkSize,(x+1)*chunkSize) on each axis. Result is sorted and unique.
template<class OwnerFn>
std::vector<RegionKey> regionsTouching(const std::vector<streaming::Coord>& chunks,double chunkSize,OwnerFn ownerFn) {
 std::vector<RegionKey> out;
 for(const auto& c:chunks) {
  const double x0=c.x*chunkSize,y0=c.y*chunkSize,x1=x0+chunkSize,y1=y0+chunkSize;
  const double mx=(x0+x1)*0.5,my=(y0+y1)*0.5;
  out.push_back(ownerFn(x0,y0));
  out.push_back(ownerFn(x1,y0));
  out.push_back(ownerFn(x0,y1));
  out.push_back(ownerFn(x1,y1));
  out.push_back(ownerFn(mx,my));
 }
 std::sort(out.begin(),out.end());
 out.erase(std::unique(out.begin(),out.end()),out.end());
 return out;
}
}
