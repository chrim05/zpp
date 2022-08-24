#pragma once
#include "/pck/sys/include/sys.h"

// ! structure for handling the source code and its size
struct CompilationInfo {
  u64 buffer_size;
  u8 const* buffer;
  u8 const* Filename;
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
    .Filename = filename
  };
}

constexpr u8 TokenTagUnknown = 0;
constexpr u8 TokenTagIdentifier = 1;
constexpr u8 TokenTagKwFn = 2;
constexpr u8 TokenTagKwExport = 3;
constexpr u8 TokenTagSymLPar = 4;
constexpr u8 TokenTagSymRPar = 5;
constexpr u8 TokenTagSymColon = 6;
constexpr u8 TokenTagSymComma = 7;

u8 const* const TokenTagReprMap[] = {
  static_cstring("unknown"),
  static_cstring("identifier"),
  static_cstring("fn"),
  static_cstring("export"),
};

struct Token {
  u8 tag;
  u16 length;
  SourceLocation location;
};

inline u8 const* GetTokenValue(Token const* token) {
  return token->location.source_reference->buffer + token->location.index;
}

inline u8 const* TokenTagToString(u8 token_tag) {
  return TokenTagReprMap[token_tag];
}