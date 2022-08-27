#pragma once

#include "sys.h"
#include "../../mimalloc/include/mimalloc.h"

constexpr error AllocErrTagOutOfMemory = Errn(1);

struct MemRegion {
  u64 buffer_size;
  u64 buffer_used_size;
  u8* buffer_starting_pointer;

  MemRegion() {
    buffer_starting_pointer = nullptr;
  }

  ~MemRegion() {
    if (buffer_starting_pointer == nullptr)
      return;
      
    mi_free(buffer_starting_pointer);
  }

  MemRegion(MemRegion const&) = delete;
};

error MemRegionResize(MemRegion* self, u64 byte_size);

error AllocateBuffer(MemRegion* self, u8** buffer_output, u64 byte_size);

template<typename BaseSliceElemT>
  error AllocateSlice(MemRegion* self, BaseSliceElemT** buffer_output, u64 slice_length) {
    return AllocateBuffer(self, (u8**)buffer_output, slice_length * sizeof(BaseSliceElemT));
}

template<typename SingleT>
  error AllocateSingle(MemRegion* self, SingleT** single_output) {
    return AllocateBuffer(self, (u8**)single_output, sizeof(SingleT));
}

inline error InitMemRegion(MemRegion* mem_region_output, u64 initializer_byte_size) {
  mem_region_output->buffer_size = initializer_byte_size;
  mem_region_output->buffer_used_size = 0;
  mem_region_output->buffer_starting_pointer = (u8*)mi_malloc(initializer_byte_size);

  if (mem_region_output->buffer_starting_pointer == (u8*)-1)
    return AllocErrTagOutOfMemory;
  
  return Ok;
}