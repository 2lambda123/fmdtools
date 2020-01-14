# -*- coding: utf-8 -*-
"""
File name: ex_pump.py
Author: Daniel Hulse
Created: October 2019
Description: A simple model for explaining fault model definition

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

from fmdtools.modeldef import *


##DEFINE MODEL FUNCTIONS
# Functions are, again, defined using Python classes that are instantiated as objects

# Import EE is the line of electricity going into the pump
# We define it here as a subclass of the FxnBlock superclass (imported from modeldef.py)
#the FxnBlock superclass, which adds the common aspects of the function objects:
# - flows added to .flow
# - faults set to nominal
# - a number of useful methods added for dealing with internal faults (e.g. addfault()) and fault
# propagation (e.g. updatefxn()) are added to the object
class ImportEE(FxnBlock):
    #Initializing the function requires the flows going in and out of the function
    def __init__(self,flows):
        #this initializes the fault state of the system and adds needed flows
        #self.faults will be used to store which faults are in the function
        #flows will now be attibutes with names given by the keys in the input
        # dict, e.g. {'EEout':EEout} means self.EEout will be the EEout flow
        super().__init__(['EEout'],flows)

        #fault modes that originate in the function are listed here in a dictionary
        #these modes will be used to generate a list of scenarios
        #each fault can be given arbitrary properties in a dictionary
        #in this case, rate and repair cost information
        self.failrate=1e-5
        #add fault modes using self.assoc_modes, which takes a dict of structure:
        # {faultname: [[distribution percentage], [opportunity vector], [repair cost]]}
        # alternatively, modes may be associated by using:
        # self.faultmodes = {modename: }
        self.assoc_modes({'no_v':[0.80,[0,1,0], 10000], 'inf_v':[0.20, [0,1,0], 10000]})
        
    #condfaults changes the state of the system if there is a change in state in a flow
    # using a condfaults method is optional but helpful for delinating between
    # the determination of a fault and the behavior that results
    def condfaults(self,time):
        #in this case, if the current is too high, the line becomes an open circuit
        # (e.g. due to a fuse or line burnout)
        if self.EEout.rate>5.0: self.add_fault('no_v')
    #behavior defines the behavior of the function
    def behavior(self,time):
        #here we can define how the function will behave with different faults
        if self.has_fault('no_v'): self.effstate=0.0 #an open circuit means no voltage is exported
        elif self.has_fault('inf_v'): self.effstate=100.0 #a voltage spike means voltage is much higher
        else: self.effstate=1.0 #normally, voltage is 1.0
        self.EEout.effort=self.effstate

# Import Water is the pipe with water going into the pump

class ImportWater(FxnBlock):
    #Initializing the function requires the flows going in and out of the function
    def __init__(self,flows):
        #init requires a dictionary of flows with the internal variable name and
        # the object reference
        super().__init__(['Watout'],flows)
        self.failrate=1e-5
        self.assoc_modes({'no_wat':[1.0, [1,1,1], 1000]})
    #in this function, no conditional faults are modelled, so we don't need to include it
    #a dummy version is used in the FxnBlock superclass
    def behavior(self,time):
        #here we can define how the function will behave with different faults
        if self.has_fault('no_wat'):
            self.Watout.level=0.0 #an open circuit means no voltage is exported
        else:
            self.Watout.level=1.0

# Import Water is the pipe with water going into the pump
class ExportWater(FxnBlock):
    #Initializing the function requires the flows going in and out of the function
    def __init__(self,flows):
        #flows going into/out of the function need to be made properties of the function
        super().__init__(['Watin'], flows)
        self.failrate=1e-5
        self.assoc_modes({'block':[1.0, [1.5, 1.0, 1.0], 10000]})
    def behavior(self,time):
        if self.has_fault('block'): #here the fault is some sort of blockage
            self.Watin.area=0.1

# Import Signal is the on/off switch
class ImportSig(FxnBlock):
    def __init__(self,flows):
        #flows going into/out of the function need to be made properties of the function
        super().__init__(['Sigout'],flows)
        self.failrate=1e-6
        self.assoc_modes({'no_sig':[1.0, [1.5, 1.0, 1.0], 10000]})
    #when the behavior changes over time (and not just internal state) time must
    # be given as an input
    def behavior(self, time):
        if self.has_fault('no_sig'):
            self.Sigout.power=0.0 #an open circuit means no voltage is exported
        else:
            #Since the signal *generally* defines the operational profile of the system,
            # here we can specify what the system is supposed to do over time
            # in this case, turning on and then off
            if time<5:
                self.Sigout.power=0.0
            elif time<50:
                self.Sigout.power=1.0
            else:
                self.Sigout.power=0.0

# Move Water is the pump itself. While one could decompose this further,
# one function is used for simplicity
class MoveWat(FxnBlock):
    def __init__(self,flows, delay):
        flownames=['EEin', 'Sigin', 'Watin', 'Watout']
        #here we also define the states of a model, which are also added as 
        #attributes to the function
        states={'eff':1.0} #effectiveness state
        self.delay=delay[0]
        super().__init__(flownames,flows,states, timers={'timer'})
        self.failrate=1e-5
        self.assoc_modes({'mech_break':[0.6, [0.1, 1.2, 0.1], 10000], 'short':[1.0, [1.5, 1.0, 1.0], 10000]})
        #timers can be set by adding variables to functions also
    def condfaults(self, time):
        # here we define a conditional fault that only occurs after a state 
        # is present after 10 seconds
        if self.delay:
            if self.Watout.effort>5.0:
                if time>self.time:
                    #increment timer: default is 1 second, if we use self.tstep, the time
                    # will increment as desired even if we change model timestep
                    self.timer.inc(self.tstep)  
                if self.timer.time>self.delay:
                    self.add_fault('mech_break')
        else: 
            if self.Watout.effort>5.0: self.add_fault('mech_break')
            
    #behavior defines the behavior of the function
    def behavior(self, time):
        #here we can define how the function will behave with different faults
        if self.has_fault('short'):
            self.EEin.rate=500*self.Sigin.power*self.EEin.effort
            self.eff=0.0
        elif self.has_fault('mech_break'):
            self.EEin.rate=5*self.Sigin.power*self.EEin.effort
            self.eff=0.0
        else:
            self.EEin.rate=1.0*self.Sigin.power*self.EEin.effort
            self.eff=1.0 
            
        self.Watout.effort=self.Sigin.power*self.eff*min(1.5, self.EEin.effort)*self.Watin.level/self.Watout.area
        self.Watout.rate=self.Sigin.power*self.eff*min(1.5, self.EEin.effort)*self.Watin.level*self.Watout.area
        
        self.Watin.effort=self.Watout.effort
        self.Watin.rate=self.Watout.rate

##DEFINE CUSTOM MODEL FLOWS
# Flows can be defined using Python classes that are instantiated as objects
# Most flows are defined in the initialize() function, however custom flows can
# also be defined here as needed
    
# Defining the class for the flow of Water
# here the flow is given the custom attribute of 'hello'--further attributes
# and methods could be given here if desired.
class Water(Flow):
    def __init__(self):
        attributes={'rate':1.0, \
                    'effort':1.0, \
                    'area':1.0, \
                    'level':1.0}
        super().__init__(attributes, 'Water')
        self.customattribute='hello'

##DEFINE MODEL OBJECT
# The model is also made an object to aid graph construction
class Pump(Model):
    def __init__(self, params={'cost':{'repair', 'water'}, 'delay':10}):
        super().__init__()
        
        self.params=params
        #Declare time range to run model over
        self.phases={'start':[0,5], 'on':[5, 50], 'end':[50,55]}
        self.times=[0,20, 55]
        self.tstep = 1 #Stepsize: (change at your own risk, because this changes how the model will execute)
        # Timestep at the moment must be an integer.
        # In this model, because every time we've entered occurs at a factor of 5,
        # and there aren't any complicated controls/dynamics interactions that would need to be 
        # tuned, we can easily use the timestep t=1 OR t=5. HOWEVER, if any time (e.g. in the behavior)
        # does not occur on the timestep, it will be missed, so proceed with caution.
        
        #Flows must be added prior to the functions that use them, since
        # the functions take them as input
        #As shown below, flows are often simple enough that they don't need to be defined
        #as classes at all, but can instead be instantiated directly from the flow class
        #Here addflow takes as input a unique name for the flow "flowname", a type for the flow, "flowtype"
        # and either:   a dict with the initial flow attributes, OR
        #               a flow object defined in the model file
        self.add_flow('EE_1', 'EE', {'rate':1.0, 'effort':1.0})
        self.add_flow('Sig_1', 'Signal', {'power':1.0})
        # custom flows which we defined earlier can be added also:
        self.add_flow('Wat_1', 'Water', Water())
        self.add_flow('Wat_2', 'Water', Water())
        
        #Flows are added to the model using the addfxn function, which needs:
        #   - a unique function name 
        #   - the class to instantiate the function with (defined above)
        #   - a list of flow names corresponding to the inputs to the flow
        #       -the *order* of which corresponds to those in the function definition
        #       -the *name* of which corresponds to the name defined above for the flow
        self.add_fxn('ImportEE',ImportEE,['EE_1'])
        self.add_fxn('ImportWater',ImportWater,['Wat_1'])
        self.add_fxn('ImportSignal',ImportSig,['Sig_1'])
        self.add_fxn('MoveWater', MoveWat, ['EE_1', 'Sig_1', 'Wat_1', 'Wat_2'], params['delay'])
        self.add_fxn('ExportWater', ExportWater, ['Wat_2'])
        
        self.construct_graph()
        
    #PROVIDE MEANS OF CLASSIFYING RESULTS
    # this function classifies the faults into severities based on the state of faults
    # in this case, we will just use the repair costs and the probability
    def find_classification(self,resgraph, endfaults, endflows, scen, mdlhists):
        
        #accumulated loss function:
        # sum([sum(vec[i:]) for i in range(len(vec))])
        #squared accumulated loss function
        # [sum(vec[i:])**2 for i in range(len(vec))]
        #squared loss function
        # sum(vec)
        # need to check: 
        #       - normal (linear) costs
        #       - accumulated costs
        #       - resetting accumulated costs
        #       - costs w- degradation / no degradation 
        #       - conditional faults triggered at different times
        #       - squared costs
        
        #get fault costs and rates
        modes, modeprops = self.return_faultmodes()
        if 'repair' in self.params['cost']: repcost = sum([ c['rcost'] for f,m in modeprops.items() for a, c in m.items()])
        else: repcost = 0.0
        
        if 'water' in self.params['cost']: 
            lostwat = sum(mdlhists['nominal']['flows']['Wat_2']['rate'] - mdlhists['faulty']['flows']['Wat_2']['rate'])
            watcost = lostwat * 100 * self.tstep
        elif 'water_exp' in self.params['cost']:
            wat = mdlhists['nominal']['flows']['Wat_2']['rate'] - mdlhists['faulty']['flows']['Wat_2']['rate']
            watcost = sum(np.array(accumulate(wat))**2) * self.tstep
        else: watcost = 0.0
        
        if 'ee' in self.params['cost']:
            eespike = sum([spike for spike in mdlhists['faulty']['flows']['EE_1']['rate'] - mdlhists['nominal']['flows']['EE_1']['rate'] if spike >1.0])
            eecost = eespike * 100 * self.tstep
        else: eecost = 0.0
        
        totcost = repcost + watcost + eecost
        
        
        if scen['properties']['type']=='nominal':
            rate=1.0
        else:
            rate=scen['properties']['rate']
        
        life=1e5
        
        expcost=rate*life*totcost
        
        return {'rate':rate, 'cost': totcost, 'expected cost': expcost}
    
#INSTANTIATE MODEL
#the model is initialized using an initialize function
def initialize():
    p=Pump()
    return p.construct_graph()


    