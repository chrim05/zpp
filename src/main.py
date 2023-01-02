from genericpath import isfile
from os import listdir, system
from lex import lex
from parse import parse
from mapast import cache_mapast
from gen import gen
from sys import argv
from utils import check_imports_of_all_modules, fixpath, get_filename_from_path, getabspath
from tempfile import gettempdir
from llvmlite.ir import Module

import utils

def compile(path):
  with open(path, 'r') as f:
    src = f.read()
  
  utils.cache = {}
  utils.output = Module(name=path)

  toks = lex(src, path)
  ast = parse(toks)
  g = cache_mapast(path, ast)
  check_imports_of_all_modules()
  gen(g)

  return src, toks, ast, g.map, utils.output

def run_tests():
  fail = lambda llvm_ir_file, msg: (
    print(msg),
    exit(llvm_ir_file)
  )

  for elem in listdir('samples'):
    if elem == 'simple.zpp' or elem.startswith('module_to_import'):
      continue

    elem = f'samples/{elem}'
    if not isfile(elem) or not elem.endswith('.zpp'):
      continue

    print(f"[+] testing '{elem}' => ", end='')
    src, _, _, _, llvmir = compile(getabspath(elem))

    expected_exitcode = src.split('\n')[0].strip('- ')
    expected_exitcode = int(expected_exitcode) if expected_exitcode != '' else None
    tmp_folder = fixpath(gettempdir())

    llvm_ir_file = f'{tmp_folder}/a.ll'
    with open(llvm_ir_file, 'w') as f:
      f.write(repr(llvmir))

    if (exitcode := system(f'clang -Wno-override-module {llvm_ir_file} -o {tmp_folder}/a.exe')) != 0:
      fail(llvm_ir_file, f'clang error, exitcode: {exitcode}')
    
    if expected_exitcode is None:
      print('skipped runtime')
    elif (exitcode := system(f'{tmp_folder}/a.exe arg')) != expected_exitcode:
      fail(llvm_ir_file, f'runtime error, (expected: {expected_exitcode}, got: {exitcode})')
    else:
      print('passed')

def main():
  if len(argv) == 2:
    if argv[1] == 'test':
      run_tests()
      return
    
    srcpath = getabspath(argv[1])
    llvm_ir = compile(srcpath)[-1]

    with open(path + '.ll', 'w') as f:
      f.write(repr(llvm_ir))
  else:
    path = getabspath('samples/simple.zpp')
    llvm_ir = compile(path)[-1]

    print(repr(llvm_ir))

if __name__ == '__main__':
  main()