# -*- coding: utf-8 -*-
"""
Created on Thu Sep 24 12:14:23 2020

@author: danie
"""

from drone_opt import *
import fmdtools.faultsim.propagate as propagate

mdl_med = x_to_mdl([1,1,80,1,2])
mdl_med.params['respolicy']

#testing mechanical fault response
endresults_med, resgraph, mdlhist_med = propagate.one_fault(mdl_med,'AffectDOF', 'RFmechbreak', time=6)
rd.plot.mdlhistvals(mdlhist_med, fxnflowvals = {'RSig_Traj':'mode', 'Planpath':'mode', 'DOFs': ['planvel','uppwr', 'planpwr'], 'AffectDOF':['LRstab', 'FRstab']}, time=6)
plot_faulttraj(mdlhist_med, mdl_med.params)
plot_xy(mdlhist_med['faulty'], endresults_med)

#testing battery fault response
endresults_med, resgraph, mdlhist_med = propagate.one_fault(mdl_med,'StoreEE', 'lowcharge', time=4)
rd.plot.mdlhistvals(mdlhist_med, fxnflowvals = {'RSig_Traj':'mode', 'Planpath':'mode', 'DOFs': 'planvel'}, time=4)
plot_faulttraj(mdlhist_med, mdl_med.params)
plot_xy(mdlhist_med['faulty'], endresults_med)


fhist=mdlhist_med['faulty']
faulttime = sum([any([fhist['functions'][f]['faults'][t]!={'nom'} for f in fhist['functions']]) for t in range(len(fhist['time'])) if fhist['flows']['DOFs']['elev'][t]])


