
# Copyright 2020, Battelle Energy Alliance, LLC
# ALL RIGHTS RESERVED
"""
  Constructs documentation files for HERON.
"""
import os
import sys

teal_path = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
build_path = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'build'))
src_path = os.path.abspath(os.path.join(build_path, '..', 'src'))

sys.path.append(teal_path)
try:
  from ravenframework.util import InputData
except ModuleNotFoundError:
  frameworkPath = os.path.join(teal_path, '..', 'ravenframework')
  if os.path.exists(frameworkPath):
    sys.path.append(os.path.dirname(frameworkPath))
  else:
    from HERON.src import _utils as hutils
    frameworkPath = hutils.get_raven_loc()
    sys.path.append(frameworkPath)
  from ravenframework.utils import InputData
from TEAL.src import CashFlows

specs_to_load = {'CashFlows': ['GlobalSettings', 'Component']
}

# Introductory sections from the .tex file #####

def read(texname):
  """
    A function to read the .tex file
    @ In, texname, str, LaTeX file name
    @ Out, filler_text, str, tex contents
  """
  with open(texname, 'r') as fd:
    filler_text = fd.read()
  return filler_text

def create(module, contents):
  """
    A function to create the .tex file by
    enquiring the methods in raven.
    @ In, module, str, name of module to get specs from
    @ In, contents, list(str), list of objects to inquire
    @ Out, None
  """
  out_name = '{}.tex'.format(module)
  intro_name = '{}_intro.tex'.format(module)
  intro_file = os.path.join(src_path, intro_name)
  if os.path.isfile(intro_file):
    intro = read(intro_file)
  else:
    intro = ''
  to_write = '\\section{{{name}}}'.format(name=module)
  to_write += intro
  to_write += '\n' * 2
  mod = getattr(sys.modules[__name__], module)
  for entry in contents:
    tex = getattr(mod, entry).getInputSpecs()().generateLatex() #double parenthesis means the function is used as an object
    to_write += tex + '\n' * 2
  with open(os.path.join(build_path, out_name), 'w') as f:
    f.writelines(to_write)

###create the tex files using the members in the list_of_files
for module_name, objects_list in specs_to_load.items():
  create(module_name, objects_list)
