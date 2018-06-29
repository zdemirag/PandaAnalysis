// THIS FILE IS AUTOGENERATED //
#ifndef L1Tree_H
#define L1Tree_H
// STARTCUSTOM HEADER

#include "TFile.h"
#include "TTree.h"
#include "TH1D.h"
#include "TLorentzVector.h"
#include "TClonesArray.h"
#include "TString.h"
#include "genericTree.h"
#include <map>

// ENDCUSTOM
#define NL1JET 3
class L1Tree : public genericTree {
  public:
    L1Tree();
    ~L1Tree();
    void WriteTree(TTree* t);
    void Fill() { treePtr->Fill(); }
    void Reset();    void SetAuxTree(TTree*);
// STARTCUSTOM PUBLIC
// ENDCUSTOM
  private:
// STARTCUSTOM PRIVATE
// ENDCUSTOM
  public:
  int runNumber;
  int lumiNumber;
  ULong64_t eventNumber;
  float met;
  float metphi;
  float mindphi;
  int finor[5];
  int filter;
  int nJot;
  float jotPt[3];
  float jotEta[3];
  float jotPhi[3];
  float jotE[3];
  float jotNEMF[3];
  float jotNHF[3];
  int jotL1EGBX[3];
  int jotL1EGIso[3];
  float jotL1Pt[3];
  float jotL1Eta[3];
  float jotL1Phi[3];
  float jotL1E[3];
  float jot12Mass;
  float jot12DEta;
  float jot12DPhi;
};
#endif