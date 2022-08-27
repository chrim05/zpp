#pragma once
#include "collections.h"

typedef Vector<u8> String;

struct RangedString {
  u64 start;
  u64 stop;
};

inline RangedString CreateRangedString(u64 start, u64 stop) {
  return (RangedString) {
    .start = start,
    .stop = stop
  };
}

inline u16 GetRangedStringLength(RangedString const* self) {
  return self->stop - self->start;
}

inline u8 RangedStringIsEmpty(RangedString const* self) {
  return self->start == self->stop;
}

inline u64 ParseUInt(u8 const* string, u64 length) {
  u64 res = 0;
 
  for (u64 i = 0; i < length; i++)
    res = res * 10 + string[i] - '0';

  return res;
}