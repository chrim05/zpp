from os import getcwd
from os.path import abspath
from sys import argv

def error(msg, pos):
  if pos is None:
    exit(f'error: {msg}')

  line, col, src, _ = pos
  lines = src.split('\n')

  print(f'{repr_pos(pos, use_path=True)}: {msg}')
  print(f'+ {lines[line - 1]}')
  exit(f'+ {" " * (col - 1)}^')

def getabspath(relative_path):
  relative_path = fixpath(relative_path)
  splits = relative_path.split('/')
  result = []

  for i, split in enumerate(splits):
    match split:
      case '.':
        if i == 0:
          result.append(fixpath(getcwd()))

      case '..':
        if i == 0:
          result.extend(fixpath(getcwd()).split('/'))

        result.pop()
      
      case _:
        result.append(split)
  
  return fixpath(abspath('/'.join(result)))

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

def var_is_comptime(name):
  return name[0].isupper()

def string_contains_float(s):
  return '.' in s

def has_to_import_all_ids(ids):
  from data import Node

  return isinstance(ids, Node)

def repr_pos(pos, use_path=False):
  line, col, _, path = pos
  r = f'[line: {line}, col: {col}]'

  if use_path:
    r = f'"{path}" {r}'

  return r

def check_imports(g):
  global cache

  for path_of_imp, ids in g.imports.items():
    has_to_import_all = has_to_import_all_ids(ids)
    imported_module_generator = cache[path_of_imp]

    if has_to_import_all:
      # we check all symbols for collition, because we imported all of them
      ids = [(sym_id, sym_id, ids) for sym_id, _ in imported_module_generator.base_map.symbols.items()]
    
    id_names = list(map(lambda i: i[0], ids))
    id_aliases = list(map(lambda i: i[1], ids))
    all_symbols_of_g = g.get_list_of_all_global_symbol_ids()
    for i, (id_name, id_alias) in enumerate(zip(id_names, id_aliases)):
      if not has_to_import_all and (
        id_aliases.count(id_alias) > 1 or id_names.count(id_name) > 1
      ):
        error(f'id `{id_name}` is imported multiple times', ids[i][2])

      if all_symbols_of_g.count(id_alias) > 1:
        error(f'imported id `{id_alias}` is in conflict with self module ids', ids[i][2])
    
    if has_to_import_all:
      return

    # check if the imported symbol actually exists in imported_module_generator
    for i, id_alias in enumerate(map(lambda i: i[0], ids)):
      if not imported_module_generator.base_map.is_declared(id_alias):
        error(f'id `{id_alias}` is not declared in the imported module', ids[i][2])

def check_imports_of_all_modules():
  global cache

  for _, g in cache.items():
    check_imports(g)

def change_extension_of_path(path, ext):
  return '.'.join(path.split('.')[:-1]) + '.' + ext

def get_filename_from_path(path):
  filename_with_ext = fixpath(path).split('/')[-1]
  return '.'.join(filename_with_ext.split('.')[:-1])

def is_debug_build():
  return '--release' not in argv

def is_release_build():
  return not is_debug_build()
