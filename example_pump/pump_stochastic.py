# -*- coding: utf-8 -*-
"""
File name: pump_stochastic.py
Author: Daniel Hulse
Created: October 2019
Description: A simple model for explaining stochastic behavior modelling

This model constitudes an extremely simple functional model of an electric-powered pump.

The functions are:
    -import EE
    -import Water
    -import Signal
    -move Water
    -export Water

The flows are:
    - EE (to power the pump)
    - Water_in
    - Water_out
    - Signal input (on/off)
"""
from fmdtools.define.common import Rand, State
from fmdtools.define.block import FxnBlock
from fmdtools.define.flow import Flow
from fmdtools.define.model import Model
from fmdtools.define.approach import NominalApproach 

from ex_pump import accumulate, reseting_accumulate
import fmdtools.analyze as rd
import fmdtools.sim.propagate as propagate
import numpy as np

"""
DEFINE MODEL FUNCTIONS
Functions are defined using Python classes that are instantiated as objects
"""
from ex_pump import ImportWater, ExportWater
from ex_pump import ImportEE as DetImportEE

class ImportEERandState(State):
    effstate:   float=1.0
    grid_noise: float=1.0
class ImportEERand(Rand):
    s= ImportEERandState()
    run_stochastic:     bool=True
class ImportEE(DetImportEE):
    _init_r = ImportEERand
    def condfaults(self,time):
        if self.ee_out.s.current>20.0: self.m.add_fault('no_v')
    def behavior(self,time):
        if self.m.has_fault('no_v'):      self.r.s.effstate=0.0 #an open circuit means no voltage is exported
        elif self.m.has_fault('inf_v'):   self.r.s.effstate=100.0 #a voltage spike means voltage is much higher
        else:                           
            if time>self.t.time: self.r.set_rand('effstate','triangular',0.9,1,1.1)
        if time>self.t.time:
            self.r.set_rand('grid_noise','normal',1, 0.1*(2+np.sin(np.pi/2*time)))
        self.ee_out.s.voltage= self.r.s.grid_noise*self.r.s.effstate * 500


from ex_pump import ImportSig as DetImportSig
class ImportSigRandState(State):
    sig_noise : float = 1.0
class ImportSigRand(Rand):
    s=ImportSigRandState()
    run_stochastic:     bool=True
class ImportSig(DetImportSig):
    _init_r=ImportSigRand
    def behavior(self, time):
        if self.m.has_fault('no_sig'): 
            self.sig_out.power=0.0 #an open circuit means no voltage is exported
        else:
            if time<5:      
                self.sig_out.power=0.0
                self.r.to_default('sig_noise')
            elif time<50: 
                if not time%5:  
                    self.r.set_rand('sig_noise', 'choice', [1.0, 0.9, 1.1])
                self.sig_out.power=1.0*self.r.s.sig_noise
            else:           
                self.sig_out.power=0.0; 
                self.r.to_default()

from ex_pump import MoveWat as DetMoveWat
class MoveWatRandState(State):
    eff: float=1.0
    eff_update = ('normal', (1.0, 0.2))
class MoveWatRand(Rand):
    s=MoveWatRandState()
    run_stochastic: bool=True
class MoveWat(DetMoveWat):
    _init_r=MoveWatRand
    def behavior(self, time):
        self.s.eff=self.r.s.eff
        super().behavior(time)

from ex_pump import PumpParam, Electricity, Water, Signal
from fmdtools.define.model import ModelParam
class Pump(Model):
    def __init__(self, params=PumpParam(), \
                 modelparams = ModelParam(phases=(('start',0,4),('on',5,49),('end',50,55)), times=(0,20, 55), dt=1.0, units='hr'), \
                    valparams={'flows':{'Wat_2':'flowrate', 'EE_1':'current'}}):

        super().__init__(params=params, modelparams=modelparams, valparams=valparams)

        self.add_flow('ee_1',   Electricity)
        self.add_flow('sig_1',  Signal)
        self.add_flow('wat_1',  Water('Wat_1'))
        self.add_flow('wat_2',  Water('Wat_1'))

        self.add_fxn('import_ee',    ImportEE,      'ee_1')
        self.add_fxn('import_water', ImportWater,   'wat_1')
        self.add_fxn('import_signal',ImportSig,     'sig_1')
        self.add_fxn('move_water',   MoveWat,       'ee_1', 'sig_1', 'wat_1', 'wat_2', p = {'delay':params.delay})
        self.add_fxn('export_water', ExportWater,   'wat_2')

        self.build_model()
    def end_condition(self,time):

        if time>self.times[-1]: return True
        else:                   return False
    def find_classification(self,scen, mdlhists):

        #get fault costs and rates
        if 'repair' in self.params.cost: repcost= self.calc_repaircost()
        else:                               repcost = 0.0
        if 'water' in self.params.cost:
            lostwat = sum(mdlhists['nominal']['flows']['wat_2']['flowrate'] - mdlhists['faulty']['flows']['wat_2']['flowrate'])
            watcost = 750 * lostwat  * self.modelparams.dt
        elif 'water_exp' in self.params.cost:
            wat = mdlhists['nominal']['flows']['wat_2']['flowrate'] - mdlhists['faulty']['flows']['wat_2']['flowrate']
            watcost =100 *  sum(np.array(accumulate(wat))**2) * self.modelparams.dt
        else: watcost = 0.0
        if 'ee' in self.params.cost:
            eespike = [spike for spike in mdlhists['faulty']['flows']['ee_1']['current'] - mdlhists['nominal']['flows']['ee_1']['current'] if spike >1.0]
            if len(eespike)>0: eecost = 14 * sum(np.array(reseting_accumulate(eespike))) * self.modelparams.dt
            else: eecost =0.0
        else: eecost = 0.0

        totcost = repcost + watcost + eecost

        if scen['properties']['type']=='nominal':   rate=1.0
        else:                                       rate=scen['properties']['rate']

        life=1e5
        expcost=rate*life*totcost
        return {'rate':rate, 'cost': totcost, 'expected cost': expcost}

def paramfunc(delay):
    return {'delay':delay}

if __name__=="__main__":
    import multiprocessing as mp


    rp = ModelParam(phases=(('start',0,4),('on',5,49),('end',50,55)), times=(0,20, 55), dt=1.0, units='hr', seed=5)
    mdl = Pump(modelparams = rp)
    
    mdl.set_vars([['ee_1','current']],[2])
    
    
    app_comp = NominalApproach()
    app_comp.add_param_replicates(paramfunc, 'delay_1', 100, (1))
    app_comp.add_param_replicates(paramfunc, 'delay_10', 100, (10))
    
    endclasses, mdlhists, apps=propagate.nested_approach(mdl,app_comp, run_stochastic=True, faults=[('export_water','block')], pool=mp.Pool(4))
    
    endclasses, mdlhists, apps =propagate.nested_approach(mdl,app_comp, run_stochastic=True, faults=[('export_water','block')], staged=True, pool=mp.Pool(4))
    
    comp_mdlhists = {scen:mdlhist['export_water block, t=27.0'] for scen,mdlhist in mdlhists.items()}
    comp_groups = {'delay_1': app_comp.ranges['delay_1']['scenarios'], 'delay_10':app_comp.ranges['delay_10']['scenarios']}
    fig = rd.plot.mdlhists(comp_mdlhists, {'move_water':['eff','total_flow'], 'Wat_2':['flowrate','pressure']}, comp_groups=comp_groups, aggregation='percentile', time_slice=27) 
    
    
    app = NominalApproach()
    app.add_param_replicates(paramfunc, 'no_delay', 100, (0))
    app.add_param_replicates(paramfunc, 'delay_10', 100, (10))
    


    
    # endresults, resgraph, mdlhist=propagate.nominal(mdl)
    # rd.plot.mdlhistvals(mdlhist, fxnflowvals={'MoveWater':'eff', 'Wat_1':'flowrate', 'Wat_2':['flowrate','pressure']})
    
    # endresults, resgraph, mdlhist=propagate.nominal(mdl,run_stochastic=True)
    # rd.plot.mdlhistvals(mdlhist, fxnflowvals={'MoveWater':['eff','total_flow'], 'Wat_2':['flowrate','pressure']})
    
    for i in range(1,10):
        mdl.update_seed(i)
        propagate.propagate(mdl, i, run_stochastic='track_pdf')
        print(mdl.return_probdens())
        #print(mdl.seed)
        
        
        #for fxnname, fxn in mdl.fxns.items():
        #    print(fxnname+': ')
        #    print(fxn.return_probdens())
        #    print(getattr(fxn,'pds', None))
    
    endresults,  mdlhist=propagate.one_fault(mdl, 'export_water','block', time=20, staged=False, run_stochastic=False, new_params={'modelparams':{'seed':50}})
    
    
    #mdlhist['faulty']['functions']['ImportEE']['probdens']
    
    rd.plot.mdlhists(mdlhist, fxnflowvals={'import_water'})
    #rd.plot.mdlhists(mdlhist, fxnflowvals={'ImportEE'})
    
    """
    endresults, resgraph, mdlhist=propagate.one_fault(mdl, 'ExportWater','block', time=20, staged=False, run_stochastic=True, modelparams={'seed':10})
    rd.plot.mdlhistvals(mdlhist, fxnflowvals={'MoveWater':['eff','total_flow'], 'Wat_2':['flowrate','pressure']}, legend=False)
    
    rd.plot.mdlhists(mdlhist, fxnflowvals={'MoveWater':['eff','total_flow'], 'Wat_2':['flowrate','pressure']})
    
    app_comp = NominalApproach()
    app_comp.add_param_replicates(paramfunc, 'delay_1', 100, (1))
    app_comp.add_param_replicates(paramfunc, 'delay_10', 100, (10))
    endclasses, mdlhists, apps =propagate.nested_approach(mdl,app_comp, run_stochastic=True, faults=[('ExportWater','block')], staged=True)
    
    comp_mdlhists = {scen:mdlhist['ExportWater block, t=27'] for scen,mdlhist in mdlhists.items()}
    comp_groups = {'delay_1': app_comp.ranges['delay_1']['scenarios'], 'delay_10':app_comp.ranges['delay_10']['scenarios']}
    fig = rd.plot.mdlhists(comp_mdlhists, {'MoveWater':['eff','total_flow'], 'Wat_2':['flowrate','pressure']}, comp_groups=comp_groups, aggregation='percentile', time_slice=27) 
    
    
    tab = rd.tabulate.resilience_factor_comparison(app_comp, endclasses, ['delay'], 'cost')
    """
    # app = NominalApproach()
    # app.add_seed_replicates('test_seeds', 100)
    # endclasses, mdlhists=propagate.nominal_approach(mdl,app, run_stochastic=True)
    # rd.plot.mdlhists(mdlhists, {'MoveWater':['eff','total_flow'], 'Wat_2':['flowrate','pressure']},\
    #                               ylabels={('Wat_2', 'flowrate'):'liters/s'}, color='blue', alpha=0.1, legend_loc=False)
    # rd.plot.mdlhists(mdlhists, {'MoveWater':['eff','total_flow'], 'Wat_2':['flowrate','pressure']}, aggregation='mean_std',\
    #                               ylabels={('Wat_2', 'flowrate'):'liters/s'})
    # rd.plot.mdlhists(mdlhists, {'MoveWater':['eff','total_flow'], 'Wat_2':['flowrate','pressure']}, aggregation='mean_bound',\
    #                               ylabels={('Wat_2', 'flowrate'):'liters/s'})
    # rd.plot.mdlhists(mdlhists, {'MoveWater':['eff','total_flow'], 'Wat_2':['flowrate','pressure']}, aggregation='percentile',\
    #                           ylabels={('Wat_2', 'flowrate'):'liters/s'})     
    
    # rd.plot.mdlhists(mdlhists, {'MoveWater':['eff','total_flow'], 'Wat_2':['flowrate','pressure']}, aggregation='mean_ci',\
    #                               ylabels={('Wat_2', 'flowrate'):'liters/s'}, time_slice=[3,5,7])
        
    # rd.plot.mdlhists(mdlhists, {'MoveWater':['eff','total_flow'], 'Wat_2':['flowrate','pressure']}, aggregation='mean_ci',\
    #                  comp_groups={'test_1':[*mdlhists.keys()][:50], 'test_2':[*mdlhists.keys()][50:]},\
    #                               ylabels={('Wat_2', 'flowrate'):'liters/s'}, time_slice=[3,5,7])
    # rd.plot.mdlhists(mdlhists, {'MoveWater':['eff','total_flow'], 'Wat_2':['flowrate','pressure'], 'ImportEE':['effstate', 'grid_noise'], 'EE_1':['voltage','current'], 'Sig_1':['power']},\
    #                               ylabels={('Wat_2', 'flowrate'):'liters/s'}, cols=2, color='blue', alpha=0.1, legend_loc=False)
    # rd.plot.mdlhists(mdlhists, {'MoveWater':['eff','total_flow'], 'Wat_2':['flowrate','pressure'], 'ImportEE':['effstate', 'grid_noise'], 'EE_1':['voltage','current'], 'Sig_1':['power']}, aggregation='percentile',\
    #                               ylabels={('Wat_2', 'flowrate'):'liters/s'}, cols=2, color='blue', alpha=0.1, legend_loc=False)
    #rd.plot.nominal_vals_1d(app, endclasses, 'test_seeds')
    
    
    