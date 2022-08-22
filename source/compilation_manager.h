#pragma once
#include "/pck/sys/include/fs.h"
#include "/pck/sys/include/mem.h"
#include "argv_parser.h"
#include "info.h"
#include <stdlib.h>

#define Help                                                                                               \
  "Usage: zpp [task] +[flags..] [input-file]\n"                                                            \
  "\n"                                                                                                     \
  "Tasks:\n"                                                                                               \
  "  + astgen ------------------------ generate ast json from 'input-file'\n"                              \
  "  + build ------------------------- generate some specifiable ouput (default: exe) from 'input-file'\n" \
  "  + run --------------------------- generate executable in /tmp/ and run it\n"                          \
  "  + test -------------------------- generate executable in /tmp/ and run its tests\n"                   \
  "\n"                                                                                                     \
  "  + version ----------------------- print out the compiler version\n"                                   \
  "  + help -------------------------- print out this message\n"                                           \
  "\n"                                                                                                     \
  "Flags:\n"                                                                                               \
  "  + opt:n ------------------------- set the optimization level (1, 2, 3, default: 0) to n\n"            \
  "  + out:path ---------------------- set the output path\n"                                              \
  "\n"                                                                                                     \
  "Examples:\n"                                                                                            \
  "  + `zpp build +opt:2 main.zpp` --- generate optimized executable from source\n"                        \

error AstGen(ArgvTable const* self) {
  if (self->InputSource == nullptr) {
    printf("required 'input-file'\n");
    return Err;
  }

  // reading input source to buffer
    auto file = fopen((char const*)self->InputSource, "rb");

    // checking that the file exists
    if (file == nullptr) {
      printf("file '%s' not found\n", self->InputSource);
      return Err;
    }

    auto file_size = GetFileSize(file);

    MemRegion chunk;
    InitMemRegion(&chunk, file_size);

    // allocating space for the source code
    u8* buffer;
    try(AllocateSlice<u8>(&chunk, &buffer, file_size + 1), {
      Dbg("Failed allocating slice of size '%llu' bytes for source code buffer, no enough memory", file_size);
    });

    // writing the file content to source code buffer
    ReadFileToBuffer(file, buffer, file_size);
  //

  printf("%.*s\n", (i32)file_size, buffer);
  return Ok;
}

// ! performs the specified task as the first parameter in the command line
// ! for example `zpp help`, `zpp version` `zpp build +opt:1 main.zpp`
error CompilationTaskRun(ArgvTable const* self) {
  // running the task
  switch (self->TaskTag) {
    case TaskTagHelp:
      printf(Help);
      break;
    
    case TaskTagVersion:
      printf("Version: %.2f\n", Version);
      break;
    
    case TaskTagAstGen:
      try(AstGen(self), {
        printf("failed generating ast\n");
      });
      break;

    default:
      Unreachable;
  }

  return Ok;
}