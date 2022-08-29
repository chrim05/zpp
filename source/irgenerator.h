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
constexpr u8 InstrTagLoadType = 2;
constexpr u8 InstrTagLoadPtrType = 3;
constexpr u8 InstrTagNamedBlockDecl = 4;
constexpr u8 InstrTagPassStmt = 5;
constexpr u8 InstrTagBin = 6;
constexpr u8 InstrTagLoadName = 7;
constexpr u8 InstrTagQuitStmt = 8;
constexpr u8 InstrTagLoadDigit = 9;
constexpr u8 InstrTagLoadField = 10;
constexpr u8 InstrTagCall = 11;
constexpr u8 InstrTagLoadBuiltinType = 12;

constexpr u8 BuiltinTypeTagU8 = 0;
constexpr u8 BuiltinTypeTagU16 = 1;
constexpr u8 BuiltinTypeTagU32 = 2;
constexpr u8 BuiltinTypeTagU64 = 3;
constexpr u8 BuiltinTypeTagI8 = 4;
constexpr u8 BuiltinTypeTagI16 = 5;
constexpr u8 BuiltinTypeTagI32 = 6;
constexpr u8 BuiltinTypeTagI64 = 7;
constexpr u8 BuiltinTypeTagLiteralInt = 8;

constexpr u8 TypeTagBuiltin = 0;
constexpr u8 TypeTagPtr = 1;

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
  } load_type;

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

  struct {
    u8 op;
  } bin;
  
  struct {
    u8 type_code;
  } load_builtin_type;

  u64 load_digit;
};

struct Type;

union TypeValue {
  struct {
    Type* pointee_type;
  } ptr;

  u8 builtin_type_code;
};

struct Type {
  u8 tag;
  TypeValue value;
};

struct IRGenerator {
  Vector<SourceLocation> instruction_locations;
  Vector<u8> instruction_tags;
  Vector<InstructionValue> instruction_values;
  Vector<u64> functions;

  Vector<u64> local_indexes;
  Vector<u8> local_type_tags;
  Vector<TypeValue> local_type_values;

  Type current_type;
  MemRegion* allocator;

  Vector<u8> stack_type_tags;
  Vector<TypeValue> stack_type_values;
};

inline void InitIRGenerator(IRGenerator* self, MemRegion* allocator) {
  unwrap(InitVector(&self->instruction_locations, 1'000'000));
  unwrap(InitVector(&self->instruction_tags, 1'000'000));
  unwrap(InitVector(&self->instruction_values, 1'000'000));
  unwrap(InitVector(&self->functions, 10'000));

  unwrap(InitVector(&self->local_indexes, 500));
  unwrap(InitVector(&self->local_type_tags, 500));
  unwrap(InitVector(&self->local_type_values, 500));

  self->allocator = allocator;

  unwrap(InitVector(&self->stack_type_tags, 16));
  unwrap(InitVector(&self->stack_type_values, 16));
}

inline u64 VisitFnDeclaration(
  IRGenerator* self,
  u8 modifier_export,
  u8 const* name,
  u16 name_length,
  SourceLocation location
) {
  Dbg("fn_decl modifier_export:%u '%.*s'", modifier_export, name_length, name);

  InstructionValue* i;
  VectorPush(&self->instruction_locations, location);
  VectorPush(&self->instruction_tags, InstrTagDeclFn);
  unwrap(AllocateSingle(&self->instruction_values.allocator, &i));

  i->fn_decl.name = name;
  i->fn_decl.name_length = name_length;
  i->fn_decl.args_count = 0;

  // index of this instruction
  return VectorLength(&self->instruction_values) - 1;
}

inline void VisitArgDeclaration(IRGenerator* self, u8 const* name, u16 name_length, SourceLocation location) {
  Dbg("arg_decl '%.*s'", name_length, name);

  InstructionValue* i;
  VectorPush(&self->instruction_locations, location);
  VectorPush(&self->instruction_tags, InstrTagArgDecl);
  unwrap(AllocateSingle(&self->instruction_values.allocator, &i));

  i->arg_decl.name = name;
  i->arg_decl.name_length = name_length;
}

inline void VisitTypeLoadType(IRGenerator* self, u8 const* name, u16 name_length, SourceLocation location) {
  Dbg("load_type '%.*s'", name_length, name);
  
  InstructionValue* i;
  VectorPush(&self->instruction_locations, location);
  VectorPush(&self->instruction_locations, location);
  VectorPush(&self->instruction_tags, InstrTagLoadType);
  unwrap(AllocateSingle(&self->instruction_values.allocator, &i));

  i->load_type.name = name;
  i->load_type.name_length = name_length;
}

inline void VisitTypeLoadBuiltinType(IRGenerator* self, u8 type_code, SourceLocation location) {
  Dbg("load_builtin_type '%u'", type_code);
  
  InstructionValue* i;
  VectorPush(&self->instruction_locations, location);
  VectorPush(&self->instruction_tags, InstrTagLoadBuiltinType);
  unwrap(AllocateSingle(&self->instruction_values.allocator, &i));

  i->load_builtin_type.type_code = type_code;
}

inline void VisitTypeLoadPtrType(IRGenerator* self, SourceLocation location) {
  DbgString("mk_ptr_typed");
  
  InstructionValue* i;
  unwrap(AllocateSingle(&self->instruction_values.allocator, &i));

  VectorPush(&self->instruction_locations, location);
  VectorPush(&self->instruction_tags, InstrTagLoadPtrType);
}

inline u64 VisitBlockNameDeclaration(IRGenerator* self, u8 const* name, u16 name_length, SourceLocation location) {
  Dbg("named_block_decl '%.*s'", name_length, name);
  
  InstructionValue* i;
  VectorPush(&self->instruction_locations, location);
  VectorPush(&self->instruction_tags, InstrTagNamedBlockDecl);
  unwrap(AllocateSingle(&self->instruction_values.allocator, &i));

  i->named_block_decl.name = name;
  i->named_block_decl.name_length = name_length;
  i->named_block_decl.stmts_count = 0;

  // index of this instruction
  return VectorLength(&self->instruction_values) - 1;
}

inline void VisitPassStmt(IRGenerator* self, SourceLocation location) {
  DbgString("pass_stmt");

  InstructionValue* i;
  unwrap(AllocateSingle(&self->instruction_values.allocator, &i));
  
  VectorPush(&self->instruction_locations, location);
  VectorPush(&self->instruction_tags, InstrTagPassStmt);
}

inline void VisitQuitStmt(IRGenerator* self, u8 const* name, u16 name_length, SourceLocation location) {
  Dbg("quit_stmt '%.*s'", name_length, name);
  
  InstructionValue* i;
  VectorPush(&self->instruction_locations, location);
  VectorPush(&self->instruction_tags, InstrTagQuitStmt);
  unwrap(AllocateSingle(&self->instruction_values.allocator, &i));

  i->quit_stmt.name = name;
  i->quit_stmt.name_length = name_length;
}

inline void VisitBinaryOperation(IRGenerator* self, u8 bin_op_tag, SourceLocation location) {
  Dbg("bin '%c'", bin_op_tag);
  
  InstructionValue* i;
  VectorPush(&self->instruction_locations, location);
  VectorPush(&self->instruction_tags, InstrTagBin);
  unwrap(AllocateSingle(&self->instruction_values.allocator, &i));

  i->bin.op = bin_op_tag;
}

inline void VisitLoadName(IRGenerator* self, u8 const* name, u16 name_length, SourceLocation location) {
  Dbg("load_name '%.*s'", name_length, name);
  
  InstructionValue* i;
  VectorPush(&self->instruction_locations, location);
  VectorPush(&self->instruction_tags, InstrTagLoadName);
  unwrap(AllocateSingle(&self->instruction_values.allocator, &i));

  i->load_name.name = name;
  i->load_name.name_length = name_length;
}

inline void VisitLoadDigit(IRGenerator* self, u64 value, SourceLocation location) {
  Dbg("load_digit '%llu'", value);
  
  InstructionValue* i;
  VectorPush(&self->instruction_locations, location);
  VectorPush(&self->instruction_tags, InstrTagLoadDigit);
  unwrap(AllocateSingle(&self->instruction_values.allocator, &i));

  i->load_digit = value;
}

inline void VisitLoadField(IRGenerator* self, u8 const* name, u16 name_length, SourceLocation location) {
  Dbg("load_field '%.*s'", name_length, name);
  
  InstructionValue* i;
  VectorPush(&self->instruction_locations, location);
  VectorPush(&self->instruction_tags, InstrTagLoadField);
  unwrap(AllocateSingle(&self->instruction_values.allocator, &i));

  i->load_field.name = name;
  i->load_field.name_length = name_length;
}

inline void VisitCall(IRGenerator* self, u8 const* name, u16 name_length, u16 args_count, SourceLocation location) {
  Dbg("call '%.*s' args:%hu", name_length, name, args_count);
  
  InstructionValue* i;
  VectorPush(&self->instruction_locations, location);
  VectorPush(&self->instruction_tags, InstrTagCall);
  unwrap(AllocateSingle(&self->instruction_values.allocator, &i));

  i->call.name = name;
  i->call.name_length = name_length;
  i->call.args_count = args_count;
}