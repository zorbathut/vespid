import vespiddeps
vespiddeps.install()

import json
import requests
import time
import os
import copy
import uuid
import getpass

from util import log

coordinator_default = "vespid-coordinator:5150"

coordinator = None
coordinator_url = None

def set_global_coordinator(coord, silent = False):
  global coordinator, coordinator_url
  coordinator = coord
  coordinator_url = "http://{}/api".format(coord)
  if not silent:
    log("Vespid coordinator URL set to", coordinator_url)

def get_global_coordinator():
  return coordinator
  
if "VESPID_COORDINATOR" in os.environ:
  set_global_coordinator(os.environ["VESPID_COORDINATOR"])
else:
  set_global_coordinator(coordinator_default, silent = True)

def send_request(data):
  while True:
    try:
      r = requests.post(coordinator_url, data=json.dumps(data))
      
      if r.status_code == 200:
        return r.json()
      else:
        log("Received status code ", r.status_code)
    except requests.exceptions.RequestException as e:
      log(e)
    
    log("Retrying in 5 seconds . . .")
    time.sleep(5)

local_env_info = None
local_env_info_acquired = False
def get_local_environment_info():
  global local_env_info
  global local_env_info_acquired
  
  if local_env_info_acquired:
    return copy.deepcopy(local_env_info)
  
  if "VESPID_TASK" not in os.environ:
    # we are not in a vespid task, return nothing
    local_env_info_acquired = True
    return None
  
  local_env_info = task_info(os.environ["VESPID_TASK"])
  local_env_info_acquired = True
  
  return copy.deepcopy(local_env_info)

class Task():
  def __init__(self, id):
    self.id = id
    self.lastChecked = 0
  
  def poll(self):
    if hasattr(self, "returncode"):
      return self.returncode
    
    sleeplen = self.lastChecked - time.time() + 5
    if sleeplen > 0:
      time.sleep(sleeplen)
    
    result = task_info(self.id)
    if "status" in result and result["status"] == "complete":
      self.returncode = result["success"]
      return self.returncode
    
    return None
    
  def wait(self):
    while True:
      result = self.poll()
      if result:
        return result
  
  def __str__(self):
    return self.id

# it is generally expected that you call this with named parameters
# returns a handle to the created class
def task_create(requirements, name, name_pretty = None, repositories = None, environment = None, executable_pyscript = None, executable_pyfile = None):
  if name_pretty is None:
    name_pretty = name

  # make a unique name
  name = name + "_" + str(round(time.time())) + "_" + str(uuid.uuid4())
  
  # get our local environment, and set up a bare skeleton if we don't have a local environment
  local_env = get_local_environment_info()
  if local_env is None:
    local_env = {
      "name": None,
      "environment": { },
      "requirements": { },
    }
  
  # Include all environment values that weren't overridden
  if environment is None:
    environment = {}
  else:
    environment = copy.copy(environment) # don't want to change the value passed in
  for env, value in local_env["environment"].items():
    if env not in environment:
      environment[env] = value

  # Include all requirement usage flags; other requirement elements shouldn't be propogated
  requirements = copy.copy(requirements)
  for env, value in local_env["requirements"].items():
    if env.startswith("usage_") and env not in requirements:
      requirements[env] = value
  
  # If we don't have a parent or an attached user, attach whatever user we have right now
  needs_owner = local_env["name"] is None
  for env, value in requirements.items():
    if env.startswith("usage_user_"):
      needs_owner = False
  if needs_owner:
    requirements["usage_user_" + getpass.getuser()] = True
  
  request = {
    "command": "task-create",
    "environment": environment,
    "name": name,
    "name_pretty": name_pretty,
    "parent": local_env["name"],
    "repositories": repositories,
    "requirements": requirements,
  }
  
  if executable_pyscript is not None:
    request["executable_pyscript"] = executable_pyscript
  if executable_pyfile is not None:
    request["executable_pyfile"] = executable_pyfile
    
  send_request(request)
  
  return Task(name)

def task_info(name):
  return send_request({
    "command": "task-info",
    "name": name,
  })
