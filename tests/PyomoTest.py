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
  Tests that TEAL can create Pyomo-style expressions when passed vardata instead of floats
"""
import os
import sys
from functools import partial

import numpy as np
import pandas as pd
import pyomo.environ as pyo

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..','..'))) # Path to access ravenframework
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..','raven'))) # Path to access ravenframework
from TEAL import CashFlows
from TEAL import CashFlow as RunCashFlow


# *** HELPER FUNCTIONS ***
def build_econ_settings(cfs, life=5, dr=0.1, tax=0.21, infl=0.02184):
  """
    Constructs global settings for econ run
    @ In, cfs, CashFlow, cash flow components
    @ In, life, float, life time of the years to evaluate
    @ In, dr, float, discount rate
    @ In, tax, float, the amount of tax ratio to apply
    @ In, infl, float, the amount of inflation ratio to apply
    @ Out, settings, CashFlow.GlobalSettings, settings
  """
  active = []
  for comp_name, cf_list in cfs.items():
    for cf in cf_list:
      active.append(f'{comp_name}|{cf}')
  print(active)
  params = {'DiscountRate': dr,
            'tax': tax,
            'inflation': infl,
            'ProjectTime': life,
            'Indicator': {'name': ['NPV'],
                          'active': active}
           }
  settings = CashFlows.GlobalSettings()
  settings.setParams(params)
  settings._verbosity = 0
  return settings


def build_generator(size, lifetime, dispatch):
  """
    Constructs the cash flow of each applicable components
    @ In, size, pyomo.core.base.var, build size
    @ In, lifetime, int, life time of the years to evaluate
    @ In, dispatch, numpy array, dispatch variables
    @ Out, generator, CashFlow.GlobalSettings, settings
  """
  # make the TEAL component
  generator = CashFlows.Component()
  generator.setParams({'name': 'Generator', 'Life_time': lifetime})
  # cash flows for generator
  cfs = []

  ## capex
  alpha = -1000.0 # $1000 to build a 1 MW generator
  capex = createCapex(generator, alpha, size)
  cfs.append(capex)
  # -> amortize the capex
  capex.setAmortization('MACRS', 3)
  amorts = generator._createDepreciation(capex)
  cfs.extend(amorts)

  ## fixed OM
  alpha = -10.0 # $10/y for upkeep of a 1 MW generator
  fixed_om = createRecurringYearly(generator, alpha, size)
  cfs.append(fixed_om)

  ## variable OM
  alpha = -1.0 # $0.10 per MWh produced
  var_om = createRecurringHourly(generator, alpha, dispatch)
  cfs.append(var_om)

  generator.addCashflows(cfs)
  return generator


def build_market(size, life, prices, dispatch):
  """
    Constructs the cash flow of each applicable components
    @ In, size, pyomo.core.base.var, build size
    @ In, life, int, life time of the years to evaluate
    @ In, prices, numpy array, values of pricing
    @ In, dispatch, numpy array, dispatch variables
    @ Out, market, TEAL.src.CashFlows.Component, hourly cashflow sales for each component
  """
  market = CashFlows.Component()
  market.setParams({'name': 'Market', 'Life_time': life})
  # cash flows for generator
  cfs = []

  ## market sales
  sales = createRecurringHourly(market, prices, dispatch)
  cfs.append(sales)

  market.addCashflows(cfs)
  return market


def createCapex(comp, alpha, driver):
  """
    Constructs the parameters for capital expenditures
    @ In, comp, TEAL.src.CashFlows.Component, main structure to add component cash flows
    @ In, alpha, float, price
    @ In, driver, pyomo.core.base.var.ScalarVar, quantity sold
    @ Out, cf, TEAL.src.CashFlows.Component, cashflow sale for each capital expenditures
  """
  life = comp.getLifetime()
  # extract alpha, driver as just one value
  cf = CashFlows.Capex()
  cf.name = 'Cap'
  cf.initParams(life)
  cfParams = {'name': 'Cap',
               'alpha': alpha,
               'driver': driver,
               'reference': 1.0,
               'X': 1.0,
               'depreciate': 3,
               'mult_target': None,
               'inflation': False,
               }
  cf.setParams(cfParams)
  return cf


def createRecurringYearly(comp, alpha, driver):
  """
    Constructs the parameters for capital expenditures
    @ In, comp, TEAL.src.CashFlows.Component, main structure to add component cash flows
    @ In, alpha, float, yearly price to populate
    @ In, driver, pyomo.core.base.var.ScalarVar, quantity sold to populate
    @ Out, cf, TEAL.src.CashFlows.Component, cashflow sale for the recurring yearly
  """
  life = comp.getLifetime()
  cf = CashFlows.Recurring()
  cfFarams = {'name': 'FixedOM',
               'X': 1,
               'mult_target': None,
               'inflation': False}
  cf.setParams(cfFarams)
  # 0 for first year (build year) -> TODO couldn't this be automatic?
  alphas = np.ones(life+1, dtype=object) * alpha
  drivers = np.ones(life+1, dtype=object) * driver
  alphas[0] = 0
  drivers[0] = 0
  # construct annual summary cashflows
  cf.computeYearlyCashflow(alphas, drivers)
  return cf


def createRecurringHourly(comp, alpha, driver):
  """
    Constructs recurring cashflow with one value per hour
    @ In, dfSet, tuple, includes pandas.Dataframe, dict of inputs, and pyomo concrete model loaded
    sto run
    @ In, comp, CashFlow.Component, component this cf will belong to
    @ In, driver, string, variable name in df to take driver from
    @ In, alpha, string, variable name in df to take alpha from
    @ Out, comps, dict, dict mapping names to CashFlow component objects
  """
  life = comp.getLifetime()
  print('DEBUGG cRH life:', comp.name, life)
  cf = CashFlows.Recurring()
  cfParams = {'name': 'Hourly',
               'X': 1,
               'mult_target': None,
               'inflation': False}
  cf.setParams(cfParams)
  cf.initParams(life, pyomoVar=True)
  for year in range(life):
    if isinstance(alpha, float):
      cf.computeIntrayearCashflow(year, alpha, driver[year, :])
    else:
      cf.computeIntrayearCashflow(year, alpha[year, :], driver[year, :])
  return cf


# main
if __name__ == '__main__':
  # problem characteristics
  project_life = 5
  hours_in_year = 10
  hours = np.arange(hours_in_year)

  # create the global cashflow settings
  expected_cfs = {'Generator': ['Cap', 'FixedOM', 'Hourly'],
                  'Market': ['Hourly']}
  tealSettings = build_econ_settings(expected_cfs, life=project_life)

  m = pyo.ConcreteModel()
  m.T = pyo.Set(initialize=hours)

  ## for this problem, let's just have 2 components, a source and a sink
  ## - source ("generator")
  ##   - has a capex, fixed OM (yearly recurring), and variable OM (hourly recurring)
  ##   - variable total size
  ##   - variable dispatch
  ## - sink ("market")
  ##   - has sales profit (hourly recurring)
  ##   - fixed size

  # then we start creating components
  tealComps = {}


  # *** GENERATOR ***
  # make the Pyomo variables, constants
  generator_life = 5 # years of operation before replacement
  generator_size = pyo.Var(initialize=1, bounds=(0, 100)) # build size, limit to 100 MW
  m.gen_size = generator_size

  # set up the generator's dispatch variables
  generator_dispatch = np.zeros((generator_life, hours_in_year), dtype=object)
  for y in range(generator_life):
    # make a new pyomo var for this "year"'s dispatch
    var = pyo.Var(list(range(hours_in_year)), initialize=lambda m, t: 0, bounds=lambda m, t: (0, 100)) #generator_size))
    setattr(m, f'Gen_disp_year_{y+1}', var)
    generator_dispatch[y, :] = np.array(list(var.values()))

  generator = build_generator(generator_size, generator_life, generator_dispatch)

  # *** MARKET ***
  # make the TEAL component
  market_size = 50 # market depth
  market_life = 5 # years of operation before replacement
  # market prices should be interesting, say cos(x) + y/10 where x is hour and y is year
  prices = np.ones((market_life, hours_in_year))
  prices[:] *= np.cos(hours) * 100
  for y in range(market_life):
    if y % 2 == 0:
      prices[y, :] *= -1

  # market has similar dispatch to generator, that we'll attach through constraints
  market_dispatch = np.zeros((market_life, hours_in_year), dtype=object)
  for y in range(market_life):
    # make a new pyomo var for this "year"'s dispatch
    var = pyo.Var(list(range(hours_in_year)), initialize=lambda m, t: 0, bounds=lambda m, t: (0, market_size))
    setattr(m, f'Market_disp_year_{y+1}', var)
    market_dispatch[y, :] = np.array(list(var.values()))

  market = build_market(market_size, market_life, prices, market_dispatch)

  metrics = RunCashFlow.run(tealSettings, [generator, market], {}, pyomoVar=True) # Past version was pyomoChk

  # now set up the rest of the Pyomo model

  # *** Constraints ***
  # hourly conservation of electricity
  def conserve_elec(y, m, t):
    gen = getattr(m, f'Gen_disp_year_{y+1}')
    mkt = getattr(m, f'Market_disp_year_{y+1}')
    return gen[t] == mkt[t]

  for y in range(project_life):
    con = pyo.Constraint(m.T, rule=partial(conserve_elec, y))
    setattr(m, f'conserve_{y+1}', con)

  # hourly dispatch < gen size
  def size_limit(size, y, m, t):
    gen = getattr(m, f'Gen_disp_year_{y+1}')
    return gen[t] <= size

  for y in range(project_life):
    lim = pyo.Constraint(m.T, rule=partial(size_limit, generator_size, y))
    setattr(m, f'size_{y+1}', lim)

  # Objective: NPV
  m.npv = pyo.Objective(expr=metrics['NPV'], sense=pyo.maximize)

  # solve pyomo problem
  solver = pyo.SolverFactory('ipopt')
  results = solver.solve(m)
  print('Display Results:')
  m.display()
  calculatedNPV = pyo.value(m.npv) # Changed from print(m.npv.value)
  calculatedGenSize = m.gen_size.value
  correctNPV = 10164.740285148146
  correctGenSize = 50.00000048819408
  # Checking if market values are alternating as anticipated
  check = 0
  for i in range(10):
    if m.Market_disp_year_1[i].value == m.Market_disp_year_2[i].value:
      check += 1
    else:
      continue
  # Final check
  if abs(calculatedNPV - correctNPV)/correctNPV < 1e-8 and abs(calculatedGenSize - correctGenSize)/correctGenSize < 1e-8 and check == 0:
    print('Success!')
    sys.exit(0)
  else:
    if abs(calculatedNPV - correctNPV)/correctNPV >= 1e-8:
      print('ERROR: correct NPV: {:1.3e}, calculated NPV: {:1.3e}, diff {:1.3e}'.format(correctNPV, calculatedNPV, correctNPV-calculatedNPV))
    if abs(calculatedGenSize - correctGenSize)/correctGenSize >= 1e-8:
      print('ERROR: correct generation size: {:1.3e}, calculated generation size: {:1.3e}, diff {:1.3e}'.format(correctGenSize, calculatedGenSize, correctGenSize-calculatedGenSize))
    if check != 0:
      print('ERROR: there are {:} market values between consecutive years that should not be matching.'.format(check))
    sys.exit(1)
