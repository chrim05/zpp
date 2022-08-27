#include "../include/mem.h"

#include "../pck/sys/include/sys.h"
#include "../pck/mimalloc/include/mimalloc.h"

AllocationError MemRegionResize(MemRegion* self, u64 byte_size) {
  // ensuring that at least the required size is being allocated
  // with just `self->BufferSize * 2` we are not ensuring it
  // because the required byte_size can be twice bigger than the internal buffer
  self->BufferSize = (self->BufferSize * 2) + byte_size;
  self->BufferStartingPointer = (u8*)mi_realloc(self->BufferStartingPointer, self->BufferSize);

  // true = 1, and AllocationError(1) = AllocErrTagOutOfMemory
  // so when this expression is true (when the pointer is null)
  // there is an error
  return (AllocationError)(self->BufferStartingPointer == nullptr);
}

AllocationError AllocateBuffer(MemRegion* self, u8** buffer_output, u64 byte_size) {
  // whether the buffer is not big enough
  // we reallocate it with double the size plus the required
  // allocation size (`byte_size`)
  if (self->BufferUsedSize + byte_size > self->BufferSize)
    try(MemRegionResize(self, byte_size), {});

  *buffer_output = self->BufferStartingPointer + self->BufferUsedSize;
  self->BufferUsedSize += byte_size;

  return Ok;
}