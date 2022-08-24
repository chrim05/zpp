#pragma once
#include "/pck/sys/include/sys.h"
#include "/pck/sys/include/dbg.h"
#include "token.h"

struct IRGenerator {
  int placeholder;
};

inline void InitIRGenerator(IRGenerator* self) {

}

inline void VisitFnDeclaration(IRGenerator* self, u8 modifier_export, Token const* name) {
  Dbg("%sfn %.*s", modifier_export ? "export " : "", name->Length, GetTokenValue(name));
}

inline void VisitArgDeclaration(IRGenerator* self, Token const* name) {
  Dbg("arg -> %.*s", name->Length, GetTokenValue(name));
}

inline void VisitTypeNameNotation(IRGenerator* self, Token const* type_name) {
  Dbg("type -> %.*s", type_name->Length, GetTokenValue(type_name));
}