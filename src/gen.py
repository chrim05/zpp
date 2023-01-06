from copy import copy
from sys import argv
from data import ComparatorDict, MappedAst, Node, Proto, RealData, RealType, Symbol
from mapast import get_full_path_from_brother_file
from utils import error, has_infinite_recursive_layout, has_to_import_all_ids, is_debug_build, is_release_build, repr_pos, string_contains_float, var_is_comptime, write_instance_content_to
import llvmlite.ir as ll

import utils

REALTYPE_PLACEHOLDER = RealType('placeholder_rt')

CSTRING_REALTYPE = RealType('ptr_rt', is_mut=False, type=RealType('u8_rt'))

STRING_REALTYPE = RealType('struct_rt', aka='String', fields={
  'ptr': CSTRING_REALTYPE,
  'len': RealType('u64_rt')
})

BUILTINS_TABLE = {
  'i8': RealType('i8_rt'),
  'i16': RealType('i16_rt'),
  'i32': RealType('i32_rt'),
  'i64': RealType('i64_rt'),

  'u8': RealType('u8_rt'),
  'u16': RealType('u16_rt'),
  'u32': RealType('u32_rt'),
  'u64': RealType('u64_rt'),

  'f32': RealType('f32_rt'),
  'f64': RealType('f64_rt'),

  'void': RealType('void_rt')
}

class Generator:
  def __init__(self, map, imports, path):
    self.path = path
    self.maps = [map]
    self.imports = imports
    self.output = utils.output
    self.libs_to_import = utils.libs_to_import
    self.llvm_internal_functions_cache = utils.llvm_internal_functions_cache
    self.strings = utils.strings_cache
    self.llvm_internal_vars_cache = utils.llvm_internal_vars_cache
    self.fn_in_evaluation = ComparatorDict()
    self.fn_evaluated = ComparatorDict()
    self.global_evaluated = []
    self.namedtypes_in_evaluation = ComparatorDict()
    self.llvm_builders = [] # the last one is the builder in use
    self.ctx_types = []
    self.loops = []
    self.tmp_counter = 0
    self.str_counter = 0
    self.internal_vars = 0
    self.defer_stmts = []
  
  @property
  def defer_nodes(self):
    return self.defer_stmts[-1]

  @defer_nodes.setter
  def defer_nodes(self, value):
    self.defer_stmts[-1] = value
  
  @property
  def base_map(self) -> MappedAst:
    return self.maps[0]

  @property
  def map(self) -> MappedAst:
    return self.maps[-1]

  @property
  def cur_fn(self):
    return list(self.fn_in_evaluation.values())[-1]
  
  @property
  def ctx(self):
    return self.ctx_types[-1]
  
  @property
  def allocas_builder(self) -> ll.IRBuilder:
    return self.cur_fn[2]

  @property
  def cur_builder(self) -> ll.IRBuilder:
    return self.llvm_builders[-1]
  
  @cur_builder.setter
  def cur_builder(self, new_builder):
    self.llvm_builders[-1] = new_builder
  
  @property
  def loop(self):
    return self.loops[-1]
  
  @property
  def inside_loop(self):
    return len(self.loop) > 0
  
  def get_symbol(self, id, pos):
    for path_of_imp, ids in self.imports.items():
      # when all symbols are imported
      if has_to_import_all_ids(ids):
        if not utils.cache[path_of_imp].base_map.is_declared(id):
          continue
        
        return utils.cache[path_of_imp].base_map.get_symbol(id, pos)

      # mapping ids to their aliases
      if id in (id_aliases := list(map(lambda i: i[1], ids))):
        real_id = list(map(lambda i: i[0], ids))[id_aliases.index(id)]
        return utils.cache[path_of_imp].base_map.get_symbol(real_id, pos)

    return self.map.get_symbol(id, pos)

  def declare_symbol(self, id, sym, pos):
    for path_of_imp, ids in self.imports.items():
      # when all symbols are imported
      if has_to_import_all_ids(ids):
        if utils.cache[path_of_imp].base_map.is_declared(id):
          error(f'id `{id}` already declared (from import at {repr_pos(ids.pos)})', pos)

        continue

      # mapping ids to their aliases
      if id in (id_aliases := list(map(lambda i: i[1], ids))):
        pos = ids[id_aliases.index(id)][2]
        error(f'id `{id}` already declared (from import at {repr_pos(pos)})', pos)

    self.map.declare_symbol(id, sym, pos)
  
  def is_declared(self, id):
    for path_of_imp, ids in self.imports.items():
      # when all symbols are imported
      if has_to_import_all_ids(ids):
        if utils.cache[path_of_imp].base_map.is_declared(id):
          return True
        
        continue

      # mapping ids to their aliases
      if id in map(lambda i: i[1], ids):
        return True

    return self.map.is_declared(id)
  
  def get_list_of_all_global_symbol_ids(self):
    r = list(self.base_map.symbols.keys())

    for path_of_imp, ids in self.imports.items():
      if has_to_import_all_ids(ids):
        r.extend(utils.cache[path_of_imp].base_map.symbols.keys())
        continue
      
      r.extend(map(lambda i: i[1], ids))
    
    return r

  def push_loop(self, loop):
    # loop = (condition_checker_block, exit_block)
    self.loops.append(loop)

  def pop_loop(self):
    self.loops.pop()

  def make_proto(self, kind, **kwargs):
    return Proto(kind, **kwargs)

  def evaluate_builtin_type(self, name):
    try:
      return copy(BUILTINS_TABLE[name])
    except KeyError:
      pass

  def internal_evaluate_named_type(self, type_node, sym):
    if sym.kind == 'generic_type_sym':
      error(f'expected `{len(sym.node.generics)}` generic args, got `0`', type_node.pos)

    check_sym_is_type(type_node, sym)

    key = id(sym)

    if key in self.namedtypes_in_evaluation:
      return self.namedtypes_in_evaluation[key]

    r = self.namedtypes_in_evaluation[key] = RealType('placeholder_rt')
    realtype = self.evaluate_type(sym.node.type, is_top_call=False)
    self.namedtypes_in_evaluation.remove_by_key(key)
    write_instance_content_to(realtype, r)
    r.aka = repr(type_node)

    return r

  def evaluate_named_type(self, type_node):
    sym = self.get_symbol(type_node.value, type_node.pos)

    if sym.kind == 'alias_sym':
      return sym.realtype

    return sym.generator.internal_evaluate_named_type(type_node, sym)
  
  def evaluate_named_generic_type(self, generic_type_node):
    sym = self.get_symbol(generic_type_node.name.value, generic_type_node.pos)
  
    check_sym_is_generic_type(generic_type_node.name, sym)

    if (got := len(generic_type_node.generics)) != (expected := len(sym.node.generics)):
      error(f'expected `{expected}` generic args, got `{got}`', generic_type_node.pos)

    generics_rt = [self.evaluate_type(generic_type_node) for generic_type_node in generic_type_node.generics]
    key = (id(sym), generics_rt)

    if key in self.namedtypes_in_evaluation:
      return self.namedtypes_in_evaluation[key]

    r = self.namedtypes_in_evaluation[key] = RealType('placeholder_rt')

    self.push_scope()
    self.declare_generics(sym.node.generics, generics_rt)

    realtype = self.evaluate_type(sym.node.type, is_top_call=False)

    self.pop_scope()
    
    self.namedtypes_in_evaluation.remove_by_key(key)
    write_instance_content_to(realtype, r)
    r.aka = repr(generic_type_node)

    return r

  def evaluate_type(self, type_node, is_top_call=True, allow_void_type=False, allow_fn_type=False):
    match type_node.kind:
      case 'id':
        t = self.evaluate_builtin_type(type_node.value)
        r = t if t is not None else self.evaluate_named_type(type_node)

        if r.is_void() and not allow_void_type:
          error('type `void` not allowed here', type_node.pos)
      
      case 'generic_type_node':
        r = self.evaluate_named_generic_type(type_node)
      
      case 'ptr_type_node':
        r = RealType('ptr_rt', is_mut=type_node.is_mut, type=self.evaluate_type(type_node.type, is_top_call=False, allow_fn_type=True))
      
      case 'array_type_node':
        length = self.evaluate_node(type_node.length, RealType('u64_rt'))
        self.expect_realdata_is_comptime_value(length, type_node.pos)
        self.expect_realdata_is_integer(length, type_node.pos)
        r = RealType('static_array_rt', length=length.value, type=self.evaluate_type(type_node.type, is_top_call=False))
      
      case 'struct_type_node':
        field_names = list(map(lambda field: field.name.value, type_node.fields))

        for i, field_name in enumerate(field_names):
          if field_names.count(field_name) > 1:
            error(f'field `{field_name}` is dupplicate', type_node.fields[i].name.pos)
        
        r = RealType(
          'struct_rt',
          fields={
            field.name.value: self.evaluate_type(field.type, is_top_call=False) for field in type_node.fields
          }
        )
      
      case 'fn_type_node':
        return RealType(
          'fn_rt',
          arg_types=[self.evaluate_type(arg_type) for arg_type in type_node.arg_types],
          ret_type=self.evaluate_type(type_node.ret_type, allow_void_type=True)
        )
      
      case 'union_type_node':
        return RealType(
          'union_rt',
          fields={
            field.name.value: self.evaluate_type(field.type, is_top_call=False) for field in type_node.fields
          }
        )

      case _:
        raise NotImplementedError()
    
    if is_top_call and has_infinite_recursive_layout(r):
      error('type has infinite recursive layout', type_node.pos)

    return r

  def evaluate_fn_proto(self, fn_node):
    arg_types = [self.evaluate_type(arg.type) for arg in fn_node.args]
    ret_type = self.evaluate_type(fn_node.ret_type, allow_void_type=True)

    return self.make_proto(
      'fn_proto',
      arg_types=arg_types,
      ret_type=ret_type,
      name=fn_node.name.value,
      is_test=hasattr(fn_node, 'is_test') and fn_node.is_test
    )

  def expect(self, cond, error_msg, pos):
    if cond:
      return

    error(error_msg, pos)

  def evaluate_num(self, num_tok, realtype_to_use=None):
    realtype = \
      realtype_to_use \
        if realtype_to_use is not None else \
          self.ctx if self.ctx.is_numeric() else RealType('i32_rt')

    value = (float if realtype.is_float() else int)(num_tok.value)
    
    return RealData(
      realtype,
      value=value,
      llvm_data=ll.Constant(self.convert_realtype_to_llvmtype(realtype), value)
    )

  def evaluate_fnum(self, fnum_tok, realtype_to_use=None):
    realtype = \
      realtype_to_use \
        if realtype_to_use is not None else \
          self.ctx if self.ctx.is_float() else RealType('f32_rt')
    
    if realtype_to_use is not None and string_contains_float(fnum_tok.value) and realtype_to_use.is_int():
      error('unable to coerce float constant expression to int type', fnum_tok.pos)

    value = float(fnum_tok.value)
    
    return RealData(
      realtype,
      value=value,
      llvm_data=ll.Constant(self.convert_realtype_to_llvmtype(realtype), value)
    )

  def evaluate_undefined(self, dd_node):
    realtype = self.ctx

    return RealData(
      realtype,
      value=0,
      llvm_data=ll.Constant(self.convert_realtype_to_llvmtype(realtype), ll.Undefined)
    )

  def evaluate_node(self, node, new_ctx, is_stmt=False, is_top_call=True):
    if new_ctx is not None:
      self.push_ctx(new_ctx)
    
    t = getattr(self, f'evaluate_{node.kind}')(node)

    if new_ctx is not None:
      self.pop_ctx()

    if is_top_call and not is_stmt and t.realtype.is_void():
      error('expression not allowed to be `void`', node.pos)
    
    if is_top_call and t.realtype.kind == 'placeholder_rt':
      error('expression has no clear type here', node.pos)
    
    if is_top_call and t.realtype.is_fn():
      error('expression has no concrete type here', node.pos)

    return t

  def expect_realtype(self, rt1, rt2, pos):
    if rt1 == rt2:
      return
    
    error(f'expected `{rt1}`, found `{rt2}`', pos)

  def evaluate_null(self, null_tok):
    realtype = self.ctx if self.ctx.is_numeric() or self.ctx.is_ptr() else RealType('ptr_rt', is_mut=False, type=RealType('u8_rt'))
    llvm_data = ll.Constant(self.convert_realtype_to_llvmtype(realtype), None)
    
    return RealData(
      realtype,
      value=0,
      llvm_data=llvm_data
    )
  
  def evaluate_global_sym(self, sym):
    key = id(sym)

    if key in self.global_evaluated:
      return

    var_decl_node = sym.node

    self.push_scope()
    realtype = self.evaluate_type(var_decl_node.type)
    realdata = self.evaluate_node(var_decl_node.expr, realtype)
    self.pop_scope()
    
    self.expect_realtype(realtype, realdata.realtype, var_decl_node.expr.pos)
    self.expect_realdata_is_comptime_value(realdata, var_decl_node.expr.pos)

    if sym.is_comptime:
      sym.realdata = realdata
    else:
      glob = ll.GlobalVariable(self.output, self.convert_realtype_to_llvmtype(realtype), self.fixname_for_llvm(var_decl_node.name.value))
      glob.initializer = realdata.llvm_data
      sym.realtype = realtype
      sym.llvm_data = glob

    self.global_evaluated.append(key)

  def evaluate_id(self, id_tok):
    sym = self.get_symbol(id_tok.value, id_tok.pos)

    check_sym_is_local_or_global_var(id_tok, sym)

    if sym.kind == 'global_var_sym':
      sym.generator.push_builder(self.cur_builder)
      sym.generator.evaluate_global_sym(sym)
      sym.generator.pop_builder()

    if sym.is_comptime:
      return sym.realdata
    
    llvm_data = self.llvm_load(self.cur_builder, sym.llvm_data, self.convert_realtype_to_llvmtype(sym.realtype))
    
    return RealData(
      sym.realtype,
      llvm_data=llvm_data
    )
  
  def evaluate_defer_node_stmt(self, defer_node):
    self.defer_nodes.insert(0, defer_node.node)
  
  def generate_llvm_bin_for_int(self, realdata_left, op, realdata_right, realtype_resulting_from_cmp):
    is_signed = realdata_left.realtype.is_signed if realdata_left.realtype.is_numeric() else True
    
    match op.kind:
      case '+': return self.cur_builder.add(realdata_left.llvm_data, realdata_right.llvm_data)
      case '-': return self.cur_builder.sub(realdata_left.llvm_data, realdata_right.llvm_data)
      case '*': return self.cur_builder.mul(realdata_left.llvm_data, realdata_right.llvm_data)
      case '/': return getattr(self.cur_builder, 'sdiv' if is_signed else 'udiv')(realdata_left.llvm_data, realdata_right.llvm_data)
      case '%': return getattr(self.cur_builder, 'srem' if is_signed else 'urem')(realdata_left.llvm_data, realdata_right.llvm_data)

      case '==' | '!=' | '<' | '>' | '<=' | '>=':
        return self.llvm_icmp(
          self.cur_builder,
          is_signed,
          op.kind,
          realdata_left.llvm_data,
          realdata_right.llvm_data,
          self.convert_realtype_to_llvmtype(realtype_resulting_from_cmp)
        )

      case _:
        raise NotImplementedError()
  
  def generate_llvm_bin_for_float(self, realdata_left, op, realdata_right, realtype_resulting_from_cmp):
    match op.kind:
      case '+': return self.cur_builder.fadd(realdata_left.llvm_data, realdata_right.llvm_data)
      case '-': return self.cur_builder.fsub(realdata_left.llvm_data, realdata_right.llvm_data)
      case '*': return self.cur_builder.fmul(realdata_left.llvm_data, realdata_right.llvm_data)
      case '/': return self.cur_builder.fdiv(realdata_left.llvm_data, realdata_right.llvm_data)
      case '%': return self.cur_builder.frem(realdata_left.llvm_data, realdata_right.llvm_data)

      case '==' | '!=' | '<' | '>' | '<=' | '>=':
        return self.llvm_fcmp(
          self.cur_builder,
          op.kind,
          realdata_left.llvm_data,
          realdata_right.llvm_data,
          self.convert_realtype_to_llvmtype(realtype_resulting_from_cmp)
        )

      case _:
        raise NotImplementedError()

  def generate_llvm_bin(self, realdata_left, op, realdata_right, realtype_resulting_from_cmp):
    if realdata_left.realtype.is_float():
      return self.generate_llvm_bin_for_float(realdata_left, op, realdata_right, realtype_resulting_from_cmp)
    
    return self.generate_llvm_bin_for_int(realdata_left, op, realdata_right, realtype_resulting_from_cmp)

  def compute_comptime_bin(self, realdata_left, op, realdata_right):
    match op.kind:
      case '+': return realdata_left.value + realdata_right.value
      case '-': return realdata_left.value - realdata_right.value
      case '*': return realdata_left.value * realdata_right.value
      case '/': return realdata_left.value / realdata_right.value
      case '%': return realdata_left.value % realdata_right.value

      case '==': return int(realdata_left.value == realdata_right.value)
      case '!=': return int(realdata_left.value != realdata_right.value)
      case '<': return int(realdata_left.value < realdata_right.value)
      case '>': return int(realdata_left.value > realdata_right.value)
      case '<=': return int(realdata_left.value <= realdata_right.value)
      case '>=': return int(realdata_left.value >= realdata_right.value)

      case _:
        raise NotImplementedError()
  
  def expect_realtype_are_compatible(self, rt1, rt2, pos):
    if rt1 == rt2:
      return
    
    error(f'types `{rt1}` and `{rt2}` are not compatible', pos)

  def expect_realdata_is_struct_or_union(self, realdata, pos):
    if realdata.realtype.is_struct() or realdata.realtype.is_union():
      return
    
    error(f'expected struct or union expression, got `{realdata.realtype}`', pos)

  def expect_realdata_has_numeric_value(self, realdata, pos):
    if realdata.has_numeric_value():
      return
    
    error(f'expected comptime value to have numeric type', pos)

  def expect_realdata_is_numeric(self, realdata, pos):
    if realdata.realtype.is_numeric():
      return
    
    error(f'expected numeric expression, got `{realdata.realtype}`', pos)

  def expect_realdata_is_numeric_or_ptr(self, realdata, pos):
    if realdata.realtype.is_numeric() or realdata.realtype.is_ptr():
      return
    
    error(f'expected numeric or ptr expression, got `{realdata.realtype}`', pos)

  def expect_realdata_is_indexable(self, realdata, pos):
    if realdata.realtype.is_ptr() or realdata.realtype.is_static_array():
      return
    
    error(f'expected indexable expression, got `{realdata.realtype}`', pos)

  def expect_realdata_is_comptime_value(self, realdata, pos):
    if realdata.is_comptime_value():
      return
    
    error(f'expected comptime expression', pos)

  def expect_realdata_is_integer(self, realdata, pos):
    if realdata.realtype.is_int():
      return
    
    error(f'expected integer expression, got `{realdata.realtype}`', pos)

  def ctx_if_int_or(self, alternative_rt):
    return self.ctx if self.ctx.is_int() else alternative_rt

  def ctx_if_numeric_or(self, alternative_rt):
    return self.ctx if self.ctx.is_numeric() else alternative_rt

  def evaluate_or_node(self, bin_node):
    '''
    # a or b
    r = undefined
    if a:
      r = true
    else:
      r = b
    '''

    and_result_var_name = self.create_internal_var_name(bin_node.pos)
    and_result_var_node = Node(
      'var_decl_node',
      pos=bin_node.pos,
      name=and_result_var_name,
      type=RealType('u8_rt'),
      expr=Node('undefined', value='undefined', pos=bin_node.pos)
    )

    and_node = Node(
      'if_node',
      pos=bin_node.pos,
      if_branch=Node(
        'if_branch_node',
        pos=bin_node.pos,
        cond=bin_node.left,
        body=[Node(
          'assignment_node',
          pos=bin_node.left.pos,
          lexpr=and_result_var_name,
          op=Node('=', value='=', pos=bin_node.pos),
          rexpr=Node('true', value='true', pos=bin_node.pos)
        )]
      ),
      elif_branches=[],
      else_branch=Node(
        'else_branch_node',
        pos=bin_node.pos,
        body=[Node(
          'assignment_node',
          pos=bin_node.right.pos,
          lexpr=and_result_var_name,
          op=Node('=', value='=', pos=bin_node.pos),
          rexpr=bin_node.right
        )]
      )
    )

    # print(f'# for `{bin_node}`')
    # print(and_result_var_node)
    # print(and_node)

    self.evaluate_var_decl_node_stmt(and_result_var_node, type_is_already_evaluated=True)
    self.evaluate_if_node_stmt(and_node)

    return self.evaluate_node(and_result_var_name, REALTYPE_PLACEHOLDER)

  def evaluate_and_node(self, bin_node):
    '''
    # a and b
    r = false
    if a:
      r = b
    '''

    realtype = self.ctx_if_int_or(RealType('u8_rt'))

    and_result_var_name = self.create_internal_var_name(bin_node.pos)
    and_result_var_node = Node(
      'var_decl_node',
      pos=bin_node.pos,
      name=and_result_var_name,
      type=realtype,
      expr=Node('false', value='false', pos=bin_node.pos)
    )

    and_node = Node(
      'if_node',
      pos=bin_node.pos,
      if_branch=Node(
        'if_branch_node',
        pos=bin_node.left.pos,
        cond=bin_node.left,
        body=[Node(
          'assignment_node',
          pos=bin_node.right.pos,
          lexpr=and_result_var_name,
          op=Node('=', value='=', pos=bin_node.pos),
          rexpr=bin_node.right
        )]
      ),
      elif_branches=[],
      else_branch=None
    )

    # print(f'# for `{bin_node}`')
    # print(and_result_var_node)
    # print(and_node)

    self.evaluate_var_decl_node_stmt(and_result_var_node, type_is_already_evaluated=True)
    self.evaluate_if_node_stmt(and_node)

    return self.evaluate_node(and_result_var_name, REALTYPE_PLACEHOLDER)

  def evaluate_andor_node(self, bin_node):
    return \
      self.evaluate_and_node(bin_node) \
        if bin_node.op.kind == 'and' else \
          self.evaluate_or_node(bin_node)
      
  def evaluate_bin_node(self, bin_node):
    if bin_node.op.kind in ['and', 'or']:
      return self.evaluate_andor_node(bin_node)

    get_resulting_realtype_of_bin_expr = lambda realdata: \
      realdata.realtype \
        if bin_node.op.kind not in ['==', '!=', '<', '>', '<=', '<='] else \
          self.ctx_if_int_or(RealType('u8_rt'))
  
    realdata_left = self.evaluate_node(bin_node.left, REALTYPE_PLACEHOLDER, is_top_call=False)
    realdata_right = self.evaluate_node(bin_node.right, REALTYPE_PLACEHOLDER, is_top_call=False)

    rd_left_is_coercable = realdata_left.realtype_is_coercable()
    rd_right_is_coercable = realdata_right.realtype_is_coercable()
    
    if rd_left_is_coercable:
      realdata_left.realtype = realdata_right.realtype

    if rd_right_is_coercable:
      realdata_right.realtype = realdata_left.realtype

    if realdata_left.is_comptime_value() and realdata_right.is_comptime_value():
      if rd_left_is_coercable and rd_right_is_coercable:
        self.expect_realdata_has_numeric_value(realdata_left, bin_node.left.pos)
        self.expect_realdata_has_numeric_value(realdata_right, bin_node.right.pos)
      else:
        self.expect_realdata_is_numeric(realdata_left, bin_node.left.pos)
        self.expect_realdata_is_numeric(realdata_right, bin_node.right.pos)

        self.expect_realtype_are_compatible(realdata_left.realtype, realdata_right.realtype, bin_node.pos)
        
      is_float = realdata_left.has_float_value()

      return (self.evaluate_fnum if is_float else self.evaluate_num)(
        Node(
          'fnum' if is_float else 'num',
          value=str(self.compute_comptime_bin(realdata_left, bin_node.op, realdata_right)),
          pos=bin_node.pos
        ),
        realtype_to_use=self.ctx
      )

    checker = \
      self.expect_realdata_is_numeric_or_ptr \
        if bin_node.op.kind in ['==', '!='] else \
          self.expect_realdata_is_numeric

    checker(realdata_left, bin_node.left.pos)
    checker(realdata_right, bin_node.right.pos)

    '''if bin_node.op.kind in ['==', '!='] and 'ptr' in [realdata_left.realtype.kind, realdata_right.realtype.kind]:
      # this will launch an error whether left and right types are of different classes
      self.expect_realtype_are_compatible(realdata_left.realtype, realdata_right.realtype, bin_node.pos)'''
    
    if realdata_left.is_comptime_value():
      new_realtype = realdata_left.realtype = realdata_right.realtype
      llvm_constant = None if new_realtype.is_ptr() else realdata_left.llvm_data.constant
      realdata_left.llvm_data = ll.Constant(self.convert_realtype_to_llvmtype(new_realtype), llvm_constant)
    
    if realdata_right.is_comptime_value():
      new_realtype = realdata_right.realtype = realdata_left.realtype
      llvm_constant = None if new_realtype.is_ptr() else realdata_right.llvm_data.constant
      realdata_right.llvm_data = ll.Constant(self.convert_realtype_to_llvmtype(new_realtype), llvm_constant)

    self.expect_realtype_are_compatible(realdata_left.realtype, realdata_right.realtype, bin_node.pos)

    realtype = get_resulting_realtype_of_bin_expr(realdata_left)
    llvm_data = self.generate_llvm_bin(realdata_left, bin_node.op, realdata_right, realtype)

    return RealData(
      realtype,
      llvm_data=llvm_data
    )
  
  def evaluate_pass_node_stmt(self, pass_node):
    pass
  
  def is_bitcast(self, source_rt, target_rt):
    return source_rt.is_ptr() and target_rt.is_ptr()

  def is_numeric_cast(self, source_rt, target_rt):
    return source_rt.is_numeric() and target_rt.is_numeric()

  def is_ptrint_cast(self, source_rt, target_rt):
    return \
      (source_rt.is_numeric() and target_rt.is_ptr()) or \
      (source_rt.is_ptr() and target_rt.is_numeric())

  def make_bitcast(self, realdata_expr, target_rt):
    realdata_expr.realtype = target_rt
    realdata_expr.llvm_data = self.cur_builder.bitcast(
      realdata_expr.llvm_data,
      self.convert_realtype_to_llvmtype(target_rt)
    )
  
  def evaluate_dot_node_for_union(self, dot_node, instance_realdata, field_name):
    field_realtype = instance_realdata.realtype.fields[field_name]
    llvm_type = self.convert_realtype_to_llvmtype(field_realtype)

    if isinstance(instance_realdata.llvm_data, ll.LoadInstr):
      self.cur_builder.remove(instance_realdata.llvm_data)
      ptr = instance_realdata.llvm_data.operands[0]
    else:
      ptr = self.allocas_builder.alloca('union.tmp')

    ptr_bitcat = self.cur_builder.bitcast(ptr, ll.PointerType(llvm_type))

    return RealData(
      field_realtype,
      llvm_data=self.cur_builder.load(ptr_bitcat)
    )
  
  def lower_match_case_branch(self, lowered_node_kind, expr_to_match, case_branch):
    return Node(
      lowered_node_kind,
      cond=Node(
        'bin_node',
        op=Node('==', value='==', pos=case_branch.pos),
        left=expr_to_match,
        right=case_branch.expr,
        pos=case_branch.pos
      ),
      body=case_branch.body,
      pos=case_branch.pos
    )
  
  def evaluate_match_node_stmt(self, match_node):
    internal_var_id = self.create_internal_var_name(match_node.expr_to_match.pos)
    var_decl_node = Node(
      'var_decl_node',
      name=internal_var_id,
      type=None,
      expr=match_node.expr_to_match,
      pos=match_node.expr_to_match.pos
    )
    
    if_node = Node(
      'if_node',
      if_branch=self.lower_match_case_branch('if_branch_node', internal_var_id, match_node.case_branches[0]),
      elif_branches=[
        self.lower_match_case_branch('elif_branch_node', internal_var_id, case)
          for case in match_node.case_branches[1:]
      ],
      else_branch=match_node.else_branch,
      pos=match_node.pos
    )

    self.evaluate_var_decl_node_stmt(var_decl_node, type_is_implicit=True)
    self.evaluate_if_node_stmt(if_node)

  def evaluate_dot_node(self, dot_node):
    instance_realdata = self.evaluate_node(dot_node.left_expr, REALTYPE_PLACEHOLDER)
    field_name = dot_node.right_expr.value

    self.expect_realdata_is_struct_or_union(instance_realdata, dot_node.pos)

    if field_name not in instance_realdata.realtype.fields:
      error(f'{instance_realdata.realtype.kind.replace("_rt", "")} `{instance_realdata.realtype}` has no field `{field_name}`', dot_node.pos)

    if instance_realdata.realtype.is_union():
      return self.evaluate_dot_node_for_union(dot_node, instance_realdata, field_name)

    field_index = list(instance_realdata.realtype.fields.keys()).index(field_name)
    realtype = instance_realdata.realtype.fields[field_name]

    if isinstance(instance_realdata.llvm_data, ll.LoadInstr):
      self.cur_builder.remove(instance_realdata.llvm_data)
      instance_realdata.llvm_data = instance_realdata.llvm_data.operands[0]

      llvm_data = self.llvm_load(self.cur_builder,
        self.llvm_gep(
          self.cur_builder,
          instance_realdata.llvm_data,
          [ll.Constant(ll.IntType(32), 0), ll.Constant(ll.IntType(32), field_index)],
          True
        ),
        self.convert_realtype_to_llvmtype(realtype)
      )
    else:
      resulting_llvm_type = self.convert_realtype_to_llvmtype(realtype)
      llvm_data = self.llvm_extract_value(self.cur_builder, instance_realdata.llvm_data, field_index, resulting_llvm_type)

    return RealData(
      realtype,
      llvm_data=llvm_data
    )
  
  def evaluate_index_node(self, index_node):
    instance_realdata = self.evaluate_node(index_node.instance_expr, REALTYPE_PLACEHOLDER)
    return self.internal_evaluate_index_node(index_node, instance_realdata)

  def internal_evaluate_index_node(self, index_node, instance_realdata):
    index_realdata = self.evaluate_node(index_node.index_expr, RealType('u64_rt'))

    self.expect_realdata_is_indexable(instance_realdata, index_node.instance_expr.pos)
    self.expect_realdata_is_integer(index_realdata, index_node.index_expr.pos)

    indices = [index_realdata.llvm_data]

    if instance_realdata.realtype.is_static_array():
      self.cur_builder.remove(instance_realdata.llvm_data)
      instance_realdata.llvm_data = instance_realdata.llvm_data.operands[0]
      indices.insert(0, ll.Constant(ll.IntType(64), 0))

    llvm_data = self.llvm_load(
      self.cur_builder,
      self.llvm_gep(
        self.cur_builder,
        instance_realdata.llvm_data,
        indices,
        False
      ),
      self.convert_realtype_to_llvmtype(instance_realdata.realtype.type)
    )

    return RealData(
      instance_realdata.realtype.type,
      llvm_data=llvm_data
    )

  def evaluate_array_init_node(self, init_node):
    if self.ctx.is_static_array() or self.ctx.is_ptr():
      realdatas = self.evaluate_array_init_nodes(init_node, self.ctx.type)
    else:
      realdatas = self.evaluate_array_init_nodes(init_node, self.ctx)

    realtype = RealType('static_array_rt', length=len(init_node.nodes), type=realdatas[0].realtype)
    element_llvm_type = self.convert_realtype_to_llvmtype(realtype.type)
    llvm_data = ll.Constant(self.convert_realtype_to_llvmtype(realtype), ll.Undefined)

    for i, realdata in enumerate(realdatas):
      llvm_data = self.llvm_insert_value(self.cur_builder, llvm_data, realdata.llvm_data, i, element_llvm_type)

    return RealData(
      realtype,
      llvm_data=llvm_data
    )

  def evaluate_array_init_nodes(self, init_node, ctx_type_for_the_first_node):
    realdatas = []
    
    for i, node in enumerate(init_node.nodes):
      is_first_node = i == 0

      realdatas.append(rd := self.evaluate_node(
        node,
        ctx_type_for_the_first_node if is_first_node else realdatas[0].realtype
      ))

      if not is_first_node:
        self.expect_realtype(realdatas[0].realtype, rd.realtype, node.pos)

    return realdatas
  
  def evaluate_struct_init_node(self, init_node):
    field_names = list(map(lambda field: field.name.value, init_node.fields))
    ctx_realtypes = list(self.ctx.fields.values()) if self.ctx.is_struct() else []
    field_realdatas = [self.evaluate_node(field.expr, ctx_realtypes[i] if i < len(ctx_realtypes) else REALTYPE_PLACEHOLDER) for i, field in enumerate(init_node.fields)]
    field_realtypes = map(lambda realdata: realdata.realtype, field_realdatas)

    for i, field_name in enumerate(field_names):
      if field_names.count(field_name) > 1:
        error(f'field `{field_name}` is dupplicate', init_node.fields[i].name.pos)
    
    realtype = RealType('struct_rt', fields=dict(zip(field_names, field_realtypes)))
    llvm_data = ll.Constant(self.convert_realtype_to_llvmtype(realtype), ll.Undefined)

    for i, field_realdata in enumerate(field_realdatas):
      real_expected_value_llvm_type = self.convert_realtype_to_llvmtype(field_realdata.realtype)
      llvm_data = self.llvm_insert_value(self.cur_builder, llvm_data, field_realdata.llvm_data, i, real_expected_value_llvm_type)

    return RealData(
      realtype,
      llvm_data=llvm_data
    )

  def make_numeric_cast(self, realdata_expr, target_rt):
    source_bits = realdata_expr.realtype.bits
    target_bits = target_rt.bits
    llvm_target_type = self.convert_realtype_to_llvmtype(target_rt)
    is_signed = realdata_expr.realtype.is_signed
    is_signed_target_rt = target_rt.is_signed

    if realdata_expr.realtype == target_rt:
      return

    if realdata_expr.realtype.is_float() and target_rt.is_float():
      llvm_caster = self.cur_builder.fpext if source_bits < target_bits else self.cur_builder.fptrunc
    elif realdata_expr.realtype.is_float():
      llvm_caster = self.cur_builder.fptosi if is_signed_target_rt else self.cur_builder.fptoui
    elif target_rt.is_float():
      llvm_caster = self.cur_builder.sitofp if is_signed else self.cur_builder.uitofp
    else:
      llvm_caster = getattr(self.cur_builder, 'sext' if is_signed else 'zext') if source_bits < target_bits else self.cur_builder.trunc

    realdata_expr.realtype = target_rt
    realdata_expr.llvm_data = llvm_caster(
      realdata_expr.llvm_data,
      llvm_target_type
    )
  
  def evaluate_as_node(self, as_node):
    target_rt = self.evaluate_type(as_node.type)
    realdata_expr = self.evaluate_node(as_node.expr, target_rt)
    source_rt = realdata_expr.realtype

    if self.is_bitcast(source_rt, target_rt):
      self.make_bitcast(realdata_expr, target_rt)
    elif self.is_numeric_cast(source_rt, target_rt):
      self.make_numeric_cast(realdata_expr, target_rt)
    # elif self.is_ptrint_cast(source_rt, target_rt):
    #   pass
    else:
      error(f'invalid cast from `{source_rt}` to `{target_rt}`', as_node.pos)
    
    if realdata_expr.is_comptime_value():
      realdata_expr.realtype_is_coerced = None

    return realdata_expr

  def is_deref_node(self, node):
    return node.kind == 'unary_node' and node.op.kind == '*'

  def is_index_node(self, node):
    return node.kind == 'index_node'

  def expect_realdata_is_ptr(self, realdata, pos):
    if realdata.realtype.is_ptr():
      return
    
    error(f'expected pointer expression, got `{realdata.realtype}`', pos)

  def create_internal_var_name(self, pos):
    self.internal_vars += 1
    return Node('id', value=f'internal.{self.internal_vars}', pos=pos)

  def evaluate_try_node_stmt(self, try_node):
    has_no_var = try_node.var is None

    var_decl_node = Node(
      'var_decl_node',
      name=self.create_internal_var_name(try_node.expr.pos) if has_no_var else try_node.var.name,
      type=self.cur_fn[0].ret_type if has_no_var else try_node.var.type,
      expr=try_node.expr,
      pos=try_node.pos if has_no_var else try_node.var.pos
    )

    return_node = Node('return_node', expr=var_decl_node.name, pos=try_node.pos)

    if_node = Node(
      'if_node',
      if_branch=Node(
        'if_branch_node',
        cond=Node(
          'bin_node',
          left=var_decl_node.name, 
          op=Node('!=', value='!=', pos=var_decl_node.name.pos),
          right=Node('num', value=0, pos=var_decl_node.name.pos),
          pos=var_decl_node.name.pos
        ),
        body=try_node.body if try_node.body is not None else [return_node],
        pos=try_node.pos
      ),
      elif_branches=[],
      else_branch=None,
      pos=try_node.pos
    )

    self.evaluate_var_decl_node_stmt(var_decl_node, type_is_already_evaluated=has_no_var)
    self.evaluate_if_node_stmt(if_node)
  
  def evaluate_out_param_node(self, out_node):
    self.evaluate_var_decl_node_stmt(Node(
      'var_decl_node',
      name=out_node.name,
      type=out_node.type,
      expr=Node('undefined', value='undefined', pos=out_node.name.pos),
      pos=out_node.name.pos
    ))

    return self.evaluate_unary_node(Node(
      'unary_node',
      op=Node('&', value='&', pos=out_node.pos),
      is_mut=True,
      expr=out_node.name,
      pos=out_node.pos
    ))

  def evaluate_unary_node(self, unary_node):
    match unary_node.op.kind:
      case '&':
        return self.evaluate_reference_node(unary_node)
      
      case 'not':
        return self.evaluate_not_node(unary_node)
    
      case '*':
        realdata_expr = self.evaluate_node(unary_node.expr, RealType('ptr_rt', is_mut=False, type=self.ctx))
        self.expect_realdata_is_ptr(realdata_expr, unary_node.expr.pos)

        return RealData(
          realdata_expr.realtype.type,
          llvm_data=self.llvm_load(self.cur_builder, realdata_expr.llvm_data, self.convert_realtype_to_llvmtype(realdata_expr.realtype.type))
        )
      
      case _:
        realdata_expr = self.evaluate_node(unary_node.expr, self.ctx)
        self.expect_realdata_is_numeric(realdata_expr, unary_node.expr.pos)

        if unary_node.op.kind != '-':
          return realdata_expr

        if realdata_expr.is_comptime_value():
          realdata_expr.value = -realdata_expr.value
          realdata_expr.llvm_data.constant = -realdata_expr.llvm_data.constant
        else:
          realdata_expr.llvm_data = self.cur_builder.neg(realdata_expr.llvm_data)

        return realdata_expr

  def evaluate_var_decl_node_stmt(self, var_decl_node, type_is_already_evaluated=False, type_is_implicit=False):
    is_comptime = var_is_comptime(var_decl_node.name.value)

    if type_is_implicit:
      realtype = REALTYPE_PLACEHOLDER
    elif type_is_already_evaluated:
      realtype = var_decl_node.type
    else:
      realtype = self.evaluate_type(var_decl_node.type)

    realdata = self.evaluate_node(var_decl_node.expr, realtype)

    if type_is_implicit:
      realtype = realdata.realtype
    else:
      self.expect_realtype(realtype, realdata.realtype, var_decl_node.expr.pos)

    if is_comptime:
      self.expect_realdata_is_comptime_value(realdata, var_decl_node.expr.pos)
      llvm_data = realdata.llvm_data
    else:
      llvm_data = self.allocas_builder.alloca(self.convert_realtype_to_llvmtype(realtype), name=var_decl_node.name.value)
      self.llvm_store(self.cur_builder, realdata.llvm_data, llvm_data)

    sym = Symbol(
      'local_var_sym',
      is_comptime=is_comptime,
      realtype=realtype,
      llvm_data=llvm_data,
      realdata=realdata if is_comptime else None
    )

    self.declare_symbol(var_decl_node.name.value, sym, var_decl_node.name.pos)

  def evaluate_if_node_stmt(self, if_node):
    has_else_branch = if_node.else_branch is not None
    
    llvm_block_if_branch = self.cur_fn[1].append_basic_block('if_branch_block')
    llvm_block_elif_condcheckers = [self.cur_fn[1].append_basic_block('elif_condchecker') for _ in if_node.elif_branches]
    llvm_block_elif_branches = [self.cur_fn[1].append_basic_block('elif_branch_block') for _ in if_node.elif_branches]
    llvm_block_else_branch = self.cur_fn[1].append_basic_block('else_branch_block') if has_else_branch else None
    llvm_exit_block = self.cur_fn[1].append_basic_block('exit_block')

    cond_rd = self.evaluate_condition_node(if_node.if_branch.cond)

    false_br = llvm_block_elif_condcheckers[0] if len(llvm_block_elif_branches) > 0 else llvm_block_else_branch if has_else_branch else llvm_exit_block

    if cond_rd.is_comptime_value():
      self.cur_builder.branch(llvm_block_if_branch if cond_rd.value else false_br)
    else:
      self.llvm_cbranch(self.cur_builder, cond_rd.llvm_data, llvm_block_if_branch, false_br)

    self.push_builder(ll.IRBuilder(llvm_block_if_branch))
    self.push_sub_scope()
    has_terminator = self.evaluate_block(if_node.if_branch.body)
    self.fix_sub_scope_terminator(has_terminator, llvm_exit_block)
    self.pop_scope()
    self.pop_builder()

    for i, elif_branch in enumerate(if_node.elif_branches):
      self.push_builder(ll.IRBuilder(llvm_block_elif_condcheckers[i]))

      cond_rd = self.evaluate_condition_node(elif_branch.cond)

      false_br = llvm_block_elif_condcheckers[i + 1] if i + 1 < len(llvm_block_elif_branches) else llvm_block_else_branch if has_else_branch else llvm_exit_block

      if cond_rd.is_comptime_value():
        self.cur_builder.branch(llvm_block_elif_branches[i] if cond_rd.value else false_br)
      else:
        self.llvm_cbranch(self.cur_builder, cond_rd.llvm_data, llvm_block_elif_branches[i], false_br)

      self.pop_builder()
      
      self.push_builder(ll.IRBuilder(llvm_block_elif_branches[i]))
      self.push_sub_scope()
      has_terminator = self.evaluate_block(elif_branch.body)
      self.fix_sub_scope_terminator(has_terminator, llvm_exit_block)
      self.pop_scope()
      self.pop_builder()

    if has_else_branch:
      self.push_builder(ll.IRBuilder(llvm_block_else_branch))
      self.push_sub_scope()
      has_terminator = self.evaluate_block(if_node.else_branch.body)
      self.fix_sub_scope_terminator(has_terminator, llvm_exit_block)
      self.pop_scope()
      self.pop_builder()

    self.cur_builder = ll.IRBuilder(llvm_exit_block)

  def evaluate_condition_node(self, condition_node):
    cond_rd = self.evaluate_node(condition_node, RealType('u8_rt'))
    self.expect_realdata_is_integer(cond_rd, condition_node.pos)

    return cond_rd
  
  def fix_sub_scope_terminator(self, has_terminator, llvm_exit_block):
    if has_terminator:
      return
    
    self.cur_builder.branch(llvm_exit_block)

  def evaluate_return_node_stmt(self, return_node):
    cur_fn_ret_type = self.cur_fn[0].ret_type

    if return_node.expr is None:
      self.expect_realtype(cur_fn_ret_type, RealType('void_rt'), return_node.pos)
      self.cur_builder.ret_void()
      return
    
    # self.evaluate_defer_nodes()
    # self.defer_nodes = []

    expr = self.evaluate_node(return_node.expr, cur_fn_ret_type)
    self.expect_realtype(cur_fn_ret_type, expr.realtype, return_node.expr.pos)
    self.llvm_ret(self.cur_builder, expr.llvm_data, self.convert_realtype_to_llvmtype(cur_fn_ret_type))
  
  def evaluate_generics_in_call(self, generic_type_nodes):
    return list(map(lambda node: self.evaluate_type(node), generic_type_nodes))

  def expect_generics_count(self, call_node, checker_fn):
    if checker_fn(len(call_node.generics)):
      return
    
    error(f'unexpected `{len(call_node.generics)}` generic args', call_node.pos)

  def expect_args_count(self, call_node, checker_fn):
    if checker_fn(len(call_node.args)):
      return
    
    error(f'unexpected `{len(call_node.args)}` args', call_node.pos)

  def evaluate_internal_call_to_ptr2int(self, call_node):
    self.expect_generics_count(call_node, lambda count: count == 1)
    self.expect_args_count(call_node, lambda count: count == 1)

    generic_realtype = self.evaluate_type(call_node.generics[0])
    if not generic_realtype.is_int():
      error(f'expected int generic type, got `{generic_realtype}`', call_node.generics[0].pos)

    realdata = self.evaluate_node(call_node.args[0], REALTYPE_PLACEHOLDER)
    self.expect_realdata_is_ptr(realdata, call_node.args[0].pos)
    
    return RealData(
      generic_realtype,
      llvm_data=self.cur_builder.ptrtoint(realdata.llvm_data, self.convert_realtype_to_llvmtype(generic_realtype))
    )

  def evaluate_internal_call_to_int2ptr(self, call_node):
    self.expect_generics_count(call_node, lambda count: count == 1)
    self.expect_args_count(call_node, lambda count: count == 1)

    generic_realtype = self.evaluate_type(call_node.generics[0])
    if not generic_realtype.is_ptr():
      error(f'expected ptr generic type, got `{generic_realtype}`', call_node.generics[0].pos)

    realdata = self.evaluate_node(call_node.args[0], RealType('u64_rt'))
    self.expect_realdata_is_integer(realdata, call_node.args[0].pos)
    
    return RealData(
      generic_realtype,
      llvm_data=self.cur_builder.inttoptr(realdata.llvm_data, self.convert_realtype_to_llvmtype(generic_realtype))
    )

  def evaluate_internal_call_to_invoke(self, call_node):
    self.expect_generics_count(call_node, lambda count: count == 0)
    self.expect_args_count(call_node, lambda count: count > 0)
    realdata_args = []

    fn_realdata = self.evaluate_node(call_node.args[0], REALTYPE_PLACEHOLDER)
    fn_arg_nodes = call_node.args[1:]

    if fn_realdata.realtype.kind != 'ptr_rt' or fn_realdata.realtype.type.kind != 'fn_rt':
      error(f'expected fn expression, got `{fn_realdata.realtype}`', call_node.args[0])
    
    fn_realtype = fn_realdata.realtype.type
    
    for i, arg_node in enumerate(fn_arg_nodes):
      realdata_args.append(realdata_arg := self.evaluate_node(arg_node, proto_arg_type := fn_realtype.arg_types[i]))
      self.expect_realtype(proto_arg_type, realdata_arg.realtype, arg_node.pos)

    llvm_args = list(map(lambda arg: arg.llvm_data, realdata_args))
    llvm_call = self.llvm_call(self.cur_builder, fn_realdata.llvm_data, llvm_args)

    return RealData(
      fn_realtype.ret_type,
      llvm_data=llvm_call
    )

  def evaluate_internal_call_to_fn2ptr(self, call_node):
    self.expect_generics_count(call_node, lambda count: count == 0)
    self.expect_args_count(call_node, lambda count: count == 1)

    fn_name = self.expect_node_is_id(call_node.args[0])
    sym = self.get_symbol(fn_name, call_node.args[0].pos)

    check_sym_is_fn(fn_name, sym)
    
    if len(sym.node.generics) != 0:
      error('generic function cannot be addressed', call_node.args[0].pos)
    
    proto, llvm_data, _ = self.gen_nongeneric_fn(sym)

    resulting_realtype = RealType('ptr_rt', is_mut=False, type=RealType(
      'fn_rt',
      arg_types=proto.arg_types,
      ret_type=proto.ret_type
    ))
    
    return RealData(
      resulting_realtype,
      llvm_data=llvm_data
    )
  
  def evaluate_internal_call_to_cstr(self, call_node):
    self.expect_generics_count(call_node, lambda count: count == 0)
    self.expect_args_count(call_node, lambda count: count == 1)

    value = self.expect_node_is_literal_str(call_node.args[0])
    llvm_data = self.cache_string(value)

    return RealData(
      CSTRING_REALTYPE,
      realtype_is_coerced=None,
      value=call_node.args[0].value,
      llvm_data=llvm_data
    )
  
  def evaluate_internal_call_to_carr_mut(self, call_node):
    return self.evaluate_internal_call_to_carr(call_node, construct_as_mut=True)

  def evaluate_internal_call_to_carr(self, call_node, construct_as_mut=False):
    self.expect_generics_count(call_node, lambda count: count == 0)
    self.expect_args_count(call_node, lambda count: count == 1)

    arg = call_node.args[0]

    if arg.kind != 'array_init_node':
      error('expected static array initializer', arg.pos)
    
    realdata = self.evaluate_node(
      Node('unary_node', is_mut=False, op=Node('&', value='&', pos=call_node.pos), expr=arg, pos=call_node.pos),
      self.ctx
    )

    realdata.llvm_data = self.cur_builder.bitcast(realdata.llvm_data, self.convert_realtype_to_llvmtype(self.ctx))
    realdata.realtype = RealType('ptr_rt', is_mut=construct_as_mut, type=realdata.realtype.type.type)

    return realdata

  def evaluate_internal_call_to_internal_var(self, call_node):
    return self.evaluate_lib_var(call_node, True)

  def evaluate_internal_call_to_extern_var(self, call_node):
    return self.evaluate_lib_var(call_node, False)

  def evaluate_lib_var(self, call_node, is_internal):
    self.expect_generics_count(call_node, lambda count: count == 1)
    self.expect_args_count(call_node, lambda count: count == (1 if is_internal else 2))

    name_to_import = self.expect_node_is_literal_str(call_node.args[0 if is_internal else 1])
    generic_realtype = self.evaluate_type(call_node.generics[0])

    if name_to_import not in self.llvm_internal_vars:
      self.llvm_internal_vars[name_to_import] = ll.GlobalVariable(
        self.output,
        self.convert_realtype_to_llvmtype(generic_realtype),
        name_to_import
      )
    
    if not is_internal:
      lib_to_import = self.expect_node_is_literal_str(call_node.args[0])
      self.libs_to_import.add(get_full_path_from_brother_file(self.path, lib_to_import))

    llvm_data = self.cur_builder.load(self.llvm_internal_vars[name_to_import])

    return RealData(
      generic_realtype,
      llvm_data=llvm_data
    )

  def evaluate_internal_call_to_is_release_build(self, call_node):
    self.expect_generics_count(call_node, lambda count: count == 0)
    self.expect_args_count(call_node, lambda count: count == 0)

    return self.evaluate_truefalse(call_node, '0' if is_debug_build() in argv else '1')

  def evaluate_internal_call_to_is_debug_build(self, call_node):
    self.expect_generics_count(call_node, lambda count: count == 0)
    self.expect_args_count(call_node, lambda count: count == 0)

    return self.evaluate_truefalse(call_node, '1' if is_debug_build() in argv else '0')
  
  def evaluate_internal_call_to_internal_call(self, call_node):
    return self.evaluate_lib_call(call_node, True)
    
  def evaluate_internal_call_to_extern_call(self, call_node):
    return self.evaluate_lib_call(call_node, False)

  def evaluate_lib_call(self, call_node, is_internal):
    self.expect_args_count(
      call_node,
      lambda count: count >= 1 and count == len(call_node.generics) + (0 if is_internal else 1)
    )

    generic_ret_realtype = self.evaluate_type(call_node.generics[-1], allow_void_type=True)
    generic_arg_realtypes = [self.evaluate_type(generic) for generic in call_node.generics[:-1]]
    
    arg_realdatas = []
    name_to_call = self.expect_node_is_literal_str(call_node.args[0 if is_internal else 1])
    
    for i, arg in enumerate(call_node.args[(1 if is_internal else 2):]):
      arg_realdatas.append(realdata := self.evaluate_node(arg, expected_realtype := generic_arg_realtypes[i]))
      self.expect_realtype(expected_realtype, realdata.realtype, arg.pos)

    llvm_internal_fn = self.cache_lib_fn(name_to_call, generic_ret_realtype, generic_arg_realtypes)

    if not is_internal:
      lib_to_import = self.expect_node_is_literal_str(call_node.args[0])
      self.libs_to_import.add(get_full_path_from_brother_file(self.path, lib_to_import))
    
    return RealData(
      generic_ret_realtype,
      llvm_data=self.llvm_call(
        self.cur_builder,
        llvm_internal_fn,
        list(map(lambda arg_rd: arg_rd.llvm_data, arg_realdatas))
      )
    )
  
  def cache_lib_fn(self, fn_name, ret_realtype, arg_realtypes):
    if fn_name not in self.llvm_internal_functions_cache:
      self.llvm_internal_functions_cache[fn_name] = ll.Function(
        self.output,
        self.convert_proto_to_llvmproto(self.make_proto(
          'fn_proto',
          ret_type=ret_realtype,
          arg_types=arg_realtypes,
          is_test=False
        )),
        fn_name
      )

    return self.llvm_internal_functions_cache[fn_name]

  def expect_node_is_literal_str(self, node):
    if node.kind != 'str':
      error('expected literal string', node.pos)
    
    return node.value
    
  def expect_node_is_id(self, node):
    if node.kind != 'id':
      error('expected id', node.pos)
    
    return node.value
  
  def evaluate_internal_call_to_panic(self, call_node):
    self.expect_args_count(call_node, lambda count: count in [0, 1])
    self.expect_generics_count(call_node, lambda count: count == 0)

    llvm_puts = self.cache_lib_fn('puts', RealType('i32_rt'), [CSTRING_REALTYPE])
    message = f"reached `panic!()` at {repr_pos(call_node.pos, use_path=True)}, in `{self.cur_fn[0].name}`"

    if len(call_node.args) == 1:
      custom_msg = self.expect_node_is_literal_str(call_node.args[0]).replace("'", "\\'")
      message += f": '{custom_msg}'"

    self.llvm_call(self.cur_builder, llvm_puts, [self.cache_string(message)])
    self.cur_builder.unreachable()

    return RealData(RealType('void_rt'), llvm_data=None)

  def evaluate_internal_call_to_assert(self, call_node):
    create_result = lambda: RealData(RealType('void_rt'), llvm_data=None)

    if is_release_build():
      return create_result()

    self.expect_args_count(call_node, lambda count: count in [1, 2])
    self.expect_generics_count(call_node, lambda count: count == 0)

    realdata = self.evaluate_condition_node(call_node.args[0])
    llvm_puts = self.cache_lib_fn('puts', RealType('i32_rt'), [CSTRING_REALTYPE])
    failure_message = f'failed `assert!()` at {repr_pos(call_node.pos, use_path=True)}, in `{self.cur_fn[0].name}`'

    if len(call_node.args) == 2:
      custom_msg = self.expect_node_is_literal_str(call_node.args[1]).replace("'", "\\'")
      failure_message += f": '{custom_msg}'"

    llvm_truebr = self.cur_fn[1].append_basic_block('assert_success')
    llvm_falsebr = self.cur_fn[1].append_basic_block('assert_failure')

    self.llvm_cbranch(self.cur_builder, realdata.llvm_data, llvm_truebr, llvm_falsebr)

    self.push_builder(ll.IRBuilder(llvm_falsebr))
    self.llvm_call(self.cur_builder, llvm_puts, [self.cache_string(failure_message)])
    self.cur_builder.unreachable()
    self.pop_builder()

    self.cur_builder = ll.IRBuilder(llvm_truebr)

    return create_result()

  def evaluate_internal_call_to_expect(self, call_node):
    if is_release_build():
      return RealData(
        RealType('i32', aka='Error'),
        llvm_data=ll.Constant(ll.IntType(32), 0)
      )
    
    self.expect_args_count(call_node, lambda count: count == 1)
    self.expect_generics_count(call_node, lambda count: count == 0)

    arg = call_node.args[0]

    return self.evaluate_inline_if_node(
      Node(
        'inline_if_node',
        pos=call_node.pos,
        if_cond=arg,
        if_expr=Node(
          'as_node',
          expr=Node('num', value='0', pos=call_node.pos),
          type=Node('id', value='i32', pos=call_node.pos),
          pos=call_node.pos
        ),
        else_expr=Node(
          'as_node',
          expr=Node('num', value='1', pos=call_node.pos),
          type=Node('id', value='i32', pos=call_node.pos),
          pos=call_node.pos
        )
      )
    )
  
  def evaluate_internal_call_to_type_size(self, call_node):
    self.expect_args_count(call_node, lambda count: count == 0)
    self.expect_generics_count(call_node, lambda count: count == 1)

    generic_realtype = self.evaluate_type(call_node.generics[0])
    size = generic_realtype.calculate_size()

    return self.evaluate_num(
      Node('num', value=str(size), pos=call_node.pos),
      realtype_to_use=self.ctx_if_numeric_or(RealType('u64_rt'))
    )

  def evaluate_internal_call_to_here(self, call_node):
    self.expect_args_count(call_node, lambda count: count == 0)
    self.expect_generics_count(call_node, lambda count: count == 0)

    llvm_puts = self.cache_lib_fn('puts', RealType('i32_rt'), [CSTRING_REALTYPE])
    message = f'logged `here!()` at {repr_pos(call_node.pos, use_path=True)}, in `{self.cur_fn[0].name}`'
    self.llvm_call(self.cur_builder, llvm_puts, [self.cache_string(message)])

    return RealData(RealType('void_rt'), llvm_data=None)

  def evaluate_internal_call_to_fmt(self, call_node):
    self.expect_args_count(call_node, lambda count: count > 1)
    self.expect_generics_count(call_node, lambda count: count == 0)

    fmt = self.expect_node_is_literal_str(call_node.args[0])
    arg_realdatas = [self.evaluate_node(arg, REALTYPE_PLACEHOLDER) for arg in call_node.args[1:]]

    divisions = self.get_fmt_divisions(fmt)
    
    if len(divisions) != len(call_node.args):
      error(f'fmt literal wants `{len(divisions) - 1}` arguments, got `{len(call_node.args) - 1}`', call_node.args[0].pos)
    
    fmt_array_length = len(divisions) + len(call_node.args) - 1
    llvm_string = self.convert_realtype_to_llvmtype(STRING_REALTYPE)
    array_of_string_realtype = RealType('struct_rt', aka='Array[String]', fields={ 'ptr': RealType('ptr_rt', is_mut=False, type=STRING_REALTYPE), 'len': RealType('u64_rt') })
    llvm_array_of_string = self.convert_realtype_to_llvmtype(array_of_string_realtype)
    llvm_fixed_array_of_string = ll.ArrayType(llvm_string, fmt_array_length)
    llvm_data = ll.Constant(llvm_fixed_array_of_string, ll.Undefined)

    for i, div in enumerate(divisions):
      is_last_div = i == len(divisions) - 1

      if not is_last_div:
        self.expect_realtype(STRING_REALTYPE, arg_realdatas[i].realtype, call_node.args[i + 1].pos)

      string = self.cur_builder.insert_value(ll.Constant(llvm_string, ll.Undefined), self.cache_string(div), 0)
      string = self.cur_builder.insert_value(string, ll.Constant(ll.IntType(64), len(div)), 1)

      llvm_data = self.cur_builder.insert_value(llvm_data, string, i * 2)

      if not is_last_div:
        llvm_data = self.cur_builder.insert_value(llvm_data, arg_realdatas[i].llvm_data, i * 2 + 1)
    
    self.tmp_counter += 1
    tmp = self.allocas_builder.alloca(llvm_data.type, name=f'tmp.{self.tmp_counter}')
    self.cur_builder.store(llvm_data, tmp)

    llvm_data = self.cur_builder.bitcast(tmp, ll.PointerType(llvm_string))
    llvm_data = self.cur_builder.insert_value(ll.Constant(llvm_array_of_string, ll.Undefined), llvm_data, 0)
    llvm_data = self.cur_builder.insert_value(llvm_data, ll.Constant(ll.IntType(64), fmt_array_length), 1)
    
    return RealData(
      array_of_string_realtype,
      llvm_data=llvm_data
    )
  
  def get_fmt_divisions(self, fmt):
    strings = fmt.split('%')
    new_fmt = []
    while len(strings) > 0:
      s = strings.pop(0)

      if s != '':
        new_fmt.append(s)
        continue
    
      if len(new_fmt) == 0:
        new_fmt.append('')

      new_fmt[-1] = f'{new_fmt[-1]}%{strings.pop(0)}'
    
    return new_fmt

  def evaluate_internal_call_node(self, call_node):
    try:
      attr = getattr(self, f'evaluate_internal_call_to_{call_node.name.value}')
    except AttributeError:
      error(f'unknown internal function `{call_node.name.value}`', call_node.name.pos)
    
    return attr(call_node)

  def evaluate_call_node(self, call_node):
    if call_node.is_internal_call:
      return self.evaluate_internal_call_node(call_node)

    fn = self.get_symbol(call_node.name.value, call_node.name.pos)
    check_sym_is_fn(call_node.name.value, fn)

    if len(call_node.generics) != len(fn.node.generics):
      error(f'expected `{len(fn.node.generics)}` generic args, got `{len(call_node.generics)}`', call_node.pos)

    if len(call_node.args) != len(fn.node.args):
      error(f'expected `{len(fn.node.args)}` args, got `{len(call_node.args)}`', call_node.pos)

    proto, llvmfn, _ = \
      fn.generator.gen_nongeneric_fn(fn) \
        if len(fn.node.generics) == 0 else \
          fn.generator.gen_generic_fn(fn, self.evaluate_generics_in_call(call_node.generics))

    realdata_args = []
    
    for i, arg_node in enumerate(call_node.args):
      realdata_args.append(realdata_arg := self.evaluate_node(arg_node, proto_arg_type := proto.arg_types[i]))
      self.expect_realtype(proto_arg_type, realdata_arg.realtype, arg_node.pos)

    llvm_args = list(map(lambda arg: arg.llvm_data, realdata_args))
    llvm_call = self.llvm_call(self.cur_builder, llvmfn, llvm_args)

    return RealData(
      proto.ret_type,
      llvm_data=llvm_call
    )

  def evaluate_while_node_stmt(self, while_node):
    llvm_block_check = self.cur_fn[1].append_basic_block('condcheck_block')
    llvm_block_loop = self.cur_fn[1].append_basic_block('loop_branch_block')
    llvm_block_exit = self.cur_fn[1].append_basic_block('exit_branch_block')

    self.cur_builder.branch(llvm_block_check)
    self.cur_builder = ll.IRBuilder(llvm_block_check)

    cond_rd = self.evaluate_condition_node(while_node.cond)

    if cond_rd.is_comptime_value():
      self.cur_builder.branch(llvm_block_loop if cond_rd.value else llvm_block_exit)
    else:
      self.llvm_cbranch(self.cur_builder, cond_rd.llvm_data, llvm_block_loop, llvm_block_exit)

    self.push_builder(ll.IRBuilder(llvm_block_loop))
    self.push_sub_scope()
    self.push_loop((llvm_block_check, llvm_block_exit))

    has_terminator = self.evaluate_block(while_node.body)
    self.fix_sub_scope_terminator(has_terminator, llvm_block_check)

    self.pop_loop()
    self.pop_scope()
    self.pop_builder()

    self.cur_builder = ll.IRBuilder(llvm_block_exit)

  def evaluate_true(self, node):
    return self.evaluate_truefalse(node, '1')

  def evaluate_truefalse(self, node, value):
    return self.evaluate_num(
      Node('num', value=value, pos=node.pos),
      realtype_to_use=self.ctx_if_numeric_or(RealType('u8_rt'))
    )

  def evaluate_false(self, node):
    return self.evaluate_truefalse(node, '0')

  def evaluate_continue_node_stmt(self, continue_node):
    if not self.inside_loop:
      error('use of `continue` statement outside of loop body', continue_node.pos)
    
    self.cur_builder.branch(self.loop[0])
  
  def evaluate_break_node_stmt(self, break_node):
    if not self.inside_loop:
      error('use of `break` statement outside of loop body', break_node.pos)
    
    self.cur_builder.branch(self.loop[1])

  def create_tmp_alloca_for_expraddr(self, realdata_expr):
    self.tmp_counter += 1

    tmp = self.allocas_builder.alloca(self.convert_realtype_to_llvmtype(realdata_expr.realtype), name=f'tmp.{self.tmp_counter}')
    self.llvm_store(self.cur_builder, realdata_expr.llvm_data, tmp)

    return tmp

  def evaluate_not_node(self, unary_node):
    realdata_expr = self.evaluate_node(unary_node.expr, self.ctx_if_int_or(RealType('u8_rt')))
    self.expect_realdata_is_integer(realdata_expr, unary_node.expr.pos)

    if realdata_expr.is_comptime_value():
      return RealData(
        realdata_expr.realtype,
        value=(new_value := int(not realdata_expr.value)),
        llvm_data=ll.Constant(self.convert_realtype_to_llvmtype(realdata_expr.realtype), new_value),
      )

    return RealData(
      realdata_expr.realtype,
      llvm_data=self.llvm_not(
        self.cur_builder,
        realdata_expr.llvm_data,
        self.convert_realtype_to_llvmtype(realdata_expr.realtype)
      )
    )

  def evaluate_reference_node(self, unary_node):
    realdata_expr = self.evaluate_node(
      unary_node.expr,
      self.ctx.type if self.ctx.is_ptr() else \
        self.ctx.fields['ptr'].type if self.ctx.could_be_fat_pointer() else \
          REALTYPE_PLACEHOLDER
    )

    if isinstance(realdata_expr.llvm_data, ll.LoadInstr):
      self.cur_builder.remove(realdata_expr.llvm_data)
      realdata_expr.llvm_data = realdata_expr.llvm_data.operands[0]
    else:
      if unary_node.is_mut:
        error('temporary expression allocation address cannot be mutable', unary_node.pos)

      realdata_expr.llvm_data = self.create_tmp_alloca_for_expraddr(realdata_expr)
    
    if self.ctx.could_be_fat_pointer() and realdata_expr.realtype.is_static_array():
      llvm_type = self.convert_realtype_to_llvmtype(self.ctx)
      ptr = self.cur_builder.bitcast(realdata_expr.llvm_data, llvm_type.elements[0])

      realdata_expr.llvm_data = self.llvm_insert_value(
        self.cur_builder, ll.Constant(llvm_type, ll.Undefined),
        ptr, 0, llvm_type.elements[0]
      )
      realdata_expr.llvm_data = self.llvm_insert_value(
        self.cur_builder, realdata_expr.llvm_data,
        ll.Constant(ll.IntType(64), realdata_expr.realtype.length), 1, llvm_type.elements[1]
      )
      realdata_expr.realtype = self.ctx
    else:
      realdata_expr.realtype = RealType('ptr_rt', is_mut=unary_node.is_mut, type=realdata_expr.realtype)

    return realdata_expr

  def evaluate_assignment_leftexpr_node(self, expr_node, assign_tok_pos):
    is_deref = self.is_deref_node(expr_node)
    is_index = self.is_index_node(expr_node)

    if is_index:
      old_expr_node = expr_node
      expr_node = expr_node.instance_expr
    elif is_deref:
      expr_node = expr_node.expr

    realdata_expr = self.evaluate_node(expr_node, REALTYPE_PLACEHOLDER)

    if is_index:
      if realdata_expr.realtype.is_ptr() and not realdata_expr.realtype.is_mut:
        error('cannot write at specific index to unmutable pointer', assign_tok_pos)
      
      expr_node = old_expr_node
      realdata_expr = self.internal_evaluate_index_node(expr_node, realdata_expr)
    
    allowed_opnames = ['load', 'bitcast'] if is_deref else ['load']

    if realdata_expr.llvm_data.opname not in allowed_opnames:
      error('cannot assign a value to an expression', expr_node.pos)
    
    if not is_deref:
      self.cur_builder.remove(realdata_expr.llvm_data)
      realdata_expr.llvm_data = realdata_expr.llvm_data.operands[0]
      realdata_expr.realtype = RealType('ptr_rt', is_mut=True, type=realdata_expr.realtype)

    return realdata_expr
  
  def evaluate_for_node_stmt(self, for_node):
    llvm_block_mid = self.cur_fn[1].append_basic_block('condcheck_block')
    llvm_block_loop = self.cur_fn[1].append_basic_block('loop_branch_block')
    llvm_block_right = self.cur_fn[1].append_basic_block('inc_branch_block')
    llvm_block_exit = self.cur_fn[1].append_basic_block('exit_branch_block')
    
    self.push_sub_scope()

    if for_node.left_node is not None:
      self.evaluate_var_decl_node_stmt(for_node.left_node)

    self.cur_builder.branch(llvm_block_mid)
    self.cur_builder = ll.IRBuilder(llvm_block_mid)

    cond_rd = self.evaluate_condition_node(for_node.mid_node)

    if cond_rd.is_comptime_value():
      self.cur_builder.branch(llvm_block_loop if cond_rd.value else llvm_block_exit)
    else:
      self.llvm_cbranch(self.cur_builder, cond_rd.llvm_data, llvm_block_loop, llvm_block_exit)

    self.push_builder(ll.IRBuilder(llvm_block_loop))
    self.push_loop((llvm_block_right, llvm_block_exit))

    has_terminator = self.evaluate_block(for_node.body)
    self.fix_sub_scope_terminator(has_terminator, llvm_block_right)

    self.push_builder(ll.IRBuilder(llvm_block_right))

    if for_node.right_node is not None:
      self.evaluate_stmt(for_node.right_node)

    self.cur_builder.branch(llvm_block_mid)
    self.pop_builder()

    self.pop_loop()
    self.pop_scope()
    self.pop_builder()

    self.cur_builder = ll.IRBuilder(llvm_block_exit)

  def evaluate_assignment_node_stmt(self, assignment_node):
    is_discard = assignment_node.lexpr.kind == '..'

    realdata_lexpr = self.evaluate_assignment_leftexpr_node(assignment_node.lexpr, assignment_node.pos) if not is_discard else None
    realdata_rexpr = self.evaluate_node(assignment_node.rexpr, realdata_lexpr.realtype.type if not is_discard else REALTYPE_PLACEHOLDER)

    if not is_discard:
      self.expect_realtype(realdata_lexpr.realtype.type, realdata_rexpr.realtype, assignment_node.pos)

    if not is_discard and not realdata_lexpr.realtype.is_mut:
      error('cannot write to unmutable pointer', assignment_node.pos)

    if is_discard and assignment_node.op.kind != '=':
      error('discard statement only accepts `=` as operator', assignment_node.pos)

    llvm_rexpr = {
      '=': lambda: realdata_rexpr.llvm_data,
      '+=': lambda: self.cur_builder.add(self.llvm_load(self.cur_builder, realdata_lexpr.llvm_data, self.convert_realtype_to_llvmtype(realdata_rexpr.realtype)), realdata_rexpr.llvm_data),
      '-=': lambda: self.cur_builder.sub(self.llvm_load(self.cur_builder, realdata_lexpr.llvm_data, self.convert_realtype_to_llvmtype(realdata_rexpr.realtype)), realdata_rexpr.llvm_data),
      '*=': lambda: self.cur_builder.mul(self.llvm_load(self.cur_builder, realdata_lexpr.llvm_data, self.convert_realtype_to_llvmtype(realdata_rexpr.realtype)), realdata_rexpr.llvm_data),
    }[assignment_node.op.kind]()

    if not is_discard:
      self.llvm_store(self.cur_builder, llvm_rexpr, realdata_lexpr.llvm_data)

  def evaluate_stmt(self, stmt):
    try:
      attr = getattr(self, f'evaluate_{stmt.kind}_stmt')
    except AttributeError:
      realdata = self.evaluate_node(stmt, REALTYPE_PLACEHOLDER, is_stmt=True)

      if not realdata.realtype.is_void():
        error(f'undiscarded expression of type `{realdata.realtype}` as statement', stmt.pos)
      
      return
    
    attr(stmt)
  
  def evaluate_chr(self, tok):
    return self.evaluate_num(
      Node(
        'num',
        value=str(ord(tok.value)),
        pos=tok.pos
      ),
      realtype_to_use=self.ctx_if_int_or(RealType('u8_rt'))
    )

  def evaluate_str(self, tok):
    llvm_data = self.cache_string(tok.value, use_bitcast=self.ctx != CSTRING_REALTYPE)
    
    agg = ll.Constant(self.convert_realtype_to_llvmtype(STRING_REALTYPE), ll.Undefined)
    llvm_data = self.llvm_insert_value(self.cur_builder, agg, llvm_data, 0, self.convert_realtype_to_llvmtype(CSTRING_REALTYPE))
    llvm_data = self.llvm_insert_value(self.cur_builder, llvm_data, ll.Constant(ll.IntType(64), len(tok.value)), 1, ll.IntType(64))

    return RealData(
      STRING_REALTYPE,
      realtype_is_coerced=None,
      value=tok.value,
      llvm_data=llvm_data
    )

  def cache_string(self, string, use_bitcast=True):
    if string not in self.strings:
      self.str_counter += 1
      llvm_data = self.strings[string] = ll.GlobalVariable(
        self.output,
        t := ll.ArrayType(ll.IntType(8), len(string) + 1),
        self.fixname_for_llvm(f'str.{self.str_counter}')
      )

      # llvm_data.linkage = 'private'
      llvm_data.initializer = ll.Constant(t, bytearray((string + '\0').encode('ascii')))
    else:
      llvm_data = self.strings[string]

    return \
      self.cur_builder.bitcast(llvm_data, ll.PointerType(ll.IntType(8))) \
        if use_bitcast else llvm_data

  def evaluate_block(self, block):
    for stmt in block:
      if self.cur_builder.block.is_terminated:
        error('unreachable code', stmt.pos)

      self.evaluate_stmt(stmt)
    
    return self.cur_builder.block.is_terminated
  
  def evaluate_inline_if_node(self, inline_if_node):
    cond_rd = self.evaluate_condition_node(inline_if_node.if_cond)

    if cond_rd.is_comptime_value():
      return self.evaluate_node(
        inline_if_node.if_expr if cond_rd.value else inline_if_node.else_expr,
        self.ctx
      )

    llvm_block_if_branch = self.cur_fn[1].append_basic_block('inline_if_branch_block')
    llvm_block_else_branch = self.cur_fn[1].append_basic_block('inline_else_branch_block')
    llvm_exit_block = self.cur_fn[1].append_basic_block('exit_block')
    
    self.llvm_cbranch(self.cur_builder, cond_rd.llvm_data, llvm_block_if_branch, llvm_block_else_branch)

    self.push_builder(ll.IRBuilder(llvm_block_if_branch))
    if_realdata = self.evaluate_node(inline_if_node.if_expr, self.ctx)
    self.cur_builder.branch(llvm_exit_block)
    self.pop_builder()

    realtype = if_realdata.realtype

    self.push_builder(ll.IRBuilder(llvm_block_else_branch))
    else_realdata = self.evaluate_node(inline_if_node.else_expr, realtype)
    self.cur_builder.branch(llvm_exit_block)
    self.pop_builder()

    self.expect_realtype_are_compatible(if_realdata.realtype, else_realdata.realtype, inline_if_node.else_expr.pos)

    self.cur_builder = ll.IRBuilder(llvm_exit_block)
    return RealData(
      realtype,
      llvm_data=self.llvm_phi(
        self.cur_builder,
        [(if_realdata.llvm_data, llvm_block_if_branch), (else_realdata.llvm_data, llvm_block_else_branch)],
        self.convert_realtype_to_llvmtype(realtype)
      )
    )
  
  def evaluate_union_init_node(self, init_node):
    field_node = init_node.fields[0]
    
    if not self.ctx.is_union():
      error('union constructor has an unclear type here', init_node.pos)
    
    if field_node.name.value not in self.ctx.fields:
      error(f'this union field is not present in the contect union type `{self.ctx}`', field_node.pos)
    
    ctx_type = self.ctx.fields[field_node.name.value]
    llvm_type = self.convert_realtype_to_llvmtype(ctx_type)
    realdata = self.evaluate_node(field_node.expr, ctx_type)
    self.expect_realtype(ctx_type, realdata.realtype, field_node.expr.pos)

    alloca = self.allocas_builder.alloca(self.convert_realtype_to_llvmtype(self.ctx), name='union.tmp')
    alloca_bitcast = self.cur_builder.bitcast(alloca, ll.PointerType(llvm_type))
    self.cur_builder.store(realdata.llvm_data, alloca_bitcast)

    return RealData(
      self.ctx,
      llvm_data=self.cur_builder.load(alloca)
    )

  def convert_realtype_to_llvmtype(self, realtype, in_progress_struct_rd_ids=[]):
    if realtype.is_int():
      return ll.IntType(realtype.bits)
    
    if realtype.is_float():
      return {
        32: ll.FloatType(),
        64: ll.DoubleType(),
      }[realtype.bits]
    
    match realtype.kind:
      case 'ptr_rt':
        return ll.PointerType(self.convert_realtype_to_llvmtype(realtype.type, in_progress_struct_rd_ids))
      
      case 'void_rt':
        return ll.VoidType()
      
      case 'union_rt':
        return ll.IntType(realtype.calculate_size() * 8)
      
      case 'static_array_rt':
        return ll.ArrayType(self.convert_realtype_to_llvmtype(realtype.type, in_progress_struct_rd_ids), realtype.length)

      case 'struct_rt':
        if id(realtype) in in_progress_struct_rd_ids:
          return ll.IntType(1)

        return ll.LiteralStructType(list(map(
          lambda field: self.convert_realtype_to_llvmtype(field[1], in_progress_struct_rd_ids + [id(realtype)]),
          realtype.fields.items()
        )))

      case 'fn_rt':
        return ll.FunctionType(
          self.convert_realtype_to_llvmtype(realtype.ret_type, in_progress_struct_rd_ids),
          [self.convert_realtype_to_llvmtype(
            arg_type,
            in_progress_struct_rd_ids
          ) for arg_type in realtype.arg_types]
        )
      
      case 'placeholder_rt':
        return ll.IntType(2)

      case _:
        raise NotImplementedError()

  def convert_proto_to_llvmproto(self, proto):
    match proto.kind:
      case 'fn_proto':
        return ll.FunctionType(
          self.convert_realtype_to_llvmtype(proto.ret_type),
          [self.convert_realtype_to_llvmtype(arg_type) for arg_type in proto.arg_types]
        )

      case _:
        raise NotImplementedError()

  def evaluate_defer_nodes(self):
    if len(self.defer_stmts) == 0 or len(self.defer_nodes) == 0:
      return

    terminator = None
    if self.cur_builder.block.is_terminated:
      terminator = self.cur_builder.block.terminator
      self.cur_builder.remove(terminator)
    
    allocas_terminator = None
    if self.allocas_builder.block.is_terminated:
      allocas_terminator = self.allocas_builder.block.terminator
      self.allocas_builder.remove(allocas_terminator)
    
    for node in self.defer_nodes:
      self.evaluate_stmt(node)
    
    if terminator is not None:
      self.cur_builder.append(terminator)
    
    if allocas_terminator is not None:
      self.allocas_builder.append(allocas_terminator)

  def fixname_for_llvm(self, name):
    return f'{self.path}::{name}'

  def create_llvm_function(self, fn_name, proto):
    llvm_fn = ll.Function(
      self.output,
      self.convert_proto_to_llvmproto(proto),
      self.fixname_for_llvm(fn_name)
    )

    llvm_fn.linkage = 'private'
    return llvm_fn

  def push_ctx(self, realtype):
    self.ctx_types.append(realtype)

  def pop_ctx(self):
    self.ctx_types.pop()

  def push_builder(self, llvmbuilder):
    self.llvm_builders.append(llvmbuilder)

  def pop_builder(self):
    self.llvm_builders.pop()
  
  def llvm_load(self, builder, ptr, resulting_llvm_type):
    ptr = builder.bitcast(ptr, ll.PointerType(resulting_llvm_type))
    return builder.load(ptr)
  
  def llvm_gep(self, builder, ptr, indices, inbounds, real_expected_value_llvm_type=None):
    if real_expected_value_llvm_type is not None:
      real_expected_value_llvm_type = ll.PointerType(real_expected_value_llvm_type)
      ptr = builder.bitcast(ptr, real_expected_value_llvm_type)

    return builder.gep(ptr, indices, inbounds=inbounds)
  
  def llvm_insert_value(self, builder, agg, value, idx, real_expected_value_llvm_type):
    if isinstance(value.type, ll.PointerType):
      value = builder.bitcast(value, real_expected_value_llvm_type)

    return builder.insert_value(agg, value, idx)
  
  def llvm_extract_value(self, builder, agg, idx, resulting_llvm_type):
    r = builder.extract_value(agg, idx)

    if isinstance(resulting_llvm_type, ll.PointerType):
      r = builder.bitcast(r, resulting_llvm_type)
    
    return r
  
  def llvm_ret(self, builder, value, real_expected_value_llvm_type):
    if isinstance(value.type, ll.PointerType):
      value = builder.bitcast(value, real_expected_value_llvm_type)

    return builder.ret(value)
  
  def llvm_cbranch(self, builder, cond, truebr, falsebr):
    return builder.cbranch(
      builder.trunc(cond, ll.IntType(1)),
      truebr,
      falsebr
    )
  
  def llvm_icmp(self, builder, is_signed, op, value1, value2, llvm_type_the_result_should_be):
    llvm_fn = builder.icmp_signed if is_signed else builder.icmp_unsigned
    return builder.zext(
      llvm_fn(op, value1, value2),
      llvm_type_the_result_should_be
    )
  
  def llvm_fcmp(self, builder, op, value1, value2, llvm_type_the_result_should_be):
    return builder.zext(
      builder.fcmp_ordered(op, value1, value2),
      llvm_type_the_result_should_be
    )

  def llvm_phi(self, builder, incomings, llvm_type_the_resulting_should_be):
    p = builder.phi(llvm_type_the_resulting_should_be)

    for incoming in incomings:
      p.add_incoming(*incoming)

    return p

  def llvm_not(self, builder, value, llvm_type_the_resulting_should_be):
    return builder.zext(
      builder.icmp_signed('==', value, ll.Constant(llvm_type_the_resulting_should_be, 0)),
      llvm_type_the_resulting_should_be
    )

  def llvm_store(self, builder, value, ptr):
    ptr = builder.bitcast(ptr, ll.PointerType(value.type))
    return builder.store(value, ptr)
  
  def llvm_call(self, builder, fn, args):
    for i, arg in enumerate(args):
      if isinstance(arg.type, ll.PointerType):
        args[i] = builder.bitcast(arg, fn.ftype.args[i])

    return builder.call(fn, args)

  def declare_parameters(self, proto, fn_args):
    for i, (arg_name, arg_realtype) in enumerate(zip(map(lambda a: a.name, fn_args), proto.arg_types)):
      llvm_data = self.allocas_builder.alloca(self.convert_realtype_to_llvmtype(arg_realtype), name=f'arg.{i + 1}')
      self.llvm_store(self.cur_builder, self.cur_fn[1].args[i], llvm_data)

      sym = Symbol(
        'local_var_sym',
        is_comptime=False,
        realtype=arg_realtype,
        llvm_data=llvm_data,
        realdata=None
      )

      self.declare_symbol(arg_name.value, sym, arg_name.pos)

  def gen_nongeneric_fn(self, fn):
    key = id(fn)

    if key in self.fn_in_evaluation:
      return self.fn_in_evaluation[key]
    
    if key in self.fn_evaluated:
      return self.fn_evaluated[key]

    self.push_scope()

    t = self.gen_fn(fn, fn.node.name.value, key)

    self.pop_scope()

    return t
  
  def declare_generics(self, generic_params, rt_generic_args):
    for param, rt_arg in zip(generic_params, rt_generic_args):
      self.declare_symbol(
        param.value,
        Symbol('alias_sym', realtype=rt_arg),
        param.pos
      )

  def gen_generic_fn(self, fn, rt_generics):
    key = (id(fn), rt_generics)

    if key in self.fn_in_evaluation:
      return self.fn_in_evaluation[key]
    
    if key in self.fn_evaluated:
      return self.fn_evaluated[key]
    
    # pushing the scope for the generics
    self.push_scope()
    self.declare_generics(fn.node.generics, rt_generics)

    fn_name = f'generic.{fn.node.name.value}<{", ".join(map(repr, rt_generics))}>'
    r = self.gen_fn(fn, fn_name, key)

    # popping the scope for the generics
    self.pop_scope()

    return r

  def gen_fn(self, fn, fn_name, key):
    proto = self.evaluate_fn_proto(fn.node)
    llvmfn = self.create_llvm_function(fn_name, proto)
  
    llvmfn_allocas_bb = llvmfn.append_basic_block('allocas')
    llvmfn_entry_bb = llvmfn.append_basic_block('entry')
  
    llvmbuilder_allocas = ll.IRBuilder(llvmfn_allocas_bb)
    llvmbuilder_entry = ll.IRBuilder(llvmfn_entry_bb)

    r = self.fn_in_evaluation[key] = (
      proto,
      llvmfn,
      llvmbuilder_allocas
    )

    old_loops = self.loops
    self.loops = []

    self.push_builder(llvmbuilder_entry)
    self.push_sub_scope()

    self.declare_parameters(proto, fn.node.args)
    has_terminator = self.evaluate_block(fn.node.body)
    llvmbuilder_allocas.branch(llvmfn_entry_bb)
    self.remove_dead_blocks()
    self.fix_ret_terminator(has_terminator, fn.node.pos)

    self.pop_scope()
    self.pop_builder()

    self.loops = old_loops
  
    self.fn_in_evaluation.remove_by_key(key)
    self.fn_evaluated[key] = r

    return r
  
  def remove_dead_blocks(self):
    alive_blocks = []

    for block in self.cur_fn[1].blocks:
      if not block.is_dead():
        alive_blocks.append(block)
    
    self.cur_fn[1].blocks = alive_blocks
  
  def fix_ret_terminator(self, has_terminator, fn_pos):
    if has_terminator:
      return
    
    if self.cur_fn[0].is_test:
      self.cur_builder.ret(ll.Constant(ll.IntType(32), 0))
      return
    
    if self.cur_fn[0].ret_type.is_void():
      self.cur_builder.ret_void()
      return

    if self.cur_builder.block.is_dead():
      return

    error('not all paths return a value', fn_pos)
  
  def push_sub_scope(self):
    self.defer_stmts.append([])
    self.maps.append(self.maps[-1].copy())
  
  def push_scope(self):
    self.defer_stmts.append([])
    self.maps.append(self.base_map.copy())
  
  def pop_scope(self):
    self.evaluate_defer_nodes()
    self.maps.pop()
    self.defer_stmts.pop()

def get_main(g):
  return g.base_map.get_symbol('main', None)

def check_sym_is_fn(sym_id, sym):
  if sym.kind == 'fn_sym':
    return

  error(f'`{sym_id}` is not a function', sym.node.pos)

def check_sym_is_type(name_tok, sym):
  if sym.kind == 'type_sym':
    return

  error(f'`{name_tok.value}` is not a type', name_tok.pos)

def check_sym_is_generic_type(name_tok, sym):
  if sym.kind == 'generic_type_sym':
    return

  error(f'`{name_tok.value}` is not a generic type', name_tok.pos)

def check_sym_is_local_or_global_var(name_tok, sym):
  if sym.kind in ['local_var_sym', 'global_var_sym']:
    return

  error(f'`{name_tok.value}` is not a variable', name_tok.pos)

def check_main_proto(main_proto, main_pos):
  throw_error = lambda: error('invalid `main` prototype', main_pos)

  if len(main_proto.arg_types) != 2:
    throw_error()
  
  if main_proto.arg_types != [
    RealType('u32_rt'),
    RealType('ptr_rt', is_mut=False, type=CSTRING_REALTYPE)
  ]:
    throw_error()

  if main_proto.ret_type.kind != 'i32_rt':
    throw_error()

def gen_llvm_main(llvm_internal_main, g):
  if llvm_internal_main is None:
    return ll.Function(
      g.output,
      ll.FunctionType(ll.IntType(32), []),
      'main'
    )

  llvm_main = ll.Function(g.output,
    ll.FunctionType(
      ll.IntType(32),
      [
        ll.IntType(32),
        ll.PointerType(ll.PointerType(ll.IntType(8)))
      ]
    ),
    'main'
  )

  entry = ll.IRBuilder(llvm_main.append_basic_block('entry'))
  entry.ret(
    entry.call(llvm_internal_main, [llvm_main.args[0], llvm_main.args[1]])
  )

def gen_tests(g):
  test_identifiers_and_llvm_fns = {}

  for t in g.tests:
    test_identifier = f'test.`{t.desc}`'
    
    if test_identifier in test_identifiers_and_llvm_fns:
      error('dupplicate test', t.pos)
    
    test_sym = Symbol('test_sym', generator=g, node=Node(
      'fn_node',
      name=Node('id', value=test_identifier, pos=t.desc.pos),
      args=[],
      ret_type=Node('id', value='i32', pos=t.pos),
      body=t.body,
      pos=t.pos,
      is_test=True
    ))
  
    _, llvm_fn, _ = g.gen_nongeneric_fn(test_sym)

    test_identifiers_and_llvm_fns[test_identifier] = (t, llvm_fn)
  
  llvm_main = gen_llvm_main(None, g)
  llvm_builder = ll.IRBuilder(llvm_main.append_basic_block('entry'))
  llvm_puts = g.cache_lib_fn('puts', RealType('i32_rt'), [CSTRING_REALTYPE])
  llvm_cstring = ll.PointerType(ll.IntType(8))

  for test_id, (test_node, llvm_fn_test) in test_identifiers_and_llvm_fns.items():
    failurebr = ll.IRBuilder(llvm_main.append_basic_block('failure_branch'))
    successebr = ll.IRBuilder(llvm_main.append_basic_block('success_branch'))
    newbr = ll.IRBuilder(llvm_main.append_basic_block('entry'))
    success_message = f'[.] passed test at {repr_pos(test_node.pos, use_path=True)}: {test_node.desc}'
    failure_message = f'[X] failed test at {repr_pos(test_node.pos, use_path=True)}: {test_node.desc}'

    # running the test
    llvm_test_result = llvm_builder.call(llvm_fn_test, [])
    # checking if the test passed
    llvm_cmp = llvm_builder.icmp_signed('!=', llvm_test_result, ll.Constant(ll.IntType(32), 0))
    llvm_builder.cbranch(llvm_cmp, failurebr.block, successebr.block)

    # printing success message
    llvm_success_message = successebr.bitcast(g.cache_string(success_message, use_bitcast=False), llvm_cstring)
    successebr.call(llvm_puts, [llvm_success_message])
    successebr.branch(newbr.block)

    # printing failure message
    llvm_failure_message = failurebr.bitcast(g.cache_string(failure_message, use_bitcast=False), llvm_cstring)
    failurebr.call(llvm_puts, [llvm_failure_message])
    failurebr.branch(newbr.block)
    
    # keep running remaining tests
    llvm_builder = newbr
  
  llvm_builder.ret(ll.Constant(ll.IntType(32), 0))

def gen(g):
  main = get_main(g)

  check_sym_is_fn('main', main)
  main_proto, _, _ = g.gen_nongeneric_fn(main)
  check_main_proto(main_proto, main.node.pos)

  gen_llvm_main(g.fn_evaluated[id(main)][1], g)
