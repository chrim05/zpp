#pragma once
#include "../pck/sys/include/sys.h"
#include "../pck/sys/include/dbg.h"
#include "../pck/sys/include/collections.h"
#include "token.h"

// struct FunctionSymbol {
//   u8 const* Name;
//   IRType ReturnType;
//   SourceLocation const* DeclLocation;
// };

constexpr u8 InstrTagDeclFn = 0;
constexpr u8 InstrTagArgDecl = 1;
constexpr u8 InstrTagMkTyped = 2;
constexpr u8 InstrTagMkPtrTyped = 3;
constexpr u8 InstrTagNamedBlockDecl = 4;
constexpr u8 InstrTagPassStmt = 5;
constexpr u8 InstrTagBin = 6;
constexpr u8 InstrTagLoadName = 7;
constexpr u8 InstrTagQuitStmt = 8;
constexpr u8 InstrTagLoadDigit = 9;
constexpr u8 InstrTagLoadField = 10;
constexpr u8 InstrTagCall = 11;

union InstructionValue {
  struct {
    u8 const* name;
    u16 name_length;
    u16 args_count;
  } fn_decl;

  struct {
    u8 const* name;
    u16 name_length;
  } arg_decl;

  struct {
    u8 const* name;
    u16 name_length;
  } mk_typed;

  struct {
    u8 const* name;
    u16 name_length;
    u64 stmts_count;
  } named_block_decl;

  struct {
    u8 const* name;
    u16 name_length;
  } load_name;

  struct {
    u8 const* name;
    u16 name_length;
  } load_field;

  struct {
    u8 const* name;
    u16 name_length;
    u16 args_count;
  } call;

  struct {
    u8 const* name;
    u16 name_length;
  } quit_stmt;

  u64 load_digit;

  struct { u8 op; } bin;
};

struct IRGenerator {
  Vector<u8> instruction_tags;
  MemRegion instruction_values;
  Vector<u64> functions;
};

inline void InitIRGenerator(IRGenerator* self) {
  catch(InitVector(&self->instruction_tags, 100'000), {
    DbgString("Failed to allocate IRGenerator instructions");
  });

  catch(InitMemRegion(&self->instruction_values, 100'000 * sizeof(InstructionValue)), {
    DbgString("Failed to allocate IRGenerator instructions");
  });

  catch(InitVector(&self->functions, 1'000), {
    DbgString("Failed to allocate IRGenerator functions");
  });
  // InitVector(&self->types, 100);
}

inline u64 VisitFnDeclaration(
  IRGenerator* self,
  u8 modifier_export,
  u8 const* name,
  u16 name_length
) {
  Dbg("fn_decl modifier_export:%u '%.*s'", modifier_export, name_length, name);

  InstructionValue* i;
  VectorPush(&self->instruction_tags, InstrTagDeclFn);
  unwrap(AllocateSingle(&self->instruction_values, &i));

  i->fn_decl.name = name;
  i->fn_decl.name_length = name_length;
  i->fn_decl.args_count = 0;

  // index of this instruction
  return (self->instruction_values.buffer_used_size / sizeof(InstructionValue)) - 1;
}

inline void VisitArgDeclaration(IRGenerator* self, u8 const* name, u16 name_length) {
  Dbg("arg_decl '%.*s'", name_length, name);

  InstructionValue* i;
  VectorPush(&self->instruction_tags, InstrTagArgDecl);
  unwrap(AllocateSingle(&self->instruction_values, &i));

  i->arg_decl.name = name;
  i->arg_decl.name_length = name_length;
}

inline void VisitTypeMkTyped(IRGenerator* self, u8 const* name, u16 name_length) {
  Dbg("mk_typed '%.*s'", name_length, name);
  
  InstructionValue* i;
  VectorPush(&self->instruction_tags, InstrTagMkTyped);
  unwrap(AllocateSingle(&self->instruction_values, &i));

  i->mk_typed.name = name;
  i->mk_typed.name_length = name_length;
}

inline void VisitTypeMkPtrTyped(IRGenerator* self) {
  DbgString("mk_ptr_typed");
  
  VectorPush(&self->instruction_tags, InstrTagMkPtrTyped);
}

inline u64 VisitBlockNameDeclaration(IRGenerator* self, u8 const* name, u16 name_length) {
  Dbg("named_block_decl '%.*s'", name_length, name);
  
  InstructionValue* i;
  VectorPush(&self->instruction_tags, InstrTagNamedBlockDecl);
  unwrap(AllocateSingle(&self->instruction_values, &i));

  i->named_block_decl.name = name;
  i->named_block_decl.name_length = name_length;
  i->named_block_decl.stmts_count = 0;

  // index of this instruction
  return (self->instruction_values.buffer_used_size / sizeof(InstructionValue)) - 1;
}

inline void VisitPassStmt(IRGenerator* self) {
  DbgString("pass_stmt");
  
  VectorPush(&self->instruction_tags, InstrTagPassStmt);
}

inline void VisitQuitStmt(IRGenerator* self, u8 const* name, u16 name_length) {
  Dbg("quit_stmt '%.*s'", name_length, name);
  
  InstructionValue* i;
  VectorPush(&self->instruction_tags, InstrTagQuitStmt);
  unwrap(AllocateSingle(&self->instruction_values, &i));

  i->quit_stmt.name = name;
  i->quit_stmt.name_length = name_length;
}

inline void VisitBinaryOperation(IRGenerator* self, u8 bin_op_tag) {
  Dbg("bin '%c'", bin_op_tag);
  
  InstructionValue* i;
  VectorPush(&self->instruction_tags, InstrTagBin);
  unwrap(AllocateSingle(&self->instruction_values, &i));

  i->bin.op = bin_op_tag;
}

inline void VisitLoadName(IRGenerator* self, u8 const* name, u16 name_length) {
  Dbg("load_name '%.*s'", name_length, name);
  
  InstructionValue* i;
  VectorPush(&self->instruction_tags, InstrTagLoadName);
  unwrap(AllocateSingle(&self->instruction_values, &i));

  i->load_name.name = name;
  i->load_name.name_length = name_length;
}

inline void VisitLoadDigit(IRGenerator* self, u64 value) {
  Dbg("load_digit '%llu'", value);
  
  InstructionValue* i;
  VectorPush(&self->instruction_tags, InstrTagLoadDigit);
  unwrap(AllocateSingle(&self->instruction_values, &i));

  i->load_digit = value;
}

inline void VisitLoadField(IRGenerator* self, u8 const* name, u16 name_length) {
  Dbg("load_field '%.*s'", name_length, name);
  
  InstructionValue* i;
  VectorPush(&self->instruction_tags, InstrTagLoadField);
  unwrap(AllocateSingle(&self->instruction_values, &i));

  i->load_field.name = name;
  i->load_field.name_length = name_length;
}

inline void VisitCall(IRGenerator* self, u8 const* name, u16 name_length, u16 args_count) {
  Dbg("call '%.*s' args:%hu", name_length, name, args_count);
  
  InstructionValue* i;
  VectorPush(&self->instruction_tags, InstrTagCall);
  unwrap(AllocateSingle(&self->instruction_values, &i));

  i->call.name = name;
  i->call.name_length = name_length;
  i->call.args_count = args_count;
}