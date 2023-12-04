
import os
import sys
# run the Cash Flow plugin as stand alone code
os.system('python  ../teal_standalone.py -iXML Cash_Flow_input_NPV.xml -iINP VarInp.txt -o out.out')

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
#    <classesTested>Models.ExternalModel.TEAL.CashFlow</classesTested>
#    <revisions>
#      <revision author="alfoa" date="2019-11-25">Added classTested node</revision>
#      <revision author="alfoa" date="2023-12-04">Reactivated test to test fix of issue #79</revision>
#    </revisions>
#    <requirements>CF-EA-5</requirements>
#  </TestInfo>
