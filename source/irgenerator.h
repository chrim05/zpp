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

struct FnDecl {
  u8 const* name;
  u16 name_length;
  u16 args_count;
};

struct ArgDecl {
  u8 const* name;
  u16 name_length;
};

// ! u8 | ... | MyType | ...
struct MkTypedFromName {
  u8 const* name;
  u16 name_length;
};

union InstructionValue {
  FnDecl fn_decl;
  ArgDecl arg_decl;
  MkTypedFromName mk_typed_from_name;
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
  catch(InitVector(&self->instructions, 100), {
    DbgString("Failed to allocate IRGenerator");
  });
  // InitVector(&self->functions, 100);
  // InitVector(&self->types, 100);
}

inline u32 VisitFnDeclaration(
  IRGenerator* self,
  SourceLocation* decl_location,
  u8 modifier_export,
  u8 const* name,
  u16 name_length
) {
  Dbg("%sfn %.*s", modifier_export ? "export " : "", name_length, name);
  VectorPush(
    &self->instructions,
    CreateInstruction(InstrTagDeclFn, (InstructionValue) {
      .fn_decl = (FnDecl) { .name = name, .name_length = name_length, .args_count = 0 }
    })
  );

  return VectorLength(&self->instructions) - 1;
}

inline void VisitArgDeclaration(IRGenerator* self, u8 const* name, u16 name_length) {
  Dbg("arg -> %.*s", name_length, name);
  VectorPush(
    &self->instructions,
    CreateInstruction(InstrTagArgDecl, (InstructionValue) {
      .arg_decl = (ArgDecl) { .name = name, .name_length = name_length }
    })
  );
}

inline void VisitTypeNameNotationFromName(IRGenerator* self, u8 const* name, u16 name_length) {
  Dbg("type -> %.*s", name_length, name);
  VectorPush(
    &self->instructions,
    CreateInstruction(InstrTagMkTyped, (InstructionValue) {
      .mk_typed_from_name = (MkTypedFromName) { .name = name, .name_length = name_length }
    })
  );
}