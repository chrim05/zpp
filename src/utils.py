from posixpath import abspath

cache = {}

def error(msg, pos):
  if pos is None:
    exit(f'error: {msg}')

  line, col, src, path = pos
  lines = src.split('\n')

  print(f'{path} [line: {line}, col: {col}]: {msg}')
  print(f'+ {lines[line - 1]}')
  exit(f'+ {" " * (col - 1)}^')

def getabspath(path):
  return fixpath(abspath(path))

def fixpath(path):
  return path.replace('\\', '/')