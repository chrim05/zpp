#pragma once

#include "mem.h"

// ! structure for handling dynamic arrays
template<typename T>
  struct Vector {
    MemRegion allocator;

    Vector(Vector const& v) = delete;

    Vector() { }
};

template<typename T>
  inline error InitVector(Vector<T>* self, u64 initializer_number_of_elements) {
    return InitMemRegion(&self->allocator, sizeof(T) * initializer_number_of_elements);
}

template<typename T>
  inline u64 VectorLength(Vector<T> const* self) {
    return self->allocator.buffer_used_size / sizeof(T);
}

template<typename T>
  error VectorPush(Vector<T>* self, T elem) {
    T* pointer_to_element;
    try(AllocateSingle(&self->allocator, &pointer_to_element), {});

    *pointer_to_element = elem;
    return Ok;
}

template<typename T>
  inline T* GetInternalBuffer(Vector<T>* self) {
    return (T*)self->allocator.buffer_starting_pointer;
}