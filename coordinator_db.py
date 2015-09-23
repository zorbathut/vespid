import copy
import json

from util import log

def repositories_load():
  try:
    with open('COORDINATOR_STATE.repositories.json') as file:
      repos = json.load(file)
      
      # we want to clear out all types to prevent them from being used until a node has re-registered it
      for name, data in repos.items():
        if "type" in data:
          del data["type"]
      
      return repos
      
  except FileNotFoundError:
    return {}

def repositories_save(repos):
  with open('COORDINATOR_STATE.repositories.json', 'w') as file:
    json.dump(repos, file, indent=2, sort_keys=True)

class CoordinatorDB():
  def __init__(self):
    try:
      with open('COORDINATOR_STATE.tasks.json') as file:
        self.tasks = json.load(file)
    except FileNotFoundError:
      self.tasks = {}
    
  def get_task_by_name(self, name):
    if name in self.tasks:
      return copy.deepcopy(self.tasks[name])
    
  def get_tasks_idle(self):
    result = []
    
    for _, task in self.tasks.items():
      if "status" in task:
        continue
      
      result.append(copy.deepcopy(task))
    
    return result
  
  def get_tasks_running_on(self, node):
    result = []
    
    for _, task in self.tasks.items():
      if "status" not in task:
        continue
      if task["status"] != "working":
        continue
      if task["node"] != node:
        continue
      
      result.append(copy.deepcopy(task))
    
    return result
  
  def get_tasks_ordered_by_date(self):
    result = []
    
    for _, task in self.tasks.items():
      result.append(copy.deepcopy(task))
    
    result.sort(key=lambda x: x["time-create"], reverse=True)

    return result
  
  def get_tasknames_by_parent(self, parent):
    result = []
    
    for _, task in self.tasks.items():
      if "parent" in task and task["parent"] == parent:
        result.append(task["name"])
      
    return result
  
  def update_task(self, task):
    self.tasks[task["name"]] = copy.deepcopy(task)
    
    with open('COORDINATOR_STATE.tasks.json', 'w') as file:
      json.dump(self.tasks, file, indent=2, sort_keys=True)
