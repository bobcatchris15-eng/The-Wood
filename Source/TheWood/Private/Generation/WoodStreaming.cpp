#include "Generation/WoodStreaming.h"
#include <algorithm>
#include <cmath>
#include <limits>
#include <set>
#include <stdexcept>

namespace wood::streaming {
bool retained(Coord chunk,Coord center,int radius) {
 const auto dx=static_cast<long long>(chunk.x)-center.x,dy=static_cast<long long>(chunk.y)-center.y;
 return radius>=0 && std::abs(dx)<=radius && std::abs(dy)<=radius;
}
Plan plan(double playerX,double playerY,const std::vector<Coord>& loaded,const std::vector<Coord>& pending,Settings settings) {
 if(!std::isfinite(playerX) || !std::isfinite(playerY) || !std::isfinite(settings.chunkSize) || settings.chunkSize<=0 ||
  settings.desiredRadius<0 || settings.desiredRadius>32 || settings.retainRadius>64 || settings.retainRadius<settings.desiredRadius || settings.maxConcurrentJobs==0)
  throw std::invalid_argument("Invalid streaming window settings or position");
 const double cx=std::floor(playerX/settings.chunkSize),cy=std::floor(playerY/settings.chunkSize);
 const double bound=static_cast<double>(std::numeric_limits<int>::max())-settings.retainRadius;
 if(std::abs(cx)>bound || std::abs(cy)>bound) throw std::out_of_range("Streaming coordinate exceeds integer range");
 Plan result;
 result.center={static_cast<int>(cx),static_cast<int>(cy)};
 const std::set<Coord> existing(loaded.begin(),loaded.end()),inflight(pending.begin(),pending.end());
 result.availableJobs=inflight.size()>=settings.maxConcurrentJobs?0:settings.maxConcurrentJobs-inflight.size();
 for(int y=-settings.desiredRadius;y<=settings.desiredRadius;++y) for(int x=-settings.desiredRadius;x<=settings.desiredRadius;++x) {
  const Coord coord{result.center.x+x,result.center.y+y};
  if(existing.count(coord)==0 && inflight.count(coord)==0) result.needed.push_back(coord);
 }
 for(const auto coord:existing) if(!retained(coord,result.center,settings.retainRadius)) result.removed.push_back(coord);
 const auto distance=[&](Coord coord) {
  const auto dx=static_cast<long long>(coord.x)-result.center.x,dy=static_cast<long long>(coord.y)-result.center.y;
  return dx*dx+dy*dy;
 };
 std::sort(result.needed.begin(),result.needed.end(),[&](Coord a,Coord b) {
  const auto da=distance(a),db=distance(b);return da==db?a<b:da<db;
 });
 return result;
}
}
