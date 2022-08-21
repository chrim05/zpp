def comptime_print(analyzer, call_node):
  analyzer.expect(len(call_node.generic_args) == 0, 'unexpected generic args', call_node.generic_args_pos)

  final = ''

  for arg in call_node.args:
    typed_arg = analyzer.evaluate_node(arg)
    analyzer.expect_type(typed_arg.type, 'comptime_string', arg.pos)

    final += typed_arg.comptime_value
  
  print(final, end='')

def type_to_string(analyzer, call_node):
  analyzer.expect(len(call_node.args) == 0, 'unexpected args', call_node.args_pos)
  analyzer.expect(len(call_node.generic_args) == 1, 'expected "1" generic arg', call_node.generic_args_pos)

  type = analyzer.evaluate_type(call_node.generic_args[0])
  Value, Type = analyzer.data_module.Value, analyzer.data_module.Type
  
  return Value(type=Type('comptime_string'), comptime_value=str(type))