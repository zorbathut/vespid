import importlib

def install_package(package):
  if not importlib.find_loader(package):
    import pip
    pip.main(["install", package])
    
    # reload site paths so we can later import the package
    import site
    importlib.reload(site)

def install():
  install_package("requests")
  install_package("psutil")
  install_package("getpass")

def install_coordinator():
  install()
  install_package("jinja2")
