#include "checker.h"
#include "compilation_manager.h"

void CheckFnDoublyDeclared(IRGenerator* self, i64 until_index, u64 fn_to_check_index) {
  auto fn_buf = GetInternalBuffer(&self->functions);
  auto instructions_buf = GetInternalBuffer(&self->instruction_values);
  auto fn_to_check = instructions_buf[fn_to_check_index].fn_decl;

  for (i64 i = 0; i < until_index; i++) {
    auto fn = instructions_buf[fn_buf[i]].fn_decl;
    auto name = fn.name;
    auto name_length = fn.name_length;

    if (name_length == fn_to_check.name_length and SmallFixedCStringsAreEqual(name, fn_to_check.name, name_length)) {
      auto locations_buf = GetInternalBuffer(&self->instruction_locations);
      ReportDoublyDeclared(&locations_buf[i], name, name_length);
    }
  }
}

void CheckIR(IRGenerator* self) {
  auto fn_length = VectorLength(&self->functions);
  auto fn_buf = GetInternalBuffer(&self->functions);

  for (u64 i = 0; i < fn_length; i++) {
    auto fn_index = fn_buf[i];

    // checking for double declaration
    CheckFnDoublyDeclared(self, i, fn_index);
  }
}