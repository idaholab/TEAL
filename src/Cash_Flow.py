"""
  Author:  A. S. Epiney
  Date  :  02/23/2017
"""

#Imports
from __future__ import division, print_function , unicode_literals, absolute_import
import warnings
warnings.simplefilter('default', DeprecationWarning)

#External Modules---------------------------------------------------------------
import numpy as np
import functools
#External Modules End-----------------------------------------------------------

#Internal Modules---------------------------------------------------------------
# This plugin imports RAVEN modules. if run in stand-alone, RAVEN needs to be installed and this file needs to be in the propoer plugin directory.
import os, sys
dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.abspath(os.path.join(dir_path,'..','..','..','framework')))
try:
  from utils.graphStructure import graphObject
  from PluginsBaseClasses.ExternalModelPluginBase import ExternalModelPluginBase
except:
  raise IOError("CashFlow ERROR (Initialisation): RAVEN needs to be installed and CashFlow needs to be in its plugin directory for the plugin to work!'")
#Internal Modules End-----------------------------------------------------------

class CashFlow(ExternalModelPluginBase):
  """
    This class contains the plugin class for cash flow analysis within the RAVEN framework.
  """

  #################################
  #### RAVEN API methods BEGIN ####
  #################################

  # =====================================================================================================================
  def _readMoreXML(self, container, xmlNode):
    """
      Read XML inputs from RAVEN input file needed by the CashFlow plugin.
      Note that the following is read/put from/into the container:
      - Out, container.cashFlowVerbosity, integer, The verbosity level of the CashFlow plugin
      - Out, container.cashFlowParameters, dict, contains all the information read from the XML input, i.e. components and cash flow definitions
      @ In, container, object, external 'self'
      @ In, xmlNode, xml.etree.ElementTree.Element, Xml element node
      @ Out, None
    """
    container.cashFlowParameters = {}
    for child in xmlNode:
      if child.tag == "Economics":
        # get verbosity if it exists
        if 'verbosity' in child.attrib:
          if isInt(child.attrib['verbosity']):
            container.cashFlowVerbosity = int(child.attrib['verbosity'])
          else:
            raise IOError("CashFlow ERROR (XML reading): 'verbosity' in 'Economics'  needs to be an integer'")
        else:
          container.cashFlowVerbosity = 100 # errors only
        if container.cashFlowVerbosity < 100:
          print ("CashFlow INFO (XML reading): verbosity level: %s" %container.cashFlowVerbosity)
        recursiveXmlReader(child, container.cashFlowParameters)
  # =====================================================================================================================

  # =====================================================================================================================
  def initialize(self, container, runInfoDict, inputFiles):
    """
      Method to initialize the CashFlow plugin.
      Note that the following is read/put from/into the container:
      - In, container.cashFlowParameters, dict, contains all the information read from the XML input, i.e. components and cash flow definitions
      - In, container.cashFlowVerbosity, integer, The verbosity level of the CashFlow plugin
      - Out, container.cashFlowComponentsList, list, contais a list of all Components found in the XML input
      - Out, container.cashFlowCashFlowsList, list, contains a list of all CashFlows found in the XML input
      - Out, container.customTime, bool, flag true if a <ProjectTime> has been input
      @ In, container, object, external 'self'
      @ In, runInfoDict, dict, the dictionary containing the runInfo (read in the XML input file)
      @ In, inputFiles, list, not used
      @ Out, None
    """
    # INPUT CHECKER (check that the values that we need are in the dict cashFlowParameters)
    # =====================================================================================

    # check if Economics exists
    # - - - - - - - - - - - - - - - - - - -
    if 'Economics' not in container.cashFlowParameters.keys():
      raise IOError("CashFlow ERROR (XML reading): 'Economics' node is required")

    # check if Global and children exist and are of the correct type
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if 'Global' not in container.cashFlowParameters['Economics'].keys():
      raise IOError("CashFlow ERROR (XML reading): 'Global' node is required inside 'Economics'")

    for tags in ['DiscountRate', 'tax', 'inflation', 'Indicator']:
      if tags not in container.cashFlowParameters['Economics']['Global'].keys():
        raise IOError("CashFlow ERROR (XML reading): '%s' node is required inside 'Global'" %tags)
      # type check: reals
      if tags in ['DiscountRate', 'tax', 'inflation']:
        if isReal(container.cashFlowParameters['Economics']['Global'][tags]['val']):
          container.cashFlowParameters['Economics']['Global'][tags]['val'] = float(container.cashFlowParameters['Economics']['Global'][tags]['val'])
        else:
          raise IOError("CashFlow ERROR (XML reading): '%s' needs to be a real number'" %tags)
    # check if we use a custom project time or we use the lcm of all components
    if 'ProjectTime' in container.cashFlowParameters['Economics']['Global'].keys():
      if container.cashFlowVerbosity < 1:
        print ("CashFlow INFO (XML reading): Found optional ProjectTime, this will be used over the lcm of all components: %s" %container.cashFlowParameters['Economics']['Global']['ProjectTime']['val'])
      if isInt(container.cashFlowParameters['Economics']['Global']['ProjectTime']['val']):
        container.cashFlowParameters['Economics']['Global']['ProjectTime']['val'] = int(container.cashFlowParameters['Economics']['Global']['ProjectTime']['val'])
      else:
        raise IOError("CashFlow ERROR (XML reading): 'ProjectTime' needs to be an integer inside 'Global'" )
      container.customTime = True
    else:
      container.customTime = False
    # check Indicator attributes
    # check 'name' attribute (it's actual values are checked after the 'CashFlow Nodes' are checked)
    if 'name' not in container.cashFlowParameters['Economics']['Global']['Indicator']['attr'].keys():
      raise IOError("CashFlow ERROR (XML reading): 'name' attribute of 'Indicator' is required inside 'Global'")
    container.cashFlowParameters['Economics']['Global']['Indicator']['attr']['name'] = [x.strip() for x in container.cashFlowParameters['Economics']['Global']['Indicator']['attr']['name'].split(",")]
    for indicators in container.cashFlowParameters['Economics']['Global']['Indicator']['attr']['name']:
      if indicators not in ['NPV_search', 'NPV', 'IRR', 'PI']:
        raise IOError("CashFlow ERROR (XML reading): 'name' attribut  of 'Indicator' inside 'Global' has to be 'NPV_search', 'NPV' or 'IRR' or 'PI'")
      if indicators == 'NPV_search':
        # check 'target' attribute if name is NPV_search
        if 'target' not in container.cashFlowParameters['Economics']['Global']['Indicator']['attr'].keys():
          raise IOError("CashFlow ERROR (XML reading): 'target' attribute of 'Indicator' is required inside 'Global' if name='NPV_search'")
        # type check: reals
        if isReal(container.cashFlowParameters['Economics']['Global']['Indicator']['attr']['target']):
          container.cashFlowParameters['Economics']['Global']['Indicator']['attr']['target'] = float(container.cashFlowParameters['Economics']['Global']['Indicator']['attr']['target'])
        else:
          raise IOError("CashFlow ERROR (XML reading): 'target' attribute of 'Indicator' inside 'Global' needs to be a real number")

    # check if all Components' children and attributes exist and are of the correct type
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    container.cashFlowComponentsList = []
    container.cashFlowCashFlowsList = []
    oneMultTargetTrue = False
    for compo in container.cashFlowParameters['Economics'].keys():
      if compo != 'attr' and compo != 'val':
        if container.cashFlowParameters['Economics'][compo]['attr'] == 'Component':
          if container.cashFlowVerbosity < 2:
            print ("CashFlow INFO (XML reading): Found component %s" %compo)
          container.cashFlowComponentsList.append(compo)
          # Life_time
          for tags in ['Life_time']:
            if tags not in container.cashFlowParameters['Economics'][compo].keys():
              raise IOError("CashFlow ERROR (XML reading): '%s' node is required inside '%s'" %(tags, compo))
          # type check: integers
          for tags in ['Life_time']:
            if isInt(container.cashFlowParameters['Economics'][compo][tags]['val']):
              container.cashFlowParameters['Economics'][compo][tags]['val'] = int(container.cashFlowParameters['Economics'][compo][tags]['val'])
            else:
              raise IOError("CashFlow ERROR (XML reading): '%s' needs to be an integer inside '%s'" %(tags, compo))
          # type check: optional reals
          for tags in ['tax', 'inflation']:
            if tags in container.cashFlowParameters['Economics'][compo].keys():
              if container.cashFlowVerbosity < 2:
                print ("CashFlow INFO (XML reading): Found optional tag %s for component %s" %(tags,compo))
              if isReal(container.cashFlowParameters['Economics'][compo][tags]['val']):
                container.cashFlowParameters['Economics'][compo][tags]['val'] = float(container.cashFlowParameters['Economics'][compo][tags]['val'])
              else:
                raise IOError("CashFlow ERROR (XML reading): '%s' needs to be a real number inside component %s'" %(tags,compo))
          # type check: optional integers which require customTime=True
          for tags in ['StartTime', 'Repetitions']:
            if tags in container.cashFlowParameters['Economics'][compo].keys():
              if container.cashFlowVerbosity < 2:
                print ("CashFlow INFO (XML reading): Found optional tag %s for component %s" %(tags,compo))
              if not container.customTime:
                raise IOError("CashFlow ERROR (XML reading): <ProjectTime> in <Global> is required if <StartTime> or <Repetitions> are used")
              if isInt(container.cashFlowParameters['Economics'][compo][tags]['val']):
                container.cashFlowParameters['Economics'][compo][tags]['val'] = int(container.cashFlowParameters['Economics'][compo][tags]['val'])
              else:
                raise IOError("CashFlow ERROR (XML reading): '%s' needs to be a integer number inside component %s'" %(tags,compo))
            else:
              #set some defaults (start year = 0 and repetitions = 0 = infinity)
              container.cashFlowParameters['Economics'][compo][tags] = {}
              container.cashFlowParameters['Economics'][compo][tags]['val'] = 0
              container.cashFlowParameters['Economics'][compo][tags]['attr'] = {}

          # Check CashFlow Nodes
          # - - - - - - - - - - - - -
          for cashFlow in container.cashFlowParameters['Economics'][compo]:
            if cashFlow != 'attr' and cashFlow != 'val':
              if container.cashFlowParameters['Economics'][compo][cashFlow]['attr'] == 'CashFlow':
                if container.cashFlowVerbosity < 2:
                  print ("CashFlow INFO (XML reading): Found CashFlow definition %s" %cashFlow)
                if cashFlow in container.cashFlowCashFlowsList:
                  raise IOError("CashFlow ERROR (XML reading): Cashflow names need to be unique over all components: '%s" %cashFlow)
                container.cashFlowCashFlowsList.append(cashFlow)
                # reference, alpha, X
                for tags in ['alpha', 'reference', 'X']:
                  if tags not in container.cashFlowParameters['Economics'][compo][cashFlow].keys():
                    raise IOError("CashFlow ERROR (XML reading): '%s' node is required inside CashFlow '%s'" %(tags, cashFlow))
                # type check: reals
                for tags in ['reference', 'X']:
                  if isReal(container.cashFlowParameters['Economics'][compo][cashFlow][tags]['val']):
                    container.cashFlowParameters['Economics'][compo][cashFlow][tags]['val'] = float(container.cashFlowParameters['Economics'][compo][cashFlow][tags]['val'])
                  else:
                    raise IOError("CashFlow ERROR (XML reading): '%s' needs to be a real number inside '%s'" %(tags, cashFlow))
                # type check: arrays
                for tags in ['alpha']:
                  container.cashFlowParameters['Economics'][compo][cashFlow][tags]['val'] = container.cashFlowParameters['Economics'][compo][cashFlow][tags]['val'].split()
                if len(container.cashFlowParameters['Economics'][compo][cashFlow][tags]['val']) - 1 != container.cashFlowParameters['Economics'][compo]['Life_time']['val']:
                  raise IOError("CashFlow ERROR (XML reading): '%s' needs to have the lenght of 'Life_time' (%s) + 1 in '%s'" %(tags, container.cashFlowParameters['Economics'][compo]['Life_time']['val'], cashFlow))
                for i in range(len(container.cashFlowParameters['Economics'][compo][cashFlow][tags]['val'])):
                  if isReal(container.cashFlowParameters['Economics'][compo][cashFlow][tags]['val'][i]):
                    container.cashFlowParameters['Economics'][compo][cashFlow][tags]['val'][i] = float(container.cashFlowParameters['Economics'][compo][cashFlow][tags]['val'][i])
                  else:
                    raise IOError("CashFlow ERROR (XML reading): '%s' needs to be an array of real numbers inside '%s'" %(tags, cashFlow))
                # check CashFlow attributes
                # - - - - - - - - - - - - -
                # Existence of 'driver' and 'multiply' in input space are checked during runtime (this check is not possible during initialisation)
                # tax, inflation => existence for attributes is already checked during reading
                # type check: logical
                for tags in ['tax']:
                  if container.cashFlowParameters['Economics'][compo][cashFlow][tags]['val'] in ['true'] :
                    container.cashFlowParameters['Economics'][compo][cashFlow][tags]['val'] = True
                  elif container.cashFlowParameters['Economics'][compo][cashFlow][tags]['val'] in ['false']:
                    container.cashFlowParameters['Economics'][compo][cashFlow][tags]['val'] = False
                  else:
                    raise IOError("CashFlow ERROR (XML reading): '%s' needs to be 'true' or 'false' inside '%s' of '%s'" %(tags, cashFlow, compo))
                # type check: special
                for tags in ['inflation']:
                  if container.cashFlowParameters['Economics'][compo][cashFlow][tags]['val'] not in ['real','nominal','none'] :
                    raise IOError("CashFlow ERROR (XML reading): '%s' needs to be 'real', 'nominal' or 'none' inside '%s' of '%s'" %(tags, cashFlow, compo))
                # mult_target => only needed if <Global><Indicator name='NPV_search'>
                for tags in ['mult_target']:
                  if 'NPV_search' in container.cashFlowParameters['Economics']['Global']['Indicator']['attr']['name']:
                    if container.cashFlowParameters['Economics'][compo][cashFlow]['mult_target']['val'] == 'None':
                      raise IOError("CashFlow ERROR (XML reading): Attribute '%s' needs to exist and needs to 'true' or 'false' inside '%s' of '%s' if Indicator is NPV_search" %(tags, cashFlow, compo))
                    else:
                      if container.cashFlowParameters['Economics'][compo][cashFlow]['mult_target']['val'] in ['true'] :
                        container.cashFlowParameters['Economics'][compo][cashFlow]['mult_target']['val'] = True
                        oneMultTargetTrue = True
                      elif container.cashFlowParameters['Economics'][compo][cashFlow]['mult_target']['val'] in ['false']:
                        container.cashFlowParameters['Economics'][compo][cashFlow]['mult_target']['val'] = False
                      else:
                        raise IOError("CashFlow ERROR (XML reading): '%s' needs to be 'true' or 'false' inside '%s' of '%s'" %(tags, cashFlow, compo))

    # If Indicator is NPV_search, at least one cash flow has to have mult_target="false" and one has to have mult_target="true"
    if 'NPV_search' in container.cashFlowParameters['Economics']['Global']['Indicator']['attr']['name']:
      if not oneMultTargetTrue:
        raise IOError("CashFlow ERROR (XML reading): If Indicator is NPV, at laest one CashFlow has to have mult_target=true")

    # Check Indictor node inside Global
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # all CashFlows requested in Indicator have to be defined in the cash flows
    container.cashFlowParameters['Economics']['Global']['Indicator']['val'] = container.cashFlowParameters['Economics']['Global']['Indicator']['val'].split()
    for request in container.cashFlowParameters['Economics']['Global']['Indicator']['val']:
      if request not in container.cashFlowCashFlowsList:
        raise IOError("CashFlow ERROR (XML reading): '%s' requested in 'Indicator' needs to be a CashFlow" %request)
  # =====================================================================================================================

  # =====================================================================================================================
  def run(self, container, Inputs):
    """
      Computes economic key figures (NPV, IRR, PI as well as NPV serach)
      Note that the following is read/put from/into the container:
      - In, container.cashFlowParameters, dict, contains all the information read from the XML input, i.e. components and cash flow definitions
      - In, container.cashFlowVerbosity, integer, The verbosity level of the CashFlow plugin
      - In, container.cashFlowComponentsList, list, contais a list of all Components found in the XML input
      - In, container.cashFlowCashFlowsList, list, contains a list of all CashFlows found in the XML input
      - In, container.customTime, bool, flag true if a <ProjectTime> has been input
      _ Out, container.NPV, real, NPV  (only if<Indicator name='NPV'>)
      - Out, container.IRR, real, IRR  (only if<Indicator name='IRR'>)
      - Out, container.IP, real, IP (only if<Indicator name='IP'>)
      - Out, container.NPV_mult, real, multiplier (only if<Indicator name='NPV_search'>)
      @ In, container, object, external 'self'
      @ In, Inputs, dict, contains the inputs needed by the CashFlow plugin as specified in the RAVEN input file
      @ Out, None
    """
    if container.cashFlowVerbosity < 1:
      print ("CashFlow INFO (run): Inside Economics")

    # add "Default" multiplier to inputs
    if 'Deafult' in Inputs.keys():
      raise IOError("CashFlow ERROR (run): The input 'Default' is passed from Raven in to the Economics. This is not allowed at the moment.... sorry... ")
    Inputs['Default'] = 1.0

    # Check if the needed inputs (drivers and multipliers) for the different cash flows are present
    # ------------------------------------------------------------------------
    if container.cashFlowVerbosity < 1:
      print ("CashFlow INFO (run): Checking if all drivers for cash flow are present")
    dictionaryOfNodes = {}
    dictionaryOfNodes['EndNode'] = []
    # loop over components
    for compo in container.cashFlowComponentsList:
      # loop over cash flows
      for cashFlow in container.cashFlowParameters['Economics'][compo]:
        if cashFlow != 'attr' and cashFlow != 'val':
          if container.cashFlowParameters['Economics'][compo][cashFlow]['attr'] == 'CashFlow':
            if container.cashFlowVerbosity < 1:
              print ("CashFlow INFO (run): Checking component %s, cash flow: %s " %(compo,cashFlow))
            # check if the multiplier is part of the Inputs (this can not be another CashFlow)
            # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
            multiply = container.cashFlowParameters['Economics'][compo][cashFlow]['multiply']['val']
            if multiply not in Inputs.keys():
              raise IOError("CashFlow ERROR (run): multiply %s for cash flow %s not in inputs" %(multiply, cashFlow))
            # check if the driver is present in Input or is another cash flow
            # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
            driver = container.cashFlowParameters['Economics'][compo][cashFlow]['driver']['val']
            # construct dictionaryOfNodes for Graph later
            if cashFlow in dictionaryOfNodes.keys():
              dictionaryOfNodes[cashFlow].append('EndNode')
            else:
              dictionaryOfNodes[cashFlow] = ['EndNode']
            if driver in dictionaryOfNodes.keys():
              dictionaryOfNodes[driver].append(cashFlow)
            else:
              dictionaryOfNodes[driver] = [cashFlow]
            dontExitYet = True
            while dontExitYet:
              if driver in Inputs.keys():
                if container.cashFlowVerbosity < 1:
                  print ("CashFlow INFO (run): driver %s in inputs from RAVEN       " %driver)
                # check lenght of this driver. Can be 1 (same for all years) or lifetime + 1 (provioded for every year)
                if not (len(Inputs[driver]) == 1 or len(Inputs[driver]) == container.cashFlowParameters['Economics'][compo]['Life_time']['val'] + 1):
                  raise IOError("CashFlow ERROR (XML reading): driver %s for cash flow %s has to have lenght 1 or componet Lifetime + 1 (%s), but has %s" %(driver, cashFlow, container.cashFlowParameters['Economics'][compo]['Life_time']['val'] + 1, len(Inputs[driver])))
                dontExitYet = False
              if driver in container.cashFlowCashFlowsList:
                if container.cashFlowVerbosity < 1:
                  print ("CashFlow INFO (run): driver %s in another CashFlow        " %driver)
                  print ("                      Follow chain back...")
                if not dontExitYet:
                  raise IOError("CashFlow ERROR (XML reading): driver %s for cash flow %s in inputs AND other cash flows (can only be in one)  " %(driver, cashFlow))
                # to which component does this cash flow (driver) belong?
                for compos in container.cashFlowComponentsList:
                  if driver in container.cashFlowParameters['Economics'][compos].keys():
                    break
                driver = container.cashFlowParameters['Economics'][compos][driver]['driver']['val']
                # check the lifetime lenght
                if container.cashFlowParameters['Economics'][compo]['Life_time']['val'] != container.cashFlowParameters['Economics'][compos]['Life_time']['val']:
                  raise IOError("CashFlow ERROR (XML reading): If CashFlows depend on CashFlows of other Components, the Life times for these components have to be the same!")
                # check if its cyclic
                if driver == cashFlow:
                  raise IOError("CashFlow ERROR (XML reading): drivers cycle in cash flow! Can not solve this. (use verbosity = 0 to print which driver it is)")
                continue
              if dontExitYet:
                raise IOError("CashFlow ERROR (XML reading): driver %s for cash flow %s not in inputs or other cash flows " %(driver, cashFlow))

    # if everything is OK, build the sequence to execute the CsahFlows
    # ------------------------------------------------------------------------
    myGraph = graphObject(dictionaryOfNodes)
    cashFlowSequence = myGraph.createSingleListOfVertices()
    if container.cashFlowVerbosity < 2:
      print ("CashFlow INFO (run): Found sequence for execution of cash flows: %s" %cashFlowSequence)

    # construct cash flow terms for each component and year untill the end for the component life time
    # since cash flows can depend on other cash flows, the cash flows computed here are without tax and inflation
    # ------------------------------------------------------------------------------------------------------------
    cashFlowForLife = {}
    # loop over cash_flows
    for cashFlow in cashFlowSequence:
      if cashFlow in Inputs.keys() or cashFlow == 'EndNode':
        continue
      if container.cashFlowVerbosity < 2:
        print ("--------------------------------------------------------------------------------------------------")
        print ("CashFlow INFO (run): Computing cash flow               : %s" %cashFlow)
      # to which component does this CashFlow belong?
      for compos in container.cashFlowComponentsList:
        if cashFlow in container.cashFlowParameters['Economics'][compos].keys():
          break
      if container.cashFlowVerbosity < 2:
        print ("CashFlow INFO (run): cash flow belongs to component    : %s" %compos)
      if compos not in cashFlowForLife.keys():
        cashFlowForLife[compos] = {}
      cashFlowForLife[compos][cashFlow] = []
      driverName = container.cashFlowParameters['Economics'][compos][cashFlow]['driver']['val']
      if container.cashFlowVerbosity < 2:
        print ("CashFlow INFO (run): cash flow driver name is          : %s" %driverName)
      if driverName in Inputs.keys():
        # The driver is in the inputs from RAVEN!
        # lenght one or lifetime + 1?
        if len(Inputs[driverName]) == 1:
          driverValues = [Inputs[driverName]]*(container.cashFlowParameters['Economics'][compos]['Life_time']['val'] + 1)
          if container.cashFlowVerbosity < 2:
            print ("CashFlow INFO (run): cash flow driver is the same for all years")
        else:
          driverValues = Inputs[driverName]
          if container.cashFlowVerbosity < 2:
            print ("CashFlow INFO (run): cash flow has different values for each year of the project lifetime")
      else:
        # The driver is another cash flow!
        # the lenght of the list, i.e. the lifetime of the component that provides the driver has
        # to be the same than for the component to whiah the cash flow belongs
        # this check is done at the reading statge

        # to which component does this driver belong?
        for compo in container.cashFlowComponentsList:
          if driverName in container.cashFlowParameters['Economics'][compo].keys():
            break
        driverValues = cashFlowForLife[compo][driverName]
      reference = container.cashFlowParameters['Economics'][compos][cashFlow]['reference']['val']
      xExponent = container.cashFlowParameters['Economics'][compos][cashFlow]['X']['val']
      multiplierName = container.cashFlowParameters['Economics'][compos][cashFlow]['multiply']['val']
      if container.cashFlowVerbosity < 2:
        print ("CashFlow INFO (run): cash flow multiplier name is      : %s" %multiplierName)
      multiplierValues = Inputs[multiplierName]
      if container.cashFlowVerbosity < 2:
        print ("CashFlow INFO (run):      life time is                 : %s" %container.cashFlowParameters['Economics'][compos]['Life_time']['val'])
        print ("CashFlow INFO (run):      reference is                 : %s" %reference)
        print ("CashFlow INFO (run):      Exponent  is                 : %s" %xExponent)
        print ("CashFlow INFO (run):      Multiply  is                 : %s" %multiplierValues)
      # loop over the years until end of life for that component
      for y in range(container.cashFlowParameters['Economics'][compos]['Life_time']['val']+1):
        # +-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=
        # This is where the magic happens
        # +-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=
        alpha = container.cashFlowParameters['Economics'][compos][cashFlow]['alpha']['val'][y]
        driverValue = driverValues[y]
        cashFlowForYear = multiplierValues * alpha * (driverValue/reference)**xExponent
        cashFlowForLife[compos][cashFlow].append(cashFlowForYear)
        if container.cashFlowVerbosity < 1:
          print ("CashFlow INFO (run):      for year (a, driver, cashflow) %s    : %s, %s, %s" %(y,alpha,driverValue,cashFlowForYear))

    # Include tax and inflation for all cash flows for the lenght of the cumulative project
    # ------------------------------------------------------------------------------------------------------------
    if container.customTime:
      lcmTime = container.cashFlowParameters['Economics']['Global']['ProjectTime']['val']
      if container.cashFlowVerbosity < 1:
        print ("==================================================================================================")
        print ("CashFlow INFO (run):  Using total project time from input <ProjectTime>   : %s" %(lcmTime))
    else:
      # find the smallest common multiple of the differetn life times of the components
      if container.cashFlowVerbosity < 1:
        print ("==================================================================================================")
        print ("CashFlow INFO (run): finding lcm of all component lifetimes ")
      lifeTimes = []
      for compos in container.cashFlowComponentsList:
        if container.cashFlowVerbosity < 1:
          print ("CashFlow INFO (run):  Life time for Component is: %s, %s" %(compos, container.cashFlowParameters['Economics'][compos]['Life_time']['val']))
        lifeTimes.append(container.cashFlowParameters['Economics'][compos]['Life_time']['val'])
      lcmTime = lcmm(*lifeTimes)
      if container.cashFlowVerbosity < 2:
        print ("CashFlow INFO (run):  LCM is                    : %s" %(lcmTime))

    # compute all cash flows for the years
    # loop over components in cashFlowForLife
    cashFlowForLifeEquilibrium = {}
    for compo in cashFlowForLife.keys():
      lifeTime = container.cashFlowParameters['Economics'][compo]['Life_time']['val']
      cashFlowForLifeEquilibrium[compo] = {}
      # loop over cash flows
      for cashFlow in cashFlowForLife[compo].keys():
        cashFlowForLifeEquilibrium[compo][cashFlow] = []
        # treat tax
        if container.cashFlowParameters['Economics'][compo][cashFlow]['tax']['val']:
          # Does this compoent have his own tax?
          if 'tax' in container.cashFlowParameters['Economics'][compo].keys():
            multiplyTax = 1 - container.cashFlowParameters['Economics'][compo]['tax']['val']
          else:
            multiplyTax = 1 - container.cashFlowParameters['Economics']['Global']['tax']['val']
        else:
          multiplyTax = 1
        # treat inflation
        # Does this compoent have his own inflation rate?
        if 'inflation' in container.cashFlowParameters['Economics'][compo].keys():
          infRate = container.cashFlowParameters['Economics'][compo]['inflation']['val']
        else:
          infRate = container.cashFlowParameters['Economics']['Global']['inflation']['val']
        # is inflation real, nominal or none?
        if container.cashFlowParameters['Economics'][compo][cashFlow]['inflation']['val'] == 'real':
          inflat = 1 + infRate
        elif container.cashFlowParameters['Economics'][compo][cashFlow]['inflation']['val'] == 'nominal':
          print ("CashFlow WARNING (run):      nominal inflation is not supported at the moment!")
          inflat = 1
        else:
          inflat = 1
        # printing
        if container.cashFlowVerbosity < 2:
          print ("--------------------------------------------------------------------------------------------------")
          print ("CashFlow INFO (run): cash flow including tax and inflation  : %s" %cashFlow)
          print ("CashFlow INFO (run):      tax is                            : %s" %multiplyTax)
          print ("CashFlow INFO (run):      inflation type is                 : %s" %container.cashFlowParameters['Economics'][compo][cashFlow]['inflation']['val'])
          print ("CashFlow INFO (run):      inflation rate is                 : %s" %inflat)
          print ("CashFlow INFO (run):      component start time              : %s" %container.cashFlowParameters['Economics'][compo]['StartTime']['val'])
          print ("CashFlow INFO (run):      component repetitions             : %s" %container.cashFlowParameters['Economics'][compo]['Repetitions']['val'])
        # compute all the years untill the lcmTime
        # - - - - - - - - - - - - - - - - - - - - - -
        # find end time for his cash flow
        if container.cashFlowParameters['Economics'][compo]['Repetitions']['val'] == 0:
          lcmTime_compo = lcmTime
        else:
          lcmTime_compo = container.cashFlowParameters['Economics'][compo]['StartTime']['val'] + container.cashFlowParameters['Economics'][compo]['Repetitions']['val'] * lifeTime
        for y in range(lcmTime+1):
          # treat StartTime and Repetitions (end of project)
          if y < container.cashFlowParameters['Economics'][compo]['StartTime']['val']:
            cashFlowForYear = 0.0
            cashFlowForLifeEquilibrium[compo][cashFlow].append(cashFlowForYear)
            if container.cashFlowVerbosity < 1:
              print ("CashFlow INFO (run):      for global year (y, cashFlowForYear) Component is not build yet     : %s, %s" %(y, cashFlowForYear))
            continue
          elif y > lcmTime_compo:
            cashFlowForYear = 0.0
            cashFlowForLifeEquilibrium[compo][cashFlow].append(cashFlowForYear)
            if container.cashFlowVerbosity < 1:
              print ("CashFlow INFO (run):      for global year (y, cashFlowForYear) Component is not build anymore : %s, %s" %(y, cashFlowForYear))
            continue
          else :
             y_shift = y - container.cashFlowParameters['Economics'][compo]['StartTime']['val']
          # compute component year
          yReal = y_shift % lifeTime
          # +-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=
          # This is where the magic happens
          # +-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=
          # compute cash flow
          # (all years explicitely treated for better code readability)
          printHere = True
          if yReal == 0:
            # first year
            if y_shift == 0:
              cashFlowForYear = cashFlowForLife[compo][cashFlow][yReal] * multiplyTax * inflat**(-y)
              if container.cashFlowVerbosity < 1:
                print ("CashFlow INFO (run):    first year     : %s, %s, %s, %s" %(y,yReal, inflat**(-y),  cashFlowForYear))
              printHere = False
            #last year
            elif y_shift == lcmTime_compo - container.cashFlowParameters['Economics'][compo]['StartTime']['val']:
              yReal = lifeTime
              cashFlowForYear = cashFlowForLife[compo][cashFlow][yReal] * multiplyTax * inflat**(-y)
              if container.cashFlowVerbosity < 1:
                print ("CashFlow INFO (run):    last year     : %s, %s, %s, %s" %(y,yReal, inflat**(-y),  cashFlowForYear))
              printHere = False
            #in between
            else:
              if container.cashFlowVerbosity < 1:
                print ("CashFlow INFO (run):    new construction year ")
              cashFlowForYear = cashFlowForLife[compo][cashFlow][yReal] * multiplyTax * inflat**(-y)
              if container.cashFlowVerbosity < 1:
                print ("CashFlow INFO (run):                  : %s, %s, %s, %s" %(y,yReal, inflat**(-y),  cashFlowForYear))
              yReal = lifeTime
              cashFlowForYear += cashFlowForLife[compo][cashFlow][yReal] * multiplyTax * inflat**(-y)
              if container.cashFlowVerbosity < 1:
                print ("CashFlow INFO (run):                  : %s, %s, %s, %s" %(y,yReal, inflat**(-y),  cashFlowForYear))
              printHere = False
          else:
            cashFlowForYear = cashFlowForLife[compo][cashFlow][yReal] * multiplyTax * inflat**(-y)
          # is the last year of the project life? Then we need to add the construction cost for the next plant
          cashFlowForLifeEquilibrium[compo][cashFlow].append(cashFlowForYear)
          if container.cashFlowVerbosity < 1 and printHere:
            print ("CashFlow INFO (run):      for global year (y, component year, inflation, cashFlowForYear)     : %s, %s, %s, %s" %(y,yReal, inflat**(-y),  cashFlowForYear))

    # compute the IRR, NPV or do a NPV search on a multiplier (like the cost)
    # NPV search
    # == == === == ==
    if 'NPV_search' in container.cashFlowParameters['Economics']['Global']['Indicator']['attr']['name']:
      # loop over all CashFlows included in NPV
      cashFlowIncludingMultiplier = 0.0 # all contributions that include the multiplier (left hand side of the equation)
      cashFlowNotIncludingMultiplier = 0.0 # all contributions that do not include the multiplier (right hand side of the equation)
      for cashFlow in container.cashFlowParameters['Economics']['Global']['Indicator']['val']:
        # to which component does this cash flow belong?
        for compo in container.cashFlowComponentsList:
          if cashFlow in container.cashFlowParameters['Economics'][compo].keys():
            break
        for y in range(lcmTime+1):
          DiscountRate = (1 + container.cashFlowParameters['Economics']['Global']['DiscountRate']['val'])**y
          # sum multiplier true
          if container.cashFlowParameters['Economics'][compo][cashFlow]['mult_target']['val']:
            cashFlowIncludingMultiplier += cashFlowForLifeEquilibrium[compo][cashFlow][y]/DiscountRate
          # sum multiplier false
          else:
            cashFlowNotIncludingMultiplier += cashFlowForLifeEquilibrium[compo][cashFlow][y]/DiscountRate
      # THIS COMPUTES THE MULTIPLIER
      container.NPV_mult = (container.cashFlowParameters['Economics']['Global']['Indicator']['attr']['target']-cashFlowNotIncludingMultiplier)/cashFlowIncludingMultiplier
      if container.cashFlowVerbosity < 51:
        print ("CashFlow INFO (run): Multiplier : %s"  %container.NPV_mult[0])
      # do a little sanity check
      # => compute FCFF with the found multiplier and recompute NPV
      if container.cashFlowVerbosity < 1:
        FCFF = np.zeros(lcmTime + 1)
        for cashFlow in container.cashFlowParameters['Economics']['Global']['Indicator']['val']:
          # to which component does this cash flow belong?
          for compo in container.cashFlowComponentsList:
            if cashFlow in container.cashFlowParameters['Economics'][compo].keys():
              break
          for y in range(lcmTime+1):
            if container.cashFlowParameters['Economics'][compo][cashFlow]['mult_target']['val']:
              FCFF[y] += cashFlowForLifeEquilibrium[compo][cashFlow][y] * container.NPV_mult[0]
            else:
              FCFF[y] += cashFlowForLifeEquilibrium[compo][cashFlow][y]
        NPV = np.npv(container.cashFlowParameters['Economics']['Global']['DiscountRate']['val'], FCFF)
        print ("CashFlow INFO (run): NPV check : %s"  %NPV)

    # NPV, IRR
    # == == === == ==
    if 'NPV' in container.cashFlowParameters['Economics']['Global']['Indicator']['attr']['name'] or 'IRR' in container.cashFlowParameters['Economics']['Global']['Indicator']['attr']['name'] or 'PI' in container.cashFlowParameters['Economics']['Global']['Indicator']['attr']['name']:
      # create FCFF_R for every year
      FCFF = np.zeros(lcmTime + 1)
      for cashFlow in container.cashFlowParameters['Economics']['Global']['Indicator']['val']:
        # to which component does this cash flow belong?
        for compo in container.cashFlowComponentsList:
          if cashFlow in container.cashFlowParameters['Economics'][compo].keys():
            break
        for y in range(lcmTime+1):
          FCFF[y] += cashFlowForLifeEquilibrium[compo][cashFlow][y]
      if container.cashFlowVerbosity < 1:
        print ("CashFlow INFO (run): FCFF for each year (not discounted):")
        print (FCFF)
      if 'NPV' in  container.cashFlowParameters['Economics']['Global']['Indicator']['attr']['name'] or 'PI' in container.cashFlowParameters['Economics']['Global']['Indicator']['attr']['name'] :
        container.NPV = np.npv(container.cashFlowParameters['Economics']['Global']['DiscountRate']['val'], FCFF)
        if container.cashFlowVerbosity < 51:
          print ("CashFlow INFO (run): NPV : %s"  %container.NPV)
      if 'IRR' in container.cashFlowParameters['Economics']['Global']['Indicator']['attr']['name']:
        try:  # np.irr crushes, when no solution exists..  very bad... this is just a quick workaround..
          container.IRR = np.irr(FCFF)
        except:
          container.IRR = -10.0
          print ("CashFlow WARNING (run): The IRR computation failed for some reason. Setting the IRR to -10.0")
        if container.cashFlowVerbosity < 51:
          print ("CashFlow INFO (run): IRR : %s"  %container.IRR)
      if 'PI' in container.cashFlowParameters['Economics']['Global']['Indicator']['attr']['name']:
        container.PI = - container.NPV / FCFF[0]
        if container.cashFlowVerbosity < 1:
          print ("CashFlow INFO (run): FCFF[0]: %s" %FCFF[0])
        if container.cashFlowVerbosity < 51:
          print ("CashFlow INFO (run): PI : %s"  %container.PI)
  # =====================================================================================================================

###############################
#### RAVEN API methods END ####
###############################

###################################
#### LOCAL CLASS methods BEGIN ####
###################################

# =====================================================================================================================
def recursiveXmlReader(xmlNode, inDictionary):
  """
    reads an infinte depth of an XML tree into a dictionary
    @ In, xmlNode, xml.etree.ElementTree.Element, Xml element node
    @ In, inDictionary, dict, is filled with the information read from the XML input, i.e. components and cash flow definitions
    @ Out, inDictionary, dict, is filled with the information read from the XML input, i.e. components and cash flow definitions
  """
  # 'Components' and 'CasFlows' are treated specially, since the node name <Component> or <CashFlow> can be repeated multiple times
  #  => The dictionary is not called <Component> (or <CashFlow>) but replaced with the 'name' attribute of these
  # the 'attribute' of these is replaced with 'Component' or 'CashFlow' for identification. This implies that all attributes for these
  # two nodes have to be treated explicitely
  # ==> The attributes of all other nodes will be available in the 'attr' dictionary

  # treat components
  # - - - - - - - - - - - - - - - - - - -
  if xmlNode.tag == "Component":
    if 'name' in xmlNode.attrib:
      xmlNodeName = xmlNode.attrib['name']
      if xmlNodeName in inDictionary.keys():
        raise IOError("CashFlow ERROR (XML reading): 'Component' names need to be unique (cant be 'attr', 'val' or any other existing XML tag name): %s" %xmlNodeName)
      inDictionary[xmlNodeName] = {'val':xmlNode.text,'attr':'Component'}
    else:
      raise IOError("CashFlow ERROR (XML reading): 'Component' requires attribute 'name'")
  # treat CashFlow in conmponents
  # - - - - - - - - - - - - - - - - - - -
  elif xmlNode.tag == "CashFlow":
    if 'name' in xmlNode.attrib:
      xmlNodeName = xmlNode.attrib['name']
      if xmlNodeName in inDictionary.keys():
        raise IOError("CashFlow ERROR (XML reading): 'CashFlow' names need to be unique (cant be 'attr', 'val' or any other existing XML tag name): %s" %xmlNodeName)
      inDictionary[xmlNodeName] = {'val':xmlNode.text,'attr':'CashFlow'}
    else:
      raise IOError("CashFlow ERROR (XML reading): 'CashFlow' requires attribute 'name'")

    for attribute in ['driver', 'tax', 'inflation']:
      if attribute in xmlNode.attrib:
        inDictionary[xmlNodeName][attribute] = {'val':xmlNode.attrib[attribute],'attr': {}}
      else:
        raise IOError("CashFlow ERROR (XML reading): 'CashFlow' requires attribute %s" %attribute)
    # treat multiply
      if 'multiply' in xmlNode.attrib:
        inDictionary[xmlNodeName]['multiply'] = {'val':xmlNode.attrib['multiply'],'attr': {}}
      else:
        inDictionary[xmlNodeName]['multiply'] = {'val':'Default','attr': {}}
    # treat mult_target
      if 'mult_target' in xmlNode.attrib:
        inDictionary[xmlNodeName]['mult_target'] = {'val':xmlNode.attrib['mult_target'],'attr': {}}
      else:
        inDictionary[xmlNodeName]['mult_target'] = {'val':'None','attr': {}}

  # treat rest
  # - - - - - - - - - - - - - - - - - - -
  else:
    xmlNodeName = xmlNode.tag
    if xmlNodeName in inDictionary.keys():
      raise IOError("CashFlow ERROR (XML reading): XML Tags need to be unique (cant be 'attr', 'val' or any Component or CashFlow names): %s" %xmlNodeName)
    inDictionary[xmlNodeName] = {'val':xmlNode.text,'attr':xmlNode.attrib}
  # recursion
  # - - - - - - - - - - - - - - - - - - -
  if len(list(xmlNode)) > 0:
    for child in xmlNode:
      recursiveXmlReader(child, inDictionary[xmlNodeName])
# =====================================================================================================================

# =====================================================================================================================
def isInt(string):
  """
    Checks if string is an integer
    @ In, string, string, string to be checked
    @ Out, isInt, boolean, result of test, i.e. true or false
  """
  try:
    int(string)
    return True
  except:
    return False
# =====================================================================================================================

# =====================================================================================================================
def isReal(string):
  """
    Checks if string is a real
    @ In, string, string, string to be checked
    @ Out, isReal, boolean, result of test, i.e. true or false
  """
  try:
    float(string)
    return True
  except:
    return False
# =====================================================================================================================

# =====================================================================================================================
def gcd(a, b):
  """
    Return greatest common divisor using Euclid's Algorithm
    @ In, a, int, first number
    @ In, b, int, second number
    @ Out, gcd, int, greatest common divisor of a and b
  """
  while b:
    a, b = b, a % b
  return a
def lcm(a, b):
  """
    Return lowest common multiple
    @ In, a, int, first number
    @ In, b, int, second number
    @ Out, lcm, int, lowest common multiple of a and b
  """
  return a * b // gcd(a, b)
def lcmm(*args):
  """
    Return lcm of args
    @ In, args, *int, list of integers
    @ Out, lcmm, lowest common multiple of args
  """
  return functools.reduce(lcm, args)
# =====================================================================================================================

#################################
#### LOCAL CLASS methods END ####
#################################


#################################
# Run the plugin in stand alone #
#################################
if __name__ == "__main__":
  # emulate RAVEN container
  class FakeSelf:
    def __init__(self):
      pass
  import xml.etree.ElementTree as ET
  import argparse
  import csv
  # read and process input arguments
  # ================================
  inp_par = argparse.ArgumentParser(description = 'Run RAVEN CashFlow plugin as stand-alone code')
  inp_par.add_argument('-iXML', nargs=1, required=True, help='XML CashFlow input file name', metavar='inp_file')
  inp_par.add_argument('-iINP', nargs=1, required=True, help='CashFlow input file name with the input variable list', metavar='inp_file')
  inp_par.add_argument('-o', nargs=1, required=True, help='Output file name', metavar='out_file')
  inp_opt  = inp_par.parse_args()

  # check if files exist
  print ("CashFlow INFO (Run as Code): XML input file: %s" %inp_opt.iXML[0])
  print ("CashFlow INFO (Run as Code): Variable input file: %s" %inp_opt.iINP[0])
  print ("CashFlow INFO (Run as Code): Output file: %s" %inp_opt.o[0])
  if not os.path.exists(inp_opt.iXML[0]) :
    raise IOError('\033[91m' + "CashFlow INFO (Run as Code): : XML input file " + inp_opt.iXML[0] + " does not exist.. " + '\033[0m')
  if not os.path.exists(inp_opt.iINP[0]) :
    raise IOError('\033[91m' + "CashFlow INFO (Run as Code): : Variable input file " + inp_opt.iINP[0] + " does not exist.. " + '\033[0m')
  if os.path.exists(inp_opt.o[0]) :
    print ("CashFlow WARNING (Run as Code): Output file %s already exists. Will be overwritten. " %inp_opt.o[0])

  # Initialise run
  # ================================
  # create a CashFlow class instance
  MyCashFlow = CashFlow()
  # read the XML input file inp_opt.iXML[0]
  MyContainer = FakeSelf()
  notroot = ET.parse(open(inp_opt.iXML[0], 'r')).getroot()
  root = ET.Element('ROOT')
  root.append(notroot)
  MyCashFlow._readMoreXML(MyContainer, root)
  MyCashFlow.initialize(MyContainer, {}, [])
  if MyContainer.cashFlowVerbosity < 2:
    print("CashFlow INFO (Run as Code): XML input read ")
  # read the values from input file into dictionary inp_opt.iINP[0]
  MyInputs = {}
  with open(inp_opt.iINP[0]) as f:
    for l in f:
      (key, val) = l.split(' ', 1)
      MyInputs[key] = np.array([float(n) for n in val.split(",")])
  if MyContainer.cashFlowVerbosity < 2:
    print("CashFlow INFO (Run as Code): Variable input read ")
  if MyContainer.cashFlowVerbosity < 1:
    print("CashFlow INFO (Run as Code): Inputs dict %s" %MyInputs)

  # run the stuff
  # ================================
  if MyContainer.cashFlowVerbosity < 2:
    print("CashFlow INFO (Run as Code): Running the code")
  MyCashFlow.run(MyContainer, MyInputs)

  # create output file
  # ================================
  if MyContainer.cashFlowVerbosity < 2:
    print("CashFlow INFO (Run as Code): Writing output file")
  outDict = {}
  for indicator in ['NPV_mult', 'NPV', 'IRR', 'PI']:
    try:
      outDict[indicator] = getattr(MyContainer, indicator)
      if MyContainer.cashFlowVerbosity < 2:
        print("CashFlow INFO (Run as Code): %s written to file" %indicator)
    except:
      if MyContainer.cashFlowVerbosity < 2:
        print("CashFlow INFO (Run as Code): %s not found" %indicator)
  with open(inp_opt.o[0], 'w') as out:
    CSVwrite = csv.DictWriter(out, outDict.keys())
    CSVwrite.writeheader()
    CSVwrite.writerow(outDict)
