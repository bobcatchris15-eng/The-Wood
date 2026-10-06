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
 std::cout<<"PASS: hex packing, negative/far ownership, shared edges, cell cores and corner blending\n";
}
