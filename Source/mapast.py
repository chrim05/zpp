from data import MappedAst, Node, Symbol
from lex import lex
from parse import parse
from utils import error, fixpath, getabspath, var_is_comptime, get_full_path_from_brother_file

import utils

def cache_mapast(path, ast):
  from gen import Generator

  path = getabspath(path)

  if path not in utils.cache:
    g = Generator(None, None, None)
    m, import_nodes, test_nodes = mapast_except_imports(ast, g)
    paths = list(map(
      lambda import_node: get_full_path_from_brother_file(path, import_node.path.value),
      import_nodes
    ))

    for i, p in enumerate(paths):
      if paths.count(p) > 1:
        error('dupplicate import', import_nodes[i].path.pos)

    imports = {
      paths[i]: ([
        (id.name.value, id.alias.value, id.pos) for id in import_node.ids
      ] if isinstance(import_node.ids, list) else import_node.ids) for i, import_node in enumerate(import_nodes)
    }

    g.maps, g.imports, g.path, g.tests = [m], imports, path, test_nodes
    utils.cache[path] = g
    mapast_imports(import_nodes, path)
  
  return utils.cache[path]

def mapast_except_imports(ast_to_map, generator):
  m = MappedAst()
  import_nodes = []
  test_nodes = []

  for glob in ast_to_map:
    match glob.kind:
      case 'fn_node':
        m.declare_symbol(
          glob.name.value,
          Symbol('fn_sym', node=glob, generator=generator),
          glob.pos
        )
      
      case 'type_decl_node':
        m.declare_symbol(
          glob.name.value,
          Symbol('type_sym' if len(glob.generics) == 0 else 'generic_type_sym', node=glob, generator=generator),
          glob.pos
        )
      
      case 'var_decl_node':
        is_comptime = var_is_comptime(glob.name.value)
        m.declare_symbol(
          glob.name.value,
          Symbol('global_var_sym', is_comptime=is_comptime, node=glob, generator=generator),
          glob.pos
        )
      
      case 'import_node':
        import_nodes.append(glob)
      
      case 'test_node':
        test_nodes.append(glob)
      
      case _:
        raise NotImplementedError()
  
  return m, import_nodes, test_nodes

def mapast_imports(import_nodes, srcpath):
  for glob in import_nodes:
    path = get_full_path_from_brother_file(srcpath, glob.path.value)

    if path in utils.cache:
      continue

    try:
      with open(path, 'r') as f:
        src = f.read()
    except OSError:
      error(f'file not found (`{path}`)', glob.path.pos)
    
    toks = lex(src, path)
    ast = parse(toks)
    g = cache_mapast(path, ast)

    gen_and_cache_module_setupper(g)

def gen_and_cache_module_setupper(g):
  utils.modules_setupper_llvm_fns.append(
    g.gen_module_setuper_fn()
  )
