from data import MappedAst, Symbol

def mapast(ast):
  m = MappedAst()

  for glob in ast:
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

      case _:
        raise NotImplementedError()
  
  return m