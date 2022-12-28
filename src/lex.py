from data import Node
from utils import error

SKIPPABLE = [' ', '\n', '\t']
DOUBLE_PUNCTUATION = ['==', '->', '..', '+=', '-=', '*=']
KEYWORDS = [
  'fn', 'pass', 'if', 'elif', 'else',
  'return', 'true', 'false', 'null', 'type',
  'as', 'while', 'break', 'continue', 'mut'
]

class Lexer:
  def __init__(self, src):
    self.src = src
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
  def col(self):
    return self.index - self.start_line_index + 1

  @property
  def cur_pos(self):
    return (self.line, self.col)

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
        
        case '_':
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

    while self.has_char and self.cur.isalnum():
      t += self.cur
      self.advance()
    
    self.advance(-1)
    kind = 'num' if t[0].isdigit() else t if t in KEYWORDS else 'id'

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

  def gen_next(self):
    self.skip()

    if not self.has_char:
      return
    
    if self.cur.isalnum():
      t = self.collect_word()
    else:
      t = self.collect_punctuation()
    
    self.advance()
    return t

def lex(src):
  l = Lexer(src)
  r = []
  
  while l.has_char:
    tok = l.gen_next()
    
    if tok is None:
      break

    r.append(tok)
  
  return r