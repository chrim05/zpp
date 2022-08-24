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

struct FnDecl {
  u8 const* name;
  u16 name_length;
  u16 args_count;
};

union InstructionValue {
  FnDecl fn_decl;
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

inline void VisitArgDeclaration(IRGenerator* self, Token const* name) {
  Dbg("arg -> %.*s", name->length, GetTokenValue(name));
}

inline void VisitTypeNameNotation(IRGenerator* self, Token const* type_name) {
  Dbg("type -> %.*s", type_name->length, GetTokenValue(type_name));
}