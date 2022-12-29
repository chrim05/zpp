from data import MappedAst, Node, Symbol
from lex import lex
from parse import parse
from utils import error, fixpath, getabspath

import utils

def cache_mapast(path, ast):
  if path not in utils.cache:
    m, import_nodes = mapast_except_imports(ast)
    utils.cache[path] = m
    mapast_imports(m, import_nodes, path)
  
  return utils.cache[path]

def mapast_except_imports(ast_to_map):
  m = MappedAst()
  import_nodes = []

  for glob in ast_to_map:
    match glob.kind:
      case 'fn_node':
        m.declare_symbol(
          glob.name.value,
          Symbol('fn_sym', node=glob),
          glob.pos
        )
      
      case 'type_decl_node':
        m.declare_symbol(
          glob.name.value,
          Symbol('type_sym', node=glob),
          glob.pos
        )
      
      case 'import_node':
        import_nodes.append(glob)
      
      case _:
        raise NotImplementedError()
  
  return m, import_nodes

def mapast_imports(m, import_nodes, srcpath):
  for glob in import_nodes:
    path = fixpath('/'.join(srcpath.split('/')[:-1]) + '/' + glob.path.value)

    if path in utils.cache:
      continue

    try:
      with open(path, 'r') as f:
        src = f.read()
    except OSError:
      error(f'file not found (`{path}`)', glob.path.pos)
    
    toks = lex(src, path)
    ast = parse(toks)
    mapped_ast = cache_mapast(path, ast)

    for name, sym in mapped_ast.symbols.items():
      m.declare_symbol(
        name,
        Symbol(sym.kind, node=sym.node),
        glob.pos
      )
