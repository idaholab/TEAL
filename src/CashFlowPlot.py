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
  This module is TEAL outout visualization
  Author:  baoh
  Date  :  2021-11-09
"""
import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

try:
  from ravenframework.PluginBaseClasses.OutStreamPlotPlugin import PlotPlugin, InputTypes, InputData
except:
  raise IOError('TEAL ERROR (initialization): RAVEN needs to be installed and ' +
                'TEAL needs to be installed as a plugin to work!')

class CashFlowPlot(PlotPlugin):
  """
    Cash flow plot
  """
  @classmethod
  def getInputSpecification(cls):
    """
      Define the acceptable user inputs for this class.
      @ In, None
      @ Out, specs, InputData.ParameterInput, specification
    """
    specs = super().getInputSpecification()
    specs.addSub(InputData.parameterInputFactory('source', contentType=InputTypes.StringType,
        descr=r"""specifies which DataObject to take data from"""))
    specs.addSub(InputData.parameterInputFactory('startYear', contentType=InputTypes.IntegerType,
        descr=r"""specifies the beginning year for plots"""))
    specs.addSub(InputData.parameterInputFactory('endYear', contentType=InputTypes.IntegerType,
        descr=r"""specifies the ending year for plots"""))
    return specs

  def __init__(self):
    """
      Constructor.
      @ In, None
      @ Out, None
    """
    super().__init__()
    self.printTag = 'TEAL.CashFlowPlot'
    self._sourceName = None # name of source data object
    self._source = None     # actual source data object
    self._startYear = None  # start year for plotting
    self._endYear = None    # end year for plotting

  def handleInput(self, spec):
    """
      Reads in data from the input file
      @ In, spec, InputData.ParameterInput, input information
      @ Out, None
    """
    super().handleInput(spec)
    for node in spec.subparts:
      if node.getName() == 'source':
        self._sourceName = node.value
      elif node.getName() == 'startYear':
        self._startYear = node.value
      elif node.getName() == 'endYear':
        self._endYear = node.value
    if self._sourceName is None:
      self.raiseAnError(IOError, 'Input missing the <source> node!')

  def initialize(self, stepEntities):
    """
      Set up plotter for each run
      @ In, stepEntities, dict, entities from the Step
      @ Out, None
    """
    super().initialize(stepEntities)
    src = self.findSource(self._sourceName, stepEntities)
    if src is None:
      self.raiseAnError(IOError, f'Source DataObject {self._sourceName} was not found in the Step!')
    self._source = src

  def run(self):
    """
      Generate the plot
      @ In, None
      @ Out, None
    """
    data = self._source.asDataset()
    df = data.to_dataframe().reset_index(level=['cfYears']).reset_index(drop=True)
    if self._startYear is None:
      startYear = 0
    if self._endYear is None:
      endYear = len(df) - 1
    dfYear = df[startYear:endYear + 1]
    dfCashFlow = dfYear.loc[:, dfYear.columns.str.contains("_")]

    # sort data by comp name and cum for color setting
    cumCashFlow = dfCashFlow.sum().sort_values(ascending=True)
    labelCompAll = [cumCashFlow.index.tolist()[i].partition('_')[0] for i, _ in enumerate(cumCashFlow)]
    # Comp name: Comp count
    compCount = pd.Series({i:labelCompAll.count(i) for i in labelCompAll})
    cumCashFlow = cumCashFlow.set_axis([cumCashFlow.index.tolist(), labelCompAll])
    # Sorted by Comp names and values
    cumCashFlow = cumCashFlow.reset_index(level=1).sort_values('level_1').drop('level_1', axis=1).squeeze()

    # Color setting by comp names
    defaultStartColor = 60 # default starting color #. 256 selections in total
    defaultEndColor = 240 # default ending color #. 256 selections in total
    colorLib = ['Reds', 'Blues', 'Greens', 'Purples', 'Oranges', 'ocean'] # color library is changable
    compColor = []
    for i, _ in enumerate(compCount):
      _cmap = plt.get_cmap(colorLib[i])
      _rawCmapList = [_cmap(k) for k in range(_cmap.N)]
      compColor += _rawCmapList[defaultEndColor:defaultStartColor:-(defaultEndColor-defaultStartColor)//compCount[i]]
    compColor = pd.DataFrame(compColor).set_axis([cumCashFlow.index.tolist()]).T
    cumCashFlow = cumCashFlow.sort_values(ascending=True)
    compColor = compColor[cumCashFlow.index[:len(cumCashFlow)]]
    compColor = compColor.T.values.tolist()
    negVar = len(list(filter(lambda lableLoc: (lableLoc < 0), cumCashFlow))) # count # of outflows
    posVar = len(list(filter(lambda lableLoc: (lableLoc >= 0), cumCashFlow))) # count # of inflows

    dfCashFlow = dfCashFlow[cumCashFlow.index[:len(cumCashFlow)]] # Sorted cash flows
    yearNetCashFlow = dfCashFlow.sum(axis=1) # Sorted yearly net cash flow
    cumNetCashFlow = yearNetCashFlow.cumsum() # Cumulative net cash flow
    labels = pd.DataFrame(dfCashFlow.columns) # Sorted labels by CompName and sum of values
    ## Plot 1: Inflows, outflows and Net Cash Flow
    widthFlowbar = 0.35
    _, ax1 = plt.subplots(1, figsize = (15,8))
    for i, _ in enumerate(cumCashFlow[0:negVar]):
      if i == 0:
        ax1.bar(dfYear['cfYears'], dfCashFlow.iloc[:,i], widthFlowbar, color = compColor[i],
          label = labels.iloc[i,0], edgecolor='white')
      else:
        ax1.bar(dfYear['cfYears'], dfCashFlow.iloc[:,i], widthFlowbar, color = compColor[i],
          bottom = dfCashFlow.iloc[:,0:i-1].sum(axis=1), label = labels.iloc[i,0], edgecolor='white')

    for i, _ in enumerate(cumCashFlow[negVar:negVar+posVar]):
      if i == 0:
        ax1.bar(dfYear['cfYears'], dfCashFlow.iloc[:,i+negVar], widthFlowbar,
          color = compColor[i+negVar], label = labels.iloc[i+negVar,0], edgecolor='white')
      else:
        ax1.bar(dfYear['cfYears'], dfCashFlow.iloc[:,i+negVar], widthFlowbar,
          color = compColor[i+negVar], bottom = dfCashFlow.iloc[:,negVar:negVar+i].sum(axis=1),
          label = labels.iloc[i+negVar,0], edgecolor='white')

    # grid
    ax1.set_axisbelow(True)
    ax1.yaxis.grid(color='gray', linestyle='dashed', alpha=0.7)
    ax1.set_xlabel('Project Year', fontsize = 15, fontweight='bold')
    ax1.set_ylabel('Yearly Cash Flows($)', fontsize = 15, fontweight='bold')
    # total cashflow
    plt.plot(dfYear['cfYears'], yearNetCashFlow, color='darkolivegreen', marker='o',label='Yearly Net Cash Flow')
    # Shrink current axis by 20% for legends
    box = ax1.get_position()
    ax1.set_position([box.x0, box.y0, box.width * 0.8, box.height])
    plt.legend(loc='center left', bbox_to_anchor=(1.0,0.5), fancybox=True, ncol=1,fontsize = 15)
    plt.title('Yearly Inflows, Outflows and Net Cash Flow from Project Year {} to {}'.format(startYear, endYear),
      y=1.05, fontsize = 20, fontweight='bold')

    fName = os.path.abspath('Cash_Flows_from_Project_Year_{}_to_{}.png'.format(startYear, endYear))
    plt.savefig(fName,bbox_inches="tight")
    self.raiseAMessage(f'Saved figure to "{fName}"')

    ## Plot 2: Cumulative discounted free cash flow
    labelLoc = np.arange(startYear, endYear + 1)  # the label location
    widthCumBar = 0.2
    _, ax1 = plt.subplots(1, figsize = (25,12))
    for i, _ in enumerate(cumCashFlow):
      ax1.bar(labelLoc + widthCumBar * (i - (len(cumCashFlow) + 1) / 2), dfCashFlow.iloc[:,i],
        widthCumBar, color = compColor[i], label = labels.iloc[i,0], edgecolor='white')
    #grid
    ax1.set_axisbelow(True)
    ax1.yaxis.grid(color='gray', linestyle='dashed', alpha=0.7)
    ax1.set_xlabel('Project Year', fontsize = 15, fontweight='bold')
    ax1.set_ylabel('Yearly Inflows and Outflows ($)', fontsize = 15, fontweight='bold')
    # cumulative cash flow
    ax2 = ax1.twinx()
    ax2.plot(dfYear['cfYears'], cumNetCashFlow, color='darkolivegreen', marker='o',label='Cumulative Net Cash Flow')
    ax2.set_ylabel('Cumulative Net Cash Flow', color='darkolivegreen', fontsize = 15, fontweight='bold')
    ax2.tick_params(axis='y', labelcolor='darkolivegreen')
    # legends
    ax1.legend(loc='upper center', bbox_to_anchor=(0.5, -0.09),fancybox=True, ncol=negVar+posVar,fontsize = 15)
    ax2.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05),fancybox=True, ncol=1,fontsize = 15)
    plt.title('Cumulative Cash Flow from Project Year {} to {}'.format(startYear, endYear),
      y=1.05, fontsize = 20, fontweight='bold')
    fName = os.path.abspath('Cumulative_from_Project_Year_{}_to_{}.png'.format(startYear, endYear))
    plt.savefig(fName,bbox_inches="tight")
    self.raiseAMessage(f'Saved figure to "{fName}"')

    ## Plot 3: pie chart with inflows and outflows
    cumulativeCashFlowAbs = [abs(ele) for ele in cumCashFlow]
    cumOutFlow = cumulativeCashFlowAbs[0:negVar] # donut for outflows when inflows are lower
    cumInFlow = cumulativeCashFlowAbs[-posVar:] # donut for inflows when outflows are lower
    diff = sum(cumCashFlow)
    cumIn = cumInFlow + [abs(diff)]  # donut for inflows when inflows are lower
    cumOut = cumOutFlow + [abs(diff)] # donut for outflows when outflows are lower
    widthPie = 0.2
    radiusPie = 0.8
    _, ax1 = plt.subplots(1, figsize=[12,10])
    ax1.axis('equal')
    ax2 = ax1.twinx()
    if diff >= 0:
      pieOut, _ = ax1.pie(cumOut, radius=radiusPie, colors = compColor[0:negVar]+[(0, 0, 0, 0)], startangle=90)
      pieIn, _ = ax2.pie(cumInFlow, radius=radiusPie - widthPie, colors = compColor[-posVar:], startangle=90)
      ax1.text(-0.55,0.86,"Inflows - Outflows = {}".format(f'${abs(diff): 1.3e}'),
        color="black",fontsize=16, fontweight='bold')
    else:
      pieOut, _ = ax1.pie(cumOutFlow, radius=radiusPie,colors = compColor[0:negVar], startangle=90)
      pieIn, _ = ax2.pie(cumIn, radius=radiusPie-widthPie, colors = compColor[-posVar:]+[(0, 0, 0, 0)], startangle=90)
      ax1.text(-0.55,0.86,"Outflows - Inflows = {}".format(f'${abs(diff): 1.3e}'),
        color="black",fontsize=16, fontweight='bold')

    ax1.legend(labels.iloc[0:negVar,0], loc='lower right',fontsize = 15)
    ax2.legend(labels.iloc[-posVar:,0], loc='lower left',fontsize = 15)
    plt.setp([pieOut, pieIn], width=widthPie, edgecolor='white')
    plt.title('Cumulative Inflows vs. Outflows from Project Year {} to {}'.format(startYear, endYear),
      y=1, fontsize = 20, fontweight='bold')
    fName = os.path.abspath('Cumulative_pie_from_Project_Year_{}_to_{}.png'.format(startYear, endYear))
    plt.savefig(fName)
    self.raiseAMessage(f'Saved figure to "{fName}"')
