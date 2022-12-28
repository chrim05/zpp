from lex import lex
from parse import parse
from mapast import mapast
from gen import gen
from sys import argv

import utils

def compile(path):
  with open(path, 'r') as f:
    utils.src = f.read()

  toks = lex(utils.src)
  ast = parse(toks)
  mapped_ast = mapast(ast)
  llvmir = gen(mapped_ast)

  return toks, ast, mapped_ast, llvmir

if __name__ == '__main__':
  if len(argv) == 2:
    path = argv[1]
    _, _, _, llvmir = compile(path)

    with open(path + '.ll', 'w') as f:
      f.write(repr(llvmir))
  else:
    path = 'samples/simple.zpp'
    _, _, mapped_ast, llvmir = compile(path)

    print(mapped_ast, end='-----------\n\n')
    print(llvmir)