#pragma once
#include "/pck/sys/include/sys.h"

// ! structure for handling the source code and its size
struct CompilationInfo {
  u64 BufferSize;
  u8 const* Buffer;
  u8 const* Filename;
};

struct SourceLocation {
  CompilationInfo* SourceReference;
  u64 Index;
};

inline CompilationInfo CreateCompilationInfo(
  u64 buffer_size,
  u8 const* buffer,
  u8 const* filename
) {
  return (CompilationInfo) {
    .BufferSize = buffer_size,
    .Buffer = buffer,
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
  u8 Tag;
  u8 Length;
  SourceLocation Location;
};

inline u8 const* GetTokenValue(Token const* token) {
  return token->Location.SourceReference->Buffer + token->Location.Index;
}

inline u8 const* TokenTagToString(u8 token_tag) {
  return TokenTagReprMap[token_tag];
}