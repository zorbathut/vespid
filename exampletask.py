import vespidlib

from util import log

log("Creating task . . .")

task = vespidlib.task_create(
  executable_pyscript = """
import os
import vespidlib

print(os.environ)
print(vespidlib.get_local_environment_info())""", 
  name = "testenv",
  requirements = {"memory": 50, "cores": 1},
  repositories = {"env": {"type": "general_1gb"}},
)

log("Waiting for task . . .")

task.wait()

log("Task complete!")
