import subprocess
import vespidlib
import os

from util import log

log(os.getcwd())

log("Syncing p4 . . .")

subprocess.call(["p4", "sync"])

log("Starting task . . .")

task = vespidlib.task_create(
  executable_pyfile = "scripts/vespid/build_all.py",
  name = "buildall",
  requirements = {"memory": 2000, "cores": 8},
  repositories = {"env": {"local": True}}
)

log(task)

log("Waiting for task . . .")

task.wait()

log("Task complete!")
