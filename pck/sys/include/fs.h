#pragma once
#include "/pck/sys/include/sys.h"
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <unistd.h>

inline u8 IsRegularFile(u8 const* path)
{
  struct stat path_stat;
  stat((char const*)path, &path_stat);
  
  return S_ISREG(path_stat.st_mode);
}

inline u64 GetFileSize(FILE* file) {
  fseek(file, 0, SEEK_END);
  u64 file_size = ftell(file);
  fseek(file, 0, SEEK_SET);

  return file_size;
}

// ! write a file content to a fixed buffer
inline void ReadFileIntoBuffer(FILE* file, u8* buffer, u64 buffer_size) {
  Unused(fread(buffer, buffer_size, 1, file));
}