; ModuleID = '/run/media/akshat/New Volume/Akshat/RVCE/Subjects/Sem 6/Compiler Design/EL/llvm-machinations/llvm_explorer/examples/sample1.c'
source_filename = "/run/media/akshat/New Volume/Akshat/RVCE/Subjects/Sem 6/Compiler Design/EL/llvm-machinations/llvm_explorer/examples/sample1.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

; Function Attrs: nounwind sspstrong uwtable
define dso_local i32 @add_offset(i32 noundef %0, i32 noundef %1) #0 {
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  store i32 %0, ptr %3, align 4
  store i32 %1, ptr %4, align 4
  %5 = load i32, ptr %3, align 4
  %6 = load i32, ptr %4, align 4
  %7 = add nsw i32 %5, %6
  ret i32 %7
}

; Function Attrs: nounwind sspstrong uwtable
define dso_local i32 @compute() #0 {
  %1 = alloca i32, align 4
  %2 = alloca i32, align 4
  %3 = alloca i32, align 4
  %4 = call i32 @add_offset(i32 noundef 10, i32 noundef 5)
  store i32 %4, ptr %2, align 4
  %5 = load i32, ptr %2, align 4
  %6 = mul nsw i32 %5, 42
  store i32 %6, ptr %3, align 4
  %7 = load i32, ptr %2, align 4
  %8 = icmp sgt i32 %7, 0
  br i1 %8, label %9, label %12

9:                                                ; preds = %0
  %10 = load i32, ptr %2, align 4
  %11 = add nsw i32 %10, 1
  store i32 %11, ptr %1, align 4
  br label %15

12:                                               ; preds = %0
  %13 = load i32, ptr %2, align 4
  %14 = sub nsw i32 %13, 100
  store i32 %14, ptr %1, align 4
  br label %15

15:                                               ; preds = %12, %9
  %16 = load i32, ptr %1, align 4
  ret i32 %16
}

; Function Attrs: nounwind sspstrong uwtable
define dso_local i32 @main() #0 {
  %1 = alloca i32, align 4
  store i32 0, ptr %1, align 4
  %2 = call i32 @compute()
  ret i32 %2
}

attributes #0 = { nounwind sspstrong uwtable "frame-pointer"="all" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }

!llvm.module.flags = !{!0, !1, !2, !3, !4}
!llvm.ident = !{!5}

!0 = !{i32 1, !"wchar_size", i32 4}
!1 = !{i32 8, !"PIC Level", i32 2}
!2 = !{i32 7, !"PIE Level", i32 2}
!3 = !{i32 7, !"uwtable", i32 2}
!4 = !{i32 7, !"frame-pointer", i32 2}
!5 = !{!"clang version 22.1.5"}
