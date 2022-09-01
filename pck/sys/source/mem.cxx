#include "../include/mem.h"

#include "../include/sys.h"
#include "../../mimalloc/include/mimalloc.h"

error MemRegionResize(MemRegion* self, u64 byte_size) {
  // ensuring that at least the required size is being allocated
  // with just `self->BufferSize * 2` we are not ensuring it
  // because the required byte_size can be twice bigger than the internal buffer
  self->buffer_size = (self->buffer_size * 2) + byte_size;
  self->buffer_starting_pointer = (u8*)mi_realloc(self->buffer_starting_pointer, self->buffer_size);

  // true = 1, and error(1) = AllocErrTagOutOfMemory
  // so when this expression is true (when the pointer is null)
  // there is an error
  return (error)(self->buffer_starting_pointer == nullptr);
}

error AllocateBuffer(MemRegion* self, u8** buffer_output, u64 byte_size) {
  // whether the buffer is not big enough
  // we reallocate it with double the size plus the required
  // allocation size (`byte_size`)
  if (self->buffer_used_size + byte_size > self->buffer_size)
    ctry(MemRegionResize(self, byte_size), {});

  *buffer_output = self->buffer_starting_pointer + self->buffer_used_size;
  self->buffer_used_size += byte_size;

  return Ok;
}