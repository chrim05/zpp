#include "checker.h"
#include "compilation_manager.h"

void CheckFnDoublyDeclared(
  IRGenerator const* self,
  InstructionValue* instruction_values,
  SourceLocation* instruction_locations,
  u64 fn_to_check_index
) {
  auto functions = GetInternalBuffer(&self->functions);
  auto functions_length = VectorLength(&self->functions);
  auto fn_to_check = instruction_values[fn_to_check_index].fn_decl;

  for (u64 i = 0; i < functions_length; i++) {
    auto fn_index = functions[i];

    if (fn_index >= fn_to_check_index)
      return;

    auto fn = instruction_values[fn_index].fn_decl;
    auto name = fn.name;
    auto name_length = fn.name_length;

    if (name_length == fn_to_check.name_length and SmallFixedCStringsAreEqual(name, fn_to_check.name, name_length)) {
      ReportDoublyDeclared(&instruction_locations[fn_to_check_index], name, name_length);
    }
  }
}

void ProcessLoadPtrType(IRGenerator* self) {
  auto pointee_type = self->current_type;
  AllocateSingle(self->allocator, &self->current_type.value.ptr.pointee_type);
  *self->current_type.value.ptr.pointee_type = pointee_type;

  self->current_type.tag = TypeTagPtr;
}

void Declare(IRGenerator* self, u64 i) {
  VectorPush(&self->local_indexes, i);
  VectorPush(&self->local_type_tags, self->current_type.tag);
  VectorPush(&self->local_type_values, self->current_type.value);
}

void SearchDeclared(
  IRGenerator* self, u8* type_tag_out, TypeValue* type_value_out,
  u8 const* name, u16 name_length, SourceLocation* location
) {
  auto const instruction_tags = GetInternalBuffer(&self->instruction_tags);
  auto const instruction_values = GetInternalBuffer(&self->instruction_values);

  auto const local_indexes = GetInternalBuffer(&self->local_indexes);
  auto const local_type_tags = GetInternalBuffer(&self->local_type_tags);
  auto const local_type_values = GetInternalBuffer(&self->local_type_values);

  for (u64 i = 0; i < VectorLength(&self->local_indexes); i++) {
    auto index = local_indexes[i];
    auto type_tag = local_type_tags[i];
    auto type_value = local_type_values[i];

    auto it = instruction_tags[index];

    if (it != InstrTagArgDecl)
      continue;
    
    auto iv = instruction_values[index];

    if (iv.load_name.name_length != name_length or !SmallFixedCStringsAreEqual(iv.load_name.name, name, name_length))
      continue;
    
    *type_tag_out = type_tag;
    *type_value_out = type_value;
    return;
  }

  ReportNotDeclared(location, name, name_length);
}

void ProcessLoadName(IRGenerator* self, u8 const* name, u16 name_length, SourceLocation* location) {
  u8* head_tag;
  unwrap(AllocateSingle(&self->stack_type_tags.allocator, &head_tag));

  TypeValue* head_value;
  unwrap(AllocateSingle(&self->stack_type_values.allocator, &head_value));

  SearchDeclared(self, head_tag, head_value, name, name_length, location);
}

void ProcessLoadDigit(IRGenerator* self) {
  u8* head_tag;
  unwrap(AllocateSingle(&self->stack_type_tags.allocator, &head_tag));

  TypeValue* head_value;
  unwrap(AllocateSingle(&self->stack_type_values.allocator, &head_value));

  *head_tag = TypeTagBuiltin;
  head_value->builtin_type_code = BuiltinTypeTagLiteralInt;
}

u8 BuiltinTypesAreEqual(TypeValue* lvalue_ref, TypeValue* rvalue_ref) {
  if ((lvalue_ref->builtin_type_code == BuiltinTypeTagLiteralInt) | (lvalue_ref->builtin_type_code == BuiltinTypeTagLiteralInt))
    return true;
  
  return lvalue_ref->builtin_type_code == rvalue_ref->builtin_type_code;
}

void ProcessBin(IRGenerator* self, SourceLocation* location) {
  auto rtag_ref = VectorPopRef(&self->stack_type_tags);
  auto rvalue_ref = VectorPopRef(&self->stack_type_values);
  auto ltag_ref = VectorLastRef(&self->stack_type_tags);
  auto lvalue_ref = VectorLastRef(&self->stack_type_values);

  // when terms are not numbers
  if (*rtag_ref != TypeTagBuiltin or *ltag_ref != TypeTagBuiltin)
    ReportBinNotNumbers(location);
  
  if (BuiltinTypesAreEqual(lvalue_ref, rvalue_ref))
    ReportBinIncompatible(location);
}

void CheckIR(IRGenerator* self) {
  auto instruction_tags = GetInternalBuffer(&self->instruction_tags);
  auto instruction_values = GetInternalBuffer(&self->instruction_values);
  auto instruction_locations = GetInternalBuffer(&self->instruction_locations);

  for (u64 i = 0; i < VectorLength(&self->instruction_tags); i++) {
    auto tag = instruction_tags[i];
    auto value = instruction_values[i];
    auto location = &instruction_locations[i];

    switch (tag) {
      case InstrTagDeclFn:
        VectorClear(&self->local_indexes);
        VectorClear(&self->local_type_tags);
        VectorClear(&self->local_type_tags);
        CheckFnDoublyDeclared(self, instruction_values, instruction_locations, i);
        break;
      
      case InstrTagNamedBlockDecl:
      case InstrTagArgDecl:
        Declare(self, i);
        break;
      
      case InstrTagLoadBuiltinType:
        self->current_type.tag = TypeTagBuiltin;
        self->current_type.value.builtin_type_code = value.load_builtin_type.type_code;
        break;
      
      case InstrTagLoadPtrType:
        ProcessLoadPtrType(self);
        break;
      
      case InstrTagLoadName:
        ProcessLoadName(self, value.load_name.name, value.load_name.name_length, location);
        break;
      
      case InstrTagLoadDigit:
        ProcessLoadDigit(self);
        break;
      
      case InstrTagBin:
        ProcessBin(self, location);
        break;

      default:
        Dbg("unbound instr tag %u", tag);
        Todo;
    }
  }
}