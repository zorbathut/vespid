import vespiddeps
vespiddeps.install_coordinator()

from http.server import BaseHTTPRequestHandler, HTTPServer
import time
import json
import copy
import random
import coordinator_db
import coordinator_jinja
import socket
import argparse

from util import log

parser = argparse.ArgumentParser(description='Vespid coordinator.')
parser.add_argument('--port',
  dest='port',
  action='store',
  default=5150,
  help="port to use (default: 5150)")
args = parser.parse_args()

logdir = "//logservername/vespid/logs/"

jinjaenv = coordinator_jinja.environment()

class CoordinatorHandler(BaseHTTPRequestHandler):
  def do_GET(self):
    if self.path == "/favicon.ico" or self.path.startswith("/resources/"):
      try:
        with open(self.path[1:], "rb") as file:
          self.send_response(200)
          self.end_headers()
          self.wfile.write(file.read())
      except FileNotFoundError:
        self.send_response(404)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(bytes("404", "utf-8"))
      
      return
    
    self.send_response(200)
    self.send_header("Content-type", "text/html")
    self.end_headers()
    self.wfile.write(bytes(jinjaenv.get_template("frontpage.html").render(
      nodes = self.server.get_node_view(),
      repos = self.server.get_repository_view(),
      tasks = self.server.get_task_view(),
    ), "utf-8"))

  def do_POST(self):
    if self.path == "/api":
      data = json.loads(self.rfile.read(int(self.headers['Content-Length'])).decode())
      
      data["ip"] = self.client_address[0]
      
      response = self.server.process(data)
      
      self.send_response(200)
      self.send_header("Content-type", "text/html")
      self.end_headers()
      self.wfile.write(bytes(json.dumps(response), "utf-8"))
    else:
      self.send_response(404)
      self.send_header("Content-type", "text/html")
      self.end_headers()
      self.wfile.write(bytes("404", "utf-8"))

class CoordinatorServer(HTTPServer):
  def __init__(self, hostInfo):
    super(HTTPServer, self).__init__(hostInfo, CoordinatorHandler)
    
    self.nodes = {}
    self.repositories = coordinator_db.repositories_load()
    self.tasks = coordinator_db.CoordinatorDB()
  
  def process(self, data):
    if data["command"] == "task-create":
      # basic data validation and standardization - this is not intended to be battle-hardened
      if "name_pretty" not in data:
        data["name_pretty"] = data["name"]
      if "executable_pyscript" not in data and "executable_pyfile" not in data:
        return
      if "requirements" not in data:
        return
      if "memory" not in data["requirements"]:
        return
      if "cores" not in data["requirements"]:
        data["requirements"]["cores"] = 1
      if "repositories" not in data or data["repositories"] is None:
        data["repositories"] = {}
      if "environment" not in data or data["environment"] is None:
        data["environment"] = {}
      if "env" not in data["repositories"] and "repo_env" not in data["environment"]:
        return
      if len(data["repositories"]) > 1:
        return # not yet supported
        
      self.handle_taskcreate(data)
    
    elif data["command"] == "task-info":
      # basic data validation and standardization - this is not intended to be battle-hardened
      if "name" not in data:
        return
        
      return self.handle_taskinfo(data)
    
    elif data["command"] == "node-set":
      # basic data validation and standardization - this is not intended to be battle-hardened
      if "name" not in data:
        return
      if "capabilities" not in data or data["capabilities"] is None:
        data["capabilities"] = {}
      if "repositories" not in data or data["repositories"] is None:
        data["repositories"] = {}
      if "activetasks" not in data or data["activetasks"] is None:
        data["activetasks"] = {}
      
      self.handle_nodeset(data)
      
      return self.update_node(data["name"])
      
    elif data["command"] == "task-complete":
      # basic data validation and standardization - this is not intended to be battle-hardened
      if "name" not in data:
        return
      if "node" not in data:
        return
      if "success" not in data:
        return
      
      self.handle_taskcomplete(data)
      
      return self.update_node(data["node"])
      
    else:
      return

  # Handles the node-set message
  def handle_nodeset(self, data):
    # first, clear the types of all repositories we had before, if we had any before
    # this is crucial because it's possible the node is attempting to shut down some repositories
    # clearing them out here is safe; we don't abort jobs on repo being lost anyway, and if the repo's about to come back, we'll just put it right back
    if data["name"] in self.nodes:
      for reponame in self.nodes[data["name"]]["repositories"]:
        if reponame in self.repositories and "type" in self.repositories[reponame]:
          del self.repositories[reponame]["type"]
    
    # look for any jobs that we believe this node should be running, but isn't
    expectedRunningTasks = self.tasks.get_tasks_running_on(data["name"])
    for runningTask in expectedRunningTasks:
      if runningTask["name"] not in data["activetasks"]:
        # uhoh - a task has vanished. this might be caused by the node crashing; clean it up :(
        runningTask["status"] = "complete"
        runningTask["success"] = "terminated"
        
        self.task_finalize_and_write(runningTask)
    
    # register node data
    # this is a bit overkill since it includes a bunch of stuff we don't care about, but is easier
    # importantly, we *have* to include the repository paths here, so we can shut them down if the node fails to respond in the future
    self.nodes[data["name"]] = data
    
    # register repository data
    for reponame, repodata in data["repositories"].items():
      if reponame not in self.repositories:
        self.repositories[reponame] = {}
      
      self.repositories[reponame]["type"] = repodata["type"]
      self.repositories[reponame]["local"] = repodata["local"]
      self.repositories[reponame]["node"] = data["name"]
    
    coordinator_db.repositories_save(self.repositories)
  
  # Handles the task-create message
  def handle_taskcreate(self, data):
    createdTask = self.tasks.get_task_by_name(data["name"])
    if createdTask is not None:
      # In theory we should compare things here so we can see if it's a valid task replacement. In practice, we're not doing that right now.
      return
    
    data["time-create"] = time.time()
    
    self.tasks.update_task(data)
  
  # Handles the task-info message
  def handle_taskinfo(self, data):
    checkedTask = self.tasks.get_task_by_name(data["name"])
    if checkedTask is None:
      return {
        "command": "task-info-response",
        "name": data["name"],
        "status": "invalid",
      }
    
    checkedTask["command"] = "task-info-response"
    
    return checkedTask
  
  # Handles the task-complete message
  def handle_taskcomplete(self, data):
    completedTask = self.tasks.get_task_by_name(data["name"])
    if completedTask is None:
      return
    
    completedTask["status"] = "complete"
    completedTask["success"] = data["success"]
    
    self.task_finalize_and_write(completedTask)
  
  # note: writes tasks and may open other tasks. save every task before calling this function!
  def task_finalize_and_write(self, task):
    task["time-finish"] = time.time()
    
    self.tasks.update_task(task)
    
    self.task_child_completion_notify(task["name"])
  
  def task_child_completion_notify(self, taskname):
    if self.task_and_children_complete(taskname):
      # there are certainly very clever efficient ways to do this
      # but because we have so few repositories, we just iterate over all repositories
      for reponame, repodata in self.repositories.items():
        if "task" in repodata and repodata["task"] == taskname:
          del repodata["task"]
          # TODO: clean up repository here
      
      coordinator_db.repositories_save(self.repositories)

      # we need to bother with this only if task and children are complete, since if not, the parent's children certainly won't be
      taskdata = self.tasks.get_task_by_name(taskname)
      if "parent" in taskdata and taskdata["parent"]:
        self.task_child_completion_notify(taskdata["parent"])
  
  def task_and_children_complete(self, taskname):
    taskdata = self.tasks.get_task_by_name(taskname)
    if "status" not in taskdata or taskdata["status"] is not "complete":
      return False
    
    children = self.tasks.get_tasknames_by_parent(taskname)
    for child in children:
      if not self.task_and_children_complete(child):
        return False
    
    return True
  
  # Does the per-tick node processing; generally this cancels tasks, starts tasks, and/or reboots the node
  def update_node(self, node):
    # TODO: look for tasks to cancel
    # TODO: test to see if we should reboot the node
    
    taskToStart = None
    taskToStartRepos = None
    
    for task in self.tasks.get_tasks_idle():
      
      # This should be a priority test
      if taskToStart is not None:
        continue;
      
      # Ensure resources are available on this node
      
      # Task can be used; ensure we have the right repos available
      # WARNING - If a task requests more than one repository of the same type, it could in theory acquire the same repo twice
      # This takes a little work to avoid and is why we currently don't permit more than one repo request
      chosenRepos = {}
      for requestRepoName, requestRepoData in task["repositories"].items():
        if "request" in requestRepoData:
          # Requesting an entire new repo
          repoOptions = []
          for reponame, repodata in self.repositories.items():
            if "task" in repodata:
              # repo is currently being used
              continue
            
            if "type" not in repodata:
              # repo is currently not available
              continue
            
            if repodata["type"] != requestRepoData["request"]:
              # repo is of the wrong kind
              continue
            
            if "local" in requestRepoData and repodata["node"] != node:
              # repo request is for a local repo, and this isn't one
              continue
              
            # success! this repo can be used
            repoOptions.append(reponame)
          
          if not repoOptions:
            # no repo available, abort
            chosenRepos = None
            break
          
          chosenRepos[requestRepoName] = random.choice(repoOptions)
        elif "local" in requestRepoData:
          # Merely verifying that an already-claimed repo is local
          if ("repo_" + requestRepoName) not in task["environment"]:
            # no such repo even exists, this is confusing ;.;
            chosenRepos = None
            break
          
          reponame = task["environment"]["repo_" + requestRepoName]
          if reponame in self.repositories and self.repositories[reponame]["node"] != node:
            # repo mismatch, abort
            chosenRepos = None
            break
      
      if chosenRepos is None:
        # couldn't find a repo :(
        continue
      
      taskToStart = task
      taskToStartRepos = chosenRepos
    
    if taskToStart is not None:
      # We are actually starting!

      # Lock repos, add to environment
      for envname, reponame in taskToStartRepos.items():
        self.repositories[reponame]["task"] = taskToStart["name"]
        taskToStart["environment"]["repo_" + envname] = reponame
      
      taskToStart["node"] = node
      taskToStart["status"] = "working"
      taskToStart["time-start"] = time.time()
      taskToStart["log"] = logdir + taskToStart["name"] + ".log"
      
      self.tasks.update_task(taskToStart)
      coordinator_db.repositories_save(self.repositories)
      
      startCommand = {
        "command": "task-run",
        "name": taskToStart["name"],
        "path": taskToStart["environment"]["repo_env"],
        "log": taskToStart["log"],
      }
      
      if "executable_pyscript" in taskToStart:
        startCommand["executable_pyscript"] = taskToStart["executable_pyscript"]
      if "executable_pyfile" in taskToStart:
        startCommand["executable_pyfile"] = taskToStart["executable_pyfile"]
      
      return startCommand
      
  def get_node_view(self):
    result = []
    
    for _, node in self.nodes.items():
      nodeclone = copy.deepcopy(node)
      
      nodeclone["rawdata"] = json.dumps(nodeclone, indent=1, sort_keys=True)
      
      # add up utilization and tasklist for nodes
      
      nodeclone["utilization"] = {}
      nodeclone["tasklist"] = []
      
      for task in self.tasks.get_tasks_running_on(node["name"]):
        nodeclone["tasklist"].append(task["name"])
        for reqname, reqamount in task["requirements"].items():
          if not reqname.startswith("usage_"):
            nodeclone["utilization"][reqname] = nodeclone["utilization"].get(reqname, 0) + reqamount
      
      utilization = 0
      
      for capname, capamount in nodeclone["capabilities"].items():
        if not capname.startswith("usage_"):
          # if we haven't counted up utilization then the member may not exist at all; initialize it to 0
          if capname not in nodeclone["utilization"]:
            nodeclone["utilization"][capname] = 0
            
          thisutil = nodeclone["utilization"][capname] / capamount
          utilization = max(utilization, thisutil)
          #nodeclone["utilization"][capname + "_pct"] = thisutil  # not using this right now, but maybe in the future?

      nodeclone["utilization_total"] = utilization
      nodeclone["tasklist"].sort()
      
      result.append(nodeclone)
    
    result.sort(key = lambda x: x["name"])
    
    return result
    
  def get_repository_view(self):
    result = []
    
    for name, repo in self.repositories.items():
      item = copy.deepcopy(repo)
      
      item["name"] = name
      
      item["rawdata"] = json.dumps(item, indent=1, sort_keys=True)
      
      result.append(item)
    
    result.sort(key = lambda x: x["name"])
    
    return result
    
  def get_task_view(self):
    result = self.tasks.get_tasks_ordered_by_date()
    
    for task in result:
      task["rawdata"] = json.dumps(task, indent=1, sort_keys=True)
      
      task["repoview"] = {}
      
      if "status" not in task:
        for key, value in task["repositories"].items():
          if "request" in value:
            task["repoview"][key] = "requesting " + value["request"] + ("local" in value and " (local)" or "")
      else:
        for key, value in task["environment"].items():
          if key.startswith("env_"):
            envname = key[len("env_"):]
            task["repoview"][envname] = value + ((envname not in task["repositories"] or "request" not in task["repositories"]["request"]) and " (inherited)" or "") + (envname in task["repositories"] and "local" in task["repositories"]["request"] and " (inherited)" or "")
      
      if "success" in task:
        if task["success"] == "terminated":
          task["success"] = "term"
        elif task["success"] == "warning":
          task["success"] = "warn"
    
    return result
    
myServer = CoordinatorServer((socket.gethostname(), int(args.port)))
log("Server start")

try:
  myServer.serve_forever()
except:
  pass

myServer.server_close()
log("Server terminate")
