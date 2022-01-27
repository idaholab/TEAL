# Copyright 2020, Battelle Energy Alliance, LLC
#
# All Rights Reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
@authors: C. Wang, P. Talbot, A. Alfonsi

Execution for TEAL (Tool for Economic AnaLysis)
"""

import os
import sys
import functools
from collections import defaultdict, OrderedDict

import numpy as np
import numpy_financial as npf
try:
  from TEAL.src import CashFlows
  # NOTE this import exception is ONLY to allow RAVEN to directly import this extmod.
  # In general, this should not exist, and RAVEN should import TEAL.CashFlow instead of importing Teal directly, implicitly.
except (ImportError, ModuleNotFoundError):
  import CashFlows

raven_path= os.path.abspath(os.path.dirname(__file__)) + '/../../raven/framework'
sys.path.append(raven_path) #'~/projects/raven/framework') # TODO generic RAVEN location

from utils.graphStructure import graphObject
from utils import mathUtils as utils

#=====================
# UTILITIES
#=====================
def readFromXml(xml):
  """
    reads in cash flow from XML
    @ In, xml, xml.etree.ElementTree.Element, "Economics" node from input
    @ Out, globalSettings, CashFlows.GlobalSettings instance, settings for a run (None if none provided)
    @ Out, components, list, CashFlows.Components instances for a run
  """
  # read in XML to global settings, component list
  attr = xml.attrib
  globalSettings = None
  components = []
  econ = xml.find('Economics')
  verb = int(econ.attrib.get('verbosity', 100))
  for node in econ:
    if node.tag == 'Global':
      globalSettings = CashFlows.GlobalSettings(**attr)
      globalSettings.readInput(node)
      globalSettings._verbosity = verb
    elif node.tag == 'Component':
      new = CashFlows.Component(**attr)
      new.readInput(node)
      components.append(new)
    else:
      raise IOError('Unrecognized node under <Economics>: {}'.format(node.tag))
  return globalSettings, components

def checkRunSettings(settings, components):
  """
    Checks that basic settings between global and components are satisfied.
    Errors out if any problems are found.
    @ In, settings, CashFlows.GlobalSettings, global settings
    @ In, components, list, list of CashFlows.Component instances
    @ Out, None
  """
  compByName = dict((c.name, c) for c in components)
  # perform final checks for the global settings and components
  for find, find_cf in settings.getActiveComponents().items():
    if find not in compByName:
      raise IOError('Requested active component "{}" but not found! Options are: {}'.format(find, list(compByName.keys())))
    # check cash flow is in comp
  # check that StartTime/Repetitions triggers a ProjectTime node
  ## if projecttime is not given, then error if start time/repetitions given (otherwise answer is misleading)
  if settings.getProjectTime() is None:
    for comp in components:
      warn = 'TEAL: <{node}> given for component "{comp}" but no <ProjectTime> in global settings!'
      if comp.getStartTime() != 0:
        raise IOError(warn.format(node='StartTime', comp=comp.name))
      if comp.getRepetitions() != 0:
        raise IOError(warn.format(node='Repetitions', comp=comp.name))
  # check that if npvSearch is an indicator, then mult_target is on at least one cashflow.
  if 'NPV_search' in settings.getIndicators() and sum(comp.countMulttargets() for comp in components) < 1:
    raise IOError('NPV_search in <Indicators> "name" but no cash flows have "mult_target=True"!')

def checkDrivers(settings, components, variables, v=100):
  """
    checks if all drivers needed are present in variables
    @ In, settings, CashFlows.GlobalSettings, global settings
    @ In, components, list, list of CashFlows.Component instances
    @ In, variables, dict, variable-value map from RAVEN
    @ In, v, int, verbosity level
    @ Out, ordered, list, list of ordered cashflows to evaluate (in order)
  """
  m = 'checkDrivers'
  #active = _get_active_drivers(settings, components)
  active = list(comp for comp in components if comp.name in settings.getActiveComponents())
  vprint(v, 0, m, '... creating evaluation sequence ...')
  ordered = _createEvalProcess(active, variables)
  vprint(v, 0, m, '... evaluation sequence:', ordered)
  return ordered

def _createEvalProcess(components, variables):
  """
    Sorts the cashflow evaluation process so sensible evaluation order is used
    @ In, components, list, list of CashFlows.Component instances
    @ In, variables, dict, variable-value map from RAVEN
    @ Out, unique, list, list of ordered cashflows to evaluate (in order, no duplicates)
  """
  # TODO does this work with float drivers (e.g. already-evaluated drivers)?
  # storage for creating graph sequence
  driverGraph = defaultdict(list)
  driverGraph['EndNode'] = []
  evaluated = [] # for cashflows that have already been evaluated and don't need more treatment
  for comp in components:
    lifetime = comp.getLifetime()
    # find multiplier variables
    multipliers = comp.getMultipliers()
    for mult in multipliers:
      if mult is None:
        continue
      if mult not in variables.keys():
        raise RuntimeError('CashFlow: multiplier "{}" required for Component "{}" but not found among variables!'.format(mult, comp.name))
    # find order in which to evaluate cash flow components
    for c, cf in enumerate(comp.getCashflows()):
      # keys for graph are drivers, cash flow names
      driver = cf.getParam('driver')
      # does the driver come from the variable list, or from another cashflow, or is it already evaluated?
      cfn = '{}|{}'.format(comp.name, cf.name)
      found = False
      if driver is None or utils.isAFloatOrInt(driver) or isinstance(driver, np.ndarray) or ('pyomo.core.expr' in str(type(driver))) == True:
        found = True
        # TODO assert it's already filled?
        evaluated.append(cfn)
        continue
      elif driver in variables:
        found = True
        # check length of driver
        n = len(np.atleast_1d(variables[driver]))
        if n > 1 and n != lifetime+1:
          raise RuntimeError(('Component "{c}" TEAL {cf} driver variable "{d}" has "{n}" entries, '+\
                              'but "{c}" has a lifetime of {el}!')
                             .format(c=comp.name,
                                     cf=cf.name,
                                     d=driver,
                                     n=n,
                                     el=lifetime))
      else:
        # driver should be in cash flows if not in variables
        driverComp, driverCf = driver.split('|')
        for matchComp in components:
          if matchComp.name == driverComp:
            # for cross-referencing, component lifetimes have to be the same!
            if matchComp.getLifetime() != comp.getLifetime():
              raise RuntimeError(('Lifetimes for Component "{d}" and cross-referenced Component {m} ' +\
                                  'do not match, so no cross-reference possible!')
                                 .format(d=driverComp, m=matchComp.name))
            found = True # here this means that so far the component was found, not the specific cash flow.
            break
        else:
          found = False
        # if the component was found, check the cash flow is part of the component
        if found:
          if driverCf not in list(m_cf.name for m_cf in matchComp.getCashflows()):
            found = False
      if not found:
        raise RuntimeError(('Component "{c}" TEAL {cf} driver variable "{d}" was not found ' +\
                            'among variables or other cashflows!')
                           .format(c=comp.name,
                                   cf=cf.name,
                                   d=driver))

      # assure each cashflow is in the mix, and has an EndNode to rely on (helps graph construct accurately)
      driverGraph[cfn].append('EndNode')
      # each driver depends on its cashflow
      driverGraph[driver].append(cfn)
  ordered = evaluated + graphObject(driverGraph).createSingleListOfVertices()
  unique = list(OrderedDict.fromkeys(ordered))
  return unique

def componentLifeCashflow(comp, cf, variables, lifetimeCashflows, v=100, pyomoSwitch=None):
  """
    Calcualtes the annual lifetime-based cashflow for a cashflow of a component
    @ In, comp, CashFlows.Component, component whose cashflow is being analyzed
    @ In, cf, CashFlows.CashFlow, cashflow who is being analyzed
    @ In, variables, dict, RAVEN variables as name: value
    @ In, v, int, verbosity
    @ In, pyomoSwitch, pyo.ConcreteModel(), concrete model including all variables
    @ Out, lifeCashflow, np.array, array of cashflow values with length of component life
  """
  m = 'compLife'
  vprint(v, 1, m, "-"*75)
  print('DEBUGG comp:', comp.name, cf)
  vprint(v, 1, m, 'Computing LIFETIME cash flow for Component "{}" CashFlow "{}" ...'.format(comp.name, cf.name))
  paramText = '... {:^10.10s}: {: 1.9e}'
  # do cashflow
  results = cf.calculateCashflow(variables, lifetimeCashflows, comp.getLifetime()+1, v)
  lifeCashflow = results['result']

  if v < 1:
    # print out all of the parts of the cashflow calc
    for item, value in results.items():
      if item == 'result':
        continue
      if utils.isAFloatOrInt(value):
        vprint(v, 1, m, paramText.format(item, value))
      else:
        orig = cf.getParam(item)
        if utils.isSingleValued(orig):
          name = orig
        else:
          name = '(from input)'
        if pyomoSwitch == None:
          vprint(v, 1, m, '... {:^10.10s}: {}'.format(item, name))
          vprint(v, 1, m, '...           mean: {: 1.9e}'.format(value.mean()))
          vprint(v, 1, m, '...           std : {: 1.9e}'.format(value.std()))
          vprint(v, 1, m, '...           min : {: 1.9e}'.format(value.min()))
          vprint(v, 1, m, '...           max : {: 1.9e}'.format(value.max()))
          vprint(v, 1, m, '...           nonz: {:d}'.format(np.count_nonzero(value)))
        else:
          continue

    yx = max(len(str(len(lifeCashflow))),4)
    vprint(v, 0, m, 'LIFETIME cash flow summary by year:')
    vprint(v, 0, m, '    {y:^{yx}.{yx}s}, {a:^10.10s}, {d:^10.10s}, {c:^15.15s}'.format(y='year',
                                                                                        yx=yx,
                                                                                        a='alpha',
                                                                                        d='driver',
                                                                                        c='cashflow'))
    for y, cash in enumerate(lifeCashflow):
      if cf.type in ['Capex']:
        if pyomoSwitch == None:
          vprint(v, 1, m, '    {y:^{yx}d}, {a: 1.3e}, {d: 1.3e}, {c: 1.9e}'.format(y=y,
                                                                                 yx=yx,
                                                                                 a=results['alpha'][y],
                                                                                 d=results['driver'][y],
                                                                                 c=cash))
        else:
          vprint(v, 1, m, '    {y:^{yx}d}, pyomo expression (too long to show...), pyomo expression (too long to show...), pyomo expression (too long to show...)'.format(y=y,
                                                                                   yx=yx))
      elif cf.type == 'Recurring':
        if pyomoSwitch == None:
          vprint(v, 1, m, '    {y:^{yx}d}, -- N/A -- , -- N/A -- , {c: 1.9e}'.format(y=y,
                                                             yx=yx,
                                                             c=cash))
        else:
          vprint(v, 1, m, '    {y:^{yx}d}, -- N/A -- , -- N/A -- , pyomo expression (too long to show...)'.format(y=y,
                                                             yx=yx))

  return lifeCashflow

def getProjectLength(settings, components, v=100):
  """
    checks if all drivers needed are present in variables
    @ In, settings, CashFlows.GlobalSettings, global settings
    @ In, components, list, list of CashFlows.Component instances
    @ In, v, int, verbosity level
    @ Out, projectLength, int, length of project (explicit or implicit)
  """
  m = 'getProjectLength'
  projectLength = settings.getProjectTime()
  if not projectLength:
    vprint(v, 0, m, 'Because project length was not specified, using least common multiple of component lifetimes.')
    lifetimes = list(c.getLifetime() for c in components)
    projectLength = lcmm(*lifetimes) + 1
  return int(projectLength)

def projectLifeCashflows(settings, components, lifetimeCashflows, projectLength, v=100, pyomoChoice=None):
  """
    creates all cashflows for life of project, for all components
    @ In, settings, CashFlows.GlobalSettings, global settings
    @ In, components, list, list of CashFlows.Component instances
    @ In, lifetimeCashflows, dict, component: cashflow: np.array of annual economic values
    @ In, projectLength, int, project years
    @ In, v, int, verbosity level
    @ In, pyomoChoice, pyo.ConcreteModel(), concrete model including all variables
    @ Out, projectCashflows, dict, dictionary of project-length cashflows (same structure as lifetime dict)
  """
  m = 'proj_life'
  # apply tax, inflation
  projectCashflows = {} # same keys as lifetimeCashflows
  for comp in components:
    tax = comp.getTax() if comp.getTax() is not None else settings.getTax()
    inflation = comp.getInflation() if comp.getInflation() is not None else settings.getInflation()
    compProjCashflows = projectComponentCashflows(comp, tax, inflation, lifetimeCashflows[comp.name], projectLength, v=v, pyomoComp=pyomoChoice)
    projectCashflows[comp.name] = compProjCashflows
  return projectCashflows

def projectComponentCashflows(comp, tax, inflation, lifeCashflows, projectLength, v=100, pyomoComp=None):
  """
    does all the cashflows for a SINGLE COMPONENT for the life of the project
    @ In, comp, CashFlows.Component, component to run numbers for
    @ In, tax, float, tax rate for component as decimal
    @ In, inflation, float, inflation rate as decimal
    @ In, lifeCashflows, dict, dictionary of component lifetime cash flows
    @ In, projectLength, int, project years
    @ In, v, int, verbosity level
    @ In, pyomoComp, pyo.ConcreteModel(), concrete model including all variables
    @ Out, cashflows, dict, dictionary of cashflows for this component, taken to project life
  """
  m = 'proj comp'
  vprint(v, 1, m, "-"*75)
  vprint(v, 1, m, 'Computing PROJECT cash flow for Component "{}" ...'.format(comp.name))
  cashflows = {}
  # what is the first project year this component will be in existence?
  compStart = comp.getStartTime()
  # how long does each build of this component last?
  compLife = comp.getLifetime()
  # what is the last project year this component will be in existence?
  ## TODO will this work properly if start time is negative? Initial tests say yes ...
  ## note that we use projectLength as the default END of the component's cashflow life, NOT a decomission year!
  compEnd = projectLength if comp.getRepetitions() == 0 else compStart + compLife * comp.getRepetitions()
  vprint(v, 1, m, ' ... component start: {}'.format(compStart))
  vprint(v, 1, m, ' ... component end:   {}'.format(compEnd))
  for cf in comp.getCashflows():
    if cf.isTaxable():
      taxMult = 1.0 - tax
    else:
      taxMult = 1.0
    if cf.isInflated():
      inflRate = inflation + 1.0
    else:
      inflRate = 1.0 # TODO nominal inflation rate?
    vprint(v, 1, m, ' ... inflation rate: {}'.format(inflRate))
    vprint(v, 1, m, ' ... tax rate: {}'.format(taxMult))
    lifeCf = lifeCashflows[cf.name]
    singleCashflow = projectSingleCashflow(cf, compStart, compEnd, compLife, lifeCf, taxMult, inflRate, projectLength, v=v, pyomoSing=pyomoComp)
    vprint(v, 0, m, 'Project Cashflow for Component "{}" CashFlow "{}":'.format(comp.name, cf.name))
    if v < 1:
      vprint(v, 0, m, 'Year, Time-Adjusted Value')
      for y, val in enumerate(singleCashflow):
        if pyomoComp == None:
          vprint(v, 0, m, '{:4d}: {: 1.9e}'.format(y, val))
        else:
          vprint(v, 0, m, '{:4d}: pyomo expression (too long to show...)'.format(y))
    cashflows[cf.name] = singleCashflow

  return cashflows

def projectSingleCashflow(cf, start, end, life, lifeCf, taxMult, inflRate, projectLength, v=100, pyomoSing=None):
  """
    does a single cashflow for the life of the project
    @ In, cf, CashFlows.CashFlow, cash flow to extend to full project life
    @ In, start, int, project year in which component begins operating
    @ In, end, int, project year in which component ends operating
    @ In, life, int, lifetime of component
    @ In, lifeCf, np.array, cashflow for lifetime of component
    @ In, taxMult, float, tax rate multiplyer (1 - tax)
    @ In, inflRate, float, inflation rate multiplier (1 - inflation)
    @ In, projectLength, int, total years of analysis
    @ In, v, int, verbosity
    @ In, pyomoSing, pyo.ConcreteModel(), concrete model including all variables
    @ Out, projCf, np.array, cashflow for project life of component
  """
  m = 'proj c_fl'
  vprint(v, 1, m, "-"*50)
  vprint(v, 1, m, 'Computing PROJECT cash flow for CashFlow "{}" ...'.format(cf.name))
  pyomoCheck = 0
  for value in lifeCf:
    if "pyomo.core.expr" in str(type(value)):
      pyomoCheck = 1
  if pyomoCheck == 1:
    projCf = np.zeros(projectLength, dtype=object)
  else:
    projCf = np.zeros(projectLength)
  years = np.arange(projectLength) # years in project time, year 0 is first year # TODO just indices, pandas?
  # before the project starts, after it ends are zero; we want the working part
  # ALFOA: Modified following expression (see issue #20):
  #        from operatingMask = np.logical_and(years >= start, years <= end)
  #        to operatingMask = np.logical_and(years >= start, years < end)
  operatingMask = np.logical_and(years >= start, years < end)
  operatingYears = years[operatingMask]
  startShift = operatingYears - start # y_shift
  # what year realative to production is this component in, for each operating year?
  relativeOperation = startShift % life # yReal
  # handle new builds
  ## three types of new builds:
  ### 1) first ever build (only construction cost)
  ### 2) decomission after last year ever running (assuming said decomission is inside the operational years)
  ### 3) years with both a decomissioning and a construction
  ## this is all years in which construction will occur (covers 1 and half of 3)
  newBuildMask = [a[relativeOperation==0] for a in np.where(operatingMask)]
  # NOTE make the decomissionMask BEFORE removing the last-year-rebuild, if present.
  ## This lets us do smoother numpy operations.
  decomissionMask = [newBuildMask[0][1:]]
  # if the last year is a rebuild year, don't rebuild, as it won't be operated.
  if newBuildMask[0][-1] == years[-1]:
    newBuildMask[0] = newBuildMask[0][:-1]
  ## numpy requires tuples as indices, not lists
  newBuildMask = tuple(newBuildMask)
  ## add construction costs for all of these new build years
  #projCf[newBuildMask] = lifeCf[0] * taxMult * np.power(inflRate, -1*years[newBuildMask])
  for i in range(len(newBuildMask[0])):
    projCf[newBuildMask[0][i]] = lifeCf[0] * taxMult * np.power(inflRate, -1*years[newBuildMask[0][i]])
  ## this is all the years in which decomissioning happens
  ### note that the [0] index is sort of a dummy dimension to help the numpy handshakes
  ### if last decomission is within project life, include that too
  if operatingYears[-1] < years[-1]:
    decomissionMask[0] = np.hstack((decomissionMask[0],np.atleast_1d(operatingYears[-1]+1)))
  for i in range(len(decomissionMask[0])):
    projCf[decomissionMask[0][i]] += lifeCf[-1] * taxMult * np.power(inflRate, -1*years[decomissionMask[0][i]])
  #projCf[decomissionMask] += lifeCf[-1] * taxMult * np.power(inflRate, -1*years[decomissionMask])
  ## handle the non-build operational years
  nonBuildMask = [a[relativeOperation!=0] for a in np.where(operatingMask)]
  projCf[nonBuildMask] += lifeCf[relativeOperation[relativeOperation!=0]] * taxMult * np.power(inflRate, -1*years[nonBuildMask])
  return projCf

def npvSearch(settings, components, cashFlows, projectLength, v=100):
  """
    Performs NPV matching search
    TODO is the target value required to be 0?
    @ In, settings, CashFlows.GlobalSettings, global settings
    @ In, components, list, list of CashFlows.Component instances
    @ In, cashFlows, dict, component: cashflow: np.array of annual economic values
    @ In, projectLength, int, project years
    @ In, v, int, verbosity level
    @ Out, mult, float, multiplier that causes the NPV to match the target value
  """
  m = 'npv search'
  multiplied = 0.0 # cash flows that are meant to include the multiplier
  others = 0.0 # cash flows without the multiplier
  years = np.arange(projectLength)
  for comp in components:
    for cf in comp.getCashflows():
      data = cashFlows[comp.name][cf.name]
      discountRates = np.power(1.0 + settings.getDiscountRate(), years)
      discounted = np.sum(data/discountRates)
      if cf.isMultTarget():
        multiplied += discounted
      else:
        others += discounted
  targetVal = settings.getMetricTarget()
  mult = (targetVal - others)/multiplied # TODO div zero possible?
  vprint(v, 0, m, '... NPV multiplier: {: 1.9e}'.format(mult))
  # SANITY CHECL -> FCFF with the multiplier, re-calculate NPV
  if v < 1:
    npv = NPV(components, cashFlows, projectLength, settings.getDiscountRate(), mult=mult, v=v)
    if npv != targetVal:
      vprint(v, 1, m, 'NPV mismatch warning! Calculated NPV with mult: {: 1.9e}, target: {: 1.9e}'.format(npv, targetVal))
  return mult

def FCFF(components, cashFlows, projectLength, mult=None, v=100, pyomoFCFF=None):
  """
    Calculates "free cash flow to the firm" (FCFF)
    @ In, settings, CashFlows.GlobalSettings, global settings
    @ In, cashFlows, dict, component: cashflow: np.array of annual economic values
    @ In, projectLength, int, project years
    @ In, mult, float, optional, if provided then scale target cash flow by value
    @ In, v, int, verbosity level
    @ In, pyomoFCFF, pyo.ConcreteModel(), concrete model including all variables
    @ Out, fcff, float, free cash flow to the firm
  """
  m = 'FCFF'
  # FCFF_R for each year
  if pyomoFCFF == None:
    fcff = np.zeros(projectLength)
  else:
    fcff = np.zeros(projectLength, dtype=object)
  for comp in components:
    for cf in comp.getCashflows():
      data = cashFlows[comp.name][cf.name]
      for i in range(len(fcff)):
        if mult is not None and cf.isMultTarget():
          fcff[i] += data[i] * mult
        else:
          fcff[i] += data[i]
  if pyomoFCFF == None:
    vprint(v, 1, m, 'FCFF yearly (not discounted):\n{}'.format(fcff))
  else:
    vprint(v, 1, m, 'FCFF yearly (not discounted):\n pyomo expression (too long to show...)')
  return fcff

def NPV(components, cashFlows, projectLength, discountRate, mult=None, v=100, pyomoNPV=None, returnFcff=False):
  """
    Calculates net present value of cash flows
    @ In, components, list, list of CashFlows.Component instances
    @ In, cashFlows, dict, component: cashflow: np.array of annual economic values
    @ In, projectLength, int, project years
    @ In, discountRate, float, firm discount rate to use in discounting future dollars value
    @ In, mult, float, optional, if provided then scale target cash flow by value
    @ In, pyomoNPV, pyo.ConcreteModel(), concrete model including all variables
    @ In, returnFcff, bool, optional, if True then provide calculated FCFF as well
    @ In, v, int, verbosity level
    @ Out, npv, float, net-present value of system
    @ Out, fcff, float, optional, free cash flow to the firm for same system
  """
  m = 'NPV'
  fcff = FCFF(components, cashFlows, projectLength, mult=mult, v=v, pyomoFCFF=pyomoNPV)
  npv = npf.npv(discountRate, fcff)
  if pyomoNPV == None:
    vprint(v, 0, m, '... NPV: {: 1.9e}'.format(npv))
  else:
    vprint(v, 0, m, '... NPV: pyomo expression (too long to show...)')
  if not returnFcff:
    return npv
  else:
    return npv, fcff

def IRR(components, cashFlows, projectLength, v=100):
  """
    Calculates internal rate of return for system of cash flows
    @ In, components, list, list of CashFlows.Component instances
    @ In, cashFlows, dict, component: cashflow: np.array of annual economic values
    @ In, projectLength, int, project years
    @ In, v, int, verbosity level
    @ Out, irr, float, internal rate of return
  """
  m = 'IRR'
  fcff = FCFF(components, cashFlows, projectLength, mult=None, v=v) # TODO mult is none always?
  # this method can crash if no solution exists!
  #try:
  irr = npf.irr(fcff)
  vprint(v, 1, m, '... IRR: {: 1.9e}'.format(irr))
  #except: # TODO what kind of crash? General catching is bad practice.
  #  vprint(v, 99, m, 'IRR search failed! No solution found. Setting IRR to -10 for debugging.')
  #  irr = -10.0
  return irr

def PI(components, cashFlows, projectLength, discountRate, mult=None, v=100):
  """
    Calculates the profitability index for system
    @ In, components, list, list of CashFlows.Component instances
    @ In, cashFlows, dict, component: cash flow: np.array of annual economic values
    @ In, projectLength, int, project years
    @ In, discountRate, float, firm discount rate to use in discounting future dollars value
    @ In, mult, float, optional, if provided then scale target cash flow by value
    @ In, v, int, verbosity level
    @ Out, pi, float, profitability index
  """
  m = 'PI'
  npv, fcff = NPV(components, cashFlows, projectLength, discountRate, mult=mult, v=v, returnFcff=True)
  pi = -1.0 * npv / fcff[0] # yes, really! This seems strange, but it also seems to be right.
  vprint(v, 1, m, '... PI: {: 1.9e}'.format(pi))
  return pi

def gcd(a, b):
  """
    Find greatest common denominator
    @ In, a, int, first value
    @ In, b, int, sescond value
    @ Out, a, int, greatest common denominator
  """
  while b:
    a, b = b, a % b
  return a

def lcm(a, b):
  """
    Find least common multiple
    @ In, a, int, first value
    @ In, b, int, sescond value
    @ Out, lcm, int, least common multiple
  """
  return a * b // gcd(a, b)

def lcmm(*args):
  """
    Find the least common multiple of many values
    @ In, args, list, list of integers to find lcm for
    @ Out, lcmm, int, least common multiple of collection
  """
  return functools.reduce(lcm, args)

#=====================
# MAIN METHOD
#=====================
def run(settings, components, variables, pyomoChk=None):
  """
    @ In, settings, CashFlows.GlobalSettings, global settings
    @ In, components, list, list of CashFlows.Component instances
    @ In, variables, dict, variables from RAVEN
    @ In, pyomoChk, pyo.ConcreteModel(), concrete model including all variables
    @ Out, results, dict, economic metric results
  """
  # make a dictionary mapping component names to components
  compsByName = dict((c.name, c) for c in components)
  v = settings._verbosity
  m = 'run'
  vprint(v, 0, m, 'Starting CashFlow Run ...')
  # check mapping of drivers and determine order in which they should be evaluated
  vprint(v, 0, m, '... Checking if all drivers present ...')
  ordered = checkDrivers(settings, components, variables, v=v)


  # compute project cashflows
  ## this comes in multiple styles!
  ## -> for the "capex/amortization" cashflows, as follows:
  ##    - compute the COMPONENT LIFE cashflow for the component
  ##    - loop the COMPONENT LIFE cashflow until it's as long as the PROJECT LIFE cashflow
  ## -> for the "recurring" sales-type cashflow, as follows:
  ##    - there should already be enough information for the entire PROJECT LIFE
  ##    - if not, and there's only one entry, repeat that entry for the entire project life
  vprint(v, 0, m, '='*90)
  vprint(v, 0, m, 'Component Lifetime Cashflow Calculations')
  vprint(v, 0, m, '='*90)
  lifetimeCashflows = defaultdict(dict) # keys are component, cashflow, then indexed by lifetime
  #count = 0
  for ocf in ordered:
    #count += 1
    if ocf in variables or ocf == 'EndNode': # TODO why this check for ocf in variables? Should it be comp, or cf?
      continue
    compName, cfName = ocf.split('|')
    comp = compsByName[compName]
    cf = comp.getCashflow(cfName)
    # if this component is a "recurring" type, then we don't need to do the lifetime cashflow bit
    #if cf.type == 'Recurring':
    #  raise NotImplementedError # FIXME how to do this right?
    # calculate cash flow for component's lifetime for this cash flow
    lifeCf = componentLifeCashflow(comp, cf, variables, lifetimeCashflows, v=0, pyomoSwitch=pyomoChk)
    lifetimeCashflows[compName][cfName] = lifeCf

  vprint(v, 0, m, '='*90)
  vprint(v, 0, m, 'Project Lifetime Cashflow Calculations')
  vprint(v, 0, m, '='*90)
  # determine how the project life is calculated.
  projectLength = getProjectLength(settings, components, v=v)
  vprint(v, 0, m, ' ... project length: {} years'.format(projectLength))
  projectCashflows = projectLifeCashflows(settings, components, lifetimeCashflows, projectLength, v=v, pyomoChoice=pyomoChk)
  compCashflows = {}
  for comp in components:
    tax = comp.getTax() if comp.getTax() is not None else settings.getTax()
    inflation = comp.getInflation() if comp.getInflation() is not None else settings.getInflation()
    compProjCashflows = projectComponentCashflows(comp, tax, inflation, lifetimeCashflows[comp.name], projectLength, v=v, pyomoComp=pyomoChk)
    compCashflows[comp.name] = compProjCashflows

  vprint(v, 0, m, '='*90)
  vprint(v, 0, m, 'Economic Indicator Calculations')
  vprint(v, 0, m, '='*90)
  indicators = settings.getIndicators()
  outputType = settings.getOutput()


  some_data = {**projectCashflows, **compCashflows }

  if outputType is True:
    some_data = {**projectCashflows, **compCashflows }
    results = {"all_data": some_data, "outputType": outputType}
    if 'NPV_search' in indicators:
      metric = npvSearch(settings, components, projectCashflows, projectLength, v=v)
      results['NPV_mult'] = metric
    if 'NPV' in indicators:
      metric = NPV(components, projectCashflows, projectLength, settings.getDiscountRate(), v=v, pyomoNPV=pyomoChk)
      results['NPV'] = metric
    if 'IRR' in indicators:
      metric = IRR(components, projectCashflows, projectLength, v=v)
      results['IRR'] = metric
    if 'PI' in indicators:
      metric = PI(components, projectCashflows, projectLength, settings.getDiscountRate(), v=v)
      results['PI'] = metric

  else:
    results = {}
    if 'NPV_search' in indicators:
      metric = npvSearch(settings, components, projectCashflows, projectLength, v=v)
      results['NPV_mult'] = metric
    if 'NPV' in indicators:
      metric = NPV(components, projectCashflows, projectLength, settings.getDiscountRate(), v=v, pyomoNPV=pyomoChk)
      results['NPV'] = metric
    if 'IRR' in indicators:
      metric = IRR(components, projectCashflows, projectLength, v=v)
      results['IRR'] = metric
    if 'PI' in indicators:
      metric = PI(components, projectCashflows, projectLength, settings.getDiscountRate(), v=v)
      results['PI'] = metric
    results['outputType'] = False

  return results


#=====================
# PRINTING STUFF
#=====================
def vprint(threshold, desired, method, *msg):
  """
    Light wrapper for printing that considers verbosity levels
    @ In, threshold, int, cutoff verbosity
    @ In, desired, int, requested message verbosity level
    @ In, method, str, name of method raising print
    @ In, msg, list(str), messages to print
    @ Out, None
  """
  if desired >= threshold:
    print('CashFlow INFO ({}):'.format(method), *msg)
