from genericpath import isdir, isfile
from os import listdir, system
from lex import lex
from parse import parse
from mapast import cache_mapast
from gen import gen, gen_tests
from sys import argv
from utils import *
from tempfile import gettempdir
from llvmlite.ir import Module

import utils

def clang(llvm_ir_filepath, output_filepath, flags=''):
  cmd = f'clang -Wno-override-module {flags} {" ".join(utils.libs_to_import)} {llvm_ir_filepath} -o {output_filepath}'
  # print(f'[+] {cmd}')
  return system(cmd)

def compile(path, gen_tests_instead=False):
  path = getabspath(path)

  with open(path, 'r') as f:
    src = f.read()
  
  utils.cache = {}
  utils.output = Module(name=path)
  utils.libs_to_import = set()
  utils.llvm_internal_functions_cache = {}
  utils.strings_cache = {}
  utils.llvm_internal_vars_cache = {}

  toks = lex(src, path)
  ast = parse(toks)
  g = cache_mapast(path, ast)
  check_imports_of_all_modules()

  if gen_tests_instead:
    gen_tests(g)
  else:
    gen(g)

  return src, toks, ast, g.map, utils.output, path

'''
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
'''

def compile_file(srcpath, is_test):
  _, _, _, _, llvm_ir, path = compile(srcpath, is_test)
  tmp_folder = fixpath(gettempdir())
  llvm_ir_file = f'{tmp_folder}/{get_filename_from_path(path)}.ll'
  clang_flags = '-O3' if is_release_build() in argv else ''

  if is_test:
    output_filepath = f'{tmp_folder}/{get_filename_from_path(path)}.exe'
  else:
    output_filepath = change_extension_of_path(path, 'exe')

  with open(llvm_ir_file, 'w') as f:
    f.write(repr(llvm_ir))
  
  if '--print-llvm-ir' in argv:
    print(llvm_ir)
  
  if (exitcode := clang(llvm_ir_file, output_filepath, clang_flags)) != 0:
    error(f'clang error, exitcode: {exitcode}', None)
  
  if is_test:
    system(output_filepath)

def collect_zpp_files_in_dir(path):
  return [f'{path}/{elem}' for elem in listdir(path) if elem.endswith('.zpp')]

def main():
  if len(argv) == 1:
    _, _, _, _, llvm_ir, _ = compile('samples/simple.zpp')
    print(repr(llvm_ir))
    return

  if argv[1] != 'test':
    compile_file(argv[1], False)
    return
  
  srcpath = argv[2]
  files = collect_zpp_files_in_dir(srcpath) if isdir(srcpath) else [srcpath]
  
  for file in files:
    compile_file(file, True)

if __name__ == '__main__':
  main()