import subprocess
import time
import sys

from util import log

while True:
  subprocess.call(["c:/python34/python.exe", "node.py"] + sys.argv[1:])
  
  log("Watchdog pausing until next startup . . .")
  time.sleep(5)
