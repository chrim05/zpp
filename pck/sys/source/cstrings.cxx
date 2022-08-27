#include "../include/cstrings.h"

u8 CStringsAreEqual(u8 const* left, u8 const* right) {
  while (true) {
    if (*left == *right) {
      if (*left == '\0')
        return true;
    } else
      return false;
      
    left++;
    right++;
  }

  Unreachable;
}

u8 SmallFixedCStringsAreEqual(u8 const* left, u8 const* right, u32 length) {
  while (length--)
    if (left[length] != right[length])
      return false;
  
  return true;
}

u8 FixedCStringsAreEqual(u8 const* left, u8 const* right, u32 length) {
  // ensuring the strings are at least of one character
  // otherwise `offset` is potentially negative
  Assert(length > 0);

  u32 fast = length / sizeof(u64) + 1;
  u32 offset = (fast - 1) * sizeof(u64);
  u32 current_block = 0;

  if(length <= sizeof(u64))
    fast = 0;

  auto lptr0 = (u64*)left;
  auto lptr1 = (u64*)right;

  while (current_block < fast) {
    if (!(lptr0[current_block] ^ lptr1[current_block])) {
      current_block++;
      continue;
    }

    for (u32 pos = current_block * sizeof(u64); pos < length; pos++)
      if ((left[pos] ^ right[pos]) || (left[pos] == 0) || (right[pos] == 0))
        return left[pos] - right[pos];

    current_block++;
  }

  while (length > offset) {
    if (left[offset] ^ right[offset])
      return left[offset] - right[offset];

    offset++;
  }
	
  return false;
}