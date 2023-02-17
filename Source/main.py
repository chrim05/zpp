from genericpath import isdir
from os import listdir, system
from subprocess import Popen
from lex import lex
from parse import parse
from mapast import cache_mapast, gen_and_cache_module_setupper
from gen import gen, gen_tests
from sys import argv
from utils import *
from tempfile import gettempdir

import utils

def clang(llvm_ir_filepath, output_filepath, flags=[]):
  cmd = f'clang -Wno-override-module {" ".join(flags)} {llvm_ir_filepath} -o {output_filepath} {" ".join(utils.libs_to_import)}'
  # print(f'[+] {cmd}')
  return system(cmd), cmd

def compile(path, gen_tests_instead=False):
  path = getabspath(path)

  with open(path, 'r') as f:
    src = f.read()
  
  setup_globals()

  toks = lex(src, path)
  ast = parse(toks)
  g = cache_mapast(path, ast)
  check_imports_of_all_modules()

  gen_and_cache_module_setupper(g)

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

def compile_file(srcpath, is_test, has_to_be_runned):
  _, _, _, _, llvm_ir, path = compile(srcpath, is_test)
  tmp_folder = fixpath(gettempdir())
  llvm_ir_file = f'{tmp_folder}/{get_filename_from_path(path)}.ll'
  clang_flags = []
  
  clang_flags.append('-O3' if is_release_build() in argv else '')
  clang_flags.append(argv[argv.index('--clang') + 1])

  if has_to_be_runned:
    output_filepath = f'{tmp_folder}/{get_filename_from_path(path)}.exe'
  else:
    output_filepath = change_extension_of_path(path, 'exe')

  with open(llvm_ir_file, 'w') as f:
    f.write(repr(llvm_ir))
  
  if '--print-llvm-ir' in argv:
    print(llvm_ir)
  
  if '--emit-llvm-ir' in argv:
    assert not is_test and not has_to_be_runned

    with open(change_extension_of_path(output_filepath, 'll'), 'w') as f:
      f.write(repr(llvm_ir))

    return
  
  if '--no-exe' in argv:
    return
  
  if (clang_call := clang(llvm_ir_file, output_filepath, clang_flags))[0] != 0:
    exitcode, cmd = clang_call
    error(f'clang error, exitcode: {exitcode}, command: {repr(cmd)}', None)
  
  if has_to_be_runned:
    try:
      args = argv[argv.index('--') + 1:]
    except ValueError:
      args = []
    
    try:
      with Popen([output_filepath] + args) as p:
        result = p.wait()
    except KeyboardInterrupt:
      exit(1)

    if is_test and (exitcode := result) != 0:
      error(f'test executable expected to have `exitcode = 0`, got `{exitcode}`', None)
    
    return result

def collect_zpp_files_in_dir(path):
  return [f'{path}/{elem}' for elem in listdir(path) if elem.endswith('.zpp')]

def main():
  if len(argv) == 1:
    _, _, _, _, llvm_ir, _ = compile('samples/simple.zpp')
    print(repr(llvm_ir))
    return

  if argv[1] not in ['test', 'run']:
    return compile_file(argv[1], False, False)
  
  srcpath = argv[2]
  files = collect_zpp_files_in_dir(srcpath) if isdir(srcpath) and argv[1] == 'test' else [srcpath]
  
  for file in files:
    r = compile_file(file, argv[1] == 'test', True)
  
  return r

if __name__ == '__main__':
  r = main()

  if '--print-exit-code' in argv:
    print(f'\nExitCode({r})\n')

  exit(r)