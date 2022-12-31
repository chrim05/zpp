from genericpath import isfile
from os import listdir, system
from lex import lex
from parse import parse
from mapast import cache_mapast
from gen import gen
from sys import argv
from utils import getabspath
from tempfile import gettempdir

import utils

def compile(path):
  with open(path, 'r') as f:
    src = f.read()
  
  utils.cache = {}

  toks = lex(src, path)
  ast = parse(toks)
  mapped_ast = cache_mapast(path, ast)
  llvmir = gen(mapped_ast)

  return src, toks, ast, mapped_ast, llvmir

def run_tests():
  fail = lambda mapped_ast, llvmir, msg: (
    print(msg),
    print(mapped_ast, end='-----------\n\n'),
    exit(llvmir),
  )

  for elem in listdir('samples'):
    if elem == 'simple.zpp':
      continue

    elem = f'samples/{elem}'
    if not isfile(elem) or not elem.endswith('.zpp'):
      continue

    print(f"[+] testing '{elem}' => ", end='')
    src, _, _, mapped_ast, llvmir = compile(getabspath(elem))

    expected_exitcode = src.split('\n')[0].strip('- ')
    expected_exitcode = int(expected_exitcode) if expected_exitcode != '' else None
    tmp_folder = gettempdir()

    with open(f'{tmp_folder}/a.ll', 'w') as f:
      f.write(repr(llvmir))
    
    if (exitcode := system(f'clang -Wno-override-module {tmp_folder}/a.ll -o {tmp_folder}/a.exe')) != 0:
      fail(mapped_ast, llvmir, f'clang error, exitcode: {exitcode}')
    
    if expected_exitcode is None:
      print('skipped runtime')
    elif (exitcode := system(f'{tmp_folder}/a.exe arg')) != expected_exitcode:
      fail(mapped_ast, llvmir, f'runtime error, (expected: {expected_exitcode}, got: {exitcode})')
    else:
      print('passed')

def main():
  if len(argv) == 2:
    if argv[1] == 'test':
      run_tests()
      return
    
    path = getabspath(argv[1])
    _, _, _, mapped_ast, llvmir = compile(path)

    with open(path + '.ll', 'w') as f:
      f.write(repr(llvmir))
  else:
    path = getabspath('samples/simple.zpp')
    _, _, _, mapped_ast, llvmir = compile(path)

    print(mapped_ast, end='-----------\n\n')
    print(llvmir)

if __name__ == '__main__':
  main()