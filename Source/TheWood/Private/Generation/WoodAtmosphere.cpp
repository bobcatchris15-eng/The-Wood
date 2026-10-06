#include "Generation/WoodAtmosphere.h"
#include <cmath>
#include <stdexcept>

namespace wood {
namespace {
constexpr double tau=6.2831853071795864769;
double phase(double value,double period) { return std::fmod(value,period)/period*tau; }
}
Atmosphere atmosphere(double forestWeight,double x,double y,double seconds) {
 if(!std::isfinite(forestWeight)||forestWeight<0||forestWeight>1||
    !std::isfinite(x)||!std::isfinite(y)||!std::isfinite(seconds))
  throw std::invalid_argument("Atmosphere requires finite coordinates/time and forest weight in [0,1]");

 // Travelling waves give broad weather patches without chunk boundaries or tick state.
 const double mist=0.5+0.5*std::sin(phase(seconds,720)-phase(x,1800)+phase(y,2400));
 const double clouds=0.5+0.5*std::sin(phase(seconds,900)-phase(x,3200)-phase(y,2600)-tau/4);
 const double gust=0.5+0.5*std::sin(phase(seconds,105)+phase(x,1400)+phase(y,1700));
 const double ripple=0.5+0.5*std::sin(phase(seconds,33)-phase(x,600)+phase(y,900));
 Atmosphere result;
 result.fogDensity=0.002+0.008*forestWeight+(0.002+0.01*forestWeight)*mist;
 result.cloudCover=0.15+0.7*clouds;
 result.windStrength=(0.16+0.5*gust+0.12*ripple)*(1-0.3*forestWeight);
 return result;
}
}
