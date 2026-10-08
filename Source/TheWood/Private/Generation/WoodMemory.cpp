#include "Generation/WoodMemory.h"

namespace wood::memory {
void RegionMemory::observe(const std::vector<RegionKey>& touchedByRetainedChunks, double nowSeconds) {
 for(auto& entry:records_) entry.second.touched=false;
 std::vector<RegionKey> keys=touchedByRetainedChunks;
 std::sort(keys.begin(),keys.end());
 keys.erase(std::unique(keys.begin(),keys.end()),keys.end());
 for(const auto& key:keys) {
  auto& rec=records_[key];
  rec.touched=true;
  rec.seen=true;
  rec.forgotten=false;
  rec.lastSeen=nowSeconds;
 }
}

std::vector<RegionKey> RegionMemory::forgetDue(double nowSeconds, double graceSeconds) {
 std::vector<RegionKey> due;
 for(auto& entry:records_) {
  auto& rec=entry.second;
  if(rec.touched || !rec.seen || rec.forgotten) continue;
  if(nowSeconds-rec.lastSeen<graceSeconds) continue;
  ++rec.epoch;
  rec.forgotten=true;
  due.push_back(entry.first);
 }
 return due;
}

std::uint32_t RegionMemory::epoch(RegionKey key) const {
 const auto it=records_.find(key);
 return it==records_.end() ? 0u : it->second.epoch;
}

std::vector<std::pair<RegionKey,std::uint32_t>> RegionMemory::epochs() const {
 std::vector<std::pair<RegionKey,std::uint32_t>> out;
 for(const auto& entry:records_) {
  if(entry.second.epoch>0) out.emplace_back(entry.first,entry.second.epoch);
 }
 return out;
}

void RegionMemory::restore(const std::vector<std::pair<RegionKey,std::uint32_t>>& saved) {
 for(auto& entry:records_) entry.second.epoch=0;
 for(const auto& item:saved) records_[item.first].epoch=item.second;
}
}
