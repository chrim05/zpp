; ModuleID = ""
target triple = "unknown-unknown-unknown"
target datalayout = ""

define i32 @"main"(i32 %".1", i1* %".2")
{
allocas:
  %"arg.1" = alloca i32
  %"arg.2" = alloca i1*
  %"a" = alloca {i8, i8}
  %"b" = alloca {i8, i8}
  %"tmp.1" = alloca [2 x i1*]
  %"ab" = alloca i1*
  br label %"entry"
entry:
  store i32 %".1", i32* %"arg.1"
  store i1* %".2", i1** %"arg.2"
  %".6" = insertvalue {i8, i8} undef, i8 1, 0
  %".7" = insertvalue {i8, i8} %".6", i8 2, 1
  store {i8, i8} %".7", {i8, i8}* %"a"
  %".9" = insertvalue {i8, i8} undef, i8 3, 0
  %".10" = insertvalue {i8, i8} %".9", i8 4, 1
  store {i8, i8} %".10", {i8, i8}* %"b"
  %".14" = bitcast {i8, i8}* %"a" to i1*
  %".15" = insertvalue [2 x i1*] undef, i1* %".14", 0
  %".16" = bitcast {i8, i8}* %"b" to i1*
  %".17" = insertvalue [2 x i1*] %".15", i1* %".16", 1
  store [2 x i1*] %".17", [2 x i1*]* %"tmp.1"
  %".19" = bitcast [2 x i1*]* %"tmp.1" to i1*
  store i1* %".19", i1** %"ab"
  %".21" = load i1*, i1** %"ab"
  %".22" = bitcast i1* %".21" to i1**
  %".23" = getelementptr i1*, i1** %".22", i64 0
  %".24" = load i1*, i1** %".23"
  %".25" = bitcast i1* %".24" to {i8, i8}*
  %".27" = getelementptr inbounds {i8, i8}, {i8, i8}* %".25", i32 0, i32 0
  %".28" = load i8, i8* %".27"
  %".29" = load i1*, i1** %"ab"
  %".30" = bitcast i1* %".29" to i1**
  %".31" = getelementptr i1*, i1** %".30", i64 0
  %".32" = load i1*, i1** %".31"
  %".33" = bitcast i1* %".32" to {i8, i8}*
  %".35" = getelementptr inbounds {i8, i8}, {i8, i8}* %".33", i32 0, i32 1
  %".36" = load i8, i8* %".35"
  %".37" = add i8 %".28", %".36"
  %".38" = load i1*, i1** %"ab"
  %".39" = bitcast i1* %".38" to i1**
  %".40" = getelementptr i1*, i1** %".39", i64 1
  %".41" = load i1*, i1** %".40"
  %".42" = bitcast i1* %".41" to {i8, i8}*
  %".44" = getelementptr inbounds {i8, i8}, {i8, i8}* %".42", i32 0, i32 0
  %".45" = load i8, i8* %".44"
  %".46" = load i1*, i1** %"ab"
  %".47" = bitcast i1* %".46" to i1**
  %".48" = getelementptr i1*, i1** %".47", i64 1
  %".49" = load i1*, i1** %".48"
  %".50" = bitcast i1* %".49" to {i8, i8}*
  %".52" = getelementptr inbounds {i8, i8}, {i8, i8}* %".50", i32 0, i32 1
  %".53" = load i8, i8* %".52"
  %".54" = add i8 %".45", %".53"
  %".55" = mul i8 %".37", %".54"
  %".56" = zext i8 %".55" to i32
  ret i32 %".56"
}
