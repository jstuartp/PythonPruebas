
import seiscomp.kernel
import sys

#import seiscomp3.Kernel

class Module(seiscomp.kernel.Module):
  def __init__(self, env):
    #print("SCZABBIX %s" %env)
    seiscomp.kernel.Module.__init__(self, env, env.moduleName(__file__))


  def supportsAliases(self):
    # The default handler does not support aliases
    return True

