#include <stdio.h>

#include "../include/dbg.h"
#include "../include/mem.h"

void Test1(MemRegion* region) {
  uint8_t* buffer;
  Expect(region->AllocateBuffer(&buffer, 5) == AllocationError::NoError);
  buffer[0] = 'h';
  buffer[1] = 'e';
  buffer[2] = 'l';
  buffer[3] = 'l';
  buffer[4] = 'o';

  printf("buffer[5]: \"%.*s\"\n", 5, buffer);
}

int main() {
  MemRegion region;
  Expect(InitMemRegion(&region, 16) == AllocationError::NoError);

  Test1(&region);
  Test1(&region);
}