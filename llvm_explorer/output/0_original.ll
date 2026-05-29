; ModuleID = '/run/media/akshat/New Volume/Akshat/RVCE/Subjects/Sem 6/Compiler Design/EL/llvm-machinations/llvm_explorer/output/0_raw.ll'
source_filename = "/run/media/akshat/New Volume/Akshat/RVCE/Subjects/Sem 6/Compiler Design/EL/llvm-machinations/llvm_explorer/examples/sample1.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

; Function Attrs: nounwind sspstrong uwtable
define dso_local i32 @add_offset(i32 noundef %0, i32 noundef %1) #0 {
  %3 = add nsw i32 %0, %1
  ret i32 %3
}

; Function Attrs: nounwind sspstrong uwtable
define dso_local i32 @compute() #0 {
  %1 = call i32 @add_offset(i32 noundef 10, i32 noundef 5)
  %2 = mul nsw i32 %1, 42
  %3 = icmp sgt i32 %1, 0
  br i1 %3, label %4, label %6

4:                                                ; preds = %0
  %5 = add nsw i32 %1, 1
  br label %8

6:                                                ; preds = %0
  %7 = sub nsw i32 %1, 100
  br label %8

8:                                                ; preds = %6, %4
  %.0 = phi i32 [ %5, %4 ], [ %7, %6 ]
  ret i32 %.0
}

; Function Attrs: nounwind sspstrong uwtable
define dso_local i32 @main() #0 {
  %1 = call i32 @compute()
  ret i32 %1
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
