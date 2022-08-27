#pragma once
#include "../pck/sys/include/sys.h"

// ! structure for handling the source code and its size
struct CompilationInfo {
  u64 buffer_size;
  u8 const* buffer;
  u8 const* filename;
};

struct SourceLocation {
  CompilationInfo* source_reference;
  u64 index;
};

inline CompilationInfo CreateCompilationInfo(
  u64 buffer_size,
  u8 const* buffer,
  u8 const* filename
) {
  return (CompilationInfo) {
    .buffer_size = buffer_size,
    .buffer = buffer,
    .filename = filename
  };
}

constexpr u8 TokenTagUnknown = 0;
constexpr u8 TokenTagIdentifier = 1;
constexpr u8 TokenTagKwFn = 2;
constexpr u8 TokenTagKwExport = 3;
constexpr u8 TokenTagKwQuit = 4;
constexpr u8 TokenTagDigit = 5;
constexpr u8 TokenTagSymLPar = '(';
constexpr u8 TokenTagSymRPar = ')';
constexpr u8 TokenTagSymColon = ':';
constexpr u8 TokenTagSymComma = ',';
constexpr u8 TokenTagSymLBrace = '{';
constexpr u8 TokenTagSymRBrace = '}';
constexpr u8 TokenTagSymLBrack = '[';
constexpr u8 TokenTagSymRBrack = ']';
constexpr u8 TokenTagSymSemicolon = ';';
constexpr u8 TokenTagSymEqual = '=';
constexpr u8 TokenTagSymPlus = '+';
constexpr u8 TokenTagSymMinus = '-';
constexpr u8 TokenTagSymStar = '*';
constexpr u8 TokenTagSymSlash = '/';
constexpr u8 TokenTagSymDot = '.';

u8 const* const TokenTagReprMap[] = {
  static_cstring("unknown"),
  static_cstring("identifier"),
  static_cstring("fn"),
  static_cstring("export"),
  static_cstring("quit"),
  static_cstring("digit"),
};

struct Token {
  u8 tag;
  u16 length;
  SourceLocation location;
};

inline u8 const* GetTokenValue(Token const* token) {
  return token->location.source_reference->buffer + token->location.index;
}

// ! return true whether `token_tag` is a symbol
// ! (such as ! { } * , ...)
inline u8 TokenTagIsSym(u8 token_tag) {
  return token_tag >= '!';
}

// ! can only be used for non-sym tokens
inline u8 const* TokenTagToString(u8 token_tag) {
  Assert(!TokenTagIsSym(token_tag));
  return TokenTagReprMap[token_tag];
}