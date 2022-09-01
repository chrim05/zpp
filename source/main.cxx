#include "../pck/sys/include/sys.h"
#include "../pck/sys/include/dbg.h"
#include "argv_parser.h"
#include "compilation_manager.h"
#include "checker.h"

// ! the only one `zpp.exe` entry point
error Main(u32 argc, u8 const* const* argv) {
  // creating a default argv table
  ArgvTable argv_table;
  InitArgvTable(&argv_table);

  // configurating the argv table based
  // on parsed argv
  ctry(ArgvToTable(&argv_table, argc - 1, argv + 1), {});

  // running the task
  ctry(CompilationTaskRun(&argv_table), {});

  return Ok;
}

int main(int argc, char** argv) {
  return (u8)Main(argc, (u8 const* const*)argv);
}