import numpy as np

# AMORTAZIATION SCHEMES


MACRS = {15: 0.01 * np.array([5.0, 9.5, 8.55, 7.7, 6.93, 6.23, 5.9, 5.9, 5.91, 5.9, 5.91, 5.9, 5.91, 5.9, 5.91, 2.95]),
          7: 0.01 * np.array([14.29, 24.49, 17.49, 12.49, 8.93, 8.92, 8.93, 4.46])}

def amortize(scheme, plan, start_value, component_life):
  alpha = np.zeros(component_life + 1, dtype=float)
  lscheme = scheme.lower()
  if lscheme == 'macrs':
    ys = plan[0]
    pcts = MACRS.get(ys, None)
    if pcts is None:
      raise NotImplementedError('MACRS "{}" not yet added to library; it should be easy to add.'.format(ys))
    alpha[1:len(pcts)+1] = pcts * start_value
  elif lscheme == 'custom':
    alpha[1:len(plan)+1] = np.asarray(plan)/100. * start_value
  else:
    raise NotImplementedError('Amortization scheme "{}" not yet implemented.'.format(scheme))
  return alpha
