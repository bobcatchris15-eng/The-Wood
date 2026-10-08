#include "Generation/WoodEntrance.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>

namespace wood::entrance {
namespace {
struct Pt { double x, y; };
// Path polyline, walked from the lot edge toward the passage.
constexpr std::array<Pt,5> Path{{{0.0,-546.0},{-18.0,-470.0},{10.0,-390.0},{-6.0,-300.0},{0.0,-230.0}}};
// Constant internal seed: entrance layout never depends on the World seed.
constexpr std::uint32_t EntranceSeed=0x5EED7A11u;

// Passage screen: tree arc centred on (0,ScreenCentreY) with ScreenRadius, facing the wilderness side.
constexpr double ScreenCentreY=-246.0, ScreenRadius=24.0, ScreenTreeR=2.2, ScreenOutcropR=1.2;
constexpr double OutcropX=3.4, OutcropY=-240.0;
// Nothing from the scatter layers may sit at or beyond this y (keeps the passage clear).
constexpr double PassageClearY=-250.0;

double clamp01(double v) { return std::clamp(v,0.0,1.0); }
double smoothstep(double v) { v=clamp01(v); return v*v*(3-2*v); }
double mix(double a,double b,double w) {
 if(w>=1) return b;
 if(w<=0) return a;
 return a+(b-a)*w;
}
std::uint32_t hash(std::uint32_t a,std::uint32_t b,std::uint32_t c) {
 std::uint32_t h=EntranceSeed^(a*0x9e3779b9u)^(b*0x85ebca6bu)^(c*0xc2b2ae35u);
 h^=h>>16; h*=0x7feb352du; h^=h>>15; h*=0x846ca68bu; return h^(h>>16);
}
double rnd(std::uint32_t a,std::uint32_t b,std::uint32_t c) { return hash(a,b,c)/4294967296.0; }
double segmentDistance(double px,double py,double ax,double ay,double bx,double by) {
 const double vx=bx-ax, vy=by-ay, wx=px-ax, wy=py-ay;
 const double len2=vx*vx+vy*vy;
 const double t=len2>0?clamp01((wx*vx+wy*vy)/len2):0.0;
 const double dx=wx-t*vx, dy=wy-t*vy;
 return std::sqrt(dx*dx+dy*dy);
}
bool admissible(Kind kind,double x,double y) {
 if(y>=PassageClearY) return false;
 const double clearance=kind==Kind::Tree?PathHalfWidth+PathMargin+0.2:PathHalfWidth+0.6;
 if(pathDistance(x,y)<clearance) return false;
 return lotDistance(x,y)>=(kind==Kind::Tree?8.0:2.0);
}
Feature make(Kind kind,double x,double y,double yaw,double scale) {
 return Feature{kind,{x,y,0},yaw,scale};
}
// Scatter along each path segment: one candidate per spacing metres, jittered along and offset to a side.
void scatter(std::vector<Feature>& out,Kind kind,double spacing,double minOffset,double maxOffset,double minScale,double maxScale,std::uint32_t salt) {
 for(std::size_t i=0;i+1<Path.size();++i) {
  const double vx=Path[i+1].x-Path[i].x, vy=Path[i+1].y-Path[i].y;
  const double len=std::sqrt(vx*vx+vy*vy);
  const double nx=-vy/len, ny=vx/len;
  const auto seg=static_cast<std::uint32_t>(i);
  const auto count=static_cast<std::uint32_t>(len/spacing);
  for(std::uint32_t k=0;k<count;++k) {
   const double s=(k+rnd(seg,k,salt*8+1))*spacing;
   if(s>=len) continue;
   const double side=rnd(seg,k,salt*8+2)<0.5?-1.0:1.0;
   const double offset=minOffset+(maxOffset-minOffset)*rnd(seg,k,salt*8+3);
   const double px=Path[i].x+vx*s/len+side*offset*nx;
   const double py=Path[i].y+vy*s/len+side*offset*ny;
   if(!admissible(kind,px,py)) continue;
   const double scale=minScale+(maxScale-minScale)*rnd(seg,k,salt*8+5);
   out.push_back(make(kind,px,py,rnd(seg,k,salt*8+4)*360.0,scale));
  }
 }
}
struct Screen { Kind kind; double x, y, r, scale; };
// Passage screen: 31 mature trees on an arc around the bend, plus two outcrops flanking the final approach.
std::vector<Screen> passageScreens() {
 std::vector<Screen> screens;
 for(int i=0;i<=30;++i) {
  const double phi=(i-15)*5.0*3.14159265358979323846/180.0;
  screens.push_back({Kind::Tree,ScreenRadius*std::sin(phi),ScreenCentreY+ScreenRadius*std::cos(phi),ScreenTreeR,1.6+0.02*i});
 }
 screens.push_back({Kind::Rock,-OutcropX,OutcropY,ScreenOutcropR,1.4});
 screens.push_back({Kind::Rock,OutcropX,OutcropY,ScreenOutcropR,1.4});
 return screens;
}
}

double lotDistance(double x,double y) {
 const double dx=std::max(std::abs(x-LotX)-LotHalfW,0.0), dy=std::max(std::abs(y-LotY)-LotHalfH,0.0);
 return std::sqrt(dx*dx+dy*dy);
}
double pathDistance(double x,double y) {
 double best=1e300;
 for(std::size_t i=0;i+1<Path.size();++i) best=std::min(best,segmentDistance(x,y,Path[i].x,Path[i].y,Path[i+1].x,Path[i+1].y));
 return best;
}
namespace {
// Signed-style distance to the zone: negative or zero inside, clamped at the zone end line.
double zoneDistance(double x,double y) {
 return std::max(std::min(lotDistance(x,y),pathDistance(x,y)-ZoneMargin),y-ZoneEndY);
}
}
bool inZone(double x,double y) { return zoneDistance(x,y)<=0; }
double blend(double x,double y) {
 const double d=zoneDistance(x,y);
 if(d<=0) return 1;
 if(d>=ZoneSkirt) return 0;
 return 1-smoothstep(d/ZoneSkirt);
}
double shapedHeight(double x,double y,double base,double lotHeight) {
 const double pathWeight=1-smoothstep((pathDistance(x,y)-PathHalfWidth)/PathHalfWidth);
 const double lotWeight=1-smoothstep(lotDistance(x,y)/LotSkirt);
 const double pathed=mix(base,base-PathSink,pathWeight);
 return mix(pathed,lotHeight,lotWeight);
}
bool lineOfSightBlocked(Vec3 from,Vec3 to) {
 for(const auto& screen:passageScreens()) {
  if(segmentDistance(screen.x,screen.y,from.x,from.y,to.x,to.y)<=screen.r) return true;
 }
 return false;
}
std::vector<Feature> fixedFeatures() {
 std::vector<Feature> out;
 // Mature path forest, then understory and rocks.
 scatter(out,Kind::Tree,7.0,4.4,8.4,0.95,2.1,1);
 scatter(out,Kind::Fern,3.5,2.2,3.4,0.6,1.2,2);
 scatter(out,Kind::Grass,2.5,1.9,2.8,0.5,1.0,3);
 scatter(out,Kind::Rock,14.0,5.5,7.5,0.6,1.3,4);
 for(const auto& screen:passageScreens()) out.push_back(make(screen.kind,screen.x,screen.y,0,screen.scale));

 // Lot bollards: boulders every 4 m around the perimeter, gap at the path entrance on the north edge.
 const std::array<Pt,5> corners{{{LotX-LotHalfW,LotY-LotHalfH},{LotX+LotHalfW,LotY-LotHalfH},{LotX+LotHalfW,LotY+LotHalfH},{LotX-LotHalfW,LotY+LotHalfH},{LotX-LotHalfW,LotY-LotHalfH}}};
 std::uint32_t bollard=0;
 for(std::size_t side=0;side+1<corners.size();++side) {
  const double vx=corners[side+1].x-corners[side].x, vy=corners[side+1].y-corners[side].y;
  const double len=std::sqrt(vx*vx+vy*vy);
  for(double d=0;d<len;d+=4.0,++bollard) {
   const double px=corners[side].x+vx*d/len, py=corners[side].y+vy*d/len;
   if(side==2&&std::abs(px-LotX)<=4.0) continue;
   out.push_back(make(Kind::Rock,px,py,rnd(7,bollard,9)*360.0,0.8+0.2*rnd(7,bollard,10)));
  }
 }

 // Placeholder props inside the lot: signboard, picnic table, bin, fence segment.
 const struct { int id; double x, y; } props[]={{0,-9,-555},{1,12,-566},{2,10,-553},{3,-16,-570}};
 for(const auto& p:props) {
  Feature f=make(Kind::Prop,p.x,p.y,0,1.0);
  f.propId=p.id;
  out.push_back(f);
 }
 return out;
}
}
