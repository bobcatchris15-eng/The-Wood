#include "Generation/WoodHex.h"
#include <iostream>
#include <cstdlib>
using namespace wood::hex;
void check(bool v,const char* m){if(!v){std::cerr<<m<<"\n";std::exit(1);}}
double at(Point p,Coord c){for(auto i:weights(p))if(i.cell==c)return i.weight;return 0;}
int main(){
 for(int q=-60;q<=60;++q)for(int r=-60;r<=60;++r){Coord c{q,r};check(owner(center(c))==c,"round trip");check(at(center(c),c)>.999999,"distinct core");for(Coord d:directions){Coord b{q+d.q,r+d.r};auto x=edge(c,b),y=edge(b,c);check(x.a==y.a&&x.b==y.b,"reciprocal edge");}}
 Point v{std::sqrt(3.0)*radius/2,radius/2};check(std::abs(at(v,{0,0})-1.0/3)<1e-8,"triple corner");
 for(int i=-10000;i<=10000;++i){Point p=warp({i*31.13,i*17.91},42);double sum=0;for(auto x:weights(p)){check(x.weight>=0&&std::isfinite(x.weight),"finite weight");sum+=x.weight;}check(std::abs(sum-1)<1e-10,"complete coverage");}
 {
  // Region crossing: flats-to-flats distance (pointy-top, opposite flat midpoints from vertices at 30+60k deg) over 500 sampled cells, at 4.2 m/s.
  double sum=0;int n=0;
  for(int i=0;i<500;++i){
   Coord c{i%25-12,i/25-10};Point o=center(c);
   auto vert=[&](int k){double a=(30+60*k)*3.14159265358979323846/180;return Point{o.x+radius*std::cos(a),o.y+radius*std::sin(a)};};
   // Edge between vertices k=5 (330 deg) and k=0 (30 deg) has midpoint at 0 deg; edge k=2 (150) and k=3 (210) has midpoint at 180 deg.
   Point e0{(vert(5).x+vert(0).x)/2,(vert(5).y+vert(0).y)/2},e1{(vert(2).x+vert(3).x)/2,(vert(2).y+vert(3).y)/2};
   sum+=std::hypot(e0.x-e1.x,e0.y-e1.y);++n;
  }
  const double crossing=sum/n/4.2;
  check(crossing>240&&crossing<360,"mean region crossing time at 4.2 m/s lies between 240 and 360 s");
 }
 std::cout<<"PASS: hex packing, negative/far ownership, shared edges, cell cores and corner blending\n";
}
