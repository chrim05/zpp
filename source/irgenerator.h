#pragma once
#include "/pck/sys/include/sys.h"
#include "/pck/sys/include/dbg.h"
#include "/pck/sys/include/collections.h"
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

struct FnDecl {
  u8 const* name;
  u16 name_length;
  u16 args_count;
};

struct ArgDecl {
  u8 const* name;
  u16 name_length;
};

struct NamedBlockDecl {
  u8 const* name;
  u16 name_length;
  u64 stmts_count;
};

// ! u8 | ... | MyType | ...
struct MkTyped {
  u8 const* name;
  u16 name_length;
};

union InstructionValue {
  FnDecl fn_decl;
  ArgDecl arg_decl;
  MkTyped mk_typed_from_name;
  NamedBlockDecl named_block_decl;
};

struct Instruction {
  u16 tag;
  InstructionValue value;
};

inline Instruction CreateInstruction(u16 tag, InstructionValue value) {
  return (Instruction) {
    .tag = tag,
    .value = value
  };
}

struct IRGenerator {
  Vector<Instruction> instructions;
};

inline void InitIRGenerator(IRGenerator* self) {
  catch(InitVector(&self->instructions, 1'000), {
    DbgString("Failed to allocate IRGenerator");
  });
  // InitVector(&self->functions, 100);
  // InitVector(&self->types, 100);
}

inline u64 VisitFnDeclaration(
  IRGenerator* self,
  SourceLocation* decl_location,
  u8 modifier_export,
  u8 const* name,
  u16 name_length
) {
  Dbg("fn_decl modifier_export:%u '%.*s'", modifier_export, name_length, name);
  VectorPush(
    &self->instructions,
    CreateInstruction(InstrTagDeclFn, (InstructionValue) {
      .fn_decl = (FnDecl) { .name = name, .name_length = name_length, .args_count = 0 }
    })
  );

  return VectorLength(&self->instructions) - 1;
}

inline void VisitArgDeclaration(IRGenerator* self, u8 const* name, u16 name_length) {
  Dbg("arg_decl '%.*s'", name_length, name);
  VectorPush(
    &self->instructions,
    CreateInstruction(InstrTagArgDecl, (InstructionValue) {
      .arg_decl = (ArgDecl) { .name = name, .name_length = name_length }
    })
  );
}

inline void VisitTypeMkTyped(IRGenerator* self, u8 const* name, u16 name_length) {
  Dbg("mk_typed '%.*s'", name_length, name);
  VectorPush(
    &self->instructions,
    CreateInstruction(InstrTagMkTyped, (InstructionValue) {
      .mk_typed_from_name = (MkTyped) { .name = name, .name_length = name_length }
    })
  );
}

inline void VisitTypeMkPtrTyped(IRGenerator* self) {
  DbgString("mk_ptr_typed");
  VectorPush(
    &self->instructions,
    CreateInstruction(InstrTagMkPtrTyped, (InstructionValue) {
      
    })
  );
}

inline u64 VisitBlockNameDeclaration(IRGenerator* self, u8 const* name, u16 name_length) {
  Dbg("named_block_decl '%.*s'", name_length, name);
  VectorPush(
    &self->instructions,
    CreateInstruction(InstrTagNamedBlockDecl, (InstructionValue) {
      .named_block_decl = (NamedBlockDecl) { .name = name, .name_length = name_length, .stmts_count = 0 }
    })
  );

  return VectorLength(&self->instructions) - 1;
}

inline void VisitPassStmt(IRGenerator* self) {
  DbgString("pass_stmt");
  VectorPush(
    &self->instructions,
    CreateInstruction(InstrTagPassStmt, (InstructionValue) {

    })
  );
}