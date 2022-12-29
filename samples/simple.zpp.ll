; ModuleID = ""
target triple = "unknown-unknown-unknown"
target datalayout = ""

define i32 @"main"(i32 %".1", ptr %".2")
{
allocas:
  %"arg.1" = alloca i32
  %"arg.2" = alloca ptr
  %"x" = alloca {i32, ptr}
  %"y" = alloca {i32, ptr}
  br label %"entry"
entry:
  store i32 %".1", i32* %"arg.1"
  store ptr %".2", ptr* %"arg.2"
  %".6" = load ptr, ptr* %"arg.2"
  %".7" = insertvalue {i32, ptr} undef, i32 1, 0
  %".8" = insertvalue {i32, ptr} %".7", ptr %".6", 1
  store {i32, ptr} %".8", {i32, ptr}* %"x"
  %".11" = getelementptr inbounds {i32, ptr}, {i32, ptr}* %"x", i32 0, i32 1
  %".12" = load ptr, ptr* %".11"
  %".13" = load {i32, ptr}, ptr %".12"
  store {i32, ptr} %".13", {i32, ptr}* %"y"
  %".16" = getelementptr inbounds {i32, ptr}, {i32, ptr}* %"x", i32 0, i32 0
  %".17" = load i32, i32* %".16"
  ret i32 %".17"
}
