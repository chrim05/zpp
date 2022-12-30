from posixpath import abspath

def error(msg, pos):
  if pos is None:
    exit(f'error: {msg}')

  line, col, src, path = pos
  lines = src.split('\n')

  print(f'{path} [line: {line}, col: {col}]: {msg}')
  print(f'+ {lines[line - 1]}')
  exit(f'+ {" " * (col - 1)}^')

def getabspath(path):
  return fixpath(abspath(path))

def fixpath(path):
  return path.replace('\\', '/')

def write_instance_content_to(src_instance, target_instance):
  target_instance.__dict__ = src_instance.__dict__

def has_infinite_recursive_layout(realtype, in_progres_struct_rt_ids=[]):
  if not realtype.is_struct():
    return False
  
  if id(realtype) in in_progres_struct_rt_ids:
    return True

  for _, field_realtype in realtype.fields.items():
    if has_infinite_recursive_layout(field_realtype, in_progres_struct_rt_ids + [id(realtype)]):
      return True
  
  return False