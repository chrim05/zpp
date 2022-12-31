from data import Node
from utils import error

SKIPPABLE = [' ', '\n', '\t']
DOUBLE_PUNCTUATION = ['==', '->', '..', '+=', '-=', '*=', '!=', '<=', '>=']
KEYWORDS = [
  'fn', 'pass', 'if', 'elif', 'else',
  'return', 'true', 'false', 'null', 'type',
  'as', 'while', 'break', 'continue', 'mut',
  'for', 'undefined', 'import'
]

class Lexer:
  def __init__(self, src, path):
    self.src = src
    self.path = path
    self.index = 0
    self.indent = 0
    self.on_new_line = True
    self.line = 1
    self.start_line_index = 0
  
  @property
  def has_char(self):
    return self.index < len(self.src)
    
  @property
  def has_next_char(self):
    return self.index + 1 < len(self.src)

  @property
  def nxt(self):
    return self.src[self.index + 1]

  @property
  def cur(self):
    return self.src[self.index]

  @property
  def bck(self):
    return self.src[self.index - 1]

  @property
  def col(self):
    return self.index - self.start_line_index + 1

  @property
  def cur_pos(self):
    return (self.line, self.col, self.src, self.path)

  def advance(self, count=1):
    self.index += count

  def skip(self):
    is_collecting_inline_comment = False

    while self.has_char and (is_collecting_inline_comment or self.cur in SKIPPABLE or self.cur == '-'):
      match self.cur:
        case '\n':
          self.line += 1
          self.indent = 0
          self.start_line_index = self.index + 1
          self.on_new_line = True

          is_collecting_inline_comment = False

        case ' ':
          self.indent += 1
        
        case '\t':
          error('tab illegal', self.cur_pos)
        
        case '-':
          if is_collecting_inline_comment:
            self.advance()
            continue

          if not self.has_next_char or self.nxt != '-':
            break
          
          is_collecting_inline_comment = True
        
        case _:
          if is_collecting_inline_comment:
            self.advance()
            continue

          raise NotImplementedError()

      self.advance()

  def consume_is_on_new_line(self):
    t = self.on_new_line
    self.on_new_line = False
    
    return t
  
  def consume_indent(self):
    t = self.indent
    self.indent = 0
    
    return t
  
  def collect_word(self):
    t = ''
    p = self.cur_pos
    is_digit = self.cur.isdigit()
    is_ident = not is_digit

    while self.has_char and (
      self.cur.isalnum() or
      (is_digit and self.cur in ["'", '.']) or
      (is_ident and self.cur == '_')
    ):
      t += self.cur
      self.advance()
    
    self.advance(-1)

    if is_digit:
      if ".'" in t or "'." in t or t.endswith("'") or t.endswith('.'):
        error('malformed num', p)

      kind = 'fnum' if '.' in t else 'num'
      t = t.replace("'", '')
    else:
      kind = t if t in KEYWORDS else 'id'

    return self.make_tok(
      kind,
      value=t,
      pos=p
    )
  
  def make_tok(self, kind, **kwargs):
    assert 'pos' in kwargs

    return Node(
      kind,
      indent=self.consume_indent(),
      is_on_new_line=self.consume_is_on_new_line(),
      **kwargs
    )

  def collect_punctuation(self):
    k = self.cur
    p = self.cur_pos

    if self.has_next_char and k + self.src[self.index + 1] in DOUBLE_PUNCTUATION:
      self.advance()
      k += self.cur

    return self.make_tok(k, value=k, pos=p)

  def collect_str(self):
    p = self.cur_pos
    self.advance()
    t = ''

    while self.has_char and (self.cur != "'" or self.bck == '\\'):
      t += self.cur
      self.advance()
    
    return self.make_tok(
      'str',
      value=t,
      pos=p
    )

  def gen_next(self):
    self.skip()

    if not self.has_char:
      return
    
    if self.cur.isalnum() or self.cur == '_':
      t = self.collect_word()
    elif self.cur == "'":
      t = self.collect_str()
    else:
      t = self.collect_punctuation()
    
    self.advance()
    return t

def lex(src, path):
  l = Lexer(src, path)
  r = []
  
  while l.has_char:
    tok = l.gen_next()
    
    if tok is None:
      break

    r.append(tok)
  
  return r