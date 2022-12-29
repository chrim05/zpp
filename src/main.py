from lex import lex
from parse import parse
from mapast import cache_mapast
from gen import gen
from sys import argv
from utils import getabspath

def compile(path):
  with open(path, 'r') as f:
    src = f.read()

  toks = lex(src, path)
  ast = parse(toks)
  mapped_ast = cache_mapast(path, ast)
  llvmir = gen(mapped_ast)

  return toks, ast, mapped_ast, llvmir

if __name__ == '__main__':
  if len(argv) == 2:
    path = getabspath(argv[1])
    _, _, mapped_ast, llvmir = compile(path)
    
    print(mapped_ast, end='-----------\n\n')

    with open(path + '.ll', 'w') as f:
      f.write(repr(llvmir))
  else:
    path = getabspath('samples/simple.zpp')
    _, _, mapped_ast, llvmir = compile(path)

    print(mapped_ast, end='-----------\n\n')
    print(llvmir)