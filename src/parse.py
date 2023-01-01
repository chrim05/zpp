from data import Node
from utils import error

class Parser:
  def __init__(self, toks):
    self.toks = toks
    self.index = 0
    self.indents = [0]
  
  @property
  def eof_pos(self):
    return self.toks[-1].pos if len(self.toks) > 0 else (1, 1)

  @property
  def cur(self):
    return self.toks[self.index] if self.has_tok else error('unexpected `eof`', self.eof_pos)

  @property
  def has_tok(self):
    return self.index < len(self.toks)

  @property
  def cur_indent(self):
    return self.indents[-1]

  def make_node(self, kind, **kwargs):
    assert 'pos' in kwargs
    assert kind.endswith('_node')

    return Node(kind, **kwargs)

  def advance(self, count=1):
    self.index += count

  def consume_cur(self):
    t = self.cur
    self.advance()

    return t
  
  def match_tok(self, kind, allow_on_new_line=False):
    if not self.has_tok:
      return False

    return self.cur.kind == kind and (allow_on_new_line or not self.cur.is_on_new_line)

  def expect_and_consume(self, kind, allow_on_new_line=False):
    if self.cur.kind != kind:
      error(f'expected `{kind}`, found `{self.cur.value}`', self.cur.pos)
    
    if not allow_on_new_line and self.cur.is_on_new_line:
      error(f'unexpected token to be on a new line', self.cur.pos)
    
    return self.consume_cur()

  def parse_struct_fields(self):
    fields = []

    while True:
      name = self.expect_and_consume('id', allow_on_new_line=True)
      self.expect_and_consume(':')
      type = self.parse_type()

      fields.append(self.make_node('struct_field_node', name=name, type=type, pos=name.pos))

      if not self.match_tok(','):
        break
      
      self.advance()

    self.expect_and_consume(')', allow_on_new_line=True)
    return fields

  def parse_type(self):
    if self.match_tok('*'):
      pos = self.consume_cur().pos
      is_mut = self.consume_tok_if_match('mut') is not None
      return self.make_node('ptr_type_node', is_mut=is_mut, type=self.parse_type(), pos=pos)
    
    if self.match_tok('['):
      pos = self.consume_cur().pos
      length = self.parse_expr()
      i = self.expect_and_consume('id')

      if i.value != 'x':
        error('expected token `x`', i.pos)
      
      type = self.parse_type()
      self.expect_and_consume(']')
      return self.make_node(
        'array_type_node',
        length=length,
        type=type,
        pos=pos
      )
    
    if self.match_tok('('):
      pos = self.consume_cur().pos
      fields = self.parse_struct_fields()
      
      return self.make_node(
        'struct_type_node',
        fields=fields,
        pos=pos
      )

    return self.expect_and_consume('id')

  def parse_generics(self):
    if not self.match_tok('|'):
      return []
    
    self.expect_and_consume('|')
    generics = []

    while True:
      t = self.expect_and_consume('id')
      generics.append(t)

      if not self.match_tok(','):
        break
      
      self.advance()
    
    self.expect_and_consume('|')
    return generics

  def parse_generics_in_call(self):
    if not self.match_tok('|'):
      return []
    
    self.expect_and_consume('|')
    generics = []

    while True:
      t = self.parse_type()
      generics.append(t)

      if not self.match_tok(','):
        break
      
      self.advance()
    
    self.expect_and_consume('|')
    return generics

  def parse_fn_args(self):
    args = []
    self.expect_and_consume('(')

    generics = self.parse_generics()

    while True:
      if len(args) == 0 and self.match_tok(')', allow_on_new_line=True):
        break

      name = self.expect_and_consume('id', allow_on_new_line=True)
      self.expect_and_consume(':')
      type = self.parse_type()

      args.append(self.make_node('fn_arg_node', name=name, type=type, pos=name.pos))

      if not self.match_tok(','):
        break
      
      self.advance()

    self.expect_and_consume(')', allow_on_new_line=True)
    return (args, generics)
  
  def parse_fn_type(self):
    self.expect_and_consume('->')

    return self.parse_type()

  def parse_bin(self, ops, terms_parser_fn):
    left = terms_parser_fn()
    
    while self.match_toks(ops):
      op = self.consume_cur()
      right = terms_parser_fn()

      left = self.make_node(
        'bin_node',
        op=op,
        left=left,
        right=right,
        pos=op.pos
      )
    
    return left
  
  def parse_call_node(self, node_to_call, is_internal_call):
    args = []
    pos = self.expect_and_consume('(').pos
    generics = self.parse_generics_in_call()

    while True:
      if len(args) == 0 and self.match_tok(')', allow_on_new_line=True):
        break

      args.append(self.parse_expr())

      if not self.match_tok(','):
        break
      
      self.advance()

    self.expect_and_consume(')', allow_on_new_line=True)

    if node_to_call.kind != 'id' and is_internal_call:
      error('internal calls need an specific id, not an expression', node_to_call.pos)
    
    return self.make_node(
      'call_node',
      name=node_to_call,
      generics=generics,
      is_internal_call=is_internal_call,
      args=args,
      pos=pos
    )
  
  def match_pattern(self, pattern_toks, allow_first_on_new_line=False):
    old_index = self.index

    for i, tok in enumerate(pattern_toks):
      if not self.match_tok(tok, allow_on_new_line=allow_first_on_new_line and i == 0):
        self.index = old_index
        return 0
      
      self.advance()
    
    r = self.index - old_index
    self.index = old_index
    
    return r
  
  def parses_array_init_node(self, pos):
    nodes = []

    while True:
      nodes.append(self.parse_expr())

      if not self.match_tok(','):
        break
      
      self.advance()

    self.expect_and_consume(']', allow_on_new_line=True)
    
    return self.make_node(
      'array_init_node',
      nodes=nodes,
      pos=pos
    )

  def parse_term(self):
    term = self.consume_cur()

    match term.kind:
      case 'num' | 'fnum' | 'id' | 'true' | 'false' | 'null' | 'undefined' | 'str' | 'chr':
        pass
    
      case '[':
        term = self.parses_array_init_node(term.pos)
    
      case '+' | '-' | '&' | '*' | 'not':
        op = term
        is_mut = (self.consume_tok_if_match('mut') is not None) if op.kind == '&' else None
        expr = self.parse_term()

        term = self.make_node(
          'unary_node',
          op=op,
          expr=expr,
          pos=op.pos
        )

        if op.kind == '&':
          term.is_mut = is_mut
      
      case '(':
        if self.match_pattern(['id', ':'], True):
          term = self.parse_struct_init_node(term.pos)
        else:
          term = self.parse_expr()
          self.expect_and_consume(')')

      case _:
        error('invalid term in expression', term.pos)
    
    # matching call node
    if self.match_toks(['!', '(']):
      is_internal_call = self.consume_tok_if_match('!') is not None
      term = self.parse_call_node(term, is_internal_call)
    
    while self.match_toks(['.', '->', '['], allow_on_new_line=True):
      if self.cur.kind == '[':
        pos = self.consume_cur().pos
        term = self.make_node('index_node', instance_expr=term, index_expr=self.parse_expr(), pos=pos)
        self.expect_and_consume(']')
        continue

      dot_tok = self.consume_cur()
      left_expr = term if dot_tok.kind == '.' else self.make_node(
        'unary_node',
        op=Node('*', value='*', pos=dot_tok.pos),
        expr=term,
        pos=dot_tok.pos
      )
      right_expr = self.expect_and_consume('id')

      term = self.make_node(
        'dot_node',
        left_expr=left_expr,
        right_expr=right_expr,
        pos=dot_tok.pos
      )
    
    return term
  
  def parse_struct_init_node(self, pos):
    fields = []

    while True:
      name = self.expect_and_consume('id', allow_on_new_line=True)
      self.expect_and_consume(':')
      expr = self.parse_expr()

      fields.append(self.make_node('struct_field_init_node', name=name, expr=expr, pos=name.pos))

      if not self.match_tok(','):
        break
      
      self.advance()

    self.expect_and_consume(')', allow_on_new_line=True)

    return self.make_node(
      'struct_init_node',
      fields=fields,
      pos=pos
    )

  def parse_large_term(self):
    term = self.parse_term()

    if self.match_tok('as'):
      term = self.parse_as_node(term)
    
    return term
  
  def parse_as_node(self, expr_node):
    pos = self.consume_cur().pos
    type_node = self.parse_type()

    return self.make_node(
      'as_node',
      expr=expr_node,
      type=type_node,
      pos=pos
    )

  def consume_tok_if_match(self, kind, allow_on_new_line=False):
    if not self.match_tok(kind, allow_on_new_line=allow_on_new_line):
      return

    return self.consume_cur()

  def parse_expr(self):
    return self.parse_bin(
      ['or'], lambda: self.parse_bin(
        ['and'], lambda: self.parse_bin(
          ['==', '!=', '<', '>', '<=', '>='], lambda: self.parse_bin(
            ['+', '-'], lambda: self.parse_bin(
              ['*', '/'], lambda: self.parse_large_term()
            )
          )
        )
      )
    )

  def match_toks(self, toks, allow_on_new_line=False):
    for tok in toks:
      if self.match_tok(tok, allow_on_new_line=allow_on_new_line):
        return True
    
    return False

  def parse_if_node(self):
    if_branch = None
    elif_branches = []
    else_branch = None

    make_if_node = lambda: self.make_node(
      'if_node',
      if_branch=if_branch,
      elif_branches=elif_branches,
      else_branch=else_branch,
      pos=if_branch.pos
    )

    while self.match_toks(['if', 'elif', 'else'], allow_on_new_line=True):
      if self.cur.indent > self.cur_indent:
        error('invalid indent', self.cur.pos)
      
      if self.cur.indent < self.cur_indent:
        break

      branch_kind = self.consume_cur()

      match branch_kind.kind:
        case 'if':
          # we matched a separated if statement
          if if_branch is not None:
            self.advance(-1)
            break
          
          cond = self.parse_expr()
          block = self.parse_block()
          
          if_branch = self.make_node(
            'if_branch_node',
            cond=cond,
            body=block,
            pos=branch_kind.pos
          )
        
        case 'elif':
          cond = self.parse_expr()
          block = self.parse_block()

          elif_branches.append(self.make_node(
            'elif_branch_node',
            cond=cond,
            body=block,
            pos=branch_kind.pos
          ))
        
        case 'else':
          block = self.parse_block()

          else_branch = self.make_node(
            'else_branch_node',
            body=block,
            pos=branch_kind.pos
          )

          break

        case _:
          raise NotImplementedError()
    
    return make_if_node()

  def parse_return_node(self):
    pos = self.consume_cur().pos
    expr = self.parse_expr() if self.has_tok and not self.cur.is_on_new_line else None

    return self.make_node(
      'return_node',
      expr=expr,
      pos=pos
    )

  def parse_var_decl(self):
    name = self.expect_and_consume('id', allow_on_new_line=True)
    self.expect_and_consume(':')

    type = self.parse_type()
    self.expect_and_consume('=')

    expr = self.parse_expr()

    return self.make_node(
      'var_decl_node',
      name=name,
      type=type,
      expr=expr,
      pos=name.pos
    )

  def parse_while_node(self):
    pos = self.consume_cur().pos

    cond = self.parse_expr()
    body = self.parse_block()

    return self.make_node(
      'while_node',
      cond=cond,
      body=body,
      pos=pos
    )

  def parse_for_node(self):
    pos = self.consume_cur().pos
    left_node = self.parse_var_decl() if self.consume_tok_if_match('..') is None else None
    self.expect_and_consume(',')
    mid_node = self.parse_expr()
    self.expect_and_consume(',')
    
    if self.match_pattern(['..', ':']):
      self.advance()
      right_node = None
    else:
      right_node = self.parse_stmt()
      
    body = self.parse_block()

    return self.make_node(
      'for_node',
      left_node=left_node,
      mid_node=mid_node,
      right_node=right_node,
      body=body,
      pos=pos
    )

  def parse_stmt(self):
    match self.cur.kind:
      case 'pass':
        return self.make_node('pass_node', pos=self.consume_cur().pos)
      
      case 'if':
        return self.parse_if_node()
      
      case 'return':
        return self.parse_return_node()
      
      case 'while':
        return self.parse_while_node()

      case 'break' | 'continue':
        return self.make_node(f'{self.cur.kind}_node', pos=self.consume_cur().pos)

      case 'for':
        return self.parse_for_node()

      case _:
        if self.match_pattern(['id', ':'], allow_first_on_new_line=True):
          return self.parse_var_decl()
        
        stmt = self.parse_expr() if not self.match_tok('..', allow_on_new_line=True) else self.consume_cur()
        
        if self.match_toks(['=', '+=', '-=', '*=']):
          op = self.consume_cur()
          expr = self.parse_expr()

          stmt = self.make_node(
            'assignment_node',
            lexpr=stmt,
            op=op,
            rexpr=expr,
            pos=op.pos
          )
        
        return stmt

  def parse_block(self):
    block = []
    self.expect_and_consume(':')

    if self.cur.indent <= self.cur_indent:
      error('invalid indent', self.cur.pos)

    self.indents.append(self.cur.indent)

    while True:
      block.append(self.parse_stmt())

      if self.has_tok and not self.cur.is_on_new_line:
        error(f'unexpected token `{self.cur.value}` at the end of a statement', self.cur.pos)

      if not self.has_tok or self.cur.indent < self.cur_indent:
        break

      if self.cur.indent > self.cur_indent:
        error('invalid indent', self.cur.pos)
    
    self.indents.pop()
    return block

  def parse_fn_node(self):
    # eating `fn`
    self.advance()

    name = self.expect_and_consume('id')
    args, generics = self.parse_fn_args()
    ret_type = self.parse_fn_type()
    body = self.parse_block()

    return self.make_node(
      'fn_node',
      name=name,
      generics=generics,
      args=args,
      ret_type=ret_type,
      body=body,
      pos=name.pos
    )

  def parse_type_decl_node(self):
    pos = self.consume_cur().pos
    name = self.expect_and_consume('id')
    self.expect_and_consume('=')
    type = self.parse_type()

    return self.make_node(
      'type_decl_node',
      name=name,
      type=type,
      pos=pos
    )
  '''
  def parse_import_ids(self):
    if self.match_tok('*'):
      return self.consume_cur()

    ids = []
    self.expect_and_consume('[')

    while True:
      if len(ids) == 0 and self.match_tok(']', allow_on_new_line=True):
        break

      name = self.expect_and_consume('id', allow_on_new_line=True)
      alias = name
      
      if self.match_tok('as'):
        self.advance()
        alias = self.expect_and_consume('id')

      ids.append(self.make_node('id_import_node', name=name, alias=alias, pos=alias.pos))

      if not self.match_tok(','):
        break
      
      self.advance()

    self.expect_and_consume(']', allow_on_new_line=True)
    return ids
  '''

  def parse_import_node(self):
    pos = self.consume_cur().pos
    path = self.expect_and_consume('str')
    #self.expect_and_consume('import')
    # ids = self.parse_import_ids()

    return self.make_node(
      'import_node',
      path=path,
      # ids=ids,
      pos=pos
    )

  def parse_next_global(self):
    if not self.has_tok:
      return
    
    if self.cur.indent != 0:
      error('global has bad indent', self.cur.pos)

    match self.cur.kind:
      case 'fn':
        node = self.parse_fn_node()

      case 'type':
        node = self.parse_type_decl_node()
      
      case 'import':
        node = self.parse_import_node()

      case _:
        error('token invalid here', self.cur.pos)
    
    return node

def parse(toks):
  p = Parser(toks)
  r = []

  while p.has_tok:
    node = p.parse_next_global()

    if node is None:
      break
    
    r.append(node)
  
  return r