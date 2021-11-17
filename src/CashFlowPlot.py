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

from PluginBaseClasses.OutStreamPlotPlugin import PlotPlugin, InputTypes, InputData
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
    dfCashFlow = dfYear.loc[:, dfYear.columns.str.endswith("CashFlow") + dfYear.columns.str.endswith("Depreciate") + dfYear.columns.str.endswith("Amortize")]
    cumulativeCashFlow = dfCashFlow.sum().sort_values(ascending=True) # Sorted cummulative cash flow in Project Year 'endYear' in an ascending order
    dfCashFlow = dfCashFlow[cumulativeCashFlow.sort_values(ascending=True).index[:len(cumulativeCashFlow)]] # Sorted cash flows
    yearNetCashFlow = dfCashFlow.sum(axis=1) # Sorted yearly net cash flow
    cumulativeNetCashFlow = yearNetCashFlow.cumsum() # Cumulative net cash flow
    labels = pd.DataFrame(dfCashFlow.columns) # Sorted labels
    # Color setting
    negativeVariable = len(list(filter(lambda lableLoc: (lableLoc < 0), cumulativeCashFlow))) # count # of outflows
    positiveVariable = len(list(filter(lambda lableLoc: (lableLoc >= 0), cumulativeCashFlow))) # count # of inflows
    defaultStartColor = 60 # default starting color #. 256 selections in total
    defaultEndColor = 240 # default ending color #. 256 selections in total
    negativeCmap = plt.get_cmap('Reds')
    negativeRawCmapList = [negativeCmap(i) for i in range(negativeCmap.N)]
    negativeCmapList = negativeRawCmapList[defaultEndColor:defaultStartColor:-(defaultEndColor-defaultStartColor)//negativeVariable]
    positiveCmap = plt.get_cmap('Blues')
    positiveRawCmapList = [positiveCmap(i) for i in range(positiveCmap.N)]
    positiveCmapList = positiveRawCmapList[defaultStartColor:defaultEndColor:(defaultEndColor-defaultStartColor)//positiveVariable]
    cmapList = negativeCmapList + positiveCmapList # Color list

    ## Plot 1: Inflows, outflows and Net Cash Flow
    widthFlowbar = 0.35
    _, ax1 = plt.subplots(1, figsize = (15,8))
    for i, _ in enumerate(cumulativeCashFlow[0:negativeVariable]):
      if i == 0:
        ax1.bar(dfYear['cfYears'], dfCashFlow.iloc[:,i], widthFlowbar, color = cmapList[i], label = labels.iloc[i,0], edgecolor='white')
      else:
        ax1.bar(dfYear['cfYears'], dfCashFlow.iloc[:,i], widthFlowbar, color = cmapList[i], bottom = dfCashFlow.iloc[:,0:i-1].sum(axis=1), label = labels.iloc[i,0], edgecolor='white')

    for i, _ in enumerate(cumulativeCashFlow[negativeVariable:negativeVariable+positiveVariable]):
      if i == 0:
        ax1.bar(dfYear['cfYears'], dfCashFlow.iloc[:,i+negativeVariable], widthFlowbar, color = cmapList[i+negativeVariable], label = labels.iloc[i+negativeVariable,0], edgecolor='white')
      else:
        ax1.bar(dfYear['cfYears'], dfCashFlow.iloc[:,i+negativeVariable], widthFlowbar, color = cmapList[i+negativeVariable], bottom = dfCashFlow.iloc[:,negativeVariable:negativeVariable+i].sum(axis=1), label = labels.iloc[i+negativeVariable,0], edgecolor='white')

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
    plt.title('Yearly Inflows, Outflows and Net Cash Flow from Project Year {} to {}'.format(startYear, endYear), y=1.05, fontsize = 20, fontweight='bold')
    fName = os.path.abspath('Cash_Flows_from_Project_Year_{}_to_{}.png'.format(startYear, endYear))
    plt.savefig(fName,bbox_inches="tight")
    self.raiseAMessage(f'Saved figure to "{fName}"')

    ## Plot 2: Cumulative discounted free cash flow
    lableLoc = np.arange(endYear + 1 - startYear)  # the label location
    widthCumBar = 0.1
    _, ax1 = plt.subplots(1, figsize = (22,12))
    for i, _ in enumerate(cumulativeCashFlow):
      ax1.bar(lableLoc + widthCumBar * (i - 7/2), dfCashFlow.iloc[:,i], widthCumBar, color = cmapList[i], label = labels.iloc[i,0], edgecolor='white')
    #grid
    ax1.set_axisbelow(True)
    ax1.yaxis.grid(color='gray', linestyle='dashed', alpha=0.7)
    ax1.set_xlabel('Project Year', fontsize = 15, fontweight='bold')
    ax1.set_ylabel('Yearly Inflows and Outflows ($)', fontsize = 15, fontweight='bold')
    # cumulative discounted free cash flow
    ax2 = ax1.twinx()
    ax2.plot(dfYear['cfYears'], cumulativeNetCashFlow, color='darkolivegreen', marker='o',label='Cumulative Net Cash Flow')
    ax2.set_ylabel('Cumulative Net Cash Flow', color='darkolivegreen', fontsize = 15, fontweight='bold')
    ax2.tick_params(axis='y', labelcolor='darkolivegreen')
    # legends
    ax1.legend(loc='upper center', bbox_to_anchor=(0.5, -0.09),fancybox=True, ncol=negativeVariable+positiveVariable,fontsize = 15)
    ax2.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05),fancybox=True, ncol=1,fontsize = 15)
    plt.title('Cumulative Discounted Free Cash Flow from Project Year {} to {}'.format(startYear, endYear), y=1.05, fontsize = 20, fontweight='bold')
    fName = os.path.abspath('Cumulative_from_Project_Year_{}_to_{}.png'.format(startYear, endYear))
    plt.savefig(fName,bbox_inches="tight")
    self.raiseAMessage(f'Saved figure to "{fName}"')

    ## Plot 3: pie chart with inflows and outflows
    cumulativeCashFlowAbs = [abs(ele) for ele in cumulativeCashFlow]
    cumOutFlow = cumulativeCashFlowAbs[0:negativeVariable] # donut for outflows when inflows are lower
    cumInFlow = cumulativeCashFlowAbs[-positiveVariable:] # donut for inflows when outflows are lower
    diff = sum(cumulativeCashFlow)
    cumIn = cumInFlow + [abs(diff)]  # donut for inflows when inflows are lower
    cumOut = cumOutFlow + [abs(diff)] # donut for outflows when outflows are lower
    widthPieChart = 0.2
    radiusPieChart = 0.8
    _, ax1 = plt.subplots(1, figsize=[12,10])
    ax1.axis('equal')
    ax2 = ax1.twinx()
    if diff >= 0:
      pieOut, _ = ax1.pie(cumOut, radius=radiusPieChart, colors = cmapList[0:negativeVariable]+[(0.0, 0.0, 0.0, 0.0)], startangle=90)
      pieIn, _ = ax2.pie(cumInFlow, radius=radiusPieChart - widthPieChart, colors = cmapList[-positiveVariable:], startangle=90)
      ax1.text(-0.55,0.86,"Inflows", color="darkblue", fontsize=16, fontweight='bold')
      ax1.text(-0.29,0.86,"-              ≈", color="black", fontsize=18, fontweight='bold')
      ax1.text(-0.25,0.86,"Outflows", color="darkred", fontsize=16, fontweight='bold')
      ax1.text(0.14,0.86,f'${abs(diff): 1.3e}', color="royalblue", fontsize=16, fontweight='bold')
    else:
      pieOut, _ = ax1.pie(cumOutFlow, radius=radiusPieChart,colors = cmapList[0:negativeVariable], startangle=90)
      pieIn, _ = ax2.pie(cumIn, radius=radiusPieChart-widthPieChart, colors = cmapList[-positiveVariable:]+[(0.0, 0.0, 0.0, 0.0)], startangle=90)
      ax1.text(-0.55,0.86,"Outflows", color="darkred",fontsize=16, fontweight='bold')
      ax1.text(-0.23,0.86,"-            ≈", color="black", fontsize=18, fontweight='bold')
      ax1.text(-0.18,0.86,"Inflows", color="darkblue", fontsize=16, fontweight='bold')
      ax1.text(0.16,0.86,f'${abs(diff): 1.3e}', color="salmon", fontsize=16, fontweight='bold')

    ax1.legend(labels.iloc[0:negativeVariable,0], loc='lower right',fontsize = 15)
    ax2.legend(labels.iloc[-positiveVariable:,0], loc='lower left',fontsize = 15)
    plt.setp([pieOut, pieIn], width=widthPieChart, edgecolor='white')
    plt.title('Cumulative Inflows vs. Outflows from Project Year {} to {}'.format(startYear, endYear), y=1, fontsize = 20, fontweight='bold')
    fName = os.path.abspath('Cumulative_pie_from_Project_Year_{}_to_{}.png'.format(startYear, endYear))
    plt.savefig(fName)
    self.raiseAMessage(f'Saved figure to "{fName}"')
