#pragma once
#include "compilation_manager.h"
#include "irgenerator.h"
#include "/pck/sys/include/strings.h"

struct ZppParser {
  // contains the source code and its size
  CompilationInfo* SourceReference;
  MemRegion* Allocator;
  // points to the current char
  u64 Index;
  // the ast visitor
  IRGenerator* AstVisitor;
};

inline void InitZppParser(
  ZppParser* self, MemRegion* allocator, CompilationInfo* compilation_info,
  IRGenerator* ir_generator
) {
  self->SourceReference = compilation_info;
  self->Allocator = allocator;
  self->Index = 0;
  self->AstVisitor = ir_generator;
}

struct Token {
  u8 TokenKind;
  RangedString value;
};

// ! return true whether `c` is a skippable character
inline u8 IsWhitespaceChar(u8 c) {
  return
    c == ' ' or
    c == '\n' or
    c == '\t';
}

inline u8 IsWhitespaceChar(u8 c) {
  return
    c == ' ' or
    c == '\n' or
    c == '\t';
}

inline u8 GetCurrentChar(ZppParser* self) {
  return self->SourceReference->Buffer[self->Index];
}

// ! return true whether there is at least one character (which is not whitespace)
// ! `i` will be setted to the index of the first non whitespace character
u8 HasNextTokenAndEatWhitespaces(ZppParser* self);

// ! parse a single global node (such as fn types ...)
error VisitNextGlobalNode(ZppParser* self);

// ! parse the entire file
void VisitGlobalScope(ZppParser* self);

error CollectNextToken(ZppParser* self, Token* next_token_out);