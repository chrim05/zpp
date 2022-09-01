#pragma once
#include "dbg.h"
#include "sys.h"

// ! take two strings of the same length and compare them in the fastest possible way
u8 FixedCStringsAreEqual(u8 const* left, u8 const* right, u32 length);

// ! takes two null terminated strings and returns true whether they are equal
u8 CStringsAreEqual(u8 const* left, u8 const* right);

constexpr u64 ComptimeCStringLength(u8 const* string) {
  u64 length = 0;

  while (*(string++))
    length++;
  
  return length;
}