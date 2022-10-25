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
  utilities for use within TEAL

"""
import xml.etree.ElementTree as ET
from os import path

def get_raven_loc():
  """
    Return RAVEN location
    hopefully this is read from TEAL/.ravenconfig.xml
    @ In, None
    @ Out, loc, string, absolute location of RAVEN
  """
  config = path.abspath(path.join(path.dirname(__file__),'..','.ravenconfig.xml'))
  if not path.isfile(config):
    raise IOError(
        f'HERON config file not found at "{config}"! Has HERON been installed as a plugin in a RAVEN installation?'
    )
  loc = ET.parse(config).getroot().find('FrameworkLocation')
  assert loc is not None and loc.text is not None
  # The addition of ravenframework as an installable package requires
  # adding the raven directory to the PYTHONPATH instead of adding
  # ravenframework. We will expect '.ravenconfig.xml' to point to
  # raven/ravenframework always, so this is why we grab the parent dir.
  return path.abspath(path.dirname(loc.text))
