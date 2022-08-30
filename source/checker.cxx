#include "checker.h"
#include "compilation_manager.h"

void CheckFnDoublyDeclared(IRGenerator const* self, u64 fn_to_check_index) {
  auto instruction_values = GetInternalBuffer(&self->instruction_values);
  auto instruction_locations = GetInternalBuffer(&self->instruction_locations);
  auto functions = GetInternalBuffer(&self->functions);
  auto functions_length = VectorLength(&self->functions);
  auto fn_to_check = &instruction_values[fn_to_check_index].fn_decl;

  for (u64 i = 0; i < functions_length; i++) {
    auto fn_index = functions[i];

    if (fn_index >= fn_to_check_index)
      return;

    auto fn = &instruction_values[fn_index].fn_decl;

    if (fn->name_length == fn_to_check->name_length and SmallFixedCStringsAreEqual(fn->name, fn_to_check->name, fn->name_length))
      ReportDoublyDeclared(&instruction_locations[fn_to_check_index], fn->name, fn->name_length);
  }
}

void ProcessLoadPtrType(IRGenerator* self) {
  auto pointee_type = self->current_type;
  AllocateSingle(self->allocator, &self->current_type.value.ptr.pointee_type);
  *self->current_type.value.ptr.pointee_type = pointee_type;

  self->current_type.tag = TypeTagPtr;
}

void ProcessLoadBuiltinType(IRGenerator* self, u8 type_code) {
  self->current_type.tag = TypeTagBuiltin;
  self->current_type.value.builtin_type_code = type_code;
}

void Declare(IRGenerator* self, u64 instr_index, u8 type_tag, TypeValue type_value) {
  VectorPush(&self->local_indexes, instr_index);
  VectorPush(&self->local_type_tags, type_tag);
  VectorPush(&self->local_type_values, type_value);
}

void SearchDeclared(
  IRGenerator* self, u8* type_tag_out, TypeValue* type_value_out,
  u8 const* name, u16 name_length, SourceLocation const* location
) {
  auto instruction_tags = GetInternalBuffer(&self->instruction_tags);
  auto instruction_values = GetInternalBuffer(&self->instruction_values);

  auto local_indexes = GetInternalBuffer(&self->local_indexes);
  auto local_indexes_length = VectorLength(&self->local_indexes);
  auto local_type_tags = GetInternalBuffer(&self->local_type_tags);
  auto local_type_values = GetInternalBuffer(&self->local_type_values);

  for (u64 i = 0; i < local_indexes_length; i++) {
    auto index = local_indexes[i];
    auto type_tag = local_type_tags[i];
    auto type_value = local_type_values[i];

    auto it = instruction_tags[index];

    if (it != InstrTagArgDecl)
      continue;
    
    auto iv = &instruction_values[index];

    if (iv->load_name.name_length != name_length or !SmallFixedCStringsAreEqual(iv->load_name.name, name, name_length))
      continue;
    
    *type_tag_out = type_tag;
    *type_value_out = type_value;
    return;
  }

  ReportNotDeclared(location, name, name_length);
}

void CheckLoadName(IRGenerator* self, u8 const* name, u16 name_length, SourceLocation const* location) {
  u8* head_tag;
  unwrap(AllocateSingle(&self->stack_type_tags.allocator, &head_tag));

  TypeValue* head_value;
  unwrap(AllocateSingle(&self->stack_type_values.allocator, &head_value));

  SearchDeclared(self, head_tag, head_value, name, name_length, location);
}

void CheckLoadDigit(IRGenerator* self) {
  u8* head_tag;
  unwrap(AllocateSingle(&self->stack_type_tags.allocator, &head_tag));

  TypeValue* head_value;
  unwrap(AllocateSingle(&self->stack_type_values.allocator, &head_value));

  *head_tag = TypeTagBuiltin;
  head_value->builtin_type_code = BuiltinTypeTagLiteralInt;
}

void LoadFunctionReturnType(IRGenerator* self, Type ret_type) {
  u8* head_tag;
  unwrap(AllocateSingle(&self->stack_type_tags.allocator, &head_tag));

  TypeValue* head_value;
  unwrap(AllocateSingle(&self->stack_type_values.allocator, &head_value));

  *head_tag = ret_type.tag;
  *head_value = ret_type.value;
}

u8 BuiltinTypesAreCompatible(TypeValue const* lvalue_ref, TypeValue const* rvalue_ref) {
  if ((lvalue_ref->builtin_type_code == BuiltinTypeTagLiteralInt) | (rvalue_ref->builtin_type_code == BuiltinTypeTagLiteralInt))
    return true;
  
  return lvalue_ref->builtin_type_code == rvalue_ref->builtin_type_code;
}

u8 TypeIsLiteralInt(u8 tag, TypeValue const* value_ref) {
  return tag == TypeTagBuiltin and value_ref->builtin_type_code == BuiltinTypeTagLiteralInt;
}

void CheckBin(IRGenerator* self, SourceLocation const* location) {
  auto rtag_ref = VectorPopRef(&self->stack_type_tags);
  auto rvalue_ref = VectorPopRef(&self->stack_type_values);
  auto ltag_ref = VectorLastRef(&self->stack_type_tags);
  auto lvalue_ref = VectorLastRef(&self->stack_type_values);

  // when terms are not numbers
  if (*rtag_ref != TypeTagBuiltin or *ltag_ref != TypeTagBuiltin)
    ReportBinNotNumbers(location);
  // otherwise checking that those numbers types are equal
  else if (!BuiltinTypesAreCompatible(lvalue_ref, rvalue_ref))
    ReportBinIncompatible(location);
  
  // when the left term (which is not actually popped)
  // is a literal int type, we try to replace it with the
  // right int type which could be a concrete one
  if (TypeIsLiteralInt(*ltag_ref, lvalue_ref))
    lvalue_ref->builtin_type_code = rvalue_ref->builtin_type_code;
}

void SearchFunction(
  IRGenerator* self, InstructionValue const** iv_out,
  u8 const* name, u16 name_length, SourceLocation const* location
) {
  auto functions_length = VectorLength(&self->functions);
  auto instruction_values = GetInternalBuffer(&self->instruction_values);
  auto function_indexes = GetInternalBuffer(&self->functions);

  for (u64 i = 0; i < functions_length; i++) {
    auto index = function_indexes[i];
    *iv_out = &instruction_values[index];

    if ((*iv_out)->fn_decl.name_length != name_length or !SmallFixedCStringsAreEqual((*iv_out)->fn_decl.name, name, name_length))
      continue;
    
    return;
  }

  ReportNotDeclared(location, name, name_length);
  Unreachable;
}

u8 PtrTypesAreCompatible(TypeValue* expected_value, TypeValue* found_value) {
  return TypesAreCompatible(
    expected_value->ptr.pointee_type->tag,
    &expected_value->ptr.pointee_type->value,

    found_value->ptr.pointee_type->tag,
    &found_value->ptr.pointee_type->value
  );
}

u8 TypesAreCompatible(u8 expected_tag, TypeValue* expected_value, u8 found_tag, TypeValue* found_value) {
  if (expected_tag != found_tag)
    return false;
  
  switch (expected_tag) {
    case TypeTagBuiltin: return BuiltinTypesAreCompatible(expected_value, found_value);
    case TypeTagPtr: return PtrTypesAreCompatible(expected_value, expected_value);
    default: Unreachable;
  }
}

void CheckTypesMismatch(SourceLocation const* location, u8 expected_tag, TypeValue* expected_value, u8 found_tag, TypeValue* found_value) {
  if (!TypesAreCompatible(expected_tag, expected_value, found_tag, found_value))
    ReportTypesMismatch(location);
}

void CheckCall(IRGenerator* self, InstructionValue const* value, SourceLocation const* location) {
  InstructionValue const* fn_instr;
  SearchFunction(self, &fn_instr, value->call.name, value->call.name_length, location);

  // checking that the args count match between decl and call
  if (value->call.args_count != fn_instr->fn_decl.args_count)
    ReportWrongNumberOfArgs(location);
  
  // checking that arg types match
  for (u16 i = 0; i < fn_instr->fn_decl.args_count; i++) {
    auto expected_tag = *VectorPopRef(&self->stack_type_tags);
    auto expected_value = VectorPopRef(&self->stack_type_values);
    auto found_tag = fn_instr->fn_decl.checker_info->arg_type_tags[i];
    auto found_value = &fn_instr->fn_decl.checker_info->arg_type_values[i];

    // expecting the types match
    CheckTypesMismatch(location, expected_tag, expected_value, found_tag, found_value);
  }
  
  // loading on the stack the return type
  LoadFunctionReturnType(self, fn_instr->fn_decl.checker_info->ret_type);
}

void CreateFunctionPrototype(IRGenerator* self, u64 fn_instr_index, InstructionValue* fn_value) {
  auto instruction_tags = GetInternalBuffer(&self->instruction_tags);
  auto instruction_values = GetInternalBuffer(&self->instruction_values);
  
  // skipping the fn_decl instr
  fn_instr_index++;

  unwrap(AllocateSingle(self->allocator, &fn_value->fn_decl.checker_info));
  unwrap(AllocateSlice(self->allocator, &fn_value->fn_decl.checker_info->arg_indexes, fn_value->fn_decl.args_count));
  unwrap(AllocateSlice(self->allocator, &fn_value->fn_decl.checker_info->arg_type_tags, fn_value->fn_decl.args_count));
  unwrap(AllocateSlice(self->allocator, &fn_value->fn_decl.checker_info->arg_type_values, fn_value->fn_decl.args_count));

  // prototyping args
  u32 i = 0;
  for (u16 args_counter = 0; args_counter < fn_value->fn_decl.args_count; i++) {
    auto index = fn_instr_index + i;
    auto tag = instruction_tags[index];
    auto value = &instruction_values[index];

    if (tag == InstrTagArgDecl) {
      fn_value->fn_decl.checker_info->arg_type_tags[args_counter] = self->current_type.tag;
      fn_value->fn_decl.checker_info->arg_type_values[args_counter] = self->current_type.value;
      fn_value->fn_decl.checker_info->arg_indexes[args_counter] = index;

      args_counter++;
      continue;
    }

    switch (tag) {
      case InstrTagLoadBuiltinType: ProcessLoadBuiltinType(self, value->load_builtin_type.type_code); break;
      case InstrTagLoadPtrType: ProcessLoadPtrType(self); break;
      default: Unreachable;
    }
  }

  // skipping the arg_decl instr
  i++;

  // prototyping ret type
  for (; true; i++) {
    auto index = fn_instr_index + i;
    auto tag = instruction_tags[index];
    auto value = &instruction_values[index];

    if (tag == InstrTagNamedBlockDecl) {
      fn_value->fn_decl.checker_info->ret_type = self->current_type;
      break;
    }

    switch (tag) {
      case InstrTagLoadBuiltinType: ProcessLoadBuiltinType(self, value->load_builtin_type.type_code); break;
      case InstrTagLoadPtrType: ProcessLoadPtrType(self); break;
      default: Unreachable;
    }
  }

  // setting the first statement index (+ 1 because we need to skip the named_block_decl instr)
  fn_value->fn_decl.checker_info->first_stmt_index = fn_instr_index + i + 1;
}

void CreateFunctionPrototypes(IRGenerator* self) {
  auto functions = GetInternalBuffer(&self->functions);
  auto functions_length = VectorLength(&self->functions);
  auto instruction_values = GetInternalBuffer(&self->instruction_values);

  for (u64 i = 0; i < functions_length; i++) {
    auto fn_instr_index = functions[i];
    auto value = &instruction_values[fn_instr_index];

    CheckFnDoublyDeclared(self, fn_instr_index);
    CreateFunctionPrototype(self, fn_instr_index, value);
  }
}

void CheckFunction(IRGenerator* self, u64 i) {
  auto instruction_tags = GetInternalBuffer(&self->instruction_tags);
  auto instruction_values = GetInternalBuffer(&self->instruction_values);
  auto instruction_locations = GetInternalBuffer(&self->instruction_locations);
  auto stmts_count = instruction_values[i - 1].named_block_decl.stmts_count;
  
  // checking statements
  for (u32 j = 0; j < stmts_count; i++) {
    auto tag = instruction_tags[i];
    auto value = &instruction_values[i];
    auto location = &instruction_locations[i];

    switch (tag) {
      // expressions
      case InstrTagLoadName: CheckLoadName(self, value->load_name.name, value->load_name.name_length, location); break;
      case InstrTagLoadDigit: CheckLoadDigit(self); break;
      case InstrTagBin: CheckBin(self, location); break;
      case InstrTagCall: CheckCall(self, value, location); break;

      // statements
      case InstrTagQuitStmt: j++; break;
      case InstrTagPassStmt: j++; break;

      default:
        Dbg("unbound instr tag %u", tag);
        Unreachable;
    }
  }
}

void DeclareFunctionPrototype(IRGenerator* self, InstructionValue* fn_value) {
  // declaring args
  for (u16 i = 0; i < fn_value->fn_decl.args_count; i++)
    Declare(
      self,
      fn_value->fn_decl.checker_info->arg_indexes[i],
      fn_value->fn_decl.checker_info->arg_type_tags[i],
      fn_value->fn_decl.checker_info->arg_type_values[i]
    );
  
  // declaring ret type name
  auto named_block_instr_index = fn_value->fn_decl.checker_info->first_stmt_index - 1;
  Declare(
    self,
    named_block_instr_index,
    fn_value->fn_decl.checker_info->ret_type.tag,
    fn_value->fn_decl.checker_info->ret_type.value
  );
}

void ClearLocals(IRGenerator* self) {
  VectorClear(&self->local_indexes);
  VectorClear(&self->local_type_tags);
  VectorClear(&self->local_type_values);
}

void CheckFunctions(IRGenerator* self) {
  auto functions = GetInternalBuffer(&self->functions);
  auto functions_length = VectorLength(&self->functions);
  auto instruction_values = GetInternalBuffer(&self->instruction_values);

  for (u64 i = 0; i < functions_length; i++) {
    auto fn_instr_index = functions[i];
    auto value = &instruction_values[fn_instr_index];

    ClearLocals(self);
    DeclareFunctionPrototype(self, value);
    CheckFunction(self, value->fn_decl.checker_info->first_stmt_index);
  }
}

void CheckIR(IRGenerator* self) {
  // this takes a cycle O(n)
  // where n is the number of functions
  CreateFunctionPrototypes(self);

  // O(n*k)
  // where n is the number of functions
  // where k is the number of instructions of that function
  CheckFunctions(self);
}