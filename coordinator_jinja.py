import jinja2
import datetime
import html

def environment():
  jinjaenv = jinja2.Environment(
    autoescape = True,
    loader = jinja2.FileSystemLoader("templates"),
    extensions = ["jinja2.ext.autoescape"])
    
  def jinja_format_datetime(value, format='standard'):
    if value is None:
      return ""
    if format == 'standard':
      format = "%Y-%m-%d %H:%M:%S"
    return datetime.datetime.fromtimestamp(value).strftime(format)

  def jinja_format_duration(value):
    value = int(value)
    if value < 60:
      return "{}s".format(int(value))
    elif value < 60 * 60:
      return "{}m {}s".format(int(value / 60), int(value % 60))
    elif value < 60 * 60 * 24:
      return "{}h {}m {}s".format(int(value / 60 / 60), int(value / 60 % 60), int(value % 60))
    else:
      return "{}d {}h {}m {}s".format(int(value / 60 / 60 / 24), int(value / 60 / 60 % 24), int(value / 60 % 60), int(value % 60))
    
  def jinja_format_jsonformat(value):
    accumulator = ""
    cdepth = 0
    for line in value.split('\n'):
      stripped = line.lstrip()
      ddepth = len(line) - len(stripped)
      while cdepth < ddepth:
        cdepth = cdepth + 1
        accumulator = accumulator + "<div>"
      while cdepth > ddepth:
        cdepth = cdepth - 1
        accumulator = accumulator + "</div>"
      accumulator = accumulator + "<div>" + html.escape(stripped) + "</div>"
    
    while cdepth > 0:
      cdepth = cdepth - 1
      accumulator = accumulator + "</div>"
    return accumulator

  jinjaenv.filters['datetime'] = jinja_format_datetime
  jinjaenv.filters['duration'] = jinja_format_duration
  jinjaenv.filters['jsonformat'] = jinja_format_jsonformat
  
  return jinjaenv
