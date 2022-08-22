#pragma once
#include "/pck/sys/include/sys.h"
#include <stdio.h>
#include "utils.h"

constexpr u8 FlagChar = '+';

constexpr u8 TaskTagHelp = 0;
constexpr u8 TaskTagVersion = 1;

// ! handles a parsed version of `argv`
struct ArgvTable {
  i32 OptimizationLevel;
  u8 TaskTag;
  u8 const* InputSource;
  // TODO when adding field here modify also the constructor
};

// ! constructor for ArgvTable
void InitArgvTable(ArgvTable* argv) {
  argv->OptimizationLevel = 0;
  argv->TaskTag = TaskTagHelp;
  argv->InputSource = nullptr;
}

// ! take the string representation of the task
// ! return the an error when the task isn't known
// ! otherwise set the out param to the task tag
error GetTaskTagFromRepr(u8 const* task_repr, u8* task_tag_out) {
  if (CStringsAreEqual(task_repr, static_cstring("help")))
    *task_tag_out = TaskTagHelp;
  else if (CStringsAreEqual(task_repr, static_cstring("version")))
    *task_tag_out = TaskTagVersion;
  else
    // unknown task
    return err;
  
  return ok;
}

// ! check input source isn't specified multiple times
// ! otherwise set the input source to the specified one
error SetInputSource(ArgvTable* self, u8 const* input_source) {
  // expecting input source not to be already specified
  if (self->InputSource != nullptr) {
    printf("input source specified multiple times\n");
    return err;
  }

  self->InputSource = input_source;
  return ok;
}

// ! take a flag value and return the length of its name
// ! the name can be the entire flag value or just the beginning part
// ! for example with `+use-bla-bla` the length is the entire flag value
// ! with `+opt:1` the length is just 3 `opt`
u32 GetFlagNameLength(u8 const* flag) {
  auto original_flag_ptr = flag;

  // until flag points to the end char of the flag name
  while (*flag != ':' and *flag != '\0')
    flag++;
  
  // the `- 1` is because `*flag != ':' and ...` will fail
  // only when flag is already pointing to the end character
  // but the end char is not part of the length of the name
  return flag - 1 - original_flag_ptr;
}

// ! take the value of the flag, without the `FlagChar`
// ! and update the argv table
error ParseFlagAndUpdateArgvTable(ArgvTable* self, u8 const* flag) {
  auto flag_name_len = GetFlagNameLength(flag);

  if (flag_name_len == 0) {
    printf("empty flag '+%s'\n", flag);
    return err;
  }

  // finding the matching flag, ensuring their length are equal
  if (flag_name_len == 3 && FixedCStringsAreEqual(flag, static_cstring("opt"), flag_name_len))
    Todo;
  else
    // unknown flag
    return err;
  
  return ok;
}

// ! analyze the parameters passed from the command line
// ! and configures a table with the information of what the user asked for
// ! if there are errors in `argv`, print them and return some value != 0
// ! here `argc` can be 0 when no param is passed to the executable (not 1)
error ArgvToTable(ArgvTable* self, u32 argc, u8 const* const* argv) {
  if (argc == 0)
    return ok;
  
  // parsing the task and checking for its validity
  auto task = argv[0];
  try(GetTaskTagFromRepr(task, &self->TaskTag), {
    printf("unknown task '%s'\n", task);
  });

  // for all remaining arguments
  // exluding the task
  while (--argc) {
    auto arg = argv[argc];

    // checking whether arg is a flag or an input file
    if (arg[0] == FlagChar)
      try(ParseFlagAndUpdateArgvTable(self, arg + 1), {
        printf("unknown flag\n");
      });
    else
      try(SetInputSource(self, arg), {});
  }

  return ok;
}