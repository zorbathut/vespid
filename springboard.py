import vespiddeps
vespiddeps.install()

import vespidlib
import os
import socket

def task_create(executable_pyscript, requirements, name, name_pretty = None, repositories = None, environment = None, files = {}):
  return vespidlib.task_create(
    executable_pyscript = """
import springboard_launcher

springboard_launcher.go()""",
    name = name + "_springboard",
    name_pretty = name + " Springboard",
    requirements = {
      "memory": 0,  # hack to ensure we start up immediately
      "cores": 0, # hack to ensure we start up immediately
      "usage_require_node_" + socket.gethostname(): True, # must be running on the same computer so we can find the files
    }, 
    repositories = repositories,
    environment = {
      "chaincall": {
        "executable_pyscript": executable_pyscript,
        "requirements": requirements,
        "name": name,
        "name_pretty": name_pretty,
      },
      "files": files,
      "path": os.getcwd(),
    }
  )
  
  