#pragma once
#include <stdio.h>
#include <stdlib.h>

#ifndef RELEASE
  #define Expect(boolean) if (!(boolean)) { printf("%s:%d: Failed at 'Expect' function, found 'false'\n", __FILE__, __LINE__);  }
  #define Here printf("[HERE] %s:%d\n", __FILE__, __LINE__)
  #define Dbg(fmt, args...) printf("[DBG] %s:%d: " fmt "\n", __FILE__, __LINE__, args)
  #define DbgString(s) printf("[DBG] %s:%d: %s\n", __FILE__, __LINE__, s)
  #define Todo ({printf("[TODO] %s:%d\n", __FILE__, __LINE__); exit(1);})
  #define Assert(boolean) ({ if (!(boolean)) { printf("[ASSERT] %s:%d: Failed\n", __FILE__, __LINE__); exit(1); } })
  #define Unreachable ({ printf("[UNREACHABLE] %s:%d: Reached\n", __FILE__, __LINE__); exit(1); })
  #define unwrap(expr) ({ if ((u8)(expr)) { printf("[UNWRAP] %s:%d: Unwrapped error\n", __FILE__, __LINE__); exit(1); } })
#else
  #define Expect(boolean) ({;})
  #define Here ({;})
  #define Dbg(fmt, args...) ({;})
  #define DbgString(s) ({;})
  #define Todo ({;})
  #define Assert(boolean) ({;})
  #define Unreachable ({;})
  #define unwrap(expr) ({ expr; })
#endif