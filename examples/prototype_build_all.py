import vespidlib

from util import log

log("Creating task . . .")

task = vespidlib.task_create(
  executable_pyscript = open("prototype_build_all_start.py", "r").read(),
  name = "fullbuild_project_main_dev",
  requirements = {"memory": 0, "cores": 0},
  repositories = {"env": {"request": "project_main_dev", "local": True}},
)

log("Waiting for task . . .")

task.wait()

log("Task complete!")
