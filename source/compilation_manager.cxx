#include "compilation_manager.h"
#include "irgenerator.h"
#include "checker.h"
#include "../pck/sys/include/dbg.h"
#include "../pck/sys/include/collections.h"
#include "../pck/sys/include/cstrings.h"

void WriteIRToFile(IRGenerator const* self) {
  auto output = fopen("a.out", "wb");

  // writing the functions indexes
  {
    // writing the indexes used buffer size
    fwrite(
      (void const*)&self->functions.allocator.buffer_used_size,
      1,
      sizeof(u64),
      output
    );

    // writing the indexes
    fwrite(
      (void const*)self->functions.allocator.buffer_starting_pointer,
      1,
      self->functions.allocator.buffer_used_size,
      output
    );
  }

  // writing the instruction
  {
    // writing the instructions used buffer size
    fwrite(
      (void const*)&self->instruction_tags.allocator.buffer_used_size,
      1,
      sizeof(u64),
      output
    );

    // writing the tags
    fwrite(
      (void const*)self->instruction_tags.allocator.buffer_starting_pointer,
      1,
      self->instruction_tags.allocator.buffer_used_size,
      output
    );

    // writing the values
    fwrite(
      (void const*)self->instruction_values.allocator.buffer_starting_pointer,
      1,
      self->instruction_values.allocator.buffer_used_size,
      output
    );
  }

  fclose(output);
}

error Build(ArgvTable const* self) {
  if (self->input_source == nullptr) {
    printf("required 'input-file'\n");
    return Err;
  }

  // mem chunk for the source code and all the parser internal stuff
  // this is basically an arena allocator
  // and will be automatically freed at the end of the scope
  MemRegion chunk;
  // contains the size of the input file with the source code
  u64 file_size;
  // contains the source code
  u8* source_code_buffer;

  // reading input file source to buffer
  {
    // opening 'input-file'
    auto file = fopen((char const*)self->input_source, "rb");

    // checking that the file exists
    if (file == nullptr or !IsRegularFile(self->input_source)) {
      printf("file '%s' not found\n", self->input_source);
      return Err;
    }

    file_size = GetFileSize(file);

    InitMemRegion(&chunk, file_size);

    // allocating space for the source code
    try(AllocateSlice<u8>(&chunk, &source_code_buffer, file_size + 1), {
      Dbg("Failed allocating slice of size '%llu' bytes for source code buffer, no enough memory", file_size);
    });

    // writing the file content to source code buffer
    ReadFileIntoBuffer(file, source_code_buffer, file_size);

    // closing 'input-file'
    fclose(file);
  }

  auto compilation_info = CreateCompilationInfo(file_size, source_code_buffer, self->input_source);

  // creating the parser instance
  ZppParser parser;
  InitZppParser(&parser, &chunk, &compilation_info);
  InitIRGenerator(&parser.ast_visitor);

  // parsing the file
  ParseGlobalScope(&parser);

  // checking the file
  CheckIR(&parser.ast_visitor);

  // writing ir to file
  // WriteIRToFile(&parser.ast_visitor);

  return Ok;
}

error CompilationTaskRun(ArgvTable const* self) {
  // running the task
  switch (self->task_tag) {
    case TaskTagHelp:
      printf(Help);
      break;
    
    case TaskTagVersion:
      printf("Version: %.2f\n", Version);
      break;
    
    case TaskTagBuild:
      try(Build(self), {});
      break;

    default:
      Unreachable;
  }

  return Ok;
}