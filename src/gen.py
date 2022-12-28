import llvmlite.ir as ll

from data import ComparatorDict, MappedAst, Node, Proto, RealData, RealType, Symbol
from utils import error

REALTYPE_PLACEHOLDER = RealType('placeholder_rt')

class Generator:
  def __init__(self, map):
    self.maps = [map]
    self.output = ll.Module()
    self.fn_in_evaluation = ComparatorDict()
    self.fn_evaluated = ComparatorDict()
    self.llvm_builders = [] # the last one is the builder in use
    self.ctx_types = []
    self.loops = []
    self.tmp_counter = 0
  
  @property
  def map(self) -> MappedAst:
    return self.maps[-1]

  @property
  def cur_fn(self) -> ll.Function:
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

  def push_loop(self, loop):
    # loop = (condition_checker_block, exit_block)
    self.loops.append(loop)

  def pop_loop(self):
    self.loops.pop()

  def make_proto(self, kind, **kwargs):
    return Proto(kind, **kwargs)

  def evaluate_builtin_type(self, name):
    try:
      return {
        'i8': RealType('i8_rt'),
        'i16': RealType('i16_rt'),
        'i32': RealType('i32_rt'),
        'i64': RealType('i64_rt'),

        'u8': RealType('u8_rt'),
        'u16': RealType('u16_rt'),
        'u32': RealType('u32_rt'),
        'u64': RealType('u64_rt')
      }[name]
    except KeyError:
      pass

  def evaluate_named_type(self, type_node):
    sym = self.map.get_symbol(type_node.value, type_node.pos)

    if sym.kind == 'alias_sym':
      return sym.realtype

    check_sym_is_type(type_node.value, sym)

    return self.evaluate_type(sym.node.type)

  def evaluate_type(self, type_node):
    match type_node.kind:
      case 'id':
        t = self.evaluate_builtin_type(type_node.value)

        return t if t is not None else self.evaluate_named_type(type_node)
      
      case 'ptr_type_node':
        return RealType('ptr_rt', is_mut=type_node.is_mut, type=self.evaluate_type(type_node.type))
      
      case 'struct_type_node':
        field_names = list(map(lambda field: field.name.value, type_node.fields))

        for i, field_name in enumerate(field_names):
          if field_names.count(field_name) > 1:
            error(f'field `{field_name}` is dupplicate', type_node.fields[i].name.pos)
        
        return RealType(
          'struct_rt',
          fields={
            field.name.value: self.evaluate_type(field.type) for field in type_node.fields
          }
        )

      case _:
        raise NotImplementedError()

  def evaluate_fn_proto(self, fn_node):
    arg_types = [self.evaluate_type(arg.type) for arg in fn_node.args]
    ret_type = self.evaluate_type(fn_node.ret_type)

    return self.make_proto(
      'fn_proto',
      arg_types=arg_types,
      ret_type=ret_type
    )

  def expect(self, cond, error_msg, pos):
    if cond:
      return

    error(error_msg, pos)

  def evaluate_num(self, num_tok, realtype_to_use=None):
    realtype = \
      realtype_to_use \
        if realtype_to_use is not None else \
          self.ctx if self.ctx.is_int() else RealType('i32_rt')

    value = int(num_tok.value)
    
    return RealData(
      realtype,
      value=value,
      llvm_data=ll.Constant(self.convert_realtype_to_llvmtype(realtype), value)
    )

  def evaluate_uninitialized(self, dd_node):
    if self.ctx.kind == 'placeholder_rt':
      error('uninitialized term has no clear type here', dd_node.pos)

    return RealData(
      self.ctx,
      value=None,
      llvm_data=ll.Constant(self.convert_realtype_to_llvmtype(self.ctx), ll.Undefined)
    )

  def evaluate_node(self, node, new_ctx):
    if new_ctx is not None:
      self.push_ctx(new_ctx)
    
    t = getattr(self, f'evaluate_{node.kind}')(node)

    if new_ctx is not None:
      self.pop_ctx()

    return t

  def expect_realtype(self, rt1, rt2, pos):
    if rt1 == rt2:
      return
    
    error(f'expected `{rt1}`, found `{rt2}`', pos)

  def evaluate_null(self, null_tok):
    realtype = self.ctx if self.ctx.is_int() or self.ctx.is_ptr() else RealType('ptr_rt', is_mut=False, type=RealType('u8_rt'))
    llvm_data = ll.Constant(self.convert_realtype_to_llvmtype(realtype), None if realtype.is_ptr() else 0)
    
    return RealData(
      realtype,
      value=0,
      llvm_data=llvm_data
    )

  def evaluate_id(self, id_tok):
    sym = self.map.get_symbol(id_tok.value, id_tok.pos)
    llvm_data = self.cur_builder.load(sym.llvm_alloca)
    
    return RealData(
      sym.realtype,
      llvm_data=llvm_data
    )

  def generate_llvm_bin(self, realdata_left, op, realdata_right):
    match op.kind:
      case '+': return self.cur_builder.add(realdata_left.llvm_data, realdata_right.llvm_data)
      case '-': return self.cur_builder.sub(realdata_left.llvm_data, realdata_right.llvm_data)
      case '*': return self.cur_builder.mul(realdata_left.llvm_data, realdata_right.llvm_data)
      case '/': return self.cur_builder.sdiv(realdata_left.llvm_data, realdata_right.llvm_data)

      case '==' | '!=' | '<' | '>' | '<=' | '>=':
        return self.cur_builder.icmp_signed(op.kind, realdata_left.llvm_data, realdata_right.llvm_data)

      case _:
        raise NotImplementedError()

  def compute_comptime_bin(self, realdata_left, op, realdata_right):
    match op.kind:
      case '+': return realdata_left.value + realdata_right.value
      case '-': return realdata_left.value - realdata_right.value
      case '*': return realdata_left.value * realdata_right.value
      case '/': return realdata_left.value / realdata_right.value

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

  def expect_realdata_is_struct(self, realdata, pos):
    if realdata.realtype.is_struct():
      return
    
    error(f'expected struct expression, got `{realdata.realtype}`', pos)

  def expect_realdata_is_numeric(self, realdata, pos):
    if realdata.realtype.is_numeric():
      return
    
    error(f'expected numeric expression, got `{realdata.realtype}`', pos)

  def evaluate_bin_node(self, bin_node):
    realdata_left = self.evaluate_node(bin_node.left, REALTYPE_PLACEHOLDER)
    realdata_right = self.evaluate_node(bin_node.right, REALTYPE_PLACEHOLDER)

    self.expect_realdata_is_numeric(realdata_left, bin_node.left.pos)
    self.expect_realdata_is_numeric(realdata_right, bin_node.right.pos)

    if realdata_left.realtype_is_coercable():
      realdata_left.realtype = realdata_right.realtype

    if realdata_right.realtype_is_coercable():
      realdata_right.realtype = realdata_left.realtype

    if realdata_left.is_comptime_value() and realdata_right.is_comptime_value():
      self.expect_realtype_are_compatible(realdata_left.realtype, realdata_right.realtype, bin_node.pos)

      return self.evaluate_num(
        Node(
          'num',
          value=str(self.compute_comptime_bin(realdata_left, bin_node.op, realdata_right)),
          pos=bin_node.pos
        ),
        realtype_to_use=realdata_left.realtype
      )
    
    if realdata_left.is_comptime_value():
      new_realtype = realdata_left.realtype = realdata_right.realtype
      realdata_left.llvm_data = ll.Constant(self.convert_realtype_to_llvmtype(new_realtype), realdata_left.llvm_data.constant)
    
    if realdata_right.is_comptime_value():
      # if bin_node.op.kind in ['/', '%'] and realdata_right.value == 0:
      #   error('dividing by `0`', bin_node.pos)

      new_realtype = realdata_right.realtype = realdata_left.realtype
      realdata_right.llvm_data = ll.Constant(self.convert_realtype_to_llvmtype(new_realtype), realdata_right.llvm_data.constant)

    self.expect_realtype_are_compatible(realdata_left.realtype, realdata_right.realtype, bin_node.pos)

    realtype = realdata_left.realtype
    llvm_data = self.generate_llvm_bin(realdata_left, bin_node.op, realdata_right)

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
  
  def evaluate_dot_node(self, dot_node):
    instance_realdata = self.evaluate_node(dot_node.left_expr, REALTYPE_PLACEHOLDER)
    field_name = dot_node.right_expr.value

    self.expect_realdata_is_struct(instance_realdata, dot_node.pos)

    if field_name not in instance_realdata.realtype.fields:
      error(f'struct `{instance_realdata.realtype}` has no field `{field_name}`', dot_node.pos)

    field_index = list(instance_realdata.realtype.fields.keys()).index(field_name)

    if isinstance(instance_realdata.llvm_data, ll.LoadInstr):
      self.cur_builder.remove(instance_realdata.llvm_data)
      instance_realdata.llvm_data = instance_realdata.llvm_data.operands[0]

      llvm_data = self.cur_builder.load(self.cur_builder.gep(
        instance_realdata.llvm_data,
        [ll.Constant(ll.IntType(32), 0), ll.Constant(ll.IntType(32), field_index)],
        inbounds=True
      ))
    else:
      llvm_data = self.cur_builder.extract_value(instance_realdata.llvm_data, field_index)

    return RealData(
      instance_realdata.realtype.fields[field_name],
      llvm_data=llvm_data
    )
  
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
      llvm_data = self.cur_builder.insert_value(llvm_data, field_realdata.llvm_data, i)

    return RealData(
      realtype,
      llvm_data=llvm_data
    )

  def make_numeric_cast(self, realdata_expr, target_rt):
    source_bits = realdata_expr.realtype.bits
    target_bits = target_rt.bits

    if source_bits == target_bits and realdata_expr.realtype.is_signed == target_rt.is_signed:
      return
    
    llvm_caster = self.cur_builder.sext if source_bits < target_bits else self.cur_builder.trunc

    realdata_expr.realtype = target_rt
    realdata_expr.llvm_data = llvm_caster(
      realdata_expr.llvm_data,
      self.convert_realtype_to_llvmtype(target_rt)
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

  def expect_realdata_is_ptr(self, realdata, pos):
    if realdata.realtype.is_ptr():
      return
    
    error(f'expected pointer expression, got `{realdata.realtype}`', pos)

  def evaluate_unary_node(self, unary_node):
    match unary_node.op.kind:
      case '&':
        return self.evaluate_reference_node(unary_node)
    
      case '*':
        realdata_expr = self.evaluate_node(unary_node.expr, self.ctx)
        self.expect_realdata_is_ptr(realdata_expr, unary_node.expr.pos)

        return RealData(
          realdata_expr.realtype.type,
          llvm_data=self.cur_builder.load(realdata_expr.llvm_data)
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

  def evaluate_var_decl_node_stmt(self, var_decl_node):
    realtype = self.evaluate_type(var_decl_node.type)
    realdata = self.evaluate_node(var_decl_node.expr, realtype)

    self.expect_realtype(realtype, realdata.realtype, var_decl_node.expr.pos)

    llvm_alloca = self.allocas_builder.alloca(self.convert_realtype_to_llvmtype(realtype), name=var_decl_node.name.value)

    self.cur_builder.store(realdata.llvm_data, llvm_alloca)

    sym = Symbol(
      'local_var_sym',
      is_imported=False,
      realtype=realtype,
      llvm_alloca=llvm_alloca
    )

    self.map.declare_symbol(var_decl_node.name.value, sym, var_decl_node.name.pos)

  def evaluate_if_node_stmt(self, if_node):
    has_else_branch = if_node.else_branch is not None
    
    llvm_block_if_branch = self.cur_fn[1].append_basic_block('if_branch_block')
    llvm_block_elif_condcheckers = [self.cur_fn[1].append_basic_block('elif_condchecker') for _ in if_node.elif_branches]
    llvm_block_elif_branches = [self.cur_fn[1].append_basic_block('elif_branch_block') for _ in if_node.elif_branches]
    llvm_block_else_branch = self.cur_fn[1].append_basic_block('else_branch_block') if has_else_branch else None
    llvm_exit_block = self.cur_fn[1].append_basic_block('exit_block')

    cond_rd = self.evaluate_node(if_node.if_branch.cond, RealType('u8_rt'))
    self.expect_realdata_is_numeric(cond_rd, if_node.if_branch.cond.pos)

    false_br = llvm_block_elif_condcheckers[0] if len(llvm_block_elif_branches) > 0 else llvm_block_else_branch if has_else_branch else llvm_exit_block

    if cond_rd.is_comptime_value():
      self.cur_builder.branch(llvm_block_if_branch if cond_rd.value else false_br)
    else:
      self.cur_builder.cbranch(cond_rd.llvm_data, llvm_block_if_branch, false_br)

    self.push_sub_scope()
    self.push_builder(ll.IRBuilder(llvm_block_if_branch))
    has_terminator = self.evaluate_block(if_node.if_branch.body)
    self.fix_sub_scope_terminator(has_terminator, llvm_exit_block)
    self.pop_builder()
    self.pop_scope()

    for i, elif_branch in enumerate(if_node.elif_branches):
      self.push_builder(ll.IRBuilder(llvm_block_elif_condcheckers[i]))

      cond_rd = self.evaluate_node(elif_branch.cond, RealType('u8_rt'))
      self.expect_realdata_is_numeric(cond_rd, elif_branch.cond.pos)

      false_br = llvm_block_elif_condcheckers[i + 1] if i + 1 < len(llvm_block_elif_branches) else llvm_block_else_branch if has_else_branch else llvm_exit_block

      if cond_rd.is_comptime_value():
        self.cur_builder.branch(llvm_block_elif_branches[i] if cond_rd.value else false_br)
      else:
        self.cur_builder.cbranch(cond_rd.llvm_data, llvm_block_elif_branches[i], false_br)

      self.pop_builder()
      
      self.push_sub_scope()
      self.push_builder(ll.IRBuilder(llvm_block_elif_branches[i]))
      has_terminator = self.evaluate_block(elif_branch.body)
      self.fix_sub_scope_terminator(has_terminator, llvm_exit_block)
      self.pop_builder()
      self.pop_scope()

    if has_else_branch:
      self.push_sub_scope()
      self.push_builder(ll.IRBuilder(llvm_block_else_branch))
      has_terminator = self.evaluate_block(if_node.else_branch.body)
      self.fix_sub_scope_terminator(has_terminator, llvm_exit_block)
      self.pop_builder()
      self.pop_scope()

    self.cur_builder = ll.IRBuilder(llvm_exit_block)
  
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

    expr = self.evaluate_node(return_node.expr, cur_fn_ret_type)

    self.expect_realtype(cur_fn_ret_type, expr.realtype, return_node.expr.pos)

    self.cur_builder.ret(expr.llvm_data)
  
  def evaluate_generics_in_call(self, generic_type_nodes):
    return list(map(lambda node: self.evaluate_type(node), generic_type_nodes))

  def evaluate_call_node(self, call_node):
    fn = self.map.get_symbol(call_node.name.value, call_node.name.pos)
    check_sym_is_fn(call_node.name.value, fn)

    if len(call_node.generics) != len(fn.node.generics):
      error(f'expected `{len(fn.node.generics)}` generic args, got `{len(call_node.generics)}`', call_node.pos)

    if len(call_node.args) != len(fn.node.args):
      error(f'expected `{len(fn.node.args)}` args, got `{len(call_node.args)}`', call_node.pos)

    proto, llvmfn, _ = \
      self.gen_nongeneric_fn(fn) \
        if len(fn.node.generics) == 0 else \
          self.gen_generic_fn(fn, self.evaluate_generics_in_call(call_node.generics))

    realdata_args = []
    
    for i, arg_node in enumerate(call_node.args):
      realdata_args.append(realdata_arg := self.evaluate_node(arg_node, proto_arg_type := proto.arg_types[i]))
      self.expect_realtype(proto_arg_type, realdata_arg.realtype, arg_node.pos)

    llvm_args = list(map(lambda arg: arg.llvm_data, realdata_args))
    llvm_call = self.cur_builder.call(llvmfn, llvm_args)

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

    cond_rd = self.evaluate_node(while_node.cond, RealType('u8_rt'))
    self.expect_realdata_is_numeric(cond_rd, while_node.cond.pos)

    if cond_rd.is_comptime_value():
      self.cur_builder.branch(llvm_block_loop if cond_rd.value else llvm_block_exit)
    else:
      self.cur_builder.cbranch(cond_rd.llvm_data, llvm_block_loop, llvm_block_exit)

    self.push_sub_scope()
    self.push_builder(ll.IRBuilder(llvm_block_loop))
    self.push_loop((llvm_block_check, llvm_block_exit))

    has_terminator = self.evaluate_block(while_node.body)
    self.fix_sub_scope_terminator(has_terminator, llvm_block_check)

    self.pop_loop()
    self.pop_builder()
    self.pop_scope()

    self.cur_builder = ll.IRBuilder(llvm_block_exit)

  def evaluate_true(self, node):
    return self.evaluate_num(
      Node('num', value='1', pos=node.pos)
    )

  def evaluate_false(self, node):
    return self.evaluate_num(
      Node('num', value='0', pos=node.pos)
    )

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
    self.cur_builder.store(realdata_expr.llvm_data, tmp)

    return tmp

  def evaluate_reference_node(self, unary_node):
    realdata_expr = self.evaluate_node(unary_node.expr, REALTYPE_PLACEHOLDER)

    if isinstance(realdata_expr.llvm_data, ll.LoadInstr):
      self.cur_builder.remove(realdata_expr.llvm_data)
      realdata_expr.llvm_data = realdata_expr.llvm_data.operands[0]
    else:
      if unary_node.is_mut:
        error('temporary expression allocation address cannot be mutable', unary_node.pos)

      realdata_expr.llvm_data = self.create_tmp_alloca_for_expraddr(realdata_expr)
    
    realdata_expr.realtype = RealType('ptr_rt', is_mut=unary_node.is_mut, type=realdata_expr.realtype)

    return realdata_expr

  def evaluate_assignment_leftexpr_node(self, expr_node):
    is_deref = self.is_deref_node(expr_node)

    if is_deref:
      expr_node = expr_node.expr

    realdata_expr = self.evaluate_node(expr_node, REALTYPE_PLACEHOLDER)
    
    if not isinstance(realdata_expr.llvm_data, ll.LoadInstr):
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

    cond_rd = self.evaluate_node(for_node.mid_node, RealType('u8_rt'))
    self.expect_realdata_is_numeric(cond_rd, for_node.mid_node.pos)

    if cond_rd.is_comptime_value():
      self.cur_builder.branch(llvm_block_loop if cond_rd.value else llvm_block_exit)
    else:
      self.cur_builder.cbranch(cond_rd.llvm_data, llvm_block_loop, llvm_block_exit)

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
    self.pop_builder()
    self.pop_scope()

    self.cur_builder = ll.IRBuilder(llvm_block_exit)

  def evaluate_assignment_node_stmt(self, assignment_node):
    is_discard = assignment_node.lexpr.kind == '..'

    realdata_lexpr = self.evaluate_assignment_leftexpr_node(assignment_node.lexpr) if not is_discard else None
    realdata_rexpr = self.evaluate_node(assignment_node.rexpr, realdata_lexpr.realtype.type if not is_discard else REALTYPE_PLACEHOLDER)

    if not is_discard:
      self.expect_realtype(realdata_lexpr.realtype.type, realdata_rexpr.realtype, assignment_node.pos)

    if not is_discard and not realdata_lexpr.realtype.is_mut:
      error('cannot write to unmutable pointer', assignment_node.pos)

    if is_discard and assignment_node.op.kind != '=':
      error('discard statement only accepts `=` as operator', assignment_node.pos)

    llvm_rexpr = {
      '=': lambda: realdata_rexpr.llvm_data,
      '+=': lambda: self.cur_builder.add(self.cur_builder.load(realdata_lexpr.llvm_data), realdata_rexpr.llvm_data),
      '-=': lambda: self.cur_builder.sub(self.cur_builder.load(realdata_lexpr.llvm_data), realdata_rexpr.llvm_data),
      '*=': lambda: self.cur_builder.mul(self.cur_builder.load(realdata_lexpr.llvm_data), realdata_rexpr.llvm_data),
    }[assignment_node.op.kind]()

    if not is_discard:
      self.cur_builder.store(llvm_rexpr, realdata_lexpr.llvm_data)

  def evaluate_stmt(self, stmt):
    try:
      attr = getattr(self, f'evaluate_{stmt.kind}_stmt')
    except AttributeError:
      realdata = self.evaluate_node(stmt, REALTYPE_PLACEHOLDER)

      if not realdata.realtype.is_void():
        error(f'undiscarded expression of type `{realdata.realtype}` as statement', stmt.pos)
      
      return
    
    attr(stmt)

  def evaluate_block(self, block):
    for stmt in block:
      if self.cur_builder.block.is_terminated:
        error('unreachable code', stmt.pos)

      self.evaluate_stmt(stmt)
    
    return self.cur_builder.block.is_terminated

  def convert_realtype_to_llvmtype(self, realtype):
    if realtype.is_int():
      return ll.IntType(int(realtype.kind[1:][:-3]))
    
    match realtype.kind:
      case 'ptr_rt':
        return ll.PointerType(self.convert_realtype_to_llvmtype(realtype.type))

      case 'struct_rt':
        return ll.LiteralStructType(list(map(
          lambda field: self.convert_realtype_to_llvmtype(field[1]),
          realtype.fields.items()
        )))

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

  def create_llvm_function(self, fn_name, proto):
    return ll.Function(
      self.output,
      self.convert_proto_to_llvmproto(proto),
      fn_name
    )

  def push_ctx(self, realtype):
    self.ctx_types.append(realtype)

  def pop_ctx(self):
    self.ctx_types.pop()

  def push_builder(self, llvmbuilder):
    self.llvm_builders.append(llvmbuilder)

  def pop_builder(self):
    self.llvm_builders.pop()

  def declare_parameters(self, proto, fn_args):
    for i, (arg_name, arg_realtype) in enumerate(zip(map(lambda a: a.name, fn_args), proto.arg_types)):
      llvm_alloca = self.allocas_builder.alloca(self.convert_realtype_to_llvmtype(arg_realtype), name=f'arg.{i + 1}')

      self.cur_builder.store(self.cur_fn[1].args[i], llvm_alloca)

      sym = Symbol(
        'local_var_sym',
        is_imported=False,
        realtype=arg_realtype,
        llvm_alloca=llvm_alloca
      )

      self.map.declare_symbol(arg_name.value, sym, arg_name.pos)

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
      self.map.declare_symbol(
        param.value,
        Symbol('alias_sym', is_imported=False, realtype=rt_arg),
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

    self.push_sub_scope()
    self.push_builder(llvmbuilder_entry)

    self.declare_parameters(proto, fn.node.args)
    has_terminator = self.evaluate_block(fn.node.body)
    llvmbuilder_allocas.branch(llvmfn_entry_bb)
    self.fix_ret_terminator(has_terminator, fn.node.pos)
    self.remove_dead_blocks()

    self.pop_builder()
    self.pop_scope()

    self.loops = old_loops
  
    self.fn_in_evaluation.remove_by_key(key)
    self.fn_evaluated[key] = r

    return r
  
  def remove_dead_blocks(self):
    for i, block in enumerate(self.cur_fn[1].blocks):
      if self.cur_fn[1].entry_basic_block == block:
        continue

      if block.is_dead_block:
        self.cur_fn[1].blocks.pop(i)
  
  def fix_ret_terminator(self, has_terminator, fn_pos):
    if has_terminator:
      return
    
    if self.cur_fn[0].ret_type.is_void():
      self.cur_builder.ret_void()
      return

    if self.cur_builder.block.is_dead_block:
      return

    error('not all paths return a value', fn_pos)
  
  def push_sub_scope(self):
    self.maps.append(self.maps[-1].copy())
  
  def push_scope(self):
    self.maps.append(self.maps[0].copy())
  
  def pop_scope(self):
    self.maps.pop()

def get_main(mapped_ast):
  return mapped_ast.get_symbol('main', None)

def check_sym_is_fn(sym_id, sym):
  if sym.kind == 'fn_sym':
    return

  error(f'`{sym_id}` is not a function', sym.node.pos)

def check_sym_is_type(sym_id, sym):
  if sym.kind == 'type_sym':
    return

  error(f'`{sym_id}` is not a type', sym.node.pos)

def check_main_proto(main_proto, main_pos):
  throw_error = lambda: error('invalid `main` prototype', main_pos)

  if len(main_proto.arg_types) != 2:
    throw_error()
  
  if main_proto.arg_types != [
    RealType('u32_rt'),
    RealType('ptr_rt', is_mut=False, type=RealType('ptr_rt', is_mut=False, type=RealType('u8_rt')))
  ]:
    throw_error()

  if main_proto.ret_type.kind != 'i32_rt':
    throw_error()

def gen(mapped_ast):
  g = Generator(mapped_ast)
  main = get_main(mapped_ast)

  check_sym_is_fn('main', main)
  main_proto, _, _ = g.gen_nongeneric_fn(main)
  check_main_proto(main_proto, main.node.pos)

  return g.output