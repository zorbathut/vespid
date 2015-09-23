import vespiddeps
vespiddeps.install()

import vespidlib
import time
import tempfile
import subprocess
import os
import socket
import psutil
import copy
import getpass
import json
import argparse

from util import log

parser = argparse.ArgumentParser(description='Vespid computation node.')
parser.add_argument('--nodename',
  dest='nodename',
  action='store',
  default=socket.gethostname(),
  help="node name to use (default: this computer's hostname)")
args = parser.parse_args()

# name to identify this node
nodename = args.nodename

# assemble the basic nodeSet prototype
def assemble_node_prototype():
  nodeproto = None
  try:
    with open('nodeconfig/' + nodename + '.conf.json') as file:
      nodeproto = json.load(file)
  except FileNotFoundError:
    with open('nodeconfig/default.conf.json') as file:
      nodeproto = json.load(file)
  
  nodeproto["command"] = "node-set"
  nodeproto["name"] = nodename
  if "capabilities" not in nodeproto:
    nodeproto["capabilities"] = {}
  nodeproto["capabilities"]["usage_node_" + nodename] = True
  nodeproto["capabilities"]["usage_user_" + getpass.getuser()] = True
  
  return nodeproto

nodeproto = assemble_node_prototype()

if "coordinator" in nodeproto:
  vespidlib.set_global_coordinator(nodeproto["coordinator"])

nodePyTimestamp = os.path.getmtime("node.py")

class VespidNode():
  def ServeForever(self):
    tasks = {}
    shutdown = False
    
    while True:
      # check if we should be shutting down for reboot
      if not shutdown and nodePyTimestamp != os.path.getmtime("node.py"):
        log("Beginning graceful shutdown to update node.py . . .")
        shutdown = True
      
      if shutdown and not tasks:
        log("All tasks finished, shutting down!")
        break
      
      # Command that came back from the coordinator
      command = None
      
      # check our tasks first
      for name, process in tasks.items():
        if process.poll() is not None:
          log("Completed task", name)
          command = vespidlib.send_request({
            "command": "task-complete",
            "name": name,
            "node": nodename,
            "success": process.returncode == 0 and "ok" or "fatal",
          })
          
          del tasks[name]
          break  # can't continue iteration anyway, so let's drop out
      
      # if we either had no finished tasks, or we had no commands, we can go ahead and update our node info
      if command is None:
        activetasks = {}
        for name, _ in tasks.items():
          activetasks[name] = True
        
        # update nodeproto as appropriate
        nodeproto["activetasks"] = activetasks
        nodeproto["capabilities"]["memory"] = shutdown and 0 or psutil.virtual_memory().total / (1024 * 1024)
        nodeproto["capabilities"]["cores"] = shutdown and 0 or psutil.cpu_count()
        
        command = vespidlib.send_request(nodeproto)
      
      if command is not None:
        log(command)
        if command["command"] == "task-run":
          # Copy environment, add vespid_task, and add appropriate keys so we have access to vespidlib
          cwd = None
          environment = {}
          
          # note: os.environ is a custom class that is not a normal dict, so we're doing it this way for safety
          for key, value in os.environ.items():
            environment[key] = value
          
          environment["VESPID_TASK"] = command["name"]
          environment["VESPID_COORDINATOR"] = vespidlib.get_global_coordinator()
          
          if "PYTHONPATH" in environment:
            environment["PYTHONPATH"] = environment["PYTHONPATH"] + os.pathsep + os.getcwd()
          else:
            environment["PYTHONPATH"] = os.getcwd()
          
          logdest = open(command["log"], 'w')
          
          scriptfileName = None
          
          if "executable_pyscript" in command:
            with tempfile.NamedTemporaryFile(prefix = "vespid_" + command["name"], suffix = ".py", delete = False) as scriptfile:
              scriptfile.write(bytes(command["executable_pyscript"], "UTF-8"))
              scriptfileName = scriptfile.name
          elif "executable_pyfile" in command:
            scriptfileName = command["executable_pyfile"]
            #environment["PYTHONPATH"] = environment["PYTHONPATH"] + os.pathsep + command["path"] + "/" + os.path.dirname(command["executable_pyfile"])
          
          path = command["path"]
          if "repositories" in nodeproto:
            for repoid, repodata in nodeproto["repositories"].items():
              if path == repoid:
                path = repodata["local"]
          
          tasks[command["name"]] = subprocess.Popen(
            args = ["c:/python34/python.exe", scriptfileName],
            cwd = path,
            env = environment,
            stdout = logdest,
            stderr = logdest,
          )
      else:
        # if we had a command, we want to loop again immediately in case we have another waiting; otherwise we can just sleep for a little bit
        time.sleep(5)

vespidNode = VespidNode()
log("Node start")

vespidNode.ServeForever()

log("Node terminate")
