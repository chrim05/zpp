#pragma once
#include "/pck/sys/include/sys.h"

// ! takes two null terminated strings and returns true whether they are equal
u8 CStringsAreEqual(u8 const* left, u8 const* right) {
  u8 c1, c2;

  do {
    c1 = *left++;
    c2 = *right++;
    
    if (c1 == '\0')
      return c1 - c2;
  } while (c1 == c2);

  return c1 - c2;
}