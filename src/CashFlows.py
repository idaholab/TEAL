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
from utils import InputData, xmlUtils



class GlobalSettings:
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
    if isinstance(source, ET.Element):
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
        self._project_time = val
      elif name == 'Indicator':
        self._indicators = node.parameterValues['name']
        self._metric_target = node.parameterValues.get('target', None)
        active_cf = val
        self._active_components = defaultdict(list)
        print('DEBUGG val:', val)
        for request in active_cf:
          print('DEBUGG request:', request)
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

  def get_active_components(self):
    return self._active_components

  def get_project_time(self):
    return self._project_time

  def get_indicators(self):
    return self._indicators

  def get_discount_rate(self):
    return self._discount_rate

  def get_metric_target(self):
    return self._metric_target

  def get_tax(self):
    return self._tax

  def get_inflation(self):
    return self._inflation




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
    comp.addSub(InputData.parameterInputFactory('StartTime', contentType=InputData.FloatType))
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
    if isinstance(source, ET.Element):
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

  def count_multitargets(self):
    return sum(cf._mult_target is not None for cf in self._cash_flows)

  #######
  # API #
  #######
  def incremental_cost(self, activity, raven_vars, meta, t):
    """
      Calculates the incremental cost of a particular system configuration.
      @ In, activity, XArray.DataArray, array of driver-centric variable values
      @ In, raven_vars, dict, additional inputs from RAVEN call (or similar)
      @ In, meta, dict, additional user-defined meta
      @ In, t, int, time of current evaluation (if any) # TODO default?
      @ Out, cost, float, cash flow evaluation
    """
    # combine into a single dict for the evaluation calls
    info = {'raven_vars': raven_vars, 'meta': meta, 't': t}
    # combine all cash flows into single cash flow evaluation
    cost = dict((cf.name, cf.evaluate_cost(activity, info)) for cf in self._cash_flows)
    return cost

  # def get_component(self):
  #   """
  #     Return the cash flow user that owns this group
  #     @ In, None
  #     @ Out, component, CashFlowUser instance, owner
  #   """
  #   return self._owner

  def get_lifetime(self):
    """
      Provides the lifetime of this cash flow user.
      @ In, None
      @ Out, lifetime, int, lifetime
    """
    return self._lifetime

  def get_start_time(self):
    return self._start_time

  def get_repetitions(self):
    return self._repetitions

  def get_cashflow(self, name):
    for cf in self._cash_flows:
      if cf.name == name:
        return cf

  def get_cashflows(self):
    return self._cash_flows

  def get_multipliers(self):
    return list(cf.get_multiplier() for cf in self._cash_flows)

  def get_tax(self):
    return self._specific_tax

  def get_inflation(self):
    return self._specific_inflation







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
    infl = InputData.makeEnumType('inflation_types', 'inflation_type', ['real', 'nominal', 'none'])
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

  def is_mult_target(self):
    return self._mult_target

  def get_multiplier(self):
    return self._multiplier

  def is_taxable(self):
    return self._taxable

  def is_inflated(self):
    return self._inflation

  def _set_valued_param(self, name, spec):
    """
      Utilitly method to set ValuedParam members via reading input specifications.
      @ In, name, str, member variable name (e.g. self.<name>)
      @ In, spec, InputData params, input parameters
      @ Out, None
    """
    vp = ValuedParam(name)
    signal = vp.read('CashFlow \'{}\''.format(self.name), spec, None) # TODO what "mode" to use?
    self._signals.update(signal)
    self._crossrefs[name] = vp
    # alias: redirect "capacity" variable
    if vp.type == 'variable' and vp._sub_name == 'capacity':
      vp = self._component.get_capacity_param()
    setattr(self, name, vp)

  def get_crossrefs(self):
    """
      Accessor for cross-referenced entities needed by this cashflow.
      @ In, None
      @ Out, crossrefs, dict, cross-referenced requirements dictionary
    """
    return self._crossrefs

  def set_crossrefs(self, refs):
    """
      Setter for cross-referenced entities needed by this cashflow.
      @ In, refs, dict, cross referenced entities
      @ Out, None
    """
    for attr, obj in refs.items():
      valued_param = self._crossrefs[attr]
      valued_param.set_object(obj)

  def evaluate_cost(self, activity, values_dict):
    """
      Evaluates cost of a particular scenario provided by "activity".
      @ In, activity, pandas.Series, multi-indexed array of scenario activities
      @ In, values_dict, dict, additional values that may be needed to evaluate cost
      @ Out, cost, float, cost of activity
    """
    # note this method gets called a LOT, so speedups here are quite effective
    # "activity" is a pandas series with production levels -> example from EGRET case
    # build aliases
    aliases = {} # currently unused, but mechanism left in place
    #aliases['capacity'] = '{}_capacity'.format(self._component.name)
    # for now, add the activity to the dictionary # TODO slow, speed this up
    res_vals = activity.to_dict()
    values_dict['raven_vars'].update(res_vals)
    params = self.calculates_params(values_dict, aliases=aliases)
    return params['cost']

  def is_finalized(self):
    """
      Checks if this CashFlow is finalized (i.e. no entries are ValuedParams)
      @ In, None
      @ Out, is_finalized, bool, True if finalized
    """
    return all(not isinstance(x, ValuedParam) for x in [self._driver, self._alpha, self._reference, self._scale])

  def finalize(self, params):
    """
      Finalize the economic parameters for this cash flow, replacing ValuedParams with evaluated values.
      @ In, params, dict, each parameter evaluated either once or at each time step
      @ Out, None
    """
    # alpha is an averaged quantity
    self._alpha = np.atleast_1d(params['alpha']).average()
    # driver is a total quantity
    self._driver = np.atleast_1d(params['driver']).sum()
    # reference, scaling are singular quantities
    assert len(np.atleast_1d(params['ref_driver'])) == 1
    self._reference = float(params['ref_driver'])
    assert len(np.atleast_1d(params['scaling'])) == 1
    self._scale = float(params['scaling'])

    # ?? mult?


  def calculate_params(self, values_dict, aliases=None, aggregate=False):
    """
      Calculates the value of the cash flow parameters.
      @ In, values_dict, dict, mapping from simulation variable names to their values (as floats or numpy arrays)
      @ In, aliases, dict, optional, means to translate variable names using an alias. Not well-tested!
      @ In, aggregate, bool, optional, if True then make an effort to collapse array values to floats meaningfully
      @ Out, params, dict, dictionary of parameters mapped to values including the cost
    """
    if aliases is None:
      aliases = {}
    a = self._alpha.evaluate(values_dict, target_var='reference_price', aliases=aliases)[0]['reference_price']
    D = self._driver.evaluate(values_dict, target_var='driver', aliases=aliases)[0]['driver']
    Dp = self._reference.evaluate(values_dict, target_var='reference_driver', aliases=aliases)[0]['reference_driver']
    x = self._scale.evaluate(values_dict, target_var='scaling_factor_x', aliases=aliases)[0]['scaling_factor_x']
    if aggregate:
      # parameters might be time-dependent, so aggregate them appropriately
      ## "alpha" should be the average price
      if len(np.atleast_1d(a)) > 1:
        a = float(a.average())
      ## "D" should be the total amount produced
      if len(np.atleast_1d(D)) > 1:
        D = float(a.sum())
      ## neither "x" nor "Dp" should have time dependence, # TODO assumption for now.
    cost = a * (D / Dp) ** x
    return {'alpha': a, 'driver': D, 'ref_driver': Dp, 'scaling': x, 'cost': float(cost)}

  def calculate_lifetime_cashflow(self, lifetime, params=None, values_dict=None):
    if params is None and values_dict is None:
      raise RuntimeError('Need either "params" or "values_dict" to evaluate "calculate_lifetime_cashflow"!')
    if params is not None and values_dict is not None:
      raise RuntimeError('Need ONLY ONE of "params" or "values_dict" to evaluate "calculate_lifetime_cashflow", not both!')
    # If we need to calculate the params ourselves, do that now
    if values_dict:
      params = self.calculate_params(values_dict, aggregate=True)
    # expand to lifetime if not already
    if lifetime > 1:
      # set how to expand values
      if self._type == 'one-time':
        expansion = np.zeros(lifetime)
      for par in ['alpha', 'driver', 'ref_driver', 'scaling']:
        val = params[par]
        if len(np.atleast_1d(val)) == 1:
          params[par] = ones * val

