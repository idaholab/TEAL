"""
  Author:  A. S. Epiney, P. Talbot, C. Wang
  Date  :  02/23/2017
"""

from __future__ import division, print_function, unicode_literals, absolute_import
import os
import sys
import numpy as np
import warnings
warnings.simplefilter('default', DeprecationWarning)

# NOTE this import exception is ONLY to allow RAVEN to directly import this module.
try:
  from CashFlow.src import main
except ImportError:
  import main

# This plugin imports RAVEN modules. if run in stand-alone, RAVEN needs to be installed and this file
# needs to be in the propoer plugin directory.
dirPath = os.path.dirname(os.path.realpath(__file__))
# TODO fix with plugin relative path
ravenPath = os.path.dirname(__file__) + '/../../../framework'
sys.path.append(os.path.expanduser(ravenPath))

try:
  from utils.graphStructure import graphObject
  from PluginsBaseClasses.ExternalModelPluginBase import ExternalModelPluginBase
except:
  raise IOError("CashFlow ERROR (Initialisation): RAVEN needs to be installed and CashFlow needs to be in its plugin directory for the plugin to work!'")


class CashFlow(ExternalModelPluginBase):
  """
    This class contains the plugin class for cash flow analysis within the RAVEN framework.
  """
  # =====================================================================================================================
  def _readMoreXML(self, container, xmlNode):
    """
      Read XML inputs from RAVEN input file needed by the CashFlow plugin.
      Note that the following is read/put from/into the container:
      - Out, verbosity, integer, The verbosity level of the CashFlow plugin
      - Out, container.cashFlowParameters, dict, contains all the information read from the XML input, i.e. components and cash flow definitions
      @ In, container, object, external 'self'
      @ In, xmlNode, xml.etree.ElementTree.Element, Xml element node
      @ Out, None
    """
    # read in XML to global settings, component list
    settings, components = main.read_from_xml(xmlNode)
    container._globalSettings = settings
    container._components = components

  # =====================================================================================================================

  # =====================================================================================================================
  def initialize(self, container, runInfoDict, inputFiles):
    """
      Method to initialize the CashFlow plugin.
      @ In, container, object, external 'self'
      @ In, runInfoDict, dict, the dictionary containing the runInfo (read in the XML input file)
      @ In, inputFiles, list, not used
      @ Out, None
    """
    settings = container._globalSettings
    components = container._components
    main.checkRunSettings(settings, components)
  # =====================================================================================================================

  # =====================================================================================================================
  def run(self, container, Inputs):
    """
      Computes economic key figures (NPV, IRR, PI as well as NPV serach)
      @ In, container, object, external 'self'
      @ In, Inputs, dict, contains the inputs needed by the CashFlow plugin as specified in the RAVEN input file
      @ Out, None
    """
    globalSettings = container._globalSettings
    components = container._components
    metrics = main.run(globalSettings, components, Inputs)
    for k, v in metrics.items():
      setattr(container, k, v)

  # =====================================================================================================================


#################################
# Run the plugin in stand alone #
#################################
if __name__ == "__main__":
  # emulate RAVEN container
  class FakeSelf:
    """
      Mimics RAVEN variable holder
    """
    def __init__(self):
      """
        Constructor.
        @ In, None
        @ Out, None
      """
      pass
  import xml.etree.ElementTree as ET
  import argparse
  import csv
  # read and process input arguments
  # ================================
  inpPar = argparse.ArgumentParser(description = 'Run RAVEN CashFlow plugin as stand-alone code')
  inpPar.add_argument('-iXML', nargs=1, required=True, help='XML CashFlow input file name', metavar='inpFile')
  inpPar.add_argument('-iINP', nargs=1, required=True, help='CashFlow input file name with the input variable list', metavar='inpFile')
  inpPar.add_argument('-o', nargs=1, required=True, help='Output file name', metavar='outFile')
  inpOpt = inpPar.parse_args()

  # check if files exist
  print ("CashFlow INFO (Run as Code): XML input file: %s" %inpOpt.iXML[0])
  print ("CashFlow INFO (Run as Code): Variable input file: %s" %inpOpt.iINP[0])
  print ("CashFlow INFO (Run as Code): Output file: %s" %inpOpt.o[0])
  if not os.path.exists(inpOpt.iXML[0]) :
    raise IOError('\033[91m' + "CashFlow INFO (Run as Code): : XML input file " + inpOpt.iXML[0] + " does not exist.. " + '\033[0m')
  if not os.path.exists(inpOpt.iINP[0]) :
    raise IOError('\033[91m' + "CashFlow INFO (Run as Code): : Variable input file " + inpOpt.iINP[0] + " does not exist.. " + '\033[0m')
  if os.path.exists(inpOpt.o[0]) :
    print ("CashFlow WARNING (Run as Code): Output file %s already exists. Will be overwritten. " %inpOpt.o[0])

  # Initialise run
  # ================================
  # create a CashFlow class instance
  MyCashFlow = CashFlow()
  # read the XML input file inpOpt.iXML[0]
  MyContainer = FakeSelf()
  notroot = ET.parse(open(inpOpt.iXML[0], 'r')).getroot()
  root = ET.Element('ROOT')
  root.append(notroot)
  MyCashFlow._readMoreXML(MyContainer, root)
  MyCashFlow.initialize(MyContainer, {}, [])
  #if Myverbosity < 2:
  print("CashFlow INFO (Run as Code): XML input read ")
  # read the values from input file into dictionary inpOpt.iINP[0]
  MyInputs = {}
  with open(inpOpt.iINP[0]) as f:
    for l in f:
      (key, val) = l.split(' ', 1)
      MyInputs[key] = np.array([float(n) for n in val.split(",")])
  #if Myverbosity < 2:
  print("CashFlow INFO (Run as Code): Variable input read ")
  #if Myverbosity < 1:
  print("CashFlow INFO (Run as Code): Inputs dict %s" %MyInputs)

  # run the stuff
  # ================================
  #if Myverbosity < 2:
  print("CashFlow INFO (Run as Code): Running the code")
  MyCashFlow.run(MyContainer, MyInputs)

  # create output file
  # ================================
  #if Myverbosity < 2:
  print("CashFlow INFO (Run as Code): Writing output file")
  outDict = {}
  for indicator in ['NPV_mult', 'NPV', 'IRR', 'PI']:
    try:
      outDict[indicator] = getattr(MyContainer, indicator)
      #if Myverbosity < 2:
      print("CashFlow INFO (Run as Code): %s written to file" %indicator)
    except (KeyError, AttributeError):
      #if Myverbosity < 2:
      print("CashFlow INFO (Run as Code): %s not found" %indicator)
  with open(inpOpt.o[0], 'w') as out:
    CSVwrite = csv.DictWriter(out, outDict.keys())
    CSVwrite.writeheader()
    CSVwrite.writerow(outDict)
