#include "parser.h"
#include "compilation_manager.h"

void ParseGlobalScope(ZppParser* self) {
  // collecting all global nodes (such as functions types ...)
  // until the eof
  while (HasNextTokenAndEatWhitespaces(self))
    ParseNextGlobalNode(self);
}

void CollectIdentifierToken(ZppParser* self, Token* next_token_out) {
  next_token_out->tag = TokenTagIdentifier;
  
  // eating all identifier chars
  while (!ReachedEof(self) and IsMiddleIdentifierChar(GetCurrentChar(self)))
    self->index++;

  // going back to the last identifier char
  // we go back because the caller will skip the last char
  self->index--;
}

void SetCurPos(ZppParser* self, SourceLocation* location_out) {
  location_out->index = self->index;
  location_out->source_reference = self->source_reference;
}

void TryToReplaceIdentifierWithKeyword(Token* token) {
  // skipping this practice for non identifier tokens
  // they will never be potential keywords
  if (token->tag != TokenTagIdentifier)
    return;
  
  // checking for all keywords ensuring the lenght is the same of the token
  if (token->length == 2 and SmallFixedCStringsAreEqual( // fn
    token->location.source_reference->buffer + token->location.index, static_cstring("fn"), token->length
  ))
    token->tag = TokenTagKwFn;

  else if (token->length == 6 and SmallFixedCStringsAreEqual( // export
    token->location.source_reference->buffer + token->location.index, static_cstring("export"), token->length
  ))
    token->tag = TokenTagKwExport;
  
  // ? Dbg("token.value: '%.*s' | token.tag: %u", token->length, token->location.source_reference->buffer + token->location.index, token->tag);
}

void CollectNextToken(ZppParser* self, Token* next_token_out) {
  EatWhitespaces(self);

  // initializing the start position of the token
  SetCurPos(self, &next_token_out->location);
  auto current_char = GetCurrentChar(self);

  if (IsFirstIdentifierChar(current_char))
    CollectIdentifierToken(self, next_token_out);
  else
    switch (current_char) {
      case '(': next_token_out->tag = TokenTagSymLPar; break;
      case ')': next_token_out->tag = TokenTagSymRPar; break;
      case ':': next_token_out->tag = TokenTagSymColon; break;
      case ',': next_token_out->tag = TokenTagSymComma; break;
      default:
        ReportUnknownToken(next_token_out);
    }
  
  // initializing the end position of the token
  next_token_out->length = (self->index + 1) - next_token_out->location.index;

  // when the token is an identifier and its value is a keyword
  // we set its tag to that keyword's one
  TryToReplaceIdentifierWithKeyword(next_token_out);

  // moving to the next character
  self->index++;
}

void CollectNextTokenAndExpect(ZppParser* self, Token* next_token_out, u8 expected_token_tag) {
  CollectNextToken(self, next_token_out);
  ExpectToken(next_token_out, expected_token_tag);
}

void ExpectToken(Token const* found_token, u8 expected_token_tag) {
  if (found_token->tag != expected_token_tag)
    ReportExpectedAnotherToken(found_token, expected_token_tag);
}

void ParseType(ZppParser* self) {
  Token type_name;
  CollectNextTokenAndExpect(self, &type_name, TokenTagIdentifier);

  VisitTypeNameNotation(&self->ast_visitor, &type_name);
}

u16 ParseArgListDeclaration(ZppParser* self) {
  Token discard_token;
  CollectNextTokenAndExpect(self, &discard_token, TokenTagSymLPar);

  // parsing first arg name or close par
  CollectNextToken(self, &discard_token);

  if (discard_token.tag == TokenTagSymRPar)
    return 0;
  
  u16 number_of_args = 0;

  // parsing the args list declaration
  while (true) {
    number_of_args++;
    // parsing the name
    ExpectToken(&discard_token, TokenTagIdentifier);   

    VisitArgDeclaration(&self->ast_visitor, &discard_token);

    // parsing type notation
    CollectNextTokenAndExpect(self, &discard_token, TokenTagSymColon);
    ParseType(self);

    // checking for another arg
    CollectNextToken(self, &discard_token);
    if (discard_token.tag != TokenTagSymComma)
      break;
    
    // collecting the name of the next arg
    CollectNextToken(self, &discard_token);
  }

  ExpectToken(&discard_token, TokenTagSymRPar);
  return number_of_args;
}

void UpdateNumberOfArgsInFnInstr(ZppParser* self, u16 number_of_args, u32 instr_index) {
  auto internal_buffer = GetInternalBuffer(&self->ast_visitor.instructions);
  internal_buffer[instr_index].value.fn_decl.args_count = number_of_args;
}

void ParseFnGlobalNode(ZppParser* self, u8 modifier_export) {
  // parsing fn 'name'
  Token name;
  CollectNextTokenAndExpect(self, &name, TokenTagIdentifier);

  auto instr_index = VisitFnDeclaration(
    &self->ast_visitor,
    &name.location,
    modifier_export,
    GetTokenValue(&name),
    name.length
  );

  // parsing fn name'(a: T, b: T2)'
  auto number_of_args = ParseArgListDeclaration(self);

  UpdateNumberOfArgsInFnInstr(self, number_of_args, instr_index);
}

void ParseNextGlobalNode(ZppParser* self) {
  // has the modifier 'export' keyword before 'fn' 'type' ...
  u8 modifier_export = false;

  Token cur_token;
  CollectNextToken(self, &cur_token);

  // when the collected token is a modifier
  // we recollect the next and set the modifier option to true
  if (cur_token.tag == TokenTagKwExport) {
    modifier_export = true;
    CollectNextToken(self, &cur_token);
  }

  switch (cur_token.tag) {
    case TokenTagKwFn:
      ParseFnGlobalNode(self, modifier_export);
      break;

    default:
      ReportUnexpectedTokenInGlobalContext(&cur_token);
  }
}

void EatWhitespaces(ZppParser* self) {
  // eating all next whitespace until the buffer ends
  for (; self->index < self->source_reference->buffer_size; self->index++)
    // or until we match a char which is not a whitespace
    if (!IsWhitespaceChar(GetCurrentChar(self)))
      return;
}

u8 HasNextTokenAndEatWhitespaces(ZppParser* self) {
  // returning false when reached eof, because for sure has not next token
  if (ReachedEof(self))
    return false;
  
  // otherwise we make sure that all the next characters are whitespace
  for (; self->index < self->source_reference->buffer_size; self->index++)
    if (!IsWhitespaceChar(GetCurrentChar(self)))
      // when find a non whitespace character it means there is a next token
      return true;

  // all remaining characters were whitespace
  return false;
}