"""
  Defines the Economics entity.
  Each component (or source?) can have one of these to describe its economics.
"""
from __future__ import unicode_literals, print_function
import os
import sys
from collections import defaultdict

from ValuedParams import ValuedParam

raven_path = '~/projects/raven/framework' # TODO fix with plugin relative path
sys.path.append(os.path.expanduser(raven_path))
from utils import InputData, xmlUtils



class CashFlowGroup:
  # Just a holder for multiple cash flows, and methods for doing stuff with them
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
    specs = InputData.parameterInputFactory('economics', ordered=False, baseNode=None)
    specs.addSub(InputData.parameterInputFactory('lifetime', contentType=InputData.FloatType))
    cf = CashFlow.get_input_specs()
    specs.addSub(cf)
    return specs

  def __init__(self, component):
    """
      Constructor.
      @ In, component, CashFlowUser instance, object to which this group belongs
      @ Out, None
    """
    self._component = component # component this one
    self._lifetime = None # lifetime of the component
    self._cash_flows = []

  def read_input(self, source, xml=False):
    """
      Sets settings from input file
      @ In, source, InputData.ParameterInput, input from user
      @ In, xml, bool, if True then XML is passed in, not input data
      @ Out, None
    """
    print(' ... loading economics ...')
    # allow read_input argument to be either xml or input specs
    if xml:
      specs = self.get_input_specs()()
      specs.parseNode(source)
    else:
      specs = source
    # read in specs
    for item in specs.subparts:
      if item.getName() == 'Lifetime':
        self._lifetime = item.value
      elif item.getName() == 'CashFlow':
        new = CashFlow(component=self._component)
        new.read_input(item)
        self._cash_flows.append(new)

  def get_crossrefs(self):
    """
      Provides a dictionary of the entities needed by this cashflow group to be evaluated
      @ In, None
      @ Out, crossreffs, dict, dictionary of crossreferences needed (see ValuedParams)
    """
    crossrefs = dict((cf, cf.get_crossrefs()) for cf in self._cash_flows)
    return crossrefs

  def set_crossrefs(self, refs):
    """
      Provides links to entities needed to evaluate this cash flow group.
      @ In, refs, dict, reference entities
      @ Out, None
    """
    for cf in list(refs.keys()):
      for try_match in self._cash_flows:
        if try_match == cf:
          try_match.set_crossrefs(refs.pop(try_match))
          break

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

  def get_component(self):
    """
      Return the cash flow user that owns this group
      @ In, None
      @ Out, component, CashFlowUser instance, owner
    """
    return self._component

  def get_lifetime(self):
    """
      Provides the lifetime of this cash flow user.
      @ In, None
      @ Out, lifetime, int, lifetime
    """
    return self._lifetime



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
    cf.addParam('type', param_type=InputData.StringType, required=True)
    cf.addParam('taxable', param_type=InputData.BoolType, required=True)
    cf.addParam('inflation', param_type=InputData.StringType, required=True)
    cf.addParam('mult_target', param_type=InputData.BoolType, required=True)

    cf.addSub(ValuedParam.get_input_specs('driver'))
    cf.addSub(ValuedParam.get_input_specs('reference_price'))
    cf.addSub(ValuedParam.get_input_specs('reference_driver'))
    cf.addSub(ValuedParam.get_input_specs('scaling_factor_x'))
    return cf

  def __init__(self, component):
    """
      Constructor
      @ In, component, CashFlowUser instance, cash flow user to which this cash flow belongs
      @ Out, None
    """
    # assert component is not None # TODO is this necessary? What if it's not a component-based cash flow?
    self._component = component # component instance to whom this cashflow belongs, if any
    # equation values
    self._driver = None       # ValuedParam "quantity produced", D
    self._alpha = None        # ValuedParam "price per produced", a
    self._reference = None    # ValuedParam "where price is accurate", D'
    self._scale = None        # ValuedParam "economy of scale", x
    # other params
    self.name = None          # base name of cash flow
    self._type = None         # needed? one-time, yearly, repeating
    self._taxable = None      # apply tax or not
    self._inflation = None    # apply inflation or not
    self._mult_target = None  # not clear
    # other members
    self._signals = set()     # variable values needed for this cash flow
    self._crossrefs = defaultdict(dict)

  def read_input(self, item):
    """
      Sets settings from input file
      @ In, item, InputData.ParameterInput, parsed specs from user
      @ Out, None
    """
    self.name = item.parameterValues['name']
    print(' ... ... loading cash flow "{}"'.format(self.name))
    # handle type directly here momentarily
    self._taxable = item.parameterValues['taxable']
    self._inflation = item.parameterValues['inflation']
    self._mult_target = item.parameterValues['mult_target']
    # the remainder of the entries are ValuedParams, so they'll be evaluated as-needed
    for sub in item.subparts:
      if sub.getName() == 'driver':
        self._set_valued_param('_driver', sub)
      elif sub.getName() == 'reference_price':
        self._set_valued_param('_alpha', sub)
      elif sub.getName() == 'reference_driver':
        self._set_valued_param('_reference', sub)
      elif sub.getName() == 'scaling_factor_x':
        self._set_valued_param('_scale', sub)
      else:
        raise IOError('Unrecognized "CashFlow" node: "{}"'.format(sub.getName()))

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
    # "activity" is a pandas series with production levels
    # build aliases
    aliases = {} # currently unused, but mechanism left in place
    #aliases['capacity'] = '{}_capacity'.format(self._component.name)
    # for now, add the activity to the dictionary # TODO slow, speed this up
    res_vals = activity.to_dict()
    values_dict['raven_vars'].update(res_vals)
    a = self._alpha.evaluate(values_dict, target_var='reference_price', aliases=aliases)[0]['reference_price']
    D = self._driver.evaluate(values_dict, target_var='driver', aliases=aliases)[0]['driver']
    Dp = self._reference.evaluate(values_dict, target_var='reference_driver', aliases=aliases)[0]['reference_driver']
    x = self._scale.evaluate(values_dict, target_var='scaling_factor_x', aliases=aliases)[0]['scaling_factor_x']
    cost = a * (D / Dp) ** x
    #print('DEBUGG evaluated cost for comp "{}" cf "{}": {}'.format(self._component.name, self.name, cost))
    return float(cost)

