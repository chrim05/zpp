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

constexpr u16 InstrTagDeclFn = 0;
constexpr u16 InstrTagArgDecl = 1;
constexpr u16 InstrTagMkTyped = 2;
constexpr u16 InstrTagMkPtrTyped = 3;
constexpr u16 InstrTagNamedBlockDecl = 4;
constexpr u16 InstrTagPassStmt = 5;
constexpr u16 InstrTagBin = 6;
constexpr u16 InstrTagLoadName = 7;
constexpr u16 InstrTagQuitStmt = 8;
constexpr u16 InstrTagLoadDigit = 9;
constexpr u16 InstrTagLoadField = 10;
constexpr u16 InstrTagCall = 11;

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

struct Instruction {
  u16 tag;
  InstructionValue value;
};

struct IRGenerator {
  Vector<Instruction> instructions;
  Vector<u64> functions;
};

inline void InitIRGenerator(IRGenerator* self) {
  catch(InitVector(&self->instructions, 100'000), {
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
  Instruction* i;
  unwrap(AllocateSingle(&self->instructions.allocator, &i));

  i->tag = InstrTagDeclFn;
  i->value.fn_decl.name = name;
  i->value.fn_decl.name_length = name_length;
  i->value.fn_decl.args_count = 0;

  return VectorLength(&self->instructions) - 1;
}

inline void VisitArgDeclaration(IRGenerator* self, u8 const* name, u16 name_length) {
  Dbg("arg_decl '%.*s'", name_length, name);
  Instruction* i;
  unwrap(AllocateSingle(&self->instructions.allocator, &i));

  i->tag = InstrTagArgDecl;
  i->value.arg_decl.name = name;
  i->value.arg_decl.name_length = name_length;
}

inline void VisitTypeMkTyped(IRGenerator* self, u8 const* name, u16 name_length) {
  Dbg("mk_typed '%.*s'", name_length, name);
  Instruction* i;
  unwrap(AllocateSingle(&self->instructions.allocator, &i));

  i->tag = InstrTagMkTyped;
  i->value.mk_typed.name = name;
  i->value.mk_typed.name_length = name_length;
}

inline void VisitTypeMkPtrTyped(IRGenerator* self) {
  DbgString("mk_ptr_typed");
  Instruction* i;
  unwrap(AllocateSingle(&self->instructions.allocator, &i));

  i->tag = InstrTagMkPtrTyped;
}

inline u64 VisitBlockNameDeclaration(IRGenerator* self, u8 const* name, u16 name_length) {
  Dbg("named_block_decl '%.*s'", name_length, name);
  Instruction* i;
  unwrap(AllocateSingle(&self->instructions.allocator, &i));

  i->tag = InstrTagNamedBlockDecl;
  i->value.named_block_decl.name = name;
  i->value.named_block_decl.name_length = name_length;
  i->value.named_block_decl.stmts_count = 0;

  return VectorLength(&self->instructions) - 1;
}

inline void VisitPassStmt(IRGenerator* self) {
  DbgString("pass_stmt");
  Instruction* i;
  unwrap(AllocateSingle(&self->instructions.allocator, &i));

  i->tag = InstrTagPassStmt;
}

inline void VisitQuitStmt(IRGenerator* self, u8 const* name, u16 name_length) {
  Dbg("quit_stmt '%.*s'", name_length, name);
  Instruction* i;
  unwrap(AllocateSingle(&self->instructions.allocator, &i));

  i->tag = InstrTagQuitStmt;
  i->value.quit_stmt.name = name;
  i->value.quit_stmt.name_length = name_length;
}

inline void VisitBinaryOperation(IRGenerator* self, u8 bin_op_tag) {
  Dbg("bin '%c'", bin_op_tag);
  Instruction* i;
  unwrap(AllocateSingle(&self->instructions.allocator, &i));

  i->tag = InstrTagBin;
  i->value.bin.op = bin_op_tag;
}

inline void VisitLoadName(IRGenerator* self, u8 const* name, u16 name_length) {
  Dbg("load_name '%.*s'", name_length, name);
  Instruction* i;
  unwrap(AllocateSingle(&self->instructions.allocator, &i));

  i->tag = InstrTagLoadName;
  i->value.load_name.name = name;
  i->value.load_name.name_length = name_length;
}

inline void VisitLoadDigit(IRGenerator* self, u64 value) {
  Dbg("load_digit '%llu'", value);
  Instruction* i;
  unwrap(AllocateSingle(&self->instructions.allocator, &i));

  i->tag = InstrTagLoadDigit;
  i->value.load_digit = value;
}

inline void VisitLoadField(IRGenerator* self, u8 const* name, u16 name_length) {
  Dbg("load_field '%.*s'", name_length, name);
  Instruction* i;
  unwrap(AllocateSingle(&self->instructions.allocator, &i));

  i->tag = InstrTagLoadField;
  i->value.load_field.name = name;
  i->value.load_field.name_length = name_length;
}

inline void VisitCall(IRGenerator* self, u8 const* name, u16 name_length, u16 args_count) {
  Dbg("call '%.*s' args:%hu", name_length, name, args_count);
  Instruction* i;
  unwrap(AllocateSingle(&self->instructions.allocator, &i));

  i->tag = InstrTagCall;
  i->value.call.name = name;
  i->value.call.name_length = name_length;
  i->value.call.args_count = args_count;
}