#pragma once
#include <cstddef>
#include <vector>

namespace wood::streaming {
struct Coord {
 int x=0,y=0;
 bool operator==(const Coord& other) const {return x==other.x && y==other.y;}
 bool operator<(const Coord& other) const {return x<other.x || (x==other.x && y<other.y);}
};
struct Settings {
 double chunkSize=128;
 // Authoring limits: desiredRadius <=32 and retainRadius <=64.
 int desiredRadius=4,retainRadius=5;
 std::size_t maxConcurrentJobs=2;
};
struct Plan {
 Coord center;
 std::vector<Coord> needed,removed;
 std::size_t availableJobs=0;
};
bool retained(Coord chunk,Coord center,int radius);
// No world generation or asset access: this only schedules bounded chunk work.
Plan plan(double playerX,double playerY,const std::vector<Coord>& loaded,
 const std::vector<Coord>& pending,Settings settings={});
}
