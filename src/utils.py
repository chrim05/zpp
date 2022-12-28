def error(msg, pos):
  if pos is None:
    exit(f'error: {msg}')
  
  global src

  lines = src.split('\n')
  line, col = pos

  print(f'error [line: {line}, col: {col}]: {msg}')
  print(f'+ {lines[line - 1]}')
  exit(f'+ {" " * (col - 1)}^')