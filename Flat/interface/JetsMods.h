#ifndef JETSMODS
#define JETSMODS

#include "Module.h"

namespace pa {
  class JetMod : public AnalysisMod {
  public: 
    JetMod(panda::EventAnalysis& event_, 
           const Config& cfg_,                 
           const Utils& utils_,                
           GeneralTree& gt_) :                 
      AnalysisMod("jet", event_, cfg_, utils_, gt_) { 
        ak4Jets = &(event.chsAK4Jets); 
      }
    ~JetMod () { 
      delete ak4JERReader;
      for (auto& iter : ak4ScaleReader)
        delete iter.second;
      for (auto& iter : ak4UncReader)
        delete iter.second;
    }

    virtual bool on() { return !analysis.genOnly; }
    
  protected:
    void do_readData(TString path);
    void do_init(Registry& registry) {
      jesShifts = registry.access<std::vector<JESHandler>>("jesShifts");
      matchLeps = registry.accessConst<std::vector<panda::Lepton*>>("looseLeps");
      matchPhos = registry.accessConst<std::vector<panda::Photon*>>("loosePhos");
    }
    void do_execute();  

    void varyJES();
  private:
    std::map<TString,FactorizedJetCorrector*> ak4ScaleReader; //!< calculate JES on the fly
    std::map<TString,JetCorrectionUncertainty*> ak4UncReader; //!< calculate JES unc on the fly
    JERReader *ak4JERReader{nullptr}; //!< fatjet jet energy resolution reader
    JetCorrectionUncertainty *uncReaderAK4  {nullptr};        
    FactorizedJetCorrector   *scaleReaderAK4{nullptr};        
    std::vector<JESHandler>* jesShifts{nullptr}; 

    const std::vector<panda::Lepton*>* matchLeps;
    const std::vector<panda::Photon*>* matchPhos;

    panda::JetCollection *ak4Jets{nullptr};

    void setupJES();
  };
}

#endif
