#include "argv_parser.h"
#include "../pck/sys/include/dbg.h"

error GetTaskTagFromRepr(u8 const* task_repr, u8* task_tag_out) {
  if (CStringsAreEqual(task_repr, static_cstring("help")))
    *task_tag_out = TaskTagHelp;
  else if (CStringsAreEqual(task_repr, static_cstring("version")))
    *task_tag_out = TaskTagVersion;
  else if (CStringsAreEqual(task_repr, static_cstring("astgen")))
    *task_tag_out = TaskTagBuild;
  else
    // unknown task
    return Err;
  
  return Ok;
}

error SetInputSource(ArgvTable* self, u8 const* input_source) {
  // expecting input source not to be already specified
  if (self->input_source != nullptr) {
    printf("input source specified multiple times\n");
    return Err;
  }

  self->input_source = input_source;
  return Ok;
}

u32 GetFlagNameLength(u8 const* flag) {
  auto original_flag_ptr = flag;

  // until flag points to the end char of the flag name
  while (*flag != ':' and *flag != '\0')
    flag++;
  
  return flag - original_flag_ptr;
}

error ParseFlagAndUpdateArgvTable(ArgvTable* self, u8 const* flag) {
  auto flag_name_len = GetFlagNameLength(flag);

  if (flag_name_len == 0) {
    printf("empty flag '+%s'\n", flag);
    return Err;
  }

  // finding the matching flag, ensuring their length are equal
  if (flag_name_len == 3 && SmallFixedCStringsAreEqual(flag, static_cstring("opt"), flag_name_len))
    Todo;
  else {
    printf("unknown flag '%.*s'\n", flag_name_len, flag);
    return Err;
  }
  
  return Ok;
}

error ArgvToTable(ArgvTable* self, u32 argc, u8 const* const* argv) {
  if (argc == 0)
    return Ok;
  
  // parsing the task and checking for its validity
  auto task = argv[0];
  try(GetTaskTagFromRepr(task, &self->task_tag), {
    printf("unknown task '%s'\n", task);
  });

  // for all remaining arguments
  // exluding the task
  while (--argc) {
    auto arg = argv[argc];

    // checking whether arg is a flag or an input file
    if (arg[0] == FlagChar)
      try(ParseFlagAndUpdateArgvTable(self, arg + 1), {});
    else
      try(SetInputSource(self, arg), {});
  }

  return Ok;
}