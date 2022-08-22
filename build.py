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
LINK = '-lpthread'
BASE_FLAGS = '-Wall'
OPTIMIZATION_LEVEL = 3 if 'release' in argv else 0
LIBS = '/pck/mimalloc/lib/mimalloc.a'

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
  try_mkdir('bin')

  for file in listdir('source'):
    if not isfile(file):
      continue

    if file == 'main.cxx':
      continue

    if file.endswith('.cxx'):
      make_pass(f'bin/{file.removesuffix(".cxx")}.o', '-c *.o')
  
  exit(make_pass('bin/zpp', f'source/main.cxx {LIBS} {LINK}'))