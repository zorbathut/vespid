import time
import sys

def log(*args):
  print(time.asctime(), *args)
  sys.stdout.flush()
