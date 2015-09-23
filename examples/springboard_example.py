import vespidlib
import springboard

from util import log

log("Creating task . . .")

task = springboard.task_create(
  executable_pyscript = """
import os

print(os.environ)

print(open("protocol.txt", "r").read())
""", 
  name = "testenv",
  requirements = {'memory': 50, 'cores': 1},
  repositories = {"env": {"type": "general_1gb"}},
  files = {
    "*": ""
  }
)

log("Waiting for task . . .")

task.wait()

log("Task complete!")
