from data import MappedAst, Node, Symbol
from lex import lex
from parse import parse
from utils import error, fixpath, getabspath

import utils

def mapast(ast_to_map, srcpath):
  m = MappedAst()

  for glob in ast_to_map:
    match glob.kind:
      case 'fn_node':
        m.declare_symbol(
          glob.name.value,
          Symbol('fn_sym', is_imported=False, node=glob),
          glob.pos
        )
      
      case 'type_decl_node':
        m.declare_symbol(
          glob.name.value,
          Symbol('type_sym', is_imported=False, node=glob),
          glob.pos
        )
      
      case 'import_node':
        path = fixpath('/'.join(srcpath.split('/')[:-1]) + '/' + glob.path.value)

        try:
          with open(path, 'r') as f:
            src = f.read()
        except OSError:
          error(f'file not found (`{path}`)', glob.path.pos)
        
        toks = lex(src, path)
        ast = parse(toks)
        mapped_ast = utils.cache[path] = utils.cache[path] if path in utils.cache else mapast(ast, path)

        has_to_import_all = isinstance(glob.ids, Node)
        ids = map(lambda i: i.value, glob.ids) if not has_to_import_all else []

        for i in ids:
          if ids.count(i) > 1:
            error(f'import id `{i}` is dupplicate', mapped_ast[ids.index(i)].pos)

        for name, sym in mapped_ast.symbols.items():
          if has_to_import_all or name in ids:
            m.declare_symbol(
              name,
              Symbol(sym.kind, is_imported=True, node=sym.node),
              glob.ids.pos if has_to_import_all else mapped_ast[ids.index(i)].pos
            )

      case _:
        raise NotImplementedError()
  
  return m