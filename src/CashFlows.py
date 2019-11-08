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
import time

try:
  from CashFlow.src import Amortization
# NOTE this import exception is ONLY to allow RAVEN to directly import this extmod.
# In general, this should not exist, and RAVEN should import CashFlow.CashFlow_ExtMod instead of importing CashFlow_ExtMod directly, implicitly.
except ImportError:
  import Amortization

raven_path = ((os.path.dirname(__file__)))#'~/projects/raven/framework' # TODO fix with plugin relative path
raven_path=raven_path+'/../../../framework'
print(raven_path)
#print(raven_path,type(raven_path))
#print(os.path.dirname(__file__),raven_path)
#time.sleep(300)
#print(os.path.expanduser(raven_path))
#time.sleep(300)
#print(os.path.expanduser(raven_path))
#time.sleep(300)
sys.path.append(os.path.expanduser(raven_path))
#print (os.getcwd())
#print (os.path.abspath(os.path.dirname(__file__)))
#time.sleep(300)

## Import error from utils need to be fixed for this file to work
from utils import utils, InputData, xmlUtils, TreeStructure



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
    # TODO make read_input call set_params so there's a uniform place to change things!
    if isinstance(source, (ET.Element, TreeStructure.InputNode)):
      specs = self.get_input_specs()()
      specs.parseNode(source)
    else:
      specs = source
    for node in specs.subparts:
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
          try:
            comp, cf = request.split('|')
          except ValueError:
            raise IOError('Expected active components in <Indicators> to be formatted as Component|Cashflow, but got {}'.format(request))
          self._active_components[comp].append(cf)
    self.check_initialization()

  def set_params(self, param_dict):
    """
      Sets the settings from a dictionary, instead of via an input file.
      @ In, param_dict, dict, settings
      @ Out, None
    """
    for name, val in param_dict.items():
      if name == 'DiscountRate':
        self._discount_rate = val
      elif name == 'tax':
        self._tax = val
      elif name == 'inflation':
        self._inflation = val
      elif name == 'ProjectTime':
        self._project_time = val + 1 # one for the construction year!
      elif name == 'Indicator':
        self._indicators = val['name']
        self._metric_target = val.get('target', None)
        active_cf = val['active']
        self._active_components = defaultdict(list)
        for request in active_cf:
          try:
            comp, cf = request.split('|')
          except ValueError:
            raise IOError('Expected active components in <Indicators> to be formatted as Component|Cashflow, but got {}'.format(request))
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
  node_var_map = {'Life_time': '_lifetime',
                  'StartTime': '_start_time',
                  'Repetitions': '_repetitions',
                  'tax': '_specific_tax',
                  'inflation': '_specific_inflation',
                  }
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
    #cf = CashFlow.get_input_specs()
    #comp.addSub(cf)
    cfs = InputData.parameterInputFactory('CashFlows')
    cfs.addSub(Capex.get_input_specs())
    cfs.addSub(Recurring.get_input_specs())
    comp.addSub(cfs)
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
    ## since all of these are simple value setters, use a mapping
    for item_name, attr in self.node_var_map.items():
      item = specs.findFirst(item_name)
      if item is not None:
        setattr(self, attr, item.value)
    cfs = specs.findFirst('CashFlows')
    if cfs is not None:
      for sub in cfs.subparts:
        new_cfs = self._cash_flow_factory(sub) #CashFlow(self.name, verbosity=self._verbosity)
        self.add_cashflows(new_cfs)
    self.check_initialization()

  def set_params(self, param_dict):
    for name, value in param_dict.items():
      if name == 'name':
        self.name = value
      elif name == 'cash_flows':
        self._cash_flows = value
      else:
        # remainder are mapped
        attr_name = self.node_var_map.get(name, None)
        if attr_name is None:
          continue
        setattr(self, attr_name, value)
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
      # set up parameters to match this component's lifetime
      params = dict((attr, cf.get_param(attr)) for attr in ['alpha', 'driver'])
      params = cf.extend_parameters(params, self._lifetime+1)
      cf.set_params(params)
      # alpha needs to be either: a variable (Recurring type cash flow) or a lifetime+1 length array
      # TODO move check to specific cashflows!
      cf.check_param_lengths(self._lifetime+1)
    # TODO this isn't a check, this is setting defaults. Should this be a different method?
    if self._start_time is None:
      self._start_time = 0
    if self._repetitions is None:
      self._repetitions = 0 # NOTE that 0 means infinite repetitions!

  #######
  # API #
  #######
  def add_cashflows(self, cf):
    self._cash_flows.extend(cf)

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

  #############
  # UTILITIES #
  #############
  def _cash_flow_factory(self, specs):
    """ based on the InputData specs provided, returns the appropriate CashFlow """
    created = []
    # get the type of this node, whether we're talking XML or RAVEN.InputData
    if not isinstance(specs, InputData.ParameterInput):
      raise TypeError('Unrecognized source specifications type: {}'.format(type(specs)))
    # create the appropriate cash flows
    typ = specs.getName()
    if typ == 'Recurring':
      # this is simple, only need one cash flow to be created
      new = Recurring(component=self.name, verbosity=self._verbosity)
      new.read_input(specs)
      created.append(new)
    elif typ == 'Capex':
      # in addition to the node itself, need to add depreciation if requested
      new = Capex(component=self.name, verbosity=self._verbosity)
      new.read_input(specs)
      deprs = self._create_depreciation(new)
      created.append(new)
      created.extend(deprs)
    #elif typ == 'Custom':
    #  new = CashFlow(self.name, self._verbosity)
    #  created.append(new)
    else:
      raise TypeError('Unrecognized cash flow type:', typ)
    return created

  def _create_depreciation(self, ocf):
    """ creates amortization cash flows depending on the originating capex cash flow """
    # use the reference plant price
    amort = ocf.get_amortization()
    if amort is None:
      return []
    print('DEBUGG amortizing cf:', ocf.name)
    original_value = ocf.get_param('alpha') * -1.0 #start with a positive value
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
              'reference': 1.0, #ocf.get_param('reference'),
              'X': 1.0, #ocf.get_param('scale')
              }
    pos.set_params(params)
    # second cash flow is as the first, except negative and taxed
    neg = Amortizor(component=self.name, verbosity=self._verbosity)
    n_alpha = np.zeros(len(alpha))
    n_alpha[alpha != 0] = -1
    print('DEBUGG amort alpha:', alpha)
    print('DEBUGG depre alpha:', n_alpha)
    params = {'name': '{}_{}_{}'.format(self.name, 'depreciate', ocf.name),
              'driver': '{}|{}'.format(self.name, pos.name),
              'tax': True,
              'inflation': 'real',
              'alpha': n_alpha,
              'reference': 1.0,
              'X': 1.0}
    neg.set_params(params)
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
  missing_node_template = 'Component "{comp}" CashFlow "{cf}" is missing the <{node}> node!'

  @classmethod
  def get_input_specs(cls, specs):
    """
      Collects input specifications for this class.
      @ In, specs, InputData, specs
      @ Out, specs, InputData, specs
    """
    # ONLY appends to existinc specs!
    #cf = InputData.parameterInputFactory('CashFlow')

    specs.addParam('name', param_type=InputData.StringType, required=True)
    specs.addParam('tax', param_type=InputData.BoolType, required=False)
    infl = InputData.makeEnumType('inflation_types', 'inflation_type', ['real', 'none']) # "nominal" not yet implemented
    specs.addParam('inflation', param_type=infl, required=False)
    specs.addParam('mult_target', param_type=InputData.BoolType, required=False)
    specs.addParam('multiply', param_type=InputData.StringType, required=False)

    specs.addSub(InputData.parameterInputFactory('driver', contentType=InputData.InterpretedListType))
    specs.addSub(InputData.parameterInputFactory('alpha', contentType=InputData.InterpretedListType))
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
    self._mult_target = None  # true if this cash flow gets multiplied by a global multiplier (e.g. NPV=0 search) (?)
    self._multiplier = None   # arbitrary scalar multiplier (variable name)
    self._depreciate = None

  def read_input(self, item):
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
        self._mult_target = value
      elif key == 'multiply':
        self._multiplier = value
    for sub in item.subparts:
      if sub.getName() == 'alpha':
        self._alpha = self.set_variable_or_floats(sub.value)
      elif sub.getName() == 'driver':
        self._driver = self.set_variable_or_floats(sub.value)
      if sub.getName() == 'reference':
        self._reference = sub.value
      elif sub.getName() == 'X':
        self._scale = sub.value
    self.check_initialization()

  def set_params(self, param_dict):
    for name, val in param_dict.items():
      if name == 'name':
        self.name = val
      elif name == 'driver':
        self._driver = val
      elif name == 'tax':
        self._taxable = val
      elif name == 'inflation':
        self._inflation = val
      elif name == 'mult_target':
        self._mult_target = val
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
    self.check_initialization()

  def check_initialization(self):
    """
      Checks that the reading in of inputs resulted in a sensible
      set of data. Should be checked whenever a new CashFlow is created
      and initialized.
      @ In, None
      @ Out, None
    """
    pass # nothing specific to check in base

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

  def get_amortization(self):
    return None

  def is_inflated(self):
    # right now only 'none' and 'real' are options, so this is boolean
    ## when nominal is implemented, might need to extend this method a bit
    return self._inflation != 'none'

  def is_mult_target(self):
    return self._mult_target

  def is_taxable(self):
    return self._taxable

  def set_variable_or_floats(self, value):
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

  def load_from_variables(self, need, variables, cashflows, lifetime):
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
    need = self.extend_parameters(need, lifetime)
    return need

  def extend_parameters(self, need, lifetime):
    # should be overwritten in the inheriting classes!
    raise NotImplementedError





class Capex(CashFlow):
  @classmethod
  def get_input_specs(cls):
    specs = InputData.parameterInputFactory('Capex')
    specs = CashFlow.get_input_specs(specs)
    specs.addSub(InputData.parameterInputFactory('reference', contentType=InputData.FloatType))
    specs.addSub(InputData.parameterInputFactory('X', contentType=InputData.FloatType))
    deprec = InputData.parameterInputFactory('depreciation', contentType=InputData.InterpretedListType)
    deprec_schemes = InputData.makeEnumType('deprec_types', 'deprec_types', ['MACRS', 'custom'])
    deprec.addParam('scheme', param_type=deprec_schemes, required=True)
    specs.addSub(deprec)
    #print(specs.subs)
    return specs

  def __init__(self, **kwargs):
    CashFlow.__init__(self, **kwargs)
    # new variables
    self.type = 'Capex'
    self._amort_scheme = None # amortization scheme for depreciating this capex
    self._amort_plan = None   # if scheme is MACRS, this is the years to recovery. Otherwise, vector percentages.
    # set defaults different from base class
    self.type = 'Capex'
    self._taxable = False
    self._inflation = False

  def read_input(self, item):
    for sub in item.subparts:
      if sub.getName() == 'depreciation':
        self._amort_scheme = sub.parameterValues['scheme']
        self._amort_plan = sub.value
    CashFlow.read_input(self, item)

  def check_initialization(self):
    CashFlow.check_initialization(self)
    if self._reference is None:
      raise IOError(self.missing_node_template.format(comp=self._component, cf=self.name, node='reference'))
    if self._scale is None:
      raise IOError(self.missing_node_template.format(comp=self._component, cf=self.name, node='X'))
    if self._driver is None:
      raise IOError(self.missing_node_template.format(comp=self._component, cf=self.name, node='driver'))
    if self._alpha is None:
      raise IOError(self.missing_node_template.format(comp=self._component, cf=self.name, node='alpha'))

  def init_params(self, lifetime):
    self._alpha = np.zeros(1 + lifetime)
    self._driver = np.zeros(1 + lifetime)

  def get_amortization(self):
    if self._amort_scheme is None:
      return None
    else:
      return self._amort_scheme, self._amort_plan

  def set_amortization(self, scheme, plan):
    self._amort_scheme = scheme
    self._amort_plan = np.atleast_1d(plan)

  def extend_parameters(self, to_extend, t):
    # for capex, both the Driver and Alpha are nonzero in year 1 and zero thereafter
    for name, value in to_extend.items():
      if name.lower() in ['alpha', 'driver']:
        if utils.isAFloatOrInt(value) or (len(value) == 1 and utils.isAFloatOrInt(value[0])):
          new = np.zeros(t)
          new[0] = float(value)
          to_extend[name] = new
    return to_extend

  def calculate_cashflow(self, variables, lifetime_cashflows, lifetime, verbosity):
    """ sets up the COMPONENT LIFETIME cashflows, and calculates yearly for the comp life """
    ## FIXME what if I have set the values already?
    # get variable values, if needed
    need = {'alpha': self._alpha, 'driver': self._driver}
    # load alpha, driver from variables if need be
    need = self.load_from_variables(need, variables, lifetime_cashflows, lifetime)
    # for Capex, use m * alpha * (D/D')^X
    alpha = need['alpha']

    driver = need['driver']
    reference = self.get_param('reference')
    if reference is None:
      reference = 1.0
    scale = self.get_param('scale')
    if scale is None:
      scale = 1.0
    mult = self.get_multiplier()
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

  def check_param_lengths(self, lifetime, comp_name=None):
    for param in ['alpha', 'driver']:
      val = self.get_param(param)
      # if a string, then it's probably a variable, so don't check it now
      if utils.isAString(val):
        continue
      # if it's valued, then it better be the same length as the lifetime (which is comp lifetime + 1)
      elif len(val) != lifetime:
        pre_msg = 'Component "{comp}" '.format(comp_name) if comp_name is not None else ''
        raise IOError((pre_msg + 'cashflow "{cf}" node <{param}> should have {correct} '+\
                       'entries (1 + lifetime), but only found {found}!')
                       .format(cf=self.name,
                               correct=lifetime,
                               param=param,
                               found=len(val)))








class Recurring(CashFlow):
  @classmethod
  def get_input_specs(cls):
    specs = InputData.parameterInputFactory('Recurring')
    specs = CashFlow.get_input_specs(specs)
    # nothing new to add
    return specs

  def __init__(self, **kwargs):
    CashFlow.__init__(self, **kwargs)
    # set defaults different from base class
    self.type = 'Recurring'
    self._taxable = True
    self._inflation = True
    self._yearly_cashflow = None

  def extend_parameters(self, to_extend, t):
    # for recurring, both the Driver and Alpha are zero in year 1 and nonzero thereafter
    # we're going to integrate alpha * D over time (not year time, intrayear time), so no changes
    return to_extend

  def init_params(self, lifetime):
    # Recurring doesn't use m alpha D/D' X, it uses integral(alpha * D)dt for each year
    self._yearly_cashflow = np.zeros(lifetime+1)

  def compute_yearly_cashflow(self, year, alpha, driver):
    """
      Computes the yearly summary of recurring interactions, and sets them to self._yearly_cashflow
      @ In, year, int, the index of the project year for this summary
      @ In, alpha, np.array, array of "prices"
      @ In, driver, np.array, array of "quantities sold"
      @ Out, None
    """
    mult = self.get_multiplier()
    if mult is None:
      mult = 1.0
    elif utils.isAString(mult):
      raise NotImplementedError
    try:
      self._yearly_cashflow[year] = mult * (alpha * driver).sum() # +1 is for initial construct year
    except ValueError as e:
      print('Error while computing yearly cash flow! Check alpha shape ({}) and driver shape ({})'.format(alpha.shape, driver.shape))
      raise e

  def compute_yearly_cashflowzj(self, year, alpha, driver):
    """
      Computes the yearly summary of recurring interactions, and sets them to self._yearly_cashflow
      @ In, year, int, the index of the project year for this summary
      @ In, alpha, np.array, array of "prices"
      @ In, driver, np.array, array of "quantities sold"
      @ Out, None
    """
    mult = self.get_multiplier()

    if mult is None:
      mult = 1.0
    elif utils.isAString(mult):
      raise NotImplementedError
    try:
      self._yearly_cashflow = mult * (alpha * driver)
    except ValueError as e:
      print('Error while computing yearly cash flow! Check alpha shape ({}) and driver shape ({})'.format(alpha.shape, driver.shape))
      raise e

  def calculate_cashflow(self, variables, lifetime_cashflows, lifetime, verbosity):
    # by now, self._yearly_cashflow should have been filled with appropriate values
    # TODO reference, scale? we've already used mult (I think)
    self.init_params(lifetime-1)
    y = lifetime - 1
    self.compute_yearly_cashflowzj(y, self._alpha, variables[self._driver])
    #assert self._yearly_cashflow is not None
    return {'result': self._yearly_cashflow}

  def check_param_lengths(self, lifetime, comp_name=None):
    pass # nothing to do here, we don't check lengths since they'll be integrated intrayear

  def extend_parameters(self, to_extend, t):
    # for recurring, Alpha is zero in year 1 and given value thereafter
    for name, value in to_extend.items():
      if name.lower() in ['alpha']:
        if utils.isAFloatOrInt(value) or (len(value) == 1 and utils.isAFloatOrInt(value[0])):
          new = np.ones(t) * float(value)
          new[0] = 0
          to_extend[name] = new
    return to_extend


class Amortizor(Capex):
  def extend_parameters(self, to_extend, t):
    # unlike normal capex, for amortization we expand the driver to all nonzero entries and keep alpha as is
    # TODO forced driver values for now
    driver = to_extend['driver']
    # how we treat the driver depends on if this is the amortizer or the depreciator
    if self.name.split('_')[-2] == 'amortize':
      if not utils.isAString(driver):
        to_extend['driver'] = np.ones(t) * driver[0] * -1.0
        to_extend['driver'][0] = 0.0
      for name, value in to_extend.items():
        if name.lower() in ['driver']:
          if utils.isAFloatOrInt(value) or (len(value) == 1 and utils.isAFloatOrInt(value[0])):
            aaaaaaa
            new = np.zeros(t)
            new[1:] = float(value)
            to_extend[name] = new
    return to_extend
