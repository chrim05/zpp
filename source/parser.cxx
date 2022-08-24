#include "parser.h"
#include "compilation_manager.h"

void ParseGlobalScope(ZppParser* self) {
  // collecting all global nodes (such as functions types ...)
  // until the eof
  while (HasNextTokenAndEatWhitespaces(self))
    ParseNextGlobalNode(self);
}

void CollectIdentifierToken(ZppParser* self, Token* next_token_out) {
  next_token_out->Tag = TokenTagIdentifier;
  
  // eating all identifier chars
  while (!ReachedEof(self) and IsMiddleIdentifierChar(GetCurrentChar(self)))
    self->Index++;

  // going back to the last identifier char
  // we go back because the caller will skip the last char
  self->Index--;
}

void SetCurPos(ZppParser* self, SourceLocation* location_out) {
  location_out->Index = self->Index;
  location_out->SourceReference = self->SourceReference;
}

void TryToReplaceIdentifierWithKeyword(Token* token) {
  // skipping this practice for non identifier tokens
  // they will never be potential keywords
  if (token->Tag != TokenTagIdentifier)
    return;
  
  // checking for all keywords ensuring the lenght is the same of the token
  if (token->Length == 2 and SmallFixedCStringsAreEqual( // fn
    token->Location.SourceReference->Buffer + token->Location.Index, static_cstring("fn"), token->Length
  ))
    token->Tag = TokenTagKwFn;

  else if (token->Length == 6 and SmallFixedCStringsAreEqual( // export
    token->Location.SourceReference->Buffer + token->Location.Index, static_cstring("export"), token->Length
  ))
    token->Tag = TokenTagKwExport;
  
  // ? Dbg("token.value: '%.*s' | token.tag: %u", token->Length, token->Location.SourceReference->Buffer + token->Location.Index, token->Tag);
}

void CollectNextToken(ZppParser* self, Token* next_token_out) {
  EatWhitespaces(self);

  // initializing the start position of the token
  SetCurPos(self, &next_token_out->Location);
  auto current_char = GetCurrentChar(self);

  if (IsFirstIdentifierChar(current_char))
    CollectIdentifierToken(self, next_token_out);
  else
    switch (current_char) {
      case '(': next_token_out->Tag = TokenTagSymLPar; break;
      case ')': next_token_out->Tag = TokenTagSymRPar; break;
      case ':': next_token_out->Tag = TokenTagSymColon; break;
      case ',': next_token_out->Tag = TokenTagSymComma; break;
      default:
        ReportUnknownToken(next_token_out);
    }
  
  // initializing the end position of the token
  next_token_out->Length = (self->Index + 1) - next_token_out->Location.Index;

  // when the token is an identifier and its value is a keyword
  // we set its tag to that keyword's one
  TryToReplaceIdentifierWithKeyword(next_token_out);

  // moving to the next character
  self->Index++;
}

void CollectNextTokenAndExpect(ZppParser* self, Token* next_token_out, u8 expected_token_tag) {
  CollectNextToken(self, next_token_out);
  ExpectToken(next_token_out, expected_token_tag);
}

void ExpectToken(Token const* found_token, u8 expected_token_tag) {
  if (found_token->Tag != expected_token_tag)
    ReportExpectedAnotherToken(found_token, expected_token_tag);
}

void ParseType(ZppParser* self) {
  Token type_name;
  CollectNextTokenAndExpect(self, &type_name, TokenTagIdentifier);

  VisitTypeNameNotation(&self->AstVisitor, &type_name);
}

void ParseArgListDeclaration(ZppParser* self) {
  Token discard_token;
  CollectNextTokenAndExpect(self, &discard_token, TokenTagSymLPar);

  // parsing first arg name or close par
  CollectNextToken(self, &discard_token);

  if (discard_token.Tag == TokenTagSymRPar)
    return;

  // parsing the args list declaration
  while (true) {
    // parsing the name
    ExpectToken(&discard_token, TokenTagIdentifier);   

    VisitArgDeclaration(&self->AstVisitor, &discard_token);

    // parsing type notation
    CollectNextTokenAndExpect(self, &discard_token, TokenTagSymColon);
    ParseType(self);

    // checking for another arg
    CollectNextToken(self, &discard_token);
    if (discard_token.Tag != TokenTagSymComma)
      break;
    
    // collecting the name of the next arg
    CollectNextToken(self, &discard_token);
  }

  ExpectToken(&discard_token, TokenTagSymRPar);
}

void ParseFnGlobalNode(ZppParser* self, u8 modifier_export) {
  // parsing fn 'name'
  Token name;
  CollectNextTokenAndExpect(self, &name, TokenTagIdentifier);

  VisitFnDeclaration(&self->AstVisitor, modifier_export, &name);

  // parsing fn name'(a: T, b: T2)'
  ParseArgListDeclaration(self);
}

void ParseNextGlobalNode(ZppParser* self) {
  // has the modifier 'export' keyword before 'fn' 'type' ...
  u8 modifier_export = false;

  Token cur_token;
  CollectNextToken(self, &cur_token);

  // when the collected token is a modifier
  // we recollect the next and set the modifier option to true
  if (cur_token.Tag == TokenTagKwExport) {
    modifier_export = true;
    CollectNextToken(self, &cur_token);
  }

  switch (cur_token.Tag) {
    case TokenTagKwFn:
      ParseFnGlobalNode(self, modifier_export);
      break;

    default:
      ReportUnexpectedTokenInGlobalContext(&cur_token);
  }
}

void EatWhitespaces(ZppParser* self) {
  // eating all next whitespace until the buffer ends
  for (; self->Index < self->SourceReference->BufferSize; self->Index++)
    // or until we match a char which is not a whitespace
    if (!IsWhitespaceChar(GetCurrentChar(self)))
      return;
}

u8 HasNextTokenAndEatWhitespaces(ZppParser* self) {
  // returning false when reached eof, because for sure has not next token
  if (ReachedEof(self))
    return false;
  
  // otherwise we make sure that all the next characters are whitespace
  for (; self->Index < self->SourceReference->BufferSize; self->Index++)
    if (!IsWhitespaceChar(GetCurrentChar(self)))
      // when find a non whitespace character it means there is a next token
      return true;

  // all remaining characters were whitespace
  return false;
}