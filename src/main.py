from genericpath import isfile
from os import listdir, system
from lex import lex
from parse import parse
from mapast import cache_mapast
from gen import gen
from sys import argv
from utils import *
from tempfile import gettempdir
from llvmlite.ir import Module

import utils

def clang(llvm_ir_filepath, output_filepath, flags=''):
  cmd = f'clang -Wno-override-module {flags} {" ".join(utils.libs_to_import)} {llvm_ir_filepath} -o {output_filepath}'
  # print(f'[+] {cmd}')
  return system(cmd)

def compile(path):
  path = getabspath(path)

  with open(path, 'r') as f:
    src = f.read()
  
  utils.cache = {}
  utils.output = Module(name=path)
  utils.libs_to_import = set()

  toks = lex(src, path)
  ast = parse(toks)
  g = cache_mapast(path, ast)
  check_imports_of_all_modules()
  gen(g)

  return src, toks, ast, g.map, utils.output, path

def run_tests():
  fail = lambda llvm_ir_file, msg: (
    print(msg),
    exit(llvm_ir_file)
  )

  for elem in listdir('samples'):
    if elem == 'simple.zpp':
      continue

    elem = getabspath(f'samples/{elem}')
    if not isfile(elem) or not elem.endswith('.zpp'):
      continue

    print(f"[+] testing '{elem}' => ", end='')
    src, _, _, _, llvmir, path = compile(elem)

    expected_exitcode = src.split('\n')[0].strip('- ')
    expected_exitcode = int(expected_exitcode) if expected_exitcode != '' else None
    tmp_folder = fixpath(gettempdir())

    llvm_ir_file = f'{tmp_folder}/a.ll'
    output_filepath = f'{tmp_folder}/a.exe'
    with open(llvm_ir_file, 'w') as f:
      f.write(repr(llvmir))

    if (exitcode := clang(llvm_ir_file, output_filepath)) != 0:
      fail(llvmir, f'clang error, exitcode: {exitcode}')
    
    if expected_exitcode is None:
      print('skipped runtime')
    elif (exitcode := system(f'{output_filepath} arg')) != expected_exitcode:
      fail(llvmir, f'runtime error, (expected: {expected_exitcode}, got: {exitcode})')
    else:
      print('passed')

def main():
  if len(argv) > 1:
    if argv[1] == 'test':
      run_tests()
      return
    
    _, _, _, _, llvm_ir, path = compile(argv[1])
    tmp_folder = fixpath(gettempdir())
    llvm_ir_file = f'{tmp_folder}/{get_filename_from_path(path)}.ll'
    output_filepath = change_extension_of_path(path, 'exe')
    clang_flags = '-O3' if is_release_build() in argv else ''

    with open(llvm_ir_file, 'w') as f:
      f.write(repr(llvm_ir))
    
    if '--print-llvm-ir' in argv:
      print(llvm_ir)
    
    if (exitcode := clang(llvm_ir_file, output_filepath, clang_flags)) != 0:
      error(f'clang error, exitcode: {exitcode}', None)
  else:
    _, _, _, _, llvm_ir, path = compile('samples/simple.zpp')

    print(repr(llvm_ir))

if __name__ == '__main__':
  main()