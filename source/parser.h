#pragma once
#include "irgenerator.h"
#include "../pck/sys/include/strings.h"
#include "token.h"

struct ZppParser {
  // contains the source code and its size
  CompilationInfo* source_reference;
  MemRegion* allocator;

  // points to the current char
  u64 index;

  // the ast visitor
  IRGenerator ast_visitor;

  // the lexed token
  Token current;
};

inline void InitZppParser(
  ZppParser* self, MemRegion* allocator, CompilationInfo* compilation_info
) {
  self->source_reference = compilation_info;
  self->allocator = allocator;
  self->index = 0;
}

// ! return true whether `c` is a skippable character
// ! (such as ' ' '\n' ...)
inline u8 IsWhitespaceChar(u8 c) {
  return
    c == ' ' or
    c == '\n' or
    c == '\t'
  ;
}

inline u8 IsAlpha(u8 c) {
  return
    (c >= 'a' and c <= 'z') or
    (c >= 'A' and c <= 'Z')
  ;
}

inline u8 IsDigitChar(u8 c) {
  return
    c >= '0' and c <= '9'
  ;
}

// ! return true whether `c` is alpha or '_'
inline u8 IsFirstIdentifierChar(u8 c) {
  return
    IsAlpha(c) or
    c == '_'
  ;
}

// ! return true whether `c` is alpha or '_' or num
inline u8 IsMiddleIdentifierChar(u8 c) {
  return
    IsFirstIdentifierChar(c) or
    IsDigitChar(c)
  ;
}

inline u8 GetCurrentChar(ZppParser const* self) {
  return self->source_reference->buffer[self->index];
}

inline u8 ReachedEof(ZppParser const* self) {
  return self->index >= self->source_reference->buffer_size;
}

// ! return true whether there is at least one character (which is not whitespace)
// ! `i` will be setted to the index of the first non whitespace character
u8 HasNextTokenAndEatWhitespaces(ZppParser* self);

void ParseFnGlobalNode(ZppParser* self);

// ! parse a single global node (such as fn types ...)
void ParseNextGlobalNode(ZppParser* self);

// ! parse the entire file
void ParseGlobalScope(ZppParser* self);

void CollectNextToken(ZppParser* self);

void CollectNextTokenAndExpect(ZppParser* self, u8 expected_token_tag);

void CollectIdentifierToken(ZppParser* self);

void CollectDigitToken(ZppParser* self);

void TryToReplaceIdentifierWithKeyword(Token* token);

void EatWhitespaces(ZppParser* self);

void ExpectToken(Token const* found_token, u8 expected_token_tag);

u8 MatchToken(ZppParser* self, u8 token_tag_to_match);

u16 ParseFnCall(ZppParser* self);

void ParseExpression(ZppParser* self);