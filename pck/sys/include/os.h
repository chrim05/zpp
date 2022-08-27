#pragma once

inline void Abort() {
  while (true)
    asm("hlt");
}