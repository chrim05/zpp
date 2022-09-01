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

inline u8 ShortCStringsAreEqual(u8 const* left, u8 const* right, u32 length) {
  while (length--)
    if (left[length] != right[length])
      return false;
  
  return true;
}

inline u8 LongCStringsAreEqual(u8 const* left, u8 const* right, u32 length) {
  if (((u32 const*)left)[0] != ((u32 const*)right)[0])
    return false;
  
  return ShortCStringsAreEqual(left + sizeof(u32), right + sizeof(u32), length - sizeof(u32));
}

u8 FixedCStringsAreEqual(u8 const* left, u8 const* right, u32 length) {
  u32 discard = length % sizeof(u64);
  u32 blocks_length = length / sizeof(u64);

  for (u32 i = 0; i < blocks_length; i++)
    if (((u64 const*)left)[i] != ((u64 const*)right)[i])
      return false;
  
  u32 offset = blocks_length * sizeof(u64);

  if (discard < sizeof(u32))
    return ShortCStringsAreEqual(left + offset, right + offset, discard);
  else if (discard < sizeof(u64))
    return LongCStringsAreEqual(left + offset, right + offset, discard);
  else
    return true;
}