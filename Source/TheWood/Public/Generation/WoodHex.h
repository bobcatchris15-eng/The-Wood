#pragma once
#include <array>
#include <cmath>
#include <algorithm>
#include <cstdint>
#include <stdexcept>
namespace wood::hex {
constexpr double radius=950,halfWidth=100;
struct Coord {int q=0,r=0; bool operator==(Coord b) const {return q==b.q&&r==b.r;} bool operator<(Coord b) const {return q<b.q||(q==b.q&&r<b.r);} };
struct Point {double x,y;};
struct Influence {Coord cell;double weight=0;};
constexpr std::array<Coord,6> directions{{{1,0},{1,-1},{0,-1},{-1,0},{-1,1},{0,1}}};
inline Point center(Coord c) {return {std::sqrt(3.0)*radius*(c.q+c.r/2.0),1.5*radius*c.r};}
inline Coord owner(Point p) {
 if(!std::isfinite(p.x)||!std::isfinite(p.y)||std::abs(p.x)>2000000||std::abs(p.y)>2000000) throw std::invalid_argument("Invalid hex coordinates");
 double q=std::sqrt(3.0)*p.x/(3*radius)-p.y/(3*radius),r=2*p.y/(3*radius),s=-q-r;
 int iq=static_cast<int>(std::round(q)),ir=static_cast<int>(std::round(r)),is=static_cast<int>(std::round(s));
 double dq=std::abs(iq-q),dr=std::abs(ir-r),ds=std::abs(is-s);
 if(dq>=dr&&dq>=ds) iq=-ir-is;else if(dr>=ds) ir=-iq-is;
 return {iq,ir};
}
inline Point warp(Point p,std::uint32_t seed) {
 // Each derivative <= 0.015: Jacobian displacement norm < 0.03, no folds.
 double phase=(seed%65521)*0.001;
 return {p.x+26.8*(std::sin(p.x/3800+phase)+std::sin(p.y/3800+phase*1.7)),p.y+26.8*(std::sin(p.x/3800+phase*.7)-std::sin(p.y/3800+phase*1.3))};
}
inline std::array<Influence,19> weights(Point p) {
 std::array<Influence,19> result{};Coord o=owner(p);int n=0;double total=0;
 const Point origin=center(o);bool core=true;
 for(Coord d:directions) {
  const Point b=center({o.q+d.q,o.r+d.r});
  const double margin=((b.x-origin.x)*((b.x+origin.x)*.5-p.x)+(b.y-origin.y)*((b.y+origin.y)*.5-p.y))/(std::sqrt(3.0)*radius);
  if(margin<halfWidth) {core=false;break;}
 }
 if(core) {result[0]={o,1};return result;}

 for(int r=-2;r<=2;++r) for(int q=-2;q<=2;++q) {
  if(std::max({std::abs(q),std::abs(r),std::abs(q+r)})>2) continue;
  Coord c{o.q+q,o.r+r};Point a=center(c);double w=1;
  for(Coord d:directions) {
   Point b=center({c.q+d.q,c.r+d.r});
   double margin=((b.x-a.x)*((b.x+a.x)*.5-p.x)+(b.y-a.y)*((b.y+a.y)*.5-p.y))/(std::sqrt(3.0)*radius);
   double t=std::clamp((margin/halfWidth+1)*.5,0.0,1.0);w*=t*t*(3-2*t);
  }
  result[n++]={c,w};total+=w;
 }
 for(auto& i:result) i.weight/=total;
 return result;
}
struct Edge {Coord a,b;};
inline Edge edge(Coord a,Coord b) {return b<a?Edge{b,a}:Edge{a,b};}
}
