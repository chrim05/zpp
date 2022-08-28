#pragma once
#include "../pck/sys/include/sys.h"
#include "../pck/sys/include/cstrings.h"
#include <stdio.h>

constexpr u8 FlagChar = '+';

constexpr u8 TaskTagHelp = 0;
constexpr u8 TaskTagVersion = 1;
constexpr u8 TaskTagBuild = 2;

// ! handles a parsed version of `argv`
struct ArgvTable {
  i32 optimization_level;
  u8 task_tag;
  u8 const* input_source;
  // TODO when adding field here modify also the constructor
};

// ! constructor for ArgvTable
inline void InitArgvTable(ArgvTable* argv) {
  argv->optimization_level = 0;
  argv->task_tag = TaskTagHelp;
  argv->input_source = nullptr;
}

// ! take the string representation of the task
// ! return the an error when the task isn't known
// ! otherwise set the out param to the task tag
error GetTaskTagFromRepr(u8 const* task_repr, u8* task_tag_out);

// ! check input source isn't specified multiple times
// ! otherwise set the input source to the specified one
error SetInputSource(ArgvTable* self, u8 const* input_source);

// ! take a flag value and return the length of its name
// ! the name can be the entire flag value or just the beginning part
// ! for example with `+use-bla-bla` the length is the entire flag value
// ! with `+opt:1` the length is just 3 `opt`
u32 GetFlagNameLength(u8 const* flag);

// ! take the value of the flag, without the `FlagChar`
// ! and update the argv table
error ParseFlagAndUpdateArgvTable(ArgvTable* self, u8 const* flag);

// ! analyze the parameters passed from the command line
// ! and configures a table with the information of what the user asked for
// ! if there are errors in `argv`, print them and return some value != 0
// ! here `argc` can be 0 when no param is passed to the executable (not 1)
error ArgvToTable(ArgvTable* self, u32 argc, u8 const* const* argv);