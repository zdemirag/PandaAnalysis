#!/usr/bin/env python

from PandaCore.Tools.Load import Load 
from PandaCore.Tools.Misc import PInfo, PError
import ROOT as root
import cppyy
import sys

# this module lets you build a LambdaSelection instance on the fly

# look we're doing C++ in python, we even have this:
this = sys.modules[__name__]

Load('PandaAnalyzer')
cppyy.cppdef('#include "PandaAnalysis/Flat/interface/GeneralTree.h"')

def build(stage, name, expr, anded=False):
    left = 'std::function<bool(const GeneralTree* gt)>'
    middle = '_fsel = [](const GeneralTree* gt) { return '
    rhs = '; };'
    cppyy.cppdef(left + name + middle + expr + rhs)
    f = getattr(cppyy.gbl, name+'_fsel')
    sel = root.LambdaSel(stage, name, f, anded)
    setattr(this, name+'Sel', sel)
    return sel

# e.g.:
# build(root.Selection.sReco, 'Trigger', '(gt->isData==0) || (gt->trigger!=0)', True) # anded = True
# build(root.Selection.sGen, 'GenBosonPt', 'gt->trueGenBosonPt > 100')
# build(root.Selection.sReco, 'Fatjet', 'gt->fj1Pt>250')
# build(root.Selection.sReco, 'Fatjet450', 'gt->fj1Pt>450')
# build(root.Selection.sGen, 'GenFatJet', 'gt->genFatJetPt>400')
