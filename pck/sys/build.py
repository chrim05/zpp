#!/usr/bin/env python3.10

from genericpath import isfile
from os import listdir, mkdir, system, getcwd
from posixpath import abspath, dirname
from sys import argv

dir = abspath(dirname(__file__))
cwd = abspath(getcwd())

if dir != cwd:
  exit('run this script in project root dir')

argv = argv[1:]

COMPILER = 'g++'
BASE_FLAGS = '-Wall' + (' -D RELEASE' if 'release' in argv else '')
OPTIMIZATION_LEVEL = 3 if 'release' in argv else 0

def cmd(c):
  print(f'[!] launching: {c}')
  return system(c)

def make_pass(output, args):
  return cmd(f'{COMPILER} {BASE_FLAGS} -O{OPTIMIZATION_LEVEL} -o {output} {args}')

def try_mkdir(dir):
  try:
    mkdir(dir)
  except OSError:
    pass

if __name__ == '__main__':
  error = False
  try_mkdir('lib')

  for file in listdir('source'):
    file = 'source/' + file

    if not isfile(file):
      continue

    if file.endswith('.cxx'):
      error += make_pass(f'lib/{file.removeprefix("source/").removesuffix(".cxx")}.o', f'{file} -c')
  
  exit(error)