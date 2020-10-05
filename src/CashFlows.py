# Copyright 2017 Battelle Energy Alliance, LLC
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
@authors: A. S. Epiney, P. Talbot, C. Wang, A. Alfonsi

Defines the Economics entity.
Each component (or source?) can have one of these to describe its economics.
"""
from __future__ import unicode_literals, print_function
import os
import sys
from collections import defaultdict
import xml.etree.ElementTree as ET

import numpy as np
import time

# NOTE this import exception is ONLY to allow RAVEN to directly import this module.
try:
  from TEAL.src import Amortization
except ImportError:
  import Amortization
# TODO fix with plugin relative path
path1 = os.path.dirname(__file__)
path2 = '/../raven/framework'
path3=os.path.abspath(os.path.expanduser(path1+'/..'+path2))
path4=os.path.abspath(os.path.expanduser(path1+path2))
path5=os.path.abspath(os.path.expanduser(path1+'/../../../framework'))
sys.path.extend([path3,path4,path5])

from utils import mathUtils as utils
from utils import InputData, InputTypes, TreeStructure


class GlobalSettings:
  """
    Stores general settings for a CashFlow calculation.
  """
  ##################
  # INITIALIZATION #
  ##################
  @classmethod
  def getInputSpecs(cls):
    """
      Collects input specifications for this class.
      @ In, None
      @ Out, glob, InputData, specs
    """
    glob = InputData.parameterInputFactory('Global')
    glob.addSub(InputData.parameterInputFactory('DiscountRate', contentType=InputTypes.FloatType))
    glob.addSub(InputData.parameterInputFactory('tax', contentType=InputTypes.FloatType))
    glob.addSub(InputData.parameterInputFactory('inflation', contentType=InputTypes.FloatType))
    glob.addSub(InputData.parameterInputFactory('ProjectTime', contentType=InputTypes.IntegerType))
    ind = InputData.parameterInputFactory('Indicator', contentType=InputTypes.StringListType)
    ind.addParam('name', param_type=InputTypes.StringListType, required=True)
    ind.addParam('target', param_type=InputTypes.FloatType)
    glob.addSub(ind)
    return glob

  def __init__(self, verbosity=100, **kwargs):
    """
      Constructor.
      @ In, **kwargs, dict, general keyword arguments: verbosity
      @ In, verbosity, int, used to control the output information
      @ Out, None
    """
    self._verbosity = verbosity
    self._metrics = None
    self._discountRate = None
    self._tax = None
    self._inflation = None
    self._projectTime = None
    self._indicators = None
    self._activeComponents = None
    self._metricTarget = None
    self._components = []

  def readInput(self, source):
    """
      Sets settings from input file
      @ In, source, InputData.ParameterInput, input from user
      @ Out, None
    """
    # TODO make readInput call setParams so there's a uniform place to change things!
    if isinstance(source, (ET.Element, TreeStructure.InputNode)):
      specs = self.getInputSpecs()()
      specs.parseNode(source)
    else:
      specs = source
    for node in specs.subparts:
      name = node.getName()
      val = node.value
      if name == 'DiscountRate':
        self._discountRate = val
      elif name == 'tax':
        self._tax = val
      elif name == 'inflation':
        self._inflation = val
      elif name == 'ProjectTime':
        self._projectTime = val + 1 # one for the construction year!
      elif name == 'Indicator':
        self._indicators = node.parameterValues['name']
        self._metricTarget = node.parameterValues.get('target', None)
        activeCf = val
        self._activeComponents = defaultdict(list)
        for request in activeCf:
          try:
            comp, cf = request.split('|')
          except ValueError:
            raise IOError('Expected active components in <Indicators> to be formatted as Component|Cashflow, but got {}'.format(request))
          self._activeComponents[comp].append(cf)
    self.checkInitialization()

  def setParams(self, params):
    """
      Sets the settings from a dictionary, instead of via an input file.
      @ In, params, dict, settings
      @ Out, None
    """
    for name, val in params.items():
      if name == 'DiscountRate':
        self._discountRate = val
      elif name == 'tax':
        self._tax = val
      elif name == 'inflation':
        self._inflation = val
      elif name == 'ProjectTime':
        self._projectTime = val + 1 # one for the construction year!
      elif name == 'Indicator':
        self._indicators = val['name']
        self._metricTarget = val.get('target', None)
        activeCf = val['active']
        self._activeComponents = defaultdict(list)
        for request in activeCf:
          try:
            comp, cf = request.split('|')
          except ValueError:
            raise IOError('Expected active components in <Indicators> to be formatted as Component|Cashflow, but got {}'.format(request))
          self._activeComponents[comp].append(cf)
    self.checkInitialization()

  def checkInitialization(self):
    """
      Checks that the reading in of inputs resulted in a sensible
      set of global data. Should be checked whenever a new GlobalSetting is created
      and initialized.
      @ In, None
      @ Out, None
    """
    # required entries
    if self._discountRate is None:
      raise IOError('Missing <DiscountRate> from global parameters!')
    if self._tax is None:
      raise IOError('Missing <tax> from global parameters!')
    if self._inflation is None:
      raise IOError('Missing <inflation> from global parameters!')
    if self._indicators is None:
      raise IOError('Missing <Indicator> from global parameters!')
    # specialized
    if 'NPV_search' in self._indicators and self._metricTarget is None:
      raise IOError('"NPV_search is an indicator and <target> is missing from <Indicators> global parameter!')
    for ind in self._indicators:
      if ind not in ['NPV_search', 'NPV', 'IRR', 'PI']:
        raise IOError('Unrecognized indicator type: "{}"'.format(ind))

  #######
  # API #
  #######
  def getActiveComponents(self):
    """
      Get the active components for the whole project
      @ In, None
      @ Out, self._activeComponents, dict, {componentName: listOfCashFlows}, the dict of active components
    """
    return self._activeComponents

  def getDiscountRate(self):
    """
      Get the global discount rate
      @ In, None
      @ Out, self._discountRate, float, discount rate
    """
    return self._discountRate

  def getInflation(self):
    """
      Get the global inflation
      @ In, None
      @ Out, self._inflation, None or float, the inflation for the whole project
    """
    return self._inflation

  def getIndicators(self):
    """
      Get the indicators
      @ In, None
      @ Out, self._indicators, string, string list of indicators, such as NPV, IRR.
    """
    return self._indicators

  def getMetricTarget(self):
    """
      Get the metric target
      @ In, None
      @ Out, self._metricTarget, float, the target metric
    """
    return self._metricTarget

  def getProjectTime(self):
    """
      Get whole project time
      @ In, None
      @ Out, self._projectTime, int, the project time
    """
    return self._projectTime

  def getTax(self):
    """
      Get the global tax rate
      @ In, None
      @ Out, self._tax, float, tax rate
    """
    return self._tax


class Component:
  """
    Just a holder for multiple cash flows, and methods for doing stuff with them
    Note the class can be constructed by reading from the XML (readInput) or directly TODO consistency
  """
  nodeVarMap = {'Life_time': '_lifetime',
                  'StartTime': '_startTime',
                  'Repetitions': '_repetitions',
                  'tax': '_specificTax',
                  'inflation': '_specificInflation',
                  }
  ##################
  # INITIALIZATION #
  ##################
  @classmethod
  def getInputSpecs(cls):
    """
      Collects input specifications for this class.
      @ In, None
      @ Out, comp, InputData, specs
    """
    comp = InputData.parameterInputFactory('Component')
    comp.addParam('name', param_type=InputTypes.StringType, required=True)
    comp.addSub(InputData.parameterInputFactory('Life_time', contentType=InputTypes.IntegerType))
    comp.addSub(InputData.parameterInputFactory('StartTime', contentType=InputTypes.IntegerType))
    comp.addSub(InputData.parameterInputFactory('Repetitions', contentType=InputTypes.IntegerType))
    comp.addSub(InputData.parameterInputFactory('tax', contentType=InputTypes.FloatType))
    comp.addSub(InputData.parameterInputFactory('inflation', contentType=InputTypes.FloatType))
    cfs = InputData.parameterInputFactory('CashFlows')
    cfs.addSub(Capex.getInputSpecs())
    cfs.addSub(Recurring.getInputSpecs())
    comp.addSub(cfs)
    return comp

  def __init__(self, verbosity=100, **kwargs):
    """
      Constructor.
      @ In, kwargs, dict, general keyword arguments: verbosity
      @ In, verbosity, int, used to control the output information
      @ Out, None
    """
    #self._owner = owner # cash flow user that uses this group
    self._verbosity = verbosity
    self._lifetime = None # lifetime of the component
    self.name = None
    self._cashFlows = []
    self._startTime = None
    self._repetitions = None
    self._specificTax = None
    self._specificInflation = None

  def readInput(self, source):
    """
      Sets settings from input file
      @ In, source, InputData.ParameterInput, input from user
      @ Out, None
    """
    print(' ... loading economics ...')
    # allow readInput argument to be either xml or input specs
    if isinstance(source, (ET.Element, TreeStructure.InputNode)):
      specs = self.getInputSpecs()()
      specs.parseNode(source)
    else:
      specs = source
    self.name = specs.parameterValues['name']
    # read in specs
    ## since all of these are simple value setters, use a mapping
    for itemName, attr in self.nodeVarMap.items():
      item = specs.findFirst(itemName)
      if item is not None:
        setattr(self, attr, item.value)
    cfs = specs.findFirst('CashFlows')
    if cfs is not None:
      for sub in cfs.subparts:
        newCfs = self._cashFlowFactory(sub) #CashFlow(self.name, verbosity=self._verbosity)
        self.addCashflows(newCfs)
    self.checkInitialization()

  def setParams(self, paramDict):
    """
      Sets the settings from a dictionary, instead of via an input file.
      @ In, paramDict, dict, settings
      @ Out, None
    """
    for name, value in paramDict.items():
      if name == 'name':
        self.name = value
      elif name == 'cash_flows':
        self._cashFlows = value
      else:
        # remainder are mapped
        attrName = self.nodeVarMap.get(name, None)
        if attrName is None:
          continue
        setattr(self, attrName, value)
    self.checkInitialization()

  def checkInitialization(self):
    """
      Checks that the reading in of inputs resulted in a sensible
      set of data. Should be checked whenever a new Component is created
      and initialized.
      @ In, None
      @ Out, None
    """
    missing = 'Component "{comp}" is missing the <{node}> node!'
    if self._lifetime is None:
      raise IOError(missing.format(comp=self.name, node='Life_time'))
    # check cashflows
    for cf in self._cashFlows:
      # set up parameters to match this component's lifetime
      params = dict((attr, cf.getParam(attr)) for attr in ['alpha', 'driver'])
      params = cf.extendParameters(params, self._lifetime+1)
      cf.setParams(params)
      # alpha needs to be either: a variable (Recurring type cash flow) or a lifetime+1 length array
      # TODO move check to specific cashflows!
      cf.checkParamLengths(self._lifetime+1)
    # TODO this isn't a check, this is setting defaults. Should this be a different method?
    if self._startTime is None:
      self._startTime = 0
    if self._repetitions is None:
      self._repetitions = 0 # NOTE that 0 means infinite repetitions!

  #######
  # API #
  #######
  def addCashflows(self, cf):
    """
      Add the cashflows for this component
      @ In, cf, list, list of CashFlow objects
      @ Out, None
    """
    self._cashFlows.extend(cf)

  def countMulttargets(self):
    """
      Get the number of targets this component
      @ In, None
      @ Out, countMulttargets, int, the number of cash flows
    """
    return sum(cf._multTarget is not None for cf in self._cashFlows)

  def getCashflow(self, name):
    """
      Get the cash flow with provided name for this component
      @ In, name, string, the name of cash flow object
      @ Out, cf, CashFlow Object, the cash flow object
    """
    for cf in self._cashFlows:
      if cf.name == name:
        return cf

  def getCashflows(self):
    """
      Get the  for this component
      @ In, None
      @ Out, self._cashFlows, list, list of cash flow objects
    """
    return self._cashFlows

  def getInflation(self):
    """
      Get the inflation for this component
      @ In, None
      @ Out, self._specificInflation, None or float, the inflation of this component
    """
    return self._specificInflation

  def getLifetime(self):
    """
      Provides the lifetime of this cash flow user.
      @ In, None
      @ Out, lifetime, int, lifetime
    """
    return self._lifetime

  def getMultipliers(self):
    """
      Get the multipliers for this component
      @ In, None
      @ Out, multipliers, list, list of multipliers
    """
    return list(cf.getMultiplier() for cf in self._cashFlows)

  def getRepetitions(self):
    """
      Get the repetitions for this component
      @ In, None
      @ Out, repetitions, int, the number of repetitions
    """
    return self._repetitions

  def getStartTime(self):
    """
      Get the _startTime for this component
      @ In, None
      @ Out, _startTime, int, the start time of this component
    """
    return self._startTime

  def getTax(self):
    """
      Get the tax rate for this component
      @ In, None
      @ Out, self._tax, float, tax rate
    """
    return self._specificTax

  #############
  # UTILITIES #
  #############
  def _cashFlowFactory(self, specs):
    """
      based on the InputData specs provided, returns the appropriate CashFlow
      @ In, specs, instant of InputData.ParameterInput, specs of provided InputData
      @ Out, created, list, list of cash flow objects
    """
    created = []
    # get the type of this node, whether we're talking XML or RAVEN.InputData
    if not isinstance(specs, InputData.ParameterInput):
      raise TypeError('Unrecognized source specifications type: {}'.format(type(specs)))
    # create the appropriate cash flows
    typ = specs.getName()
    if typ == 'Recurring':
      # this is simple, only need one cash flow to be created
      new = Recurring(component=self.name, verbosity=self._verbosity)
      new.readInput(specs)
      created.append(new)
    elif typ == 'Capex':
      # in addition to the node itself, need to add depreciation if requested
      new = Capex(component=self.name, verbosity=self._verbosity)
      new.readInput(specs)
      deprs = self._createDepreciation(new)
      created.append(new)
      created.extend(deprs)
    #elif typ == 'Custom':
    #  new = CashFlow(self.name, self._verbosity)
    #  created.append(new)
    else:
      raise TypeError('Unrecognized cash flow type:', typ)
    return created

  def _createDepreciation(self, ocf):
    """
      creates amortization cash flows depending on the originating capex cash flow
      @ In, ocf, instant of CashFlow, instant of CashFlow object
      @ Out, depreciation, list, [pos, neg], list amortization and depreciation objects
    """
    # use the reference plant price
    amort = ocf.getAmortization()
    if amort is None:
      return []
    print('DEBUGG amortizing cf:', ocf.name)
    originalValue = ocf.getParam('alpha') * -1.0 #start with a positive value
    scheme, plan = amort
    alpha = Amortization.amortize(scheme, plan, 1.0, self._lifetime)
    # first cash flow is POSITIVE on the balance sheet, is not taxed, and is a percent of the target
    pos = Amortizor(component=self.name, verbosity=self._verbosity)
    params = {'name': '{}_{}_{}'.format(self.name, 'amortize', ocf.name),
              'driver': '{}|{}'.format(self.name, ocf.name),
              'tax': False,
              'inflation': 'real',
              'alpha': alpha,
              # TODO is this reference and X right????
              'reference': 1.0, #ocf.getParam('reference'),
              'X': 1.0, #ocf.getParam('scale')
              }
    pos.setParams(params)
    # second cash flow is as the first, except negative and taxed
    neg = Amortizor(component=self.name, verbosity=self._verbosity)
    nalpha = np.zeros(len(alpha))
    nalpha[alpha != 0] = -1
    print('DEBUGG amort alpha:', alpha)
    print('DEBUGG depre alpha:', nalpha)
    params = {'name': '{}_{}_{}'.format(self.name, 'depreciate', ocf.name),
              'driver': '{}|{}'.format(self.name, pos.name),
              'tax': True,
              'inflation': 'real',
              'alpha': nalpha,
              'reference': 1.0,
              'X': 1.0}
    neg.setParams(params)
    return [pos, neg]


class CashFlow:
  """
    Hold the economics for a single cash flow, C = m * a * (D/D')^x
    where:
      C is the cashflow ($)
      m is a scalar multiplier
      a is the value of the widget, based on the D' volume sold
      D is the amount of widgets sold
      D' is the nominal amount of widgets sold
      x is the scaling factor
  """
  ##################
  # INITIALIZATION #
  ##################
  missingNodeTemplate = 'Component "{comp}" CashFlow "{cf}" is missing the <{node}> node!'

  @classmethod
  def getInputSpecs(cls, specs):
    """
      Collects input specifications for this class.
      @ In, specs, InputData, specs
      @ Out, specs, InputData, specs
    """
    # ONLY appends to existinc specs!
    #cf = InputData.parameterInputFactory('CashFlow')

    specs.addParam('name', param_type=InputTypes.StringType, required=True)
    specs.addParam('tax', param_type=InputTypes.BoolType, required=False)
    infl = InputTypes.makeEnumType('inflation_types', 'inflation_type', ['real', 'none']) # "nominal" not yet implemented
    specs.addParam('inflation', param_type=infl, required=False)
    specs.addParam('mult_target', param_type=InputTypes.BoolType, required=False)
    specs.addParam('multiply', param_type=InputTypes.StringType, required=False)

    specs.addSub(InputData.parameterInputFactory('driver', contentType=InputTypes.InterpretedListType))
    specs.addSub(InputData.parameterInputFactory('alpha', contentType=InputTypes.InterpretedListType))
    return specs

  def __init__(self, component=None, verbosity=100, **kwargs):
    """
      Constructor
      @ In, component, CashFlowUser instance, optional, cash flow user to which this cash flow belongs
      @ Out, None
    """
    # assert component is not None # TODO is this necessary? What if it's not a component-based cash flow?
    self.type = 'generic'
    self._component = component # component instance to whom this cashflow belongs, if any
    self._verbosity = verbosity
    # equation values
    self._driver = None       # "quantity produced", D
    self._alpha = None        # "price per produced", a
    self._reference = None
    self._scale = None

    # other params
    self.name = None          # base name of cash flow
    self.type = None          # Capex, Recurring, Custom
    self._taxable = None      # apply tax or not
    self._inflation = None    # apply inflation or not
    self._multTarget = None  # true if this cash flow gets multiplied by a global multiplier (e.g. NPV=0 search) (?)
    self._multiplier = None   # arbitrary scalar multiplier (variable name)
    self._depreciate = None

  def readInput(self, item):
    """
      Sets settings from input file
      @ In, item, InputData.ParameterInput, parsed specs from user
      @ Out, None
    """
    self.name = item.parameterValues['name']
    print(' ... ... loading cash flow "{}"'.format(self.name))
    # driver and alpha are specific to cashflow types # self._driver = item.parameterValues['driver']
    for key, value in item.parameterValues.items():
      if key == 'tax':
        self._taxable = value
      elif key == 'inflation':
        self._inflation = value
      elif key == 'mult_target':
        self._multTarget = value
      elif key == 'multiply':
        self._multiplier = value
    for sub in item.subparts:
      if sub.getName() == 'alpha':
        self._alpha = self.setVariableOrFloats(sub.value)
      elif sub.getName() == 'driver':
        self._driver = self.setVariableOrFloats(sub.value)
      if sub.getName() == 'reference':
        self._reference = sub.value
      elif sub.getName() == 'X':
        self._scale = sub.value
    self.checkInitialization()

  def setParams(self, paramDict):
    """
      Sets the settings from a dictionary, instead of via an input file.
      @ In, paramDict, dict, settings
      @ Out, None
    """
    for name, val in paramDict.items():
      if name == 'name':
        self.name = val
      elif name == 'driver':
        self._driver = val
      elif name == 'tax':
        self._taxable = val
      elif name == 'inflation':
        self._inflation = val
      elif name == 'mult_target':
        self._multTarget = val
      elif name == 'multiply':
        self._multiplier = val
      elif name == 'alpha':
        self._alpha = np.atleast_1d(val)
      elif name == 'reference':
        self._reference = val
      elif name == 'X':
        self._scale = val
      elif name == 'depreciate':
        self._depreciate = val
    self.checkInitialization()

  def checkInitialization(self):
    """
      Checks that the reading in of inputs resulted in a sensible
      set of data. Should be checked whenever a new CashFlow is created
      and initialized.
      @ In, None
      @ Out, None
    """
    pass # nothing specific to check in base

  def getMultiplier(self):
    """
      Get the multiplier
      @ In, None
      @ Out, multiplier, string or float, the multiplier of this cash flow
    """
    return self._multiplier

  def getParam(self, param):
    """
      Get the parameter value
      @ In, param, string, the name of requested parameter
      @ Out, getParam, float or list, the value of param
    """
    param = param.lower()
    if param in ['alpha', 'reference_price']:
      return self._alpha
    elif param in ['driver', 'amount_sold']:
      return self._driver
    elif param in ['reference', 'reference_driver']:
      return self._reference
    elif param in ['x', 'scale', 'economy of scale', 'scale_factor']:
      return self._scale
    else:
      raise RuntimeError('Unrecognized parameter request:', param)

  def getAmortization(self):
    """
      Get amortization
      @ In, None
      @ Out, None
    """
    return None

  def isInflated(self):
    """
      Check inflation
      @ In, None
      @ Out, isInflated, Bool, True if inflated otherwise False
    """
    # right now only 'none' and 'real' are options, so this is boolean
    ## when nominal is implemented, might need to extend this method a bit
    return self._inflation != 'none'

  def isMultTarget(self):
    """
      Check if multiple targets
      @ In, None
      @ Out, isMultTarget, Bool, True if multiple targets else False
    """
    return self._multTarget

  def isTaxable(self):
    """
      Check is taxable
      @ In, None
      @ Out, isTaxable, Bool, True if taxable otherwise False
    """
    return self._taxable

  def setVariableOrFloats(self, value):
    """
      Set variable
      @ In, value, str or float or list, the value of given variable
      @ Out, ret, str or float or numpy.array, the recasted value
    """
    ret = None
    # multi-entry or single-entry?
    if len(value) == 1:
      # single entry should be either a float (price) or string (raven variable)
      value = value[0]
      if utils.isAString(value) or utils.isAFloatOrInt(value):
        ret = value
      else:
        raise IOError('Unrecognized alpha/driver type: "{}" with type "{}"'.format(value, type(value)))
    else:
      # should be floats; InputData assures the entries are the same type already
      if not utils.isAFloatOrInt(value[0]):
        raise IOError('Multiple non-number entries for alpha/driver found, but require either a single variable name or multiple float entries: {}'.format(value))
      ret = np.asarray(value)
    return ret

  def loadFromVariables(self, need, variables, cashflows, lifetime):
    """
      Load the values of parameters from variables
      @ In, need, dict, the dict of parameters
      @ In, variables, dict, the dict of parameters that is provided from other sources
      @ In, cashflows, dict, dict of cashflows
      @ In, lifetime, int, the given life time
      @ Out, need, dict, the dict of parameters updated with variables
    """
    # load variable values from variables or other cash flows, as needed (ha!)
    for name, source in need.items():
      if utils.isAString(source):
        # as a string, this is either from the variables or other cashflows
        # look in variables first
        value = variables.get(source, None)
        if value is None:
          # since not found in variables, try among cashflows
          if '|' not in source:
            raise KeyError('Looking for variable "{}" to fill "{}" but not found among variables or other cashflows!'.format(source, name))
          comp, cf = source.split('|')
          value = cashflows[comp][cf][:]
        need[name] = np.atleast_1d(value)
    # now, each is already a float or an array, so in case they're a float expand them
    ## NOTE this expects the correct keys (namely alpha, driver) to expand, right?
    need = self.extendParameters(need, lifetime)
    return need

  def extendParameters(self, need, lifetime):
    """
      Extend values of parameters to the length of lifetime
      @ In, need, dict, the dict of parameters that need to extend
      @ In, lifetime, int, the given life time
      @ Out, None
    """
    # should be overwritten in the inheriting classes!
    raise NotImplementedError


class Capex(CashFlow):
  """
    Particular cashflow for infrequent large single expenditures
  """
  @classmethod
  def getInputSpecs(cls):
    """
      Collects input specifications for this class.
      @ In, specs, InputData, specs
      @ Out, specs, InputData, specs
    """
    specs = InputData.parameterInputFactory('Capex')
    specs = CashFlow.getInputSpecs(specs)
    specs.addSub(InputData.parameterInputFactory('reference', contentType=InputTypes.FloatType))
    specs.addSub(InputData.parameterInputFactory('X', contentType=InputTypes.FloatType))
    deprec = InputData.parameterInputFactory('depreciation', contentType=InputTypes.InterpretedListType)
    deprecSchemes = InputTypes.makeEnumType('deprec_types', 'deprec_types', ['MACRS', 'custom'])
    deprec.addParam('scheme', param_type=deprecSchemes, required=True)
    specs.addSub(deprec)
    return specs

  def __init__(self, **kwargs):
    """
      Constructor
      @ In, kwargs, dict, general keyword arguments
      @ Out, None
    """
    CashFlow.__init__(self, **kwargs)
    # new variables
    self.type = 'Capex'
    self._amortScheme = None # amortization scheme for depreciating this capex
    self._amortPlan = None   # if scheme is MACRS, this is the years to recovery. Otherwise, vector percentages.
    # set defaults different from base class
    self.type = 'Capex'
    self._taxable = False
    self._inflation = False

  def readInput(self, item):
    """
      Sets settings from input file
      @ In, item, InputData.ParameterInput, input from user
      @ Out, None
    """
    for sub in item.subparts:
      if sub.getName() == 'depreciation':
        self._amortScheme = sub.parameterValues['scheme']
        self._amortPlan = sub.value
    CashFlow.readInput(self, item)

  def checkInitialization(self):
    """
      Checks that the reading in of inputs resulted in a sensible
      set of data.
      @ In, None
      @ Out, None
    """
    CashFlow.checkInitialization(self)
    if self._reference is None:
      raise IOError(self.missingNodeTemplate.format(comp=self._component, cf=self.name, node='reference'))
    if self._scale is None:
      raise IOError(self.missingNodeTemplate.format(comp=self._component, cf=self.name, node='X'))
    if self._driver is None:
      raise IOError(self.missingNodeTemplate.format(comp=self._component, cf=self.name, node='driver'))
    if self._alpha is None:
      raise IOError(self.missingNodeTemplate.format(comp=self._component, cf=self.name, node='alpha'))

  def initParams(self, lifetime):
    """
      Initialize some parameters
      @ In, lifetime, int, the given life time
      @ Out, None
    """
    self._alpha = np.zeros(1 + lifetime)
    self._driver = np.zeros(1 + lifetime)

  def getAmortization(self):
    """
      Get amortization
      @ In, None
      @ Out, amortization, None or tuple, (amortizationScheme, amortizationPlan)
    """
    if self._amortScheme is None:
      return None
    else:
      return self._amortScheme, self._amortPlan

  def setAmortization(self, scheme, plan):
    """
      Set amortization
      @ In, scheme, str, 'MACRS' or 'custom'
      @ In, plan, list, list of amortization values
      @ Out, None
    """
    self._amortScheme = scheme
    self._amortPlan = np.atleast_1d(plan)

  def extendParameters(self, toExtend, t):
    """
      Extend values of parameters to the length of lifetime t
      @ In, toExtend, dict, the dict of parameters that need to extend
      @ In, t, int, the given life time
      @ Out, toExtend, dict, dict to extend
    """
    # for capex, both the Driver and Alpha are nonzero in year 1 and zero thereafter
    for name, value in toExtend.items():
      if name.lower() in ['alpha', 'driver']:
        if utils.isAFloatOrInt(value) or (len(value) == 1 and utils.isAFloatOrInt(value[0])):
          new = np.zeros(t)
          new[0] = float(value)
          toExtend[name] = new
    return toExtend

  def calculateCashflow(self, variables, lifetimeCashflows, lifetime, verbosity):
    """
      sets up the COMPONENT LIFETIME cashflows, and calculates yearly for the comp life
      @ In, variables, dict, the dict of parameters that is provided from other sources
      @ In, lifetimeCashflows, dict, dict of cashflows
      @ In, lifetime, int, the given life time
      @ In, verbosity, int, used to control the output information
      @ Out, ret, dict, the dict of caculated cashflow
    """
    ## FIXME what if I have set the values already?
    # get variable values, if needed
    need = {'alpha': self._alpha, 'driver': self._driver}
    # load alpha, driver from variables if need be
    need = self.loadFromVariables(need, variables, lifetimeCashflows, lifetime)
    # for Capex, use m * alpha * (D/D')^X
    alpha = need['alpha']
    driver = need['driver']
    reference = self.getParam('reference')
    if reference is None:
      reference = 1.0
    scale = self.getParam('scale')
    if scale is None:
      scale = 1.0
    mult = self.getMultiplier()
    if mult is None:
      mult = 1.0
    elif utils.isAString(mult):
      mult = float(variables[mult])
    result = mult * alpha * (driver / reference) ** scale
    if verbosity > 1:
      ret = {'result': result}
    else:
      ret = {'result': result,
             'alpha': alpha,
             'driver': driver,
             'reference': reference,
             'scale': scale,
             'mult': mult}
    return ret

  def checkParamLengths(self, lifetime, compName=None):
    """
      Check the length of some parameters
      @ In, lifetime, int, the given life time
      @ In, compName, str, name of component
      @ Out, None
    """
    for param in ['alpha', 'driver']:
      val = self.getParam(param)
      # if a string, then it's probably a variable, so don't check it now
      if utils.isAString(val):
        continue
      # if it's valued, then it better be the same length as the lifetime (which is comp lifetime + 1)
      elif len(val) != lifetime:
        preMsg = 'Component "{comp}" '.format(compName) if compName is not None else ''
        raise IOError((preMsg + 'cashflow "{cf}" node <{param}> should have {correct} '+\
                       'entries (1 + lifetime), but only found {found}!')
                       .format(cf=self.name,
                               correct=lifetime,
                               param=param,
                               found=len(val)))


class Recurring(CashFlow):
  """
    Particular cashflow for yearly-consistent repeating expenditures
  """

  @classmethod
  def getInputSpecs(cls):
    """
      Collects input specifications for this class.
      @ In, specs, InputData, specs
      @ Out, specs, InputData, specs
    """
    specs = InputData.parameterInputFactory('Recurring')
    specs = CashFlow.getInputSpecs(specs)
    # nothing new to add
    return specs

  def __init__(self, **kwargs):
    """
      Constructor
      @ In, kwargs, dict, general keyword arguments
      @ Out, None
    """
    CashFlow.__init__(self, **kwargs)
    # set defaults different from base class
    self.type = 'Recurring'
    self._taxable = True
    self._inflation = True
    self._yearlyCashflow = None

  def initParams(self, lifetime):
    """
      Initialize some parameters
      @ In, lifetime, int, the given life time
      @ Out, None
    """
    # Recurring doesn't use m alpha D/D' X, it uses integral(alpha * D)dt for each year
    self._yearlyCashflow = np.zeros(lifetime+1)

  def computeIntrayearCashflow(self, year, alpha, driver):
    """
      Computes the yearly summary of recurring interactions, and sets them to self._yearlyCashflow
      Use this when you need to collapse a year's worth of activity to a single year point
      Note this is more for intrayear (e.g. hourly) cash flows
      @ In, year, int, the index of the project year for this summary
      @ In, alpha, np.array, array of "prices" (all entries WITHIN one year [e.g. hourly])
      @ In, driver, np.array, array of "quantities sold" (all entries WITHIN one year [e.g. hourly])
      @ Out, None
    """
    mult = self.getMultiplier()
    if mult is None:
      mult = 1.0
    elif utils.isAString(mult):
      raise NotImplementedError
    try:
      self._yearlyCashflow[year] = mult * (alpha * driver).sum() # +1 is for initial construct year
    except ValueError as e:
      print('Error while computing yearly cash flow! Check alpha shape ({}) and driver shape ({})'.format(alpha.shape, driver.shape))
      raise e

  def computeYearlyCashflow(self, alpha, driver):
    """
      Computes the yearly summary of recurring interactions, and sets them to self._yearlyCashflow
      Use this when you need to collapse one-point-per-year alpha and one-point-per-year driver
      into one-point-per-year summaries
      Note this is more for once-per-year recurring cashflows
      @ In, alpha, np.array, array of "prices" (one entry per YEAR)
      @ In, driver, np.array, array of "quantities sold" (one entry per YEAR)
      @ Out, None
    """
    mult = self.getMultiplier()
    if mult is None:
      mult = 1.0
    elif utils.isAString(mult):
      raise NotImplementedError
    try:
      self._yearlyCashflow = mult * (alpha * driver)
    except ValueError as e:
      print('Error while computing yearly cash flow! Check alpha shape ({}) and driver shape ({})'.format(alpha.shape, driver.shape))
      raise e

  def calculateCashflow(self, variables, lifetimeCashflows, lifetime, verbosity):
    """
      sets up the COMPONENT LIFETIME cashflows, and calculates yearly for the comp life
      @ In, variables, dict, the dict of parameters that is provided from other sources
      @ In, lifetimeCashflows, dict, dict of cashflows
      @ In, lifetime, int, the given life time
      @ In, verbosity, int, used to control the output information
      @ Out, calculateCashflow, dict, the dict of calculated cashflow
    """
    # by now, self._yearlyCashflow should have been filled with appropriate values
    ## if not, then they're being provided directly through array data/variables
    # get variable values, if needed
    need = {'alpha': self.getParam('alpha'), 'driver': self.getParam('driver')}
    # load needed variables from variables as needed
    need = self.loadFromVariables(need, variables, lifetimeCashflows, lifetime)
    self.computeYearlyCashflow(need['alpha'], need['driver'])
    #assert self._yearlyCashflow is not None
    return {'result': self._yearlyCashflow}

  def checkParamLengths(self, lifetime, compName=None):
    """
      Check the length of some parameters
      @ In, lifetime, int, the given life time
      @ In, compName, str, name of component
      @ Out, None
    """
    pass # nothing to do here, we don't check lengths since they'll be integrated intrayear

  def extendParameters(self, toExtend, t):
    """
      Extend values of parameters to the length of lifetime t
      @ In, toExtend, dict, the dict of parameters that need to extend
      @ In, t, int, the given life time
      @ Out, None
    """
    # for recurring, both the Driver and Alpha are zero in year 1 and nonzero thereafter
    # FIXME: we're going to integrate alpha * D over time (not year time, intrayear time)
    for name, value in toExtend.items():
      if name.lower() in ['alpha']:
        if utils.isAFloatOrInt(value) or (len(value) == 1 and utils.isAFloatOrInt(value[0])):
          new = np.ones(t) * float(value)
          new[0] = 0
          toExtend[name] = new
    return toExtend


class Amortizor(Capex):
  """
    Particular cashflow for depreciation of capital expenditures
  """
  def extendParameters(self, toExtend, t):
    """
      Extend values of parameters to the length of lifetime t
      @ In, toExtend, dict, the dict of parameters that need to extend
      @ In, t, int, the given life time
      @ Out, None
    """
    # unlike normal capex, for amortization we expand the driver to all nonzero entries and keep alpha as is
    # TODO forced driver values for now
    driver = toExtend['driver']
    # how we treat the driver depends on if this is the amortizer or the depreciator
    if self.name.split('_')[-2] == 'amortize':
      if not utils.isAString(driver):
        toExtend['driver'] = np.ones(t) * driver[0] * -1.0
        toExtend['driver'][0] = 0.0
      for name, value in toExtend.items():
        if name.lower() in ['driver']:
          if utils.isAFloatOrInt(value) or (len(value) == 1 and utils.isAFloatOrInt(value[0])):
            new = np.zeros(t)
            new[1:] = float(value)
            toExtend[name] = new
    return toExtend
