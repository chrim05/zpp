#include "parser.h"

void VisitGlobalScope(ZppParser* self) {
  // collecting all global nodes (such as functions types ...)
  // until the eof
  while (HasNextTokenAndEatWhitespaces(self))
    VisitNextGlobalNode(self);
}

error CollectNextToken(ZppParser* self, Token* next_token_out) {
  if (IsIdentifierChar(GetCurrentChar(self)))

  return Ok;
}

error VisitNextGlobalNode(ZppParser* self) {
  Token cur_token;
  try(CollectNextToken(self, &cur_token), {});

  return Ok;
}

u8 HasNextTokenAndEatWhitespaces(ZppParser* self) {
  // returning false when reached eof, because for sure has not next token
  if (self->Index >= self->SourceReference->BufferSize)
    return false;
  
  // otherwise we make sure that all the next characters are whitespace
  for (; self->Index < self->SourceReference->BufferSize; self->Index++)
    if (!IsWhitespaceChar(GetCurrentChar(self)))
      // when find a non whitespace character it means there is a next token
      return true;

  // all remaining characters were whitespace
  return false;
}