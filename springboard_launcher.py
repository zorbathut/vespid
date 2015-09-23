import vespidlib
import glob
import os
import shutil

from util import log

def go():
  env = vespidlib.get_local_environment_info()["environment"]
    
  for match, destination in env["files"].items():
    for filename in glob.glob(os.path.join(env["path"], match)):
      full_filename = os.path.join(env["path"], filename)
      base_filename = os.path.basename(filename)
      if os.path.isfile(full_filename):
        shutil.copy2(full_filename, os.getcwd() + "/" + destination + "/" + base_filename)
      elif os.path.isdir(full_filename):
        shutil.copytree(full_filename, os.getcwd() + "/" + destination + "/" + base_filename)
  
  log(env["chaincall"])
  
  print(env["chaincall"])
  vespidlib.task_create(**env["chaincall"]).wait()
  