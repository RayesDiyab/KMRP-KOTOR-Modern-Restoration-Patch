#include "../../src/controller-native/K1TextFitPolicy.h"
#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>
#include <vector>
using namespace KmrpTextFit;
int main() {
    auto single = [](float scale) { return Measurement{200.0*scale,47.04*scale,1,true}; };
    float title=Fit(1.0f,{1000,47},single);
    assert(title>0 && title<1 && single(title).height<=47);
    assert(47.0/47.04-title<0.000001);
    auto two=[](float s) {return Measurement{200*s,94.08*s,2,true};};
    float banner=Fit(1.0f,{1000,90},two);
    assert(two(banner).height<=90 && 90.0/94.08-banner<0.000001);
    int calls=0;
    auto wrapping=[&calls](float s) { ++calls; int lines=s>0.75f?3:2; return Measurement{100*s,40*s*lines,lines,true}; };
    float wrapped=Fit(1.0f,{100,65},wrapping);
    assert(wrapped==0.75f && calls>10); // A ratio using the initial three lines is wrong.
    assert(Fit(1.0f,{200,47.04},single)==1.0f);
    const float adjacent=std::nextafter(1.0f,0.0f);
    float boundary=Fit(1.0f,{1000,47.04*static_cast<double>(adjacent)},single);
    assert(boundary<=adjacent && single(boundary).height<=47.04*static_cast<double>(adjacent));
    assert(adjacent-boundary<0.000001);
    auto invalid=[](float) {return Measurement{0,0,0,false};};
    assert(Fit(1.0f,{10,10},invalid)==1.0f);
    assert(Fit(1.0f,{0,10},single)==1.0f);
    assert(Fit(1.0f,{-1,10},single)==1.0f);
    const double nan=(std::numeric_limits<double>::quiet_NaN)();
    const float fnan=(std::numeric_limits<float>::quiet_NaN)();
    assert(Fit(1.0f,{nan,10},single)==1.0f);
    assert(Fit(0,{10,10},single)==0);
    assert(Fit(-1,{10,10},single)==-1);
    assert(std::isnan(Fit(fnan,{10,10},single)));
    assert(std::isinf(Fit((std::numeric_limits<float>::infinity)(),{10,10},single)));
    assert(Fit(1.0f,{10,10},[nan](float){return Measurement{nan,1,1,true};})==1.0f);
    assert(Fit(1.0f,{10,10},[](float){return Measurement{-1,1,1,true};})==1.0f);
    assert(Fit(1.0f,{10,10},[](float){return Measurement{1,1,-1,true};})==1.0f);
    int invalidCalls=0;
    assert(Fit(1.0f,{10,10},[&](float s){++invalidCalls;return Measurement{20*s,20*s,1,invalidCalls<3};})==1.0f);
    auto word=[](float s) {return Measurement{400*s,20*s,s>0.25f?0:1,true};};
    float longword=Fit(1.0f,{100,20},word);
    assert(longword==0.25f && word(longword).lines==1);
    assert(Fit(1.0f,{100,20},[](float){return Measurement{0,0,0,true};})==1.0f);
    assert(Fit(1.0f,{100,20},[](float){return Measurement{200,40,1,true};})==1.0f);
    // Each call starts from the preference, not the previous fitted output.
    assert(Fit(1.0f,{1000,47},single)==title);
    assert(Fit(1.0f,{1000,48},single)==1.0f);
    auto tiny=[](float s) {return Measurement{static_cast<double>(s)*1e20,1,1,true};};
    float tinyFit=Fit(1.0f,{1,1},tiny);
    assert(tinyFit>0 && tinyFit<=1e-20 && tiny(tinyFit).width<=1);
    for (int n=1;n<=1000;++n) {
        const double height=n/100.0;
        const float fit=Fit(1.0f,{1000,height},single);
        assert(fit>0 && fit<=1 && single(fit).height<=height);
        assert(height/47.04-fit<0.000001);
    }
    std::cout<<"PASS: bounded native text fitting, wrap changes, invalid input, float boundaries and restoring preference.\n";
}
