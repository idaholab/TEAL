"""
  Author:  A. S. Epiney
  Date  :  02/23/2017
"""

# This file contains difference Economics calcaultion options that can be used with RAVEN
import numpy as np
from utils.graphStructure import graphObject

# =====================================================================================================================
def _readMoreXML(self,xmlNode):
  self.CFparams = {}
  for child in xmlNode:
    if child.tag == "Economics":
      # get verbosity if it exists
      if 'verbosity' in child.attrib:
        if isInt(child.attrib['verbosity']):
          self.CFver = int(child.attrib['verbosity'])
        else:
          raise IOError("Economics ERROR (XML reading): 'verbosity' in 'Economics'  needs to be an integer'")
      else:
        self.CFver = 100 # errors only
      if self.CFver < 100:
        print "Economics INFO (XML reading): verbosity level: %s" %self.CFver
      recursiveXmlReader(child, self.CFparams)
# =====================================================================================================================

# =====================================================================================================================
def recursiveXmlReader(xmlNode, inDictionary):
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
        raise IOError("Economics ERROR (XML reading): 'Component' names need to be unique (cant be 'attr', 'val' or any other existing XML tag name): %s" %xmlNodeName)
      inDictionary[xmlNodeName] = {'val':xmlNode.text,'attr':'Component'}
    else:
      raise IOError("Economics ERROR (XML reading): 'Component' requires attribute 'name'")
  # treat CashFlow in conmponents
  # - - - - - - - - - - - - - - - - - - - 
  elif xmlNode.tag == "CashFlow":
    if 'name' in xmlNode.attrib:
      xmlNodeName = xmlNode.attrib['name']
      if xmlNodeName in inDictionary.keys():
        raise IOError("Economics ERROR (XML reading): 'CashFlow' names need to be unique (cant be 'attr', 'val' or any other existing XML tag name): %s" %xmlNodeName)
      inDictionary[xmlNodeName] = {'val':xmlNode.text,'attr':'CashFlow'}
    else:
      raise IOError("Economics ERROR (XML reading): 'CashFlow' requires attribute 'name'")

    for attribute in ['driver', 'tax', 'inflation']: 
      if attribute in xmlNode.attrib:
        inDictionary[xmlNodeName][attribute] = {'val':xmlNode.attrib[attribute],'attr': {}}
      else:
        raise IOError("Economics ERROR (XML reading): 'CashFlow' requires attribute %s" %attribute)
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
      raise IOError("Economics ERROR (XML reading): XML Tags need to be unique (cant be 'attr', 'val' or any Component or CashFlow names): %s" %xmlNodeName)
    inDictionary[xmlNodeName] = {'val':xmlNode.text,'attr':xmlNode.attrib}
  # recursion
  # - - - - - - - - - - - - - - - - - - - 
  if len(list(xmlNode)) > 0:
    for child in xmlNode:  
      recursiveXmlReader(child, inDictionary[xmlNodeName])
# =====================================================================================================================

# =====================================================================================================================
def isInt(str):
  try:
    int(str)
    return True
  except:
    return False
# =====================================================================================================================

# =====================================================================================================================
def isReal(str):
  try:
    float(str)
    return True
  except:
    return False
# =====================================================================================================================

# =====================================================================================================================
def gcd(a, b):
  """Return greatest common divisor using Euclid's Algorithm."""
  while b:
    a, b = b, a % b
  return a
def lcm(a, b):
  """Return lowest common multiple."""
  return a * b // gcd(a, b)
def lcmm(*args):
  """Return lcm of args."""   
  return reduce(lcm, args)
# =====================================================================================================================

# =====================================================================================================================
def initialize(self,runInfoDict,inputFiles):
  # check that the values that we need are in the dict CFparams
  # check if Economics exists
  # - - - - - - - - - - - - - - - - - - -
  if 'Economics' not in self.CFparams.keys():
    raise IOError("Economics ERROR (XML reading): 'Economics' node is required")

  # check if Global and children exist and are of the correct type
  # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
  if 'Global' not in self.CFparams['Economics'].keys():
    raise IOError("Economics ERROR (XML reading): 'Global' node is required inside 'Economics'")

  for tags in ['WACC', 'tax', 'inflation', 'Indicator']: 
    if tags not in self.CFparams['Economics']['Global'].keys():
      raise IOError("Economics ERROR (XML reading): '%s' node is required inside 'Global'" %tags)
    # reals
    if tags in ['WACC', 'tax', 'inflation']:
      if isReal(self.CFparams['Economics']['Global'][tags]['val']):
        self.CFparams['Economics']['Global'][tags]['val'] = float(self.CFparams['Economics']['Global'][tags]['val'])
      else:
        raise IOError("Economics ERROR (XML reading): '%s' needs to be a real number'" %tags)
  # Check Indicator attributes(values are checked after the Cash Flow nodes)
  # check 'name'
  if 'name' not in self.CFparams['Economics']['Global']['Indicator']['attr'].keys():
    raise IOError("Economics ERROR (XML reading): 'name' attribute of 'Indicator' is required inside 'Global'")
  self.CFparams['Economics']['Global']['Indicator']['attr']['name'] = self.CFparams['Economics']['Global']['Indicator']['attr']['name'].split(",")
  for indicators in self.CFparams['Economics']['Global']['Indicator']['attr']['name']:
    if indicators not in ['NPV_search', 'NPV', 'IRR', 'PI']:
      raise IOError("Economics ERROR (XML reading): 'name' attribut  of 'Indicator' inside 'Global' has to be 'NPV_search', 'NPV' or 'IRR' or 'PI'")
    if indicators == 'NPV_search':
      # check 'name' if name is name=NPV
      if 'target' not in self.CFparams['Economics']['Global']['Indicator']['attr'].keys():
        raise IOError("Economics ERROR (XML reading): 'target' attribute of 'Indicator' is required inside 'Global' if name='NPV_search'")
      if isReal(self.CFparams['Economics']['Global']['Indicator']['attr']['target']):
        self.CFparams['Economics']['Global']['Indicator']['attr']['target'] = float(self.CFparams['Economics']['Global']['Indicator']['attr']['target'])
      else:
        raise IOError("Economics ERROR (XML reading): 'target' attribute of 'Indicator' inside 'Global' needs to be a real number")

  # check if all Components' children and attributes exist and are of the correct type
  # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  self.CFcompoList = []
  self.CFcashflowList = []
  onemult_targetrue = False
  for Compo in self.CFparams['Economics'].keys():
    if Compo <> 'attr' and Compo <> 'val':
      if self.CFparams['Economics'][Compo]['attr'] == 'Component':
        if self.CFver < 2:
          print "Economics INFO (XML reading): Found component %s" %Compo
        self.CFcompoList.append(Compo)
        # Life_time
        for tags in ['Life_time']: 
          if tags not in self.CFparams['Economics'][Compo].keys():
            raise IOError("Economics ERROR (XML reading): '%s' node is required inside '%s'" %(tags, Compo))
        # integers
        for tags in ['Life_time']:
          if isInt(self.CFparams['Economics'][Compo][tags]['val']):
            self.CFparams['Economics'][Compo][tags]['val'] = int(self.CFparams['Economics'][Compo][tags]['val'])
          else:
            raise IOError("Economics ERROR (XML reading): '%s' needs to be an integer inside '%s'" %(tags, Compo))

        # Check CashFlow Nodes
        # - - - - - - - - - - - - - 
        for CashFlow in self.CFparams['Economics'][Compo]:
          if CashFlow <> 'attr' and CashFlow <> 'val':
            if self.CFparams['Economics'][Compo][CashFlow]['attr'] == 'CashFlow':
              if self.CFver < 2:
                print "Economics INFO (XML reading): Found CashFlow definition %s" %CashFlow
              if CashFlow in self.CFcashflowList:
                raise IOError("Economics ERROR (XML reading): Cashflow names need to be unique over all components: '%s" %CashFlow)
              self.CFcashflowList.append(CashFlow)
              # reference, alpha, X 
              for tags in ['alpha', 'reference', 'X']: 
                if tags not in self.CFparams['Economics'][Compo][CashFlow].keys():
                  raise IOError("Economics ERROR (XML reading): '%s' node is required inside Cash Flow '%s'" %(tags, CashFlow))
              # real values
              for tags in ['reference', 'X']:
                if isReal(self.CFparams['Economics'][Compo][CashFlow][tags]['val']):
                  self.CFparams['Economics'][Compo][CashFlow][tags]['val'] = float(self.CFparams['Economics'][Compo][CashFlow][tags]['val'])
                else:
                  raise IOError("Economics ERROR (XML reading): '%s' needs to be a real number inside '%s'" %(tags, CashFlow))
              # arrays
              for tags in ['alpha']:
                self.CFparams['Economics'][Compo][CashFlow][tags]['val'] = self.CFparams['Economics'][Compo][CashFlow][tags]['val'].split()
              if len(self.CFparams['Economics'][Compo][CashFlow][tags]['val']) - 1 <> self.CFparams['Economics'][Compo]['Life_time']['val']:
                raise IOError("Economics ERROR (XML reading): '%s' needs to have the lenght of 'Life_time' (%s) + 1 in '%s'" %(tags, self.CFparams['Economics'][Compo]['Life_time']['val'], CashFlow))
              for i in range(len(self.CFparams['Economics'][Compo][CashFlow][tags]['val'])):
                if isReal(self.CFparams['Economics'][Compo][CashFlow][tags]['val'][i]):
                  self.CFparams['Economics'][Compo][CashFlow][tags]['val'][i] = float(self.CFparams['Economics'][Compo][CashFlow][tags]['val'][i])
                else:
                  raise IOError("Economics ERROR (XML reading): '%s' needs to be an array of real numbers inside '%s'" %(tags, CashFlow))
              # check CashFlow attributes
              # - - - - - - - - - - - - - 
              # Existence of 'driver' and 'multiply' in input space are checked during runtime (this check is not possible during initialisation)
              # tax, inflation => existence for attributes is already checked during reading
              # logical
              for tags in ['tax']:
                if self.CFparams['Economics'][Compo][CashFlow][tags]['val'] in ['true'] :
                  self.CFparams['Economics'][Compo][CashFlow][tags]['val'] = True
                elif self.CFparams['Economics'][Compo][CashFlow][tags]['val'] in ['false']:
                  self.CFparams['Economics'][Compo][CashFlow][tags]['val'] = False
                else:
                  raise IOError("Economics ERROR (XML reading): '%s' needs to be 'true' or 'false' inside '%s' of '%s'" %(tags, CashFlow, Compo))
              # special
              for tags in ['inflation']:
                if self.CFparams['Economics'][Compo][CashFlow][tags]['val'] not in ['real','nominal','none'] :
                  raise IOError("Economics ERROR (XML reading): '%s' needs to be 'real', 'nominal' or 'none' inside '%s' of '%s'" %(tags, CashFlow, Compo))
              # mult_target => only needed if <Global><Indicator name='NPV_search'>
              for tags in ['mult_target']:
                if 'NPV_search' in self.CFparams['Economics']['Global']['Indicator']['attr']['name']:
                  if self.CFparams['Economics'][Compo][CashFlow]['mult_target']['val'] == 'None':
                    raise IOError("Economics ERROR (XML reading): Attribute '%s' needs to exist and needs to 'true' or 'false' inside '%s' of '%s' if Indicator is NPV_search" %(tags, CashFlow, Compo))
                  else:
                    if self.CFparams['Economics'][Compo][CashFlow]['mult_target']['val'] in ['true'] :
                      self.CFparams['Economics'][Compo][CashFlow]['mult_target']['val'] = True
                      onemult_targetrue = True
                    elif self.CFparams['Economics'][Compo][CashFlow]['mult_target']['val'] in ['false']:
                      self.CFparams['Economics'][Compo][CashFlow]['mult_target']['val'] = False
                    else:
                      raise IOError("Economics ERROR (XML reading): '%s' needs to be 'true' or 'false' inside '%s' of '%s'" %(tags, CashFlow, Compo))

  # If Indicator is NPV_search, at least one Cash Flow has to have mult_target="false" and one has to have mult_target="true"
  if 'NPV_search' in self.CFparams['Economics']['Global']['Indicator']['attr']['name']:
    if not onemult_targetrue:
      raise IOError("Economics ERROR (XML reading): If Indicator is NPV, at laest one CashFlow has to have mult_target=true")

  # Check Indictor node inside Global
  # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  # all cach flows requested in Indicator have to be defined in the Cash Flows
  self.CFparams['Economics']['Global']['Indicator']['val'] = self.CFparams['Economics']['Global']['Indicator']['val'].split()
  for request in self.CFparams['Economics']['Global']['Indicator']['val']:
    if request not in self.CFcashflowList:
      raise IOError("Economics ERROR (XML reading): '%s' requested in 'Indicator' needs to be a CashFlow" %request)
# =====================================================================================================================

# =====================================================================================================================
def run(self, Inputs):
  """
    Computes economic key figures (NPV, IRR, PI as well as NPV serach)
    Inputs  : self and Inputs dictionaries from RAVEN
    Outputs : for NPV        : self.NPV
              for IRR        : self.IRR
              for PI         : self.IP
              for NPV_search : self.NPV_mult
  """

  if self.CFver < 1:
    print "Economics INFO (run): Inside Economics"

  # add "Default" multiplier to inputs
  if 'Deafult' in Inputs.keys():
    raise IOError("Economics ERROR (run): The input 'Default' is passed from Raven in to the Economics. This is not allowed at the moment.... sorry... ")
  Inputs['Default'] = 1.0

  # Check if the needed inputs (drivers and multipliers) for the different Cash Flows are present
  # ------------------------------------------------------------------------
  if self.CFver < 1:
    print "Economics INFO (run): Checking if all drivers for Cash Flow are present"
  dictionaryOfNodes = {}
  dictionaryOfNodes['EndNode'] = []
  # loop over components
  for Compo in self.CFcompoList:
    # loop over cash flows
    for CashFlow in self.CFparams['Economics'][Compo]:
      if CashFlow <> 'attr' and CashFlow <> 'val':
        if self.CFparams['Economics'][Compo][CashFlow]['attr'] == 'CashFlow':
          if self.CFver < 1:
            print "Economics INFO (run): Checking component %s, Cash flow: %s " %(Compo,CashFlow)
          # check if the multiplier is part of the Inputs (this can not be another CashFlow)
          # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
          multiply = self.CFparams['Economics'][Compo][CashFlow]['multiply']['val']
          if multiply not in Inputs.keys():
            raise IOError("Economics ERROR (run): multiply %s for Cash flow %s not in inputs" %(multiply, CashFlow))
          # check if the driver is present in Input or is another Cash Flow 
          # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
          driver = self.CFparams['Economics'][Compo][CashFlow]['driver']['val']
          # construct dictionaryOfNodes for Graph later
          if CashFlow in dictionaryOfNodes.keys():
            dictionaryOfNodes[CashFlow].append('EndNode')
          else:
            dictionaryOfNodes[CashFlow] = ['EndNode']
          if driver in dictionaryOfNodes.keys():
            dictionaryOfNodes[driver].append(CashFlow)
          else:
            dictionaryOfNodes[driver] = [CashFlow]
          dontexityet = True
          while dontexityet:
            if driver in Inputs.keys():
              if self.CFver < 1:
                print "Economics INFO (run): driver %s in inputs from RAVEN       " %driver
              dontexityet = False
            if driver in self.CFcashflowList:
              if self.CFver < 1:
                print "Economics INFO (run): driver %s in another CashFlow        " %driver
                print "                      Follow chain back..."
              if not dontexityet:
                raise IOError("Economics ERROR (XML reading): driver %s for Cash flow %s in inputs AND other Cash flows (can only be in one)  " %(driver, CashFlow))
              # to which component does this Cash Flow (driver) belong?
              for CompoT in self.CFcompoList:
                if driver in self.CFparams['Economics'][CompoT].keys():
                  break
              driver = self.CFparams['Economics'][CompoT][driver]['driver']['val']
              # check the Amortisation  time lenght
              if self.CFparams['Economics'][Compo]['Life_time']['val'] != self.CFparams['Economics'][CompoT]['Life_time']['val']:
                raise IOError("Economics ERROR (XML reading): If CashFlows depend on CashFlows of other Components, the Life times for these components have to be the same!")
              # check if its cyclic
              if driver == CashFlow:
                raise IOError("Economics ERROR (XML reading): drivers cycle in Cash flow! Can not solve this. (use verbosity = 0 to print which driver it is)")
              continue
            if dontexityet:
              raise IOError("Economics ERROR (XML reading): driver %s for Cash flow %s not in inputs or other Cash flows " %(driver, CashFlow))

  # if everything is OK, build the sequence to execute the CsahFlows
  # ------------------------------------------------------------------------
  MyGraph = graphObject(dictionaryOfNodes)
  CF_sequence = MyGraph.createSingleListOfVertices() 
  if self.CFver < 2:
    print "Economics INFO (run): Found sequence for execution of Cash Flows: %s" %CF_sequence

  # Construct cash flow terms for each component and year untill the end for the component life time
  # Since cash flows can depend on other cash flows, the cash flows computed here are without tax and inflation 
  # ------------------------------------------------------------------------------------------------------------
  TE = {}
  # loop over cash_flows
  for CashFlow in CF_sequence:
    if CashFlow in Inputs.keys() or CashFlow == 'EndNode':
      continue
    if self.CFver < 2:
      print "--------------------------------------------------------------------------------------------------"
      print "Economics INFO (run): Computing cash flow               : %s" %CashFlow
    # to which component does this CashFlow belong?
    for CompoT in self.CFcompoList:
      if CashFlow in self.CFparams['Economics'][CompoT].keys():
        break
    if self.CFver < 2:
      print "Economics INFO (run): Cash flow belongs to component    : %s" %CompoT
    if CompoT not in TE.keys():
      TE[CompoT] = {}
    TE[CompoT][CashFlow] = []
    drivrNAME = self.CFparams['Economics'][CompoT][CashFlow]['driver']['val']
    if self.CFver < 2:
      print "Economics INFO (run): Cash flow driver name is          : %s" %drivrNAME
    if drivrNAME in Inputs.keys():
      # The driver is in the inputs from RAVEN!
      drivry = [Inputs[drivrNAME]]*(self.CFparams['Economics'][CompoT]['Life_time']['val'] + 1)
    else:
      # The driver is another cash flow!
      # the lenght of the list, i.e. the Amortisation time of the component that provides the driver has 
      # to be the same than for the component to whiah the Cash Flow belongs
      # this check is done at the reading statge

      # to which component does this driver belong?
      for CompoX in self.CFcompoList:
        if drivrNAME in self.CFparams['Economics'][CompoX].keys():
          break
      drivry = TE[CompoX][drivrNAME]
    refre = self.CFparams['Economics'][CompoT][CashFlow]['reference']['val']
    Xexpo = self.CFparams['Economics'][CompoT][CashFlow]['X']['val']
    multiNAME = self.CFparams['Economics'][CompoT][CashFlow]['multiply']['val']
    if self.CFver < 2:
      print "Economics INFO (run): Cash flow mulipl name is          : %s" %multiNAME
    multi = Inputs[multiNAME]
    if self.CFver < 2:
      print "Economics INFO (run):      life time is                 : %s" %self.CFparams['Economics'][CompoT]['Life_time']['val']
      print "Economics INFO (run):      reference is                 : %s" %refre
      print "Economics INFO (run):      Exponent  is                 : %s" %Xexpo
      print "Economics INFO (run):      Multiply  is                 : %s" %multi
    # loop over the years until end of life for that component
    for y in range(self.CFparams['Economics'][CompoT]['Life_time']['val']+1):
      # +-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=
      # This is where the magic happens
      # +-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=
      alpha = self.CFparams['Economics'][CompoT][CashFlow]['alpha']['val'][y]
      drivr = drivry[y]
      cashflow = multi * alpha * (drivr/refre)**Xexpo
      TE[CompoT][CashFlow].append(cashflow)
      if self.CFver < 1:
        print "Economics INFO (run):      for year (a, drivr, cashflow) %s    : %s, %s, %s" %(y,alpha,drivr,cashflow)

  # Include tax and inflation for all cash flows for the lenght of the cumulative project
  # ------------------------------------------------------------------------------------------------------------
  # find the smallest common multiple of the differetn life times of the components
  if self.CFver < 1:
    print "Economics INFO (run): finding lcm of all component lifetimes "
  lifetimes = []
  for CompoT in self.CFcompoList:
    if self.CFver < 1:
      print "Economics INFO (run):  Life time for Component is: %s, %s" %(CompoT, self.CFparams['Economics'][CompoT]['Life_time']['val'])
    lifetimes.append(self.CFparams['Economics'][CompoT]['Life_time']['val'])
  lcm_time = lcmm(*lifetimes)
  if self.CFver < 2:
    print "Economics INFO (run):  LCM is                    : %s" %(lcm_time)

  # compute all cash flows for the years
  # loop over components in TE
  TEequi = {}
  for Compo in TE.keys():
    life_time = self.CFparams['Economics'][Compo]['Life_time']['val']
    TEequi[Compo] = {}
    # loop over Cash Flows
    for CashFlow in TE[Compo].keys():
      TEequi[Compo][CashFlow] = []
      # treat tax
      if self.CFparams['Economics'][Compo][CashFlow]['tax']['val']:
        mutl_tax = 1 - self.CFparams['Economics']['Global']['tax']['val'] 
      else:
        mutl_tax = 1
      inflati = 1 + self.CFparams['Economics']['Global']['inflation']['val']
      # printing
      if self.CFver < 2:
        print "--------------------------------------------------------------------------------------------------"
        print "Economics INFO (run): Cash flow including tax and inflation  : %s" %CashFlow
        print "Economics INFO (run):      tax is                            : %s" %mutl_tax
        print "Economics INFO (run):      inflation is                      : %s" %self.CFparams['Economics'][Compo][CashFlow]['inflation']['val']
      # compute all the years untill the lcm_time
      for y in range(lcm_time+1):
        y_real = y % life_time
        # +-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=
        # This is where the magic happens
        # +-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=+-+=
        # treat inflation
        if self.CFparams['Economics'][Compo][CashFlow]['inflation']['val'] == 'real':
          inflat = inflati
        elif self.CFparams['Economics'][Compo][CashFlow]['inflation']['val'] == 'nominal':    
          print "Economics WARNING (run):      nominal inflation is not supported at the moment!"
          inflat = 1
        else:
          inflat = 1
        # compute cash flow
        # (all years explicitely treated for better code readability)
        printhere = True
        if y_real == 0:
          # first year
          if y == 0:
            cashflow = TE[Compo][CashFlow][y_real] * mutl_tax * inflat**(-y)
            if self.CFver < 1:
              print "Economics INFO (run):    first year     : %s, %s, %s, %s" %(y,y_real, inflat**(-y),  cashflow)
            printhere = False
          #last year
          elif y == lcm_time:
            y_real = life_time
            cashflow = TE[Compo][CashFlow][y_real] * mutl_tax * inflat**(-y)
            if self.CFver < 1:
              print "Economics INFO (run):    last year     : %s, %s, %s, %s" %(y,y_real, inflat**(-y),  cashflow)
            printhere = False
          #in between
          else:
            if self.CFver < 1:
              print "Economics INFO (run):    new construction year "
            cashflow = TE[Compo][CashFlow][y_real] * mutl_tax * inflat**(-y)
            if self.CFver < 1:
              print "Economics INFO (run):                  : %s, %s, %s, %s" %(y,y_real, inflat**(-y),  cashflow)
            y_real = life_time
            cashflow += TE[Compo][CashFlow][y_real] * mutl_tax * inflat**(-y)
            if self.CFver < 1:
              print "Economics INFO (run):                  : %s, %s, %s, %s" %(y,y_real, inflat**(-y),  cashflow)
            printhere = False
        else:
          cashflow = TE[Compo][CashFlow][y_real] * mutl_tax * inflat**(-y)
        # is the last year year of the project life? The  we need to add the construction cost for the next plant
        TEequi[Compo][CashFlow].append(cashflow)
        if self.CFver < 1 and printhere:
          print "Economics INFO (run):      for global year (y, component year, inflation, cashflow)     : %s, %s, %s, %s" %(y,y_real, inflat**(-y),  cashflow)

  # compute the IRR, NPV or do a NPV search on a multiplier (like the cost)
  # NPV search
  # == == === == == 
  if 'NPV_search' in self.CFparams['Economics']['Global']['Indicator']['attr']['name']:
    # loop over all CashFlows included in NPV
    EL = 0.0 # all contributions that include the multiplier (left hand side of the equation)
    NL = 0.0 # all contributions that do not include the multiplier (right hand side of the equation)
    for CashFlow in self.CFparams['Economics']['Global']['Indicator']['val']: 
      # to which component does this Cash Flow belong?
      for Compo in self.CFcompoList:
        if CashFlow in self.CFparams['Economics'][Compo].keys():
          break
      for y in range(lcm_time+1):
        WACC = (1 + self.CFparams['Economics']['Global']['WACC']['val'])**y
        # sum multiplier true 
        if self.CFparams['Economics'][Compo][CashFlow]['mult_target']['val']:
          EL += TEequi[Compo][CashFlow][y]/WACC 
        # sum multiplier false
        else:
          NL += TEequi[Compo][CashFlow][y]/WACC 
    # THIS COMPUTES THE MULTIPLIER
    self.NPV_mult = (self.CFparams['Economics']['Global']['Indicator']['attr']['target']-NL)/EL
    if self.CFver < 51:
      print "Economics INFO (run): Multiplier : %s"  %self.NPV_mult[0]
    # do a little sanity check
    # => compute FCFF with the found multiplier and recompute NPV
    if self.CFver < 1:
      FCFF = np.zeros(lcm_time + 1)
      for CashFlow in self.CFparams['Economics']['Global']['Indicator']['val']: 
        # to which component does this Cash Flow belong?
        for Compo in self.CFcompoList:
          if CashFlow in self.CFparams['Economics'][Compo].keys():
            break
        for y in range(lcm_time+1):
          if self.CFparams['Economics'][Compo][CashFlow]['mult_target']['val']:
            FCFF[y] += TEequi[Compo][CashFlow][y] * self.NPV_mult[0]
          else:  
            FCFF[y] += TEequi[Compo][CashFlow][y]
      NPV = np.npv(self.CFparams['Economics']['Global']['WACC']['val'], FCFF)
      print "Economics INFO (run): NPV check : %s"  %NPV

  # NPV, IRR
  # == == === == == 
  if 'NPV' in self.CFparams['Economics']['Global']['Indicator']['attr']['name'] or 'IRR' in self.CFparams['Economics']['Global']['Indicator']['attr']['name'] or 'PI' in self.CFparams['Economics']['Global']['Indicator']['attr']['name']:
    # create FCFF_R for every year
    FCFF = np.zeros(lcm_time + 1)
    for CashFlow in self.CFparams['Economics']['Global']['Indicator']['val']: 
      # to which component does this Cash Flow belong?
      for Compo in self.CFcompoList:
        if CashFlow in self.CFparams['Economics'][Compo].keys():
          break
      for y in range(lcm_time+1):
        FCFF[y] += TEequi[Compo][CashFlow][y]
    if self.CFver < 1:
      print "Economics INFO (run): FCFF for each year:"
      print FCFF
    if 'NPV' in  self.CFparams['Economics']['Global']['Indicator']['attr']['name'] or 'PI' in self.CFparams['Economics']['Global']['Indicator']['attr']['name'] :
      self.NPV = np.npv(self.CFparams['Economics']['Global']['WACC']['val'], FCFF)
      if self.CFver < 51:
        print "Economics INFO (run): NPV : %s"  %self.NPV
    if 'IRR' in self.CFparams['Economics']['Global']['Indicator']['attr']['name']:
      try:  # np.irr crushes, when no solution exists..  very bad... this is just a quick workaround.. 
        self.IRR = np.irr(FCFF)
      except:
        self.IRR = -10.0
        print "Economics WARNING (run): The IRR computation failed for some reason. Setting the IRR to -10.0"
      if self.CFver < 51:
        print "Economics INFO (run): IRR : %s"  %self.IRR
    if 'PI' in self.CFparams['Economics']['Global']['Indicator']['attr']['name']:
      self.PI = - self.NPV / FCFF[0]
      if self.CFver < 1:
        print "Economics INFO (run): FCFF[0]: %s" %FCFF[0]
      if self.CFver < 51:
        print "Economics INFO (run): PI : %s"  %self.PI
# =====================================================================================================================
