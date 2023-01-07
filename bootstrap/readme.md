# this is the stage2 of the compiler
the stage1 is written in python and it's structure has nothing
to do with this one

# how stage1 worked
stage1 had classic compiler structure:
* `tokenizing`
* `parsing`
* `check + llvmir-gen`

> (note: each point is a cycle, `check + gen` were merged in a single one, in fact the compiler generated llvm ir code immediately after having made the semantic check of the ast node)

# how stage2 works
i designed stage2 to be as fast as possible.
to do this i needed to eliminate the indirections between all those passes.
speaking more practically:
* list of tokens
* abstract syntax tree
* all strings in `token.value`

so the final compiler structure:
* `tokenizing + parsing + zir-gen`
* `check`
when compiling in release these passes are added:
* `zir2llvm-ir`

> (note: each point is a cycle, `tokenizing + par... + z..` is a single pass in which the parser asks for tokens to a module which tokenizes the text on the fly. in addition the parser avoid allocating any kind of ast or ast-node replacing it with zir)

# what is zir (zpp intermediate reppresentation)
basically a bytecode (stack based).

it is checked just before the end of the compilation process to catch errors like double symbol declaration.

after the compilation process it's executed by an interpreter. this allow for first an easier debugging experience (ub, for example, are hard to catch with native debuggers such as the llvm one, because they are not bugs/crash, they are symptoms of a bug/crash).

an interpreter makes everything more safe and stable for debug builds, and the compiler doesn't even need to generate any runtime check because the interpreter will think about all.

for release builds the zir, after its check, is converted to llvm ir.
this ensures the programmer to have a fast and optimized executable (very thanks to clang) which can potentially run on various architectures.

the general structure of this bytecode (for each zpp file):
* `functions`
* `generic_functions`
* `types`
* `generic_types`
* `imports_all`
* `imports_some`
* `tests`
* `global_variables`
* `strings`

an example of hello world program compiled to zir
```
-- file: hello_world.zpp

from 'sys.zpp' import [ Error, Ok, Err ]
from 'io.zpp' import [ print ]

fn main(argc: u32, argv: **u8) -> Error:
  try print('hello world!\n')
  
  return Ok
```

```
-- file: hello_world.zir

imports_some:
  'sys.zpp':
    ids: [@4 as @4, @7 as @7, @8 as @8]
  
  'io.zpp':
    ids: [print as print]

strings:
  0 'u32'
  1 'argc'
  2 'u8'
  3 'argv'
  4 'Error'
  5 'print'
  6 'hello world!\n'
  7 'Ok'
  8 'Err

functions:
  'main':
    proto:
      %ld_type_name @0
      %decl_arg @1

      %ld_type_name @2
      %mk_ptr_type
      %mk_ptr_type
      %decl_arg @3

      %ld_type_name @4
      %decl_ret_type
      
    body:
      %ld_fn @5
      ld_str @6
      call 1
      try

      ld_name @7
      ret
```

> (note: the zir is rendered by a specific compiler component but its nature is not in string form, it is rendered to make easier to debug but the zir module will be written in binary format)

> (note2: the instructions prefixed by `%` are meta instructions)<br>
> (note3: the values prefixed by `@` refers to string literals)