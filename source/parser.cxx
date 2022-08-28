#include "parser.h"
#include "compilation_manager.h"

#define DbgState ({ Dbg("token.value: '%.*s' | token.tag: %u", self->current.length, self->current.location.source_reference->buffer + self->current.location.index, self->current.tag); })

void ParseGlobalScope(ZppParser* self) {
  // collecting all global nodes (such as functions types ...)
  // until the eof
  while (HasNextTokenAndEatWhitespaces(self))
    ParseNextGlobalNode(self);
}

void CollectIdentifierToken(ZppParser* self) {
  self->current.tag = TokenTagIdentifier;
  
  // eating all identifier chars
  while (!ReachedEof(self) and IsMiddleIdentifierChar(GetCurrentChar(self)))
    self->index++;

  // going back to the last identifier char
  // we go back because the caller will skip the last char
  self->index--;
}

void CollectDigitToken(ZppParser* self) {
  // the char looking at
  u8 c = '\0';
  self->current.tag = TokenTagDigit;
  
  // eating all digit chars
  while (true) {
    // preventing the malformed digit check on eof
    // also no need to self->index--
    if (ReachedEof(self))
      return;

    if (!IsDigitChar(c = GetCurrentChar(self)))
      break;

    self->index++;
  }
  
  // checking for malformed digit
  if (IsFirstIdentifierChar(c))
    ReportMalformedDigit(&self->current.location, c);

  // going back to the last digit char
  // we go back because the caller will skip the last char
  self->index--;
}

void SetCurPos(ZppParser* self) {
  self->current.location.index = self->index;
  self->current.location.source_reference = self->source_reference;
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
  
  else if (token->length == 4 and SmallFixedCStringsAreEqual( // quit
    token->location.source_reference->buffer + token->location.index, static_cstring("quit"), token->length
  ))
    token->tag = TokenTagKwQuit;
}

void CollectNextToken(ZppParser* self) {
  EatWhitespaces(self);

  // initializing the start position of the token
  SetCurPos(self);
  auto current_char = GetCurrentChar(self);

  if (IsFirstIdentifierChar(current_char))
    CollectIdentifierToken(self);
  else if (IsDigitChar(current_char))
    CollectDigitToken(self);
  else
    self->current.tag = current_char;
  
  // initializing the end position of the token
  self->current.length = (self->index + 1) - self->current.location.index;

  // when the token is an identifier and its value is a keyword
  // we set its tag to that keyword's one
  TryToReplaceIdentifierWithKeyword(&self->current);

  // moving to the next character
  self->index++;
}

void CollectNextTokenAndExpect(ZppParser* self, u8 expected_token_tag) {
  CollectNextToken(self);
  ExpectToken(&self->current, expected_token_tag);
}

void ExpectToken(Token const* found_token, u8 expected_token_tag) {
  if (found_token->tag != expected_token_tag)
    ReportExpectedAnotherToken(found_token, expected_token_tag);
}

void ParseNamedType(ZppParser* self) {
  auto value = GetTokenValue(&self->current);
  auto length = self->current.length;

  if (self->current.length == 2 and SmallFixedCStringsAreEqual(
    value, static_cstring("u8"), length
  ))
    VisitTypeMkTypedBuiltin(&self->ast_visitor, BuiltinTypeTagU8, self->current.location);
  else if (self->current.length == 3 and SmallFixedCStringsAreEqual(
    value, static_cstring("u32"), length
  ))
    VisitTypeMkTypedBuiltin(&self->ast_visitor, BuiltinTypeTagU32, self->current.location);
  else
    VisitTypeMkTyped(&self->ast_visitor, value, length, self->current.location);
}

void ParseType(ZppParser* self) {
  CollectNextToken(self);
  SourceLocation location;

  switch (self->current.tag) {
    case TokenTagIdentifier:
      ParseNamedType(self);
      break;

    case TokenTagSymStar:
      location = self->current.location;

      ParseType(self);
      VisitTypeMkPtrTyped(&self->ast_visitor, location);
      break;

    default:
      ReportUnexpectedToken(&self->current);
  }
}

u16 ParseArgListDeclaration(ZppParser* self) {
  CollectNextTokenAndExpect(self, TokenTagSymLPar);

  // parsing first arg name or close par
  CollectNextToken(self);

  if (self->current.tag == TokenTagSymRPar)
    return 0;
  
  u16 number_of_args = 0;

  // parsing the args list declaration
  while (true) {
    number_of_args++;
    // parsing the name
    ExpectToken(&self->current, TokenTagIdentifier);   

    VisitArgDeclaration(&self->ast_visitor, GetTokenValue(&self->current), self->current.length, self->current.location);

    // parsing type notation
    CollectNextTokenAndExpect(self, TokenTagSymColon);
    ParseType(self);

    // checking for another arg
    CollectNextToken(self);
    if (self->current.tag != TokenTagSymComma)
      break;
    
    // collecting the name of the next arg
    CollectNextToken(self);
  }

  ExpectToken(&self->current, TokenTagSymRPar);
  return number_of_args;
}

void UpdateNumberOfArgsInFnInstr(ZppParser* self, u16 number_of_args, u64 instr_index) {
  auto internal_buffer = GetInternalBuffer(&self->ast_visitor.instruction_values);
  internal_buffer[instr_index].fn_decl.args_count = number_of_args;
}

void UpdateNumberOfStmtsInNamedBlockInstr(ZppParser* self, u64 number_of_stmts, u64 instr_index) {
  auto internal_buffer = GetInternalBuffer(&self->ast_visitor.instruction_values);
  internal_buffer[instr_index].named_block_decl.stmts_count = number_of_stmts;
}

u16 ParseFnCall(ZppParser* self) {
  // skipping '('
  CollectNextToken(self);

  if (self->current.tag == TokenTagSymRPar)
    return 0;
  
  u16 number_of_args = 0;

  // parsing the args list
  while (true) {
    number_of_args++;

    // parsing the arg
    ParseExpression(self);

    // checking for another arg
    if (self->current.tag != TokenTagSymComma)
      break;
    
    // skipping ','
    CollectNextToken(self);
  }

  ExpectToken(&self->current, TokenTagSymRPar);
  return number_of_args;
}

void ParseTerm(ZppParser* self) {
  u8 const* ident_name = nullptr;
  u64 ident_length = 0;
  auto location = self->current.location;

  switch (self->current.tag) {
    case TokenTagIdentifier:
      ident_name = GetTokenValue(&self->current);
      ident_length = self->current.length;
      break;
    
    case TokenTagDigit:
      VisitLoadDigit(&self->ast_visitor, ParseUInt(GetTokenValue(&self->current), self->current.length), location);
      break;
    
    default:
      ReportUnexpectedToken(&self->current);
  }

  CollectNextToken(self);

  // parsing function call or load name
  if ((ident_name != nullptr) & (self->current.tag == TokenTagSymLPar)) { // function call
    auto args_count = ParseFnCall(self);
    VisitCall(&self->ast_visitor, ident_name, ident_length, args_count, location);

    // skipping the ')'
    CollectNextToken(self);
  } else if (ident_name != nullptr) // load name
    VisitLoadName(&self->ast_visitor, ident_name, ident_length, location);

  // parsing function dot expr
  while (self->current.tag == TokenTagSymDot) {
    // parsing field
    CollectNextTokenAndExpect(self, TokenTagIdentifier);
    VisitLoadField(&self->ast_visitor, GetTokenValue(&self->current), self->current.length, self->current.location);
    
    // skipping the field
    CollectNextToken(self);
  }
}

// * binary priority
// 3 == != <= >=
// 2 + -
// 1 * / %

void ParseBinPriority1(ZppParser* self) {
  // parsing 'left' */ right
  ParseTerm(self);

  while (true) {
    auto op = self->current.tag;
    auto op_location = self->current.location;

    if ((op != TokenTagSymStar) & (op != TokenTagSymSlash))
      break;
    
    // skipping the bin op
    CollectNextToken(self);
    // parsing left */ 'right'
    ParseTerm(self);

    VisitBinaryOperation(&self->ast_visitor, op, op_location);
  }
}

// ! parse + -
void ParseBinPriority2(ZppParser* self) {
  // parsing 'left' +- right
  ParseBinPriority1(self);

  while (true) {
    auto op = self->current.tag;
    auto op_location = self->current.location;

    if ((op != TokenTagSymPlus) & (op != TokenTagSymMinus))
      break;
    
    // skipping the bin op
    CollectNextToken(self);
    // parsing left +- 'right'
    ParseBinPriority1(self);

    VisitBinaryOperation(&self->ast_visitor, op, op_location);
  }
}

void ParseExpression(ZppParser* self) {
  ParseBinPriority2(self);
}

void ParseQuitStmt(ZppParser* self) {
  // parsing quit 'a' =
  CollectNextTokenAndExpect(self, TokenTagIdentifier);
  auto name = GetTokenValue(&self->current);
  auto name_length = self->current.length;
  auto name_location = self->current.location;

  // parsing quit a '=' and skipping '='
  CollectNextTokenAndExpect(self, TokenTagSymEqual);
  CollectNextToken(self);

  // parsing quit a = 'expr;'
  ParseExpression(self);
  ExpectToken(&self->current, TokenTagSymSemicolon);

  VisitQuitStmt(&self->ast_visitor, name, name_length, name_location);
};

// ! try to parse a stmt, return false when metches a bracket instead of a stmt
u8 ParseStmt(ZppParser* self) {
  CollectNextToken(self);

  switch (self->current.tag) {
    case TokenTagSymRBrace:
      return false;
    
    case TokenTagKwQuit:
      ParseQuitStmt(self);
      break;
    
    case TokenTagSymSemicolon:
      VisitPassStmt(&self->ast_visitor, self->current.location);
      break;

    default:
      ReportUnexpectedToken(&self->current);
  }

  return true;
}

u64 ParseBlockContent(ZppParser* self) {
  CollectNextTokenAndExpect(self, TokenTagSymLBrace);

  u64 stmt_counter = 0;

  while (ParseStmt(self))
    stmt_counter++;
  
  // no need to expect RBrace because
  // ParseStmt already did

  return stmt_counter;
}

void ParseNamedBlock(ZppParser* self) {
  // parsing 'e: T3'
  CollectNextTokenAndExpect(self, TokenTagIdentifier);
  auto name = GetTokenValue(&self->current);
  auto name_length = self->current.length;
  auto name_location = self->current.location;

  CollectNextTokenAndExpect(self, TokenTagSymColon);
  
  auto instr_index = VisitBlockNameDeclaration(&self->ast_visitor, name, name_length, name_location);
  // parsing 'T3'
  ParseType(self);

  // parsing '{}'
  auto stmts_count = ParseBlockContent(self);

  UpdateNumberOfStmtsInNamedBlockInstr(self, stmts_count, instr_index);
}

void ParseFnGlobalNode(ZppParser* self, u8 modifier_export) {
  // parsing fn 'name'
  CollectNextTokenAndExpect(self, TokenTagIdentifier);
  auto name = GetTokenValue(&self->current);
  auto name_length = self->current.length;
  auto name_location = self->current.location;

  auto instr_index = VisitFnDeclaration(
    &self->ast_visitor,
    modifier_export,
    name,
    name_length,
    name_location
  );

  // parsing fn name'(a: T, b: T2)'
  auto number_of_args = ParseArgListDeclaration(self);

  UpdateNumberOfArgsInFnInstr(self, number_of_args, instr_index);

  // parsing fn name() 'e: T3 {}'
  ParseNamedBlock(self);

  catch(VectorPush(&self->ast_visitor.functions, instr_index), {
    DbgString("Failed to add instr index to functions");
  });
}

u8 MatchToken(ZppParser* self, u8 token_tag_to_match) {
  if (self->current.tag == token_tag_to_match) {
    CollectNextToken(self);
    return true;
  }

  return false;
}

void ParseNextGlobalNode(ZppParser* self) {
  // fecting the first global token
  CollectNextToken(self);

  // has the modifier 'export' keyword before 'fn' 'type' ...
  auto modifier_export = MatchToken(self, TokenTagKwExport);

  switch (self->current.tag) {
    case TokenTagKwFn:
      ParseFnGlobalNode(self, modifier_export);
      break;

    default:
      ReportUnexpectedTokenInGlobalContext(&self->current);
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