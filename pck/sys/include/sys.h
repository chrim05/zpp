#pragma once

/* -------------------------------------------------------------------------- */
/*                               Primitive Types                              */
/* -------------------------------------------------------------------------- */

enum struct error : char    {};
typedef char                i8;
typedef short              i16;
typedef int                i32;
typedef long long          i64;

typedef unsigned char       u8;
typedef unsigned short     u16;
typedef unsigned int       u32;
typedef unsigned long long u64;

typedef float              f32;
typedef double             f64;

/* -------------------------------------------------------------------------- */
/*                                   Macros                                   */
/* -------------------------------------------------------------------------- */

#define try(what, and_then) ({ error __try__ = what; if (__try__ != Ok) { and_then; return __try__; } })
#define catch(what, and_then) ({ if ((what) != Ok) { and_then; } })
#define static_cstring(s) ((u8 const*)s)
#define Ok ((error)0)
#define Err ((error)1)
#define Errn(n) ((error)n)
#define Unused(expr) ({ auto __unused__ = expr; (void)__unused__; })