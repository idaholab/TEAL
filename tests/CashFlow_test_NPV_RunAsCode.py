
import os
import sys

#Check if path needed to be setup
try:
  import TEAL
except ModuleNotFoundError:
  sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
  import TEAL

# run the Cash Flow plugin as stand alone code
from TEAL.src import CashFlow_ExtMod
sys.argv = [sys.argv[0],"-iXML","Cash_Flow_input_NPV.xml","-iINP","VarInp.txt","-o","out.out"]
CashFlow_ExtMod.tealMain()

# read out.out and compare with gold
last = None
with open("out.out") as out:
  for l in out:
    if len(l.strip()) > 0:
        last = l

gold = float(last)
if (gold - 630614140.519) < 0.01:
  sys.exit(0)
else:
  sys.exit(1)

#  <TestInfo>
#    <name>CashFlow_test_PI</name>
#    <author>A. Epiney</author>
#    <created>2017-10-25</created>
#    <description>
#      This input tests the RAVEN plugin CashFlow in standalone mode.
#    </description>
#    <classesTested>Models.ExternalModel.CashFlow</classesTested>
#    <revisions>
#      <revision author="alfoa" date="2019-11-25">Added classTested node</revision>
#    </revisions>
#    <requirements>CF-EA-5</requirements>
#  </TestInfo>
