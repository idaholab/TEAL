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
Created on March 23, 2018

@authors: C. Wang, P. Talbot, A. Alfonsi, A. S. Epiney

Integration test for using object-oriented API for components.
Does not use run-time variables, provides all values through arrays.
"""
import os
import sys
import numpy as np
import pandas as pd
import pyomo.environ as pyo
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from TEAL import CashFlows
from TEAL import CashFlow as RunCashFlow

def run(dfSet):
  """
    Main run command.
    @ In, dfSet, tuple, includes pandas.Dataframe, dict of inputs, and pyomo concrete model loaded
    to run
    @ Out, metrics, dict, dictionary of metric results
  """
  dictNew = {}
  m = pyo.ConcreteModel()
  for key, value in dfSet[1].items():
    setattr(m, key+'p', pyo.Var(list(range(len(value)))))
    if key == 'A':
      dictNew[key] = np.array(list(m.Ap.values()))
    elif key == 'B':
      dictNew[key] = np.array(list(m.Bp.values()))
    elif key == 'C':
      dictNew[key] = np.array(list(m.Cp.values()))
    else:
      dictNew[key] = np.array(list(m.Dp.values()))
    #dictNew[key] = np.array(list(y.values()))
  dfSetNew = (dfSet[0], dictNew, m)
  settings = build_econ_settings()
  components = build_econ_components(dfSetNew, settings)
  metrics = RunCashFlow.run(settings, list(components.values()), {}, pyomoChk=dfSetNew[2])
  return metrics, m

def build_econ_settings():
  """
    Constructs global settings for econ run
    @ In, None
    @ Out, settings, CashFlow.GlobalSettings, settings
  """
  params = {'DiscountRate': 0.10,
            'tax': 0.21,
            'inflation': 0.02184,
            'ProjectTime': 5,
            'Indicator': {'name': ['NPV'],
                          'active': ['MainComponent|RecursHourly', 'MainComponent|RecursYearly', 'MainComponent|Cap']}
           }
  settings = CashFlows.GlobalSettings()
  settings.setParams(params)
  settings._verbosity = 0
  return settings

def build_econ_components(dfSet, settings):
  """
    Constructs run components
    @ In, dfSet, tuple, includes pandas.Dataframe, dict of inputs, and pyomo concrete model loaded
    to run
    @ In, settings, CashFlow.GlobalSettings, settings
    @ Out, comps, dict, dict mapping names to CashFlow component objects
  """
  # in this simple case, the project life is the component life for all components.
  life = settings.getProjectTime()
  # construct components
  comps = {}
  ## first (and only) component in the case
  name = 'MainComponent'
  comp = CashFlows.Component()
  comps[name] = comp
  params = {'name': name,
            'Life_time': 4}
  comp.setParams(params)
  ## add cashflows to this component
  cfs = []

  ### recurring cashflow evaluated hourly, to show usage
  cf = createRecurringHourly(dfSet, comp, 'A', 'D')
  cfs.append(cf)
  print('DEBUGG hourly recurring:', cf._yearlyCashflow)
  ### recurring cashflow evaluated yearly
  cf = createRecurringYearly(dfSet, comp, 'A', 'D')
  cfs.append(cf)
  print('DEBUGG yearly recurring:', cf._yearlyCashflow)
  ### capex cashflow
  cf = createCapex(dfSet, comp, 'B', 'D')
  cfs.append(cf)
  ## amortization
  cf.setAmortization('MACRS', 3)
  amorts = comp._createDepreciation(cf)
  cfs.extend(amorts)
  # finally, add cashflows to component
  comp.addCashflows(cfs)
  return comps

def createCapex(dfSet, comp, driver, alpha):
  """
    Constructs capex object
    @ In, dfSet, tuple, includes pandas.Dataframe, dict of inputs, and pyomo concrete model loaded
    to run
    @ In, comp, CashFlow.Component, component this cf will belong to
    @ In, driver, string, variable name in df to take driver from
    @ In, alpha, string, variable name in df to take alpha from
    @ Out, comps, dict, dict mapping names to CashFlow component objects
  """
  life = comp.getLifetime()
  # extract alpha, driver as just one value
  alpha = dfSet[1][alpha].mean()
  driver = dfSet[1][driver].mean()
  cf = CashFlows.Capex()
  cf.name = 'Cap'
  cf.initParams(life)
  cfFarams = {'name': 'Cap',
               'alpha': alpha,
               'driver': driver,
               'reference': 1.0,
               'X': 0.8,
               'depreciate': 3,
               'mult_target': None,
               'inflation': False,
               }
  cf.setParams(cfFarams)
  return cf

def createRecurringYearly(dfSet, comp, driver, alpha):
  """
    Constructs recurring cashflow with one value per year
    @ In, dfSet, tuple, includes pandas.Dataframe, dict of inputs, and pyomo concrete model loaded
    to run
    @ In, comp, CashFlow.Component, component this cf will belong to
    @ In, driver, string, variable name in df to take driver from
    @ In, alpha, string, variable name in df to take alpha from
    @ Out, comps, dict, dict mapping names to CashFlow component objects
  """
  life = comp.getLifetime()
  cf = CashFlows.Recurring()
  cfFarams = {'name': 'RecursYearly',
               'X': 1,
               'mult_target': None,
               'inflation': False}
  cf.setParams(cfFarams)
  # because our data comes hourly, collapse it to be yearly
  ## 0 for first year (build year) -> TODO couldn't this be automatic?
  alphas = np.zeros(life+1, dtype=object)
  drivers = np.zeros(life+1, dtype=object)
  yearDfs = dfSet[0].groupby([dfSet[0].index.year])
  oldList = []
  newList = []
  countOld = 0
  countNew = 0
  count = 0
  for year, yearDf in yearDfs:
    countOld = countNew
    oldList.append(countOld)
    if count != 0:
      countNew = len(yearDf) + countOld
      newList.append(countNew)
      alphas[count] = dfSet[1][alpha][oldList[count]:newList[count]].mean()
      drivers[count] = dfSet[1][driver][oldList[count]:newList[count]].mean()
    else:
      newList.append(countNew)
      alphas[count] = 0
      drivers[count] = 0
    count += 1
    if count == life+1:
      break
  # construct annual summary cashflows
  cf.computeYearlyCashflow(alphas, drivers)
  return cf

def createRecurringHourly(dfSet, comp, driver, alpha):
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
  cf = CashFlows.Recurring()
  cfFarams = {'name': 'RecursHourly',
               'X': 1,
               'mult_target': None,
               'inflation': False}
  cf.setParams(cfFarams)
  cf.initParams(life, pyomoVar=dfSet[2])
  yearDfs = dfSet[0].groupby([dfSet[0].index.year])
  countOld = 0
  countNew = 0
  for year, yearDf in yearDfs:
    countOld = countNew
    countNew = len(yearDf) + countOld
    y = year - 2018
    if y > life:
      break
    cf.computeIntrayearCashflow(y, dfSet[1][driver][countOld:countNew], dfSet[1][alpha][countOld:countNew])
  return cf



if __name__ == '__main__':
  # load multiyear data
  ## TODO use analytic data! this is data from a not-propr-ietary report, but not analytic.
  targets = ['A', 'B', 'C', 'D', 'Year', 'Time']
  indices = ['RAVEN_sample_ID']
  print('Loading data ...')
  full_df = pd.read_csv('aux_file/hourly.csv',
                        index_col=indices,
                        usecols=targets+indices) #,
                        #nrows=300000)
  # just the first sample
  df = full_df.loc[0]
  years = pd.to_datetime(df['Year'].values + 2019, format='%Y')
  hours = pd.to_timedelta(df['Time'].values, unit='H')
  datetime = years + hours
  df.index = datetime
  df = df.sort_index()[['A', 'B', 'C', 'D']]

  x = df.to_numpy()
  A = np.zeros((x.shape[0]))
  B = np.zeros((x.shape[0]))
  C = np.zeros((x.shape[0]))
  D = np.zeros((x.shape[0]))
  for i in range(x.shape[0]):
    A[i] = x[i][0]
    B[i] = x[i][1]
    C[i] = x[i][2]
    D[i] = x[i][3]
  dictDf = {}
  dictDf['A'] = A
  dictDf['B'] = B
  dictDf['C'] = C
  dictDf['D'] = D
  dfSet = (df, dictDf)

  metrics, m = run(dfSet)

  calculated = metrics['NPV']

  #m.OBJ = pyo.Objective(expr = calculated)
  #m.Constraint1 = pyo.Constraint(expr = calculated <= 2.080898547e+08)
  # for i in range(x.shape[0]):
  #  m.Constraint = pyo.Constraint(expr = m.Ap[i] + m.Dp[i] >= 0)
  #  m.Constraint = pyo.Constraint(expr = m.Bp[i] + m.Dp[i] >= 0)
  #m.Constraint2 = pyo.Constraint(expr = m.Ap + m.Dp >= 0)
  #m.Constraint3 = pyo.Constraint(expr = m.Bp + m.Dp >= 0)
  #solver = pyo.SolverFactory('ipopt')
  #results = solver.solve(m)
  #correct = 2.080898547e+08
  #if abs(calculated - correct)/correct < 1e-8:
    #print('Success!')
    #sys.exit(0)
  #else:
    #print('ERROR: correct: {:1.3e}, calculated: {:1.3e}, diff {:1.3e}'.format(correct, calculated, correct-calculated))
