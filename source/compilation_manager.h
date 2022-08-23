#pragma once
#include "/pck/sys/include/fs.h"
#include "/pck/sys/include/mem.h"
#include "/pck/sys/include/strings.h"
#include "/pck/sys/include/dbg.h"
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
  "  + `zpp build +opt:2 main.zpp` --- generate optimized executable from source\n"

// ! structure for handling the source code and its size
struct CompilationInfo {
  u64 BufferSize;
  u8* Buffer;
};

struct SourceLocation {
  CompilationInfo* SourceReference;
  u32 Line;
  u16 Column;
  u8 Length;
};

struct CompilationError {
  SourceLocation ErrorLocation;
  String Message;
};

inline CompilationInfo CreateCompilationInfo(u64 buffer_size, u8* buffer) {
  return (CompilationInfo) {
    .BufferSize = buffer_size,
    .Buffer = buffer
  };
}

// ! create a parser instance
// ! and collects all global nodes into a buffer
error AstGen(ArgvTable const* self);

// ! performs the specified task as the first parameter in the command line
// ! for example `zpp help`, `zpp version` `zpp build +opt:1 main.zpp`
error CompilationTaskRun(ArgvTable const* self);