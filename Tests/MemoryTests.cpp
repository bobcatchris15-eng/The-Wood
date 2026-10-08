#include "Generation/WoodMemory.h"
#include <cassert>
#include <vector>

using namespace wood::memory;

int main() {
 const RegionKey A{1,0},B{2,0},C{3,0};

 {
  RegionMemory m;
  m.observe({A},0);
  m.observe({},60);
  assert(m.forgetDue(89.9).empty());
  assert(m.epoch(A)==0);
 }
 {
  RegionMemory m;
  m.observe({A},0);
  m.observe({},0);
  const auto due=m.forgetDue(90);
  assert(due.size()==1 && due.front()==A);
  assert(m.epoch(A)==1);
  assert(m.forgetDue(500).empty());
  assert(m.epoch(A)==1);
 }
 {
  RegionMemory m;
  m.observe({A},0);
  m.observe({},50);
  m.observe({A},80);
  m.observe({},120);
  assert(m.forgetDue(150).empty());
  const auto due=m.forgetDue(170);
  assert(due.size()==1 && due.front()==A);
 }
 {
  RegionMemory m;
  m.observe({A},0);
  m.observe({A},500);
  assert(m.forgetDue(1000).empty());
  assert(m.epoch(A)==0);
  m.observe({A},1000);
  assert(m.forgetDue(5000).empty());
 }
 {
  RegionMemory m;
  m.observe({A},0);
  m.observe({},100);
  assert(m.forgetDue(100).size()==1);
  m.observe({A},200);
  m.observe({},300);
  assert(m.forgetDue(400).size()==1);
  assert(m.epoch(A)==2);
 }
 {
  RegionMemory m;
  m.observe({A,B},0);
  m.observe({C},10);
  m.observe({},200);
  const auto due=m.forgetDue(200);
  assert(due.size()==3 && due[0]==A && due[1]==B && due[2]==C);
  m.observe({B},300);
  m.observe({A,C},400);
  m.observe({},500);
  assert(m.forgetDue(600).size()==3);
  assert(m.epoch(A)==2 && m.epoch(B)==2 && m.epoch(C)==2);
  assert(m.epoch(RegionKey{9,9})==0);
 }
 {
  RegionMemory src;
  src.observe({A,B},0);
  src.observe({},100);
  src.forgetDue(100);
  src.observe({A},200);
  src.observe({},300);
  src.forgetDue(400);
  const auto saved=src.epochs();
  assert(saved.size()==2);
  RegionMemory dst;
  dst.restore(saved);
  assert(dst.epochs()==saved);
  assert(dst.epoch(A)==2 && dst.epoch(B)==1 && dst.epoch(C)==0);
  dst.restore({});
  assert(dst.epochs().empty() && dst.epoch(A)==0);
 }
 {
  RegionMemory a,b;
  a.observe({A,B,C,A},0);
  b.observe({C,A,B,B,C},0);
  a.observe({},100);
  b.observe({},100);
  assert(a.forgetDue(100)==b.forgetDue(100));
  assert(a.epochs()==b.epochs());
 }
 {
  auto owner=[](double x,double) {return RegionKey{static_cast<int>(x/100.0),0};};
  const auto one=regionsTouching({{0,0}},128,owner);
  assert(one.size()==2 && one[0]==(RegionKey{0,0}) && one[1]==(RegionKey{1,0}));
  const auto dup=regionsTouching({{0,0},{0,0}},128,owner);
  assert(dup==one);
  const auto forward=regionsTouching({{0,0},{1,0}},128,owner);
  const auto backward=regionsTouching({{1,0},{0,0}},128,owner);
  assert(forward==backward && forward.size()==3);
 }
 return 0;
}
