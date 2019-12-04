"""
  Integration test for using object-oriented API for components.
  Does not use run-time variables, provides all values through arrays.
"""

import os
import sys
import numpy as np
import pandas as pd
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from CashFlow import CashFlows
from CashFlow import CashFlow as RunCashFlow

def run(df):
  """
    Main run command.
    @ In, df, pandas.Dataframe, loaded data to run
    @ Out, metrics, dict, dictionary of metric results
  """
  settings = build_econ_settings()
  components = build_econ_components(df, settings)
  metrics = RunCashFlow.run(settings, list(components.values()), {})
  return metrics

def build_econ_settings():
  """
    Constructs global settings for econ run
    @ In, None
    @ Out, settigns, CashFlow.GlobalSettings, settings
  """
  params = {'DiscountRate': 0.10,
            'tax': 0.21,
            'inflation': 0.02184,
            'ProjectTime': 5,
            'Indicator': {'name': ['NPV'],
                          'active': ['MainComponent|RecursHourly', 'MainComponent|RecursYearly', 'MainComponent|Cap']}
           }
  settings = CashFlows.GlobalSettings()
  settings.set_params(params)
  settings._verbosity = 0
  return settings

def build_econ_components(df, settings):
  """
    Constructs run components
    @ In, df, pandas.Dataframe, loaded data to run
    @ In, settings, CashFlow.GlobalSettings, settings
    @ Out, comps, dict, dict mapping names to CashFlow component objects
  """
  # in this simple case, the project life is the component life for all components.
  life = settings.get_project_time()
  # construct components
  comps = {}
  ## first (and only) component in the case
  name = 'MainComponent'
  comp = CashFlows.Component()
  comps[name] = comp
  params = {'name': name,
            'Life_time': 4}
  comp.set_params(params)
  ## add cashflows to this component
  cfs = []

  ### recurring cashflow evaluated hourly, to show usage
  cf = create_recurring_hourly(df, comp, 'A', 'D')
  cfs.append(cf)
  print('DEBUGG hourly recurring:', cf._yearly_cashflow)
  ### recurring cashflow evaluated yearly
  cf = create_recurring_yearly(df, comp, 'A', 'D')
  cfs.append(cf)
  print('DEBUGG yearly recurring:', cf._yearly_cashflow)
  ### capex cashflow
  cf = create_capex(df, comp, 'B', 'D')
  cfs.append(cf)
  ## amortization
  cf.set_amortization('MACRS', 3)
  amorts = comp._create_depreciation(cf)
  cfs.extend(amorts)
  # finally, add cashflows to component
  comp.add_cashflows(cfs)
  return comps

def create_capex(df, comp, driver, alpha):
  """
    Constructs capex object
    @ In, df, pandas.Dataframe, loaded data to run
    @ In, comp, CashFlow.Component, component this cf will belong to
    @ In, driver, string, variable name in df to take driver from
    @ In, alpha, string, variable name in df to take alpha from
    @ Out, comps, dict, dict mapping names to CashFlow component objects
  """
  life = comp.get_lifetime()
  # extract alpha, driver as just one value
  alpha = df[alpha].mean()
  driver = df[driver].mean()
  cf = CashFlows.Capex()
  cf.name = 'Cap'
  cf.init_params(life)
  cf_params = {'name': 'Cap',
               'alpha': alpha,
               'driver': driver,
               'reference': 1.0,
               'X': 0.8,
               'depreciate': 3,
               'mult_target': None,
               'inflation': False,
               }
  cf.set_params(cf_params)
  return cf

def create_recurring_yearly(df, comp, driver, alpha):
  """
    Constructs recurring cashflow with one value per year
    @ In, df, pandas.Dataframe, loaded data to run
    @ In, comp, CashFlow.Component, component this cf will belong to
    @ In, driver, string, variable name in df to take driver from
    @ In, alpha, string, variable name in df to take alpha from
    @ Out, comps, dict, dict mapping names to CashFlow component objects
  """
  life = comp.get_lifetime()
  cf = CashFlows.Recurring()
  cf_params = {'name': 'RecursYearly',
               'X': 1,
               'mult_target': None,
               'inflation': False}
  cf.set_params(cf_params)
  # because our data comes hourly, collapse it to be yearly
  ## 0 for first year (build year) -> TODO couldn't this be automatic?
  alphas = np.zeros(life + 1)
  drivers = np.zeros(life + 1)
  alphas[1:] = df[alpha].groupby(df.index.year).mean().values[:life]
  drivers[1:] = df[driver].groupby(df.index.year).mean().values[:life]
  # construct annual summary cashflows
  cf.compute_yearly_cashflow(alphas, drivers)
  return cf

def create_recurring_hourly(df, comp, driver, alpha):
  """
    Constructs recurring cashflow with one value per hour
    @ In, df, pandas.Dataframe, loaded data to run
    @ In, comp, CashFlow.Component, component this cf will belong to
    @ In, driver, string, variable name in df to take driver from
    @ In, alpha, string, variable name in df to take alpha from
    @ Out, comps, dict, dict mapping names to CashFlow component objects
  """
  life = comp.get_lifetime()
  cf = CashFlows.Recurring()
  cf_params = {'name': 'RecursHourly',
               'X': 1,
               'mult_target': None,
               'inflation': False}
  cf.set_params(cf_params)
  cf.init_params(life)
  year_dfs = df.groupby([df.index.year])
  for year, year_df in year_dfs:
    y = year - 2018
    if y > life:
      break
    cf.compute_intrayear_cashflow(y, year_df[driver], year_df[alpha])
  return cf



if __name__ == '__main__':
  # load multiyear data
  ## TODO use analytic data! this is data from a non-proprietary report, but not analytic.
  targets = ['A', 'B', 'C', 'D', 'Year', 'Time']
  indices = ['RAVEN_sample_ID']
  print('Loading data ...')
  full_df = pd.read_csv('aux/hourly.csv',
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

  metrics = run(df)

  calculated = metrics['NPV']
  correct = 2.080898547e+08
  if abs(calculated - correct)/correct < 1e-8:
    print('Success!')
    sys.exit(0)
  else:
    print('ERROR: correct: {:1.3e}, calculated: {:1.3e}, diff {:1.3e}'.format(correct, calculated, correct-calculated))
