#pragma once
#include "argv_parser.h"
#include "info.h"
#include <stdlib.h>

#define Help                                                                                               \
  "Usage: zpp [task] +[flags..] [input-file]\n"                                                            \
  "\n"                                                                                                     \
  "Tasks:\n"                                                                                               \
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

    default:
      Unreachable;
  }

  return ok;
}