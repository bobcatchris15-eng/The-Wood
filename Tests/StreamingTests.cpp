#include "Generation/WoodStreaming.h"
#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>

using namespace wood::streaming;
int main() {
 const auto empty=plan(0,0,{},{});
 assert(empty.needed.size()==81 && empty.needed.front()==(Coord{0,0}));
 assert(empty.availableJobs==2 && empty.removed.empty());
 const auto negative=plan(-.01,-128.01,{},{});
 assert(negative.center==(Coord{-1,-2}));
 long long last=-1;
 for(const auto c:negative.needed) {
  const auto dx=static_cast<long long>(c.x)-negative.center.x,dy=static_cast<long long>(c.y)-negative.center.y;
  assert(dx*dx+dy*dy>=last);last=dx*dx+dy*dy;
 }
 const auto held=plan(127.99,0,{{0,0},{5,0},{6,0},{-5,-5}},{{1,0},{1,0}});
 assert(held.needed.size()==79 && held.availableJobs==1);
 assert(held.removed.size()==1 && held.removed.front()==(Coord{6,0}));
 assert(retained({-5,-5},{0,0},5));
 assert(!retained({-6,0},{0,0},5));
 const auto shifted=plan(128,0,empty.needed,{{5,0},{5,1}});
 assert(shifted.center==(Coord{1,0}) && shifted.availableJobs==0);
 assert(shifted.needed.size()==7 && shifted.removed.empty());
 auto full=empty.needed;
 const auto unchanged=plan(0,0,full,{});
 assert(unchanged.needed.empty());
 const auto far=plan(128*20.,-128*20.,full,{});
 assert(far.removed.size()==81 && far.needed.size()==81);
 bool rejected=false;
 try { (void)plan(std::numeric_limits<double>::infinity(),0,{},{}); } catch(const std::invalid_argument&) {rejected=true;}
 assert(rejected);
 rejected=false;
 try { (void)plan(0,0,{},{},Settings{128,5,4,2}); } catch(const std::invalid_argument&) {rejected=true;}
 assert(rejected);
 rejected=false;
 try { (void)plan(0,0,{},{},Settings{128,33,64,2}); } catch(const std::invalid_argument&) {rejected=true;}
 assert(rejected);
 std::cout<<"PASS: bounded chunk windows, negative coordinates, retention, ordering, inflight concurrency\n";
}
