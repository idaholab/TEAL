"""
  Defines the Economics entity.
  Each component (or source?) can have one of these to describe its economics.
"""
from __future__ import unicode_literals, print_function
import os
import sys
from collections import defaultdict
import xml.etree.ElementTree as ET

import numpy as np

raven_path = '~/projects/raven/framework' # TODO fix with plugin relative path
sys.path.append(os.path.expanduser(raven_path))
from utils import InputData, xmlUtils, TreeStructure



class GlobalSettings:
  ##################
  # INITIALIZATION #
  ##################
  @classmethod
  def get_input_specs(cls):
    """
      Collects input specifications for this class.
      @ In, None
      @ Out, input_specs, InputData, specs
    """
    glob = InputData.parameterInputFactory('Global')
    glob.addSub(InputData.parameterInputFactory('DiscountRate', contentType=InputData.FloatType))
    glob.addSub(InputData.parameterInputFactory('tax', contentType=InputData.FloatType))
    glob.addSub(InputData.parameterInputFactory('inflation', contentType=InputData.FloatType))
    glob.addSub(InputData.parameterInputFactory('ProjectTime', contentType=InputData.IntegerType))
    ind = InputData.parameterInputFactory('Indicator', contentType=InputData.StringListType)
    ind.addParam('name', param_type=InputData.StringListType, required=True)
    ind.addParam('target', param_type=InputData.FloatType)
    glob.addSub(ind)
    return glob

  def __init__(self, verbosity=100, **kwargs):
    """
      Constructor.
      @ In, kwargs, dict, general keyword arguments: verbosity
      @ Out, None
    """
    self._verbosity = verbosity
    self._metrics = None
    self._discount_rate = None
    self._tax = None
    self._inflation = None
    self._project_time = None
    self._indicators = None
    self._active_components = None
    self._metric_target = None
    self._components = []

  def read_input(self, source):
    """
      Sets settings from input file
      @ In, source, InputData.ParameterInput, input from user
      @ In, xml, bool, if True then XML is passed in, not input data
      @ Out, None
    """
    if isinstance(source, (ET.Element, TreeStructure.InputNode)):
      specs = self.get_input_specs()()
      specs.parseNode(source)
    else:
      specs = source
    #print('DEBUGG specs:', type(specs), specs)
    for node in specs.subparts:
      #print('DEBUGG node:', type(node), node)
      #print(dir(node))
      name = node.getName()
      val = node.value
      if name == 'DiscountRate':
        self._discount_rate = val
      elif name == 'tax':
        self._tax = val
      elif name == 'inflation':
        self._inflation = val
      elif name == 'ProjectTime':
        self._project_time = val + 1 # one for the construction year!
      elif name == 'Indicator':
        self._indicators = node.parameterValues['name']
        self._metric_target = node.parameterValues.get('target', None)
        active_cf = val
        self._active_components = defaultdict(list)
        for request in active_cf:
          comp, cf = request.split('|')
          self._active_components[comp].append(cf)
    self.check_initialization()

  def check_initialization(self):
    """
      Checks that the reading in of inputs resulted in a sensible
      set of global data. Should be checked whenever a new GlobalSetting is created
      and initialized.
      @ In, None
      @ Out, None
    """
    # required entries
    if self._discount_rate is None:
      raise IOError('Missing <DiscountRate> from global parameters!')
    if self._tax is None:
      raise IOError('Missing <tax> from global parameters!')
    if self._inflation is None:
      raise IOError('Missing <inflation> from global parameters!')
    if self._indicators is None:
      raise IOError('Missing <Indicator> from global parameters!')
    # specialized
    if 'NPV_search' in self._indicators and self._metric_target is None:
      raise IOError('"NPV_search is an indicator and <target> is missing from <Indicators> global parameter!')
    for ind in self._indicators:
      if ind not in ['NPV_search', 'NPV', 'IRR', 'PI']:
        raise IOError('Unrecognized indicator type: "{}"'.format(ind))

  #######
  # API #
  #######
  def get_active_components(self):
    return self._active_components

  def get_discount_rate(self):
    return self._discount_rate

  def get_inflation(self):
    return self._inflation

  def get_indicators(self):
    return self._indicators

  def get_metric_target(self):
    return self._metric_target

  def get_project_time(self):
    return self._project_time

  def get_tax(self):
    return self._tax




class Component:
  # Just a holder for multiple cash flows, and methods for doing stuff with them
  # Note the class can be constructed by reading from the XML (read_input) or directly TODO
  ##################
  # INITIALIZATION #
  ##################
  @classmethod
  def get_input_specs(cls):
    """
      Collects input specifications for this class.
      @ In, None
      @ Out, input_specs, InputData, specs
    """
    comp = InputData.parameterInputFactory('Component')
    comp.addParam('name', param_type=InputData.StringType, required=True)
    comp.addSub(InputData.parameterInputFactory('Life_time', contentType=InputData.IntegerType))
    comp.addSub(InputData.parameterInputFactory('StartTime', contentType=InputData.IntegerType))
    comp.addSub(InputData.parameterInputFactory('Repetitions', contentType=InputData.IntegerType))
    comp.addSub(InputData.parameterInputFactory('tax', contentType=InputData.FloatType))
    comp.addSub(InputData.parameterInputFactory('inflation', contentType=InputData.FloatType))
    cf = CashFlow.get_input_specs()
    comp.addSub(cf)
    return comp

  def __init__(self, verbosity=100, **kwargs):
    """
      Constructor.
      @ In, kwargs, dict, general keyword arguments: verbosity
      @ Out, None
    """
    #self._owner = owner # cash flow user that uses this group
    self._verbosity = verbosity
    self._lifetime = None # lifetime of the component
    self.name = None
    self._cash_flows = []
    self._start_time = None
    self._repetitions = None
    self._specific_tax = None
    self._specific_inflation = None

  def read_input(self, source):
    """
      Sets settings from input file
      @ In, source, InputData.ParameterInput, input from user
      @ In, xml, bool, if True then XML is passed in, not input data
      @ Out, None
    """
    print(' ... loading economics ...')
    # allow read_input argument to be either xml or input specs
    if isinstance(source, (ET.Element, TreeStructure.InputNode)):
      specs = self.get_input_specs()()
      specs.parseNode(source)
    else:
      specs = source
    self.name = specs.parameterValues['name']
    # read in specs
    ## since all of these are simple value setters, make a mapping
    node_var_map = {'Life_time': '_lifetime',
                    'StartTime': '_start_time',
                    'Repetitions': '_repetitions',
                    'tax': '_specific_tax',
                    'inflation': '_specific_inflation',
                   }
    for item in specs.subparts:
      name = item.getName()
      if name == 'CashFlow':
        new = CashFlow(self.name, verbosity=self._verbosity)
        new.read_input(item)
        self._cash_flows.append(new)
      else:
        attr = node_var_map.get(name, None)
        if attr is not None:
          setattr(self, attr, item.value)
        else:
          raise IOError('Unknown input node to "Component": {}'.format(name))
    self.check_initialization()

  def check_initialization(self):
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
    for cf in self._cash_flows:
      if len(cf.get_param('alpha')) != self._lifetime + 1:
        raise IOError(('Component "{comp}" cashflow "{cf}" node <alpha> should have {correct} '+\
                       'entries (1 + lifetime), but only found {found}!')
                       .format(comp=self.name,
                               cf=cf.name,
                               correct=self._lifetime+1,
                               found=len(cf.getParam('alpha'))))
    # TODO this isn't a check, this is setting defaults. Should this be a different method?
    if self._start_time is None:
      self._start_time = 0
    if self._repetitions is None:
      self._repetitions = 0 # NOTE that 0 means infinite repetitions!

  #######
  # API #
  #######
  def count_multtargets(self):
    return sum(cf._mult_target is not None for cf in self._cash_flows)

  def get_cashflow(self, name):
    for cf in self._cash_flows:
      if cf.name == name:
        return cf

  def get_cashflows(self):
    return self._cash_flows

  def get_inflation(self):
    return self._specific_inflation

  def get_lifetime(self):
    """
      Provides the lifetime of this cash flow user.
      @ In, None
      @ Out, lifetime, int, lifetime
    """
    return self._lifetime

  def get_multipliers(self):
    return list(cf.get_multiplier() for cf in self._cash_flows)

  def get_repetitions(self):
    return self._repetitions

  def get_start_time(self):
    return self._start_time

  def get_tax(self):
    return self._specific_tax







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
  @classmethod
  def get_input_specs(cls):
    """
      Collects input specifications for this class.
      @ In, None
      @ Out, input_specs, InputData, specs
    """
    cf = InputData.parameterInputFactory('CashFlow')

    cf.addParam('name', param_type=InputData.StringType, required=True)
    cf.addParam('driver', param_type=InputData.StringType, required=True)
    cf.addParam('tax', param_type=InputData.BoolType, required=True)
    infl = InputData.makeEnumType('inflation_types', 'inflation_type', ['real', 'none']) # "nominal" not yet implemented
    cf.addParam('inflation', param_type=infl, required=True)
    cf.addParam('mult_target', param_type=InputData.BoolType, required=True)
    cf.addParam('multiply', param_type=InputData.StringType)

    cf.addSub(InputData.parameterInputFactory('alpha', contentType=InputData.FloatListType))
    cf.addSub(InputData.parameterInputFactory('reference', contentType=InputData.FloatType))
    cf.addSub(InputData.parameterInputFactory('X', contentType=InputData.FloatType))
    return cf

  def __init__(self, component=None, verbosity=100, **kwargs):
    """
      Constructor
      @ In, component, CashFlowUser instance, optional, cash flow user to which this cash flow belongs
      @ Out, None
    """
    # assert component is not None # TODO is this necessary? What if it's not a component-based cash flow?
    self._component = component # component instance to whom this cashflow belongs, if any
    self._verbosity = verbosity
    # equation values
    self._driver = None       # "quantity produced", D
    self._alpha = None        # "price per produced", a
    self._reference = None    # "where price is accurate", D'
    self._scale = None        # "economy of scale", x
    # other params
    self.name = None          # base name of cash flow
    self._type = None         # needed? one-time, yearly, repeating
    self._taxable = None      # apply tax or not
    self._inflation = None    # apply inflation or not
    self._mult_target = None  # true if this cash flow gets multiplied by a global multiplier (e.g. NPV=0 search) (?)
    self._multiplier = None   # arbitrary scalar multiplier (variable name)

  def read_input(self, item):
    """
      Sets settings from input file
      @ In, item, InputData.ParameterInput, parsed specs from user
      @ Out, None
    """
    self.name = item.parameterValues['name']
    print(' ... ... loading cash flow "{}"'.format(self.name))
    self._driver = item.parameterValues['driver']
    self._taxable = item.parameterValues['tax']
    self._inflation = item.parameterValues['inflation']
    self._mult_target = item.parameterValues['mult_target']
    self._multiplier = item.parameterValues.get('multiply', None)
    # the remainder of the entries are ValuedParams, so they'll be evaluated as-needed
    for sub in item.subparts:
      if sub.getName() == 'alpha':
        self._alpha = np.atleast_1d(sub.value)
      elif sub.getName() == 'reference':
        self._reference = sub.value
      elif sub.getName() == 'X':
        self._scale = sub.value
      else:
        raise IOError('Unrecognized "CashFlow" node: "{}"'.format(sub.getName()))
    self.check_initialization()

  def check_initialization(self):
    """
      Checks that the reading in of inputs resulted in a sensible
      set of data. Should be checked whenever a new CashFlow is created
      and initialized.
      @ In, None
      @ Out, None
    """
    # required nodes
    missing = 'Component "{comp}" CashFlow "{cf}" is missing the <{node}> node!'
    if self._alpha is None:
      raise IOError(missing.format(comp=self._component, cf=self.name, node='alpha'))
    if self._reference is None:
      raise IOError(missing.format(comp=self._component, cf=self.name, node='reference'))
    if self._scale is None:
      raise IOError(missing.format(comp=self._component, cf=self.name, node='X'))

  def get_multiplier(self):
    return self._multiplier

  def get_param(self, param):
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

  def is_inflated(self):
    # right now only 'none' and 'real' are options, so this is boolean
    ## when nominal is implemented, might need to extend this method a bit
    return self._inflation != 'none'

  def is_mult_target(self):
    return self._mult_target

  def is_taxable(self):
    return self._taxable

