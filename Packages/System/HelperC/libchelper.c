// clang -O3 -c Packages/System/HelperC/libchelper.c -o Packages/System/HelperC/libchelper.o

#include <stdio.h>

void* get_stdout() {
  return (void*)stdout;
}

void* get_stderr() {
  return (void*)stderr;
}

void* get_stdin() {
  return (void*)stdin;
}