---
title: 进程管理（上）
description: lab5
---

# Ch5 进程管理（上）：任务抽象与上下文切换

在前面的章节中，内核已经能够将多个应用程序加载到内存并顺序执行。然而，一个真正的多任务操作系统需要在多个任务之间**并发**运行——让每个任务看起来好像独占了整个处理器。本章将围绕**进程管理**的核心机制展开，分析任务控制块的设计、上下文切换的实现，以及系统调用驱动的任务调度。

## 进程与任务的理论基础

在操作系统理论中，**进程（Process）**是程序执行的一个实例，包含了代码、数据、打开的文件以及 CPU 状态等所有资源的集合。进程是操作系统进行资源分配和保护的基本单位。每个进程拥有独立的地址空间，彼此之间通过内核的内存管理机制实现隔离。

在本内核的当前实现中，使用了更轻量的**任务（Task）**概念。每个用户应用被抽象为一个任务，由 `TaskControlBlock` 管理其状态和上下文。虽然当前的任务尚未拥有独立的地址空间（所有任务共享同一个物理地址空间），但其调度和切换机制与完整的进程管理本质相同。在后续的实验中，当引入页表后，每个任务将升级为拥有独立虚拟地址空间的进程。

## 任务控制块

任务控制块（TCB, Task Control Block）是操作系统用于记录和管理一个任务全部信息的数据结构。在本内核中，`TaskControlBlock` 定义在 `kernel/src/task/task.rs` 中：

```rust
// kernel/src/task/task.rs
#[derive(Copy, Clone)]
pub struct TaskControlBlock {
    pub task_status: TaskStatus,
    pub task_cx: TaskContext,
}

#[derive(Copy, Clone, PartialEq)]
pub enum TaskStatus {
    UnInit,     // 未初始化
    Ready,      // 就绪，等待被调度
    Running,    // 正在运行
    Exited,     // 已退出
}
```

`TaskControlBlock` 结构体十分精简，目前仅包含两个字段：`task_status` 记录任务当前所处的生命周期阶段，`task_cx` 保存任务的 CPU 上下文，用于在任务切换时恢复执行状态。

任务的生命周期遵循一个经典的状态机模型。任务创建时处于 `UnInit` 状态，初始化完成后转入 `Ready` 状态。当调度器选中该任务运行时，状态变为 `Running`。当任务主动放弃 CPU（调用 `sys_yield`）或被时钟中断抢占时，状态从 `Running` 回退到 `Ready`。当任务调用 `sys_exit` 终止执行时，状态变为 `Exited`。这个状态转换可以表示为：

```
UnInit → Ready ⇄ Running → Exited
```

注意 `Ready` 和 `Running` 之间是双向转换：一个正在运行的任务可以被挂起回到就绪状态（例如时间片用完），而一个就绪的任务可以被调度器选中进入运行状态。

## 任务上下文

当操作系统将 CPU 从一个任务切换到另一个任务时，需要保存当前任务的 CPU 寄存器状态，并恢复目标任务之前被保存的状态，这就是**上下文切换（Context Switch）**。`TaskContext` 结构体定义了需要保存的寄存器集合：

```rust
// kernel/src/task/context.rs
#[derive(Copy, Clone)]
#[repr(C)]
pub struct TaskContext {
    ra: usize,       // 返回地址
    sp: usize,       // 栈指针
    s: [usize; 12],  // s0-s11，被调用者保存寄存器
}
```

这个设计体现了一个重要的优化思想：不需要保存所有 32 个通用寄存器，只需保存**被调用者保存（Callee-Saved）寄存器**。根据 RISC-V 的调用约定，`s0`-`s11` 这 12 个寄存器（以及 `ra` 和 `sp`）在函数调用过程中必须由被调用函数保持不变。而 `a0`-`a7`、`t0`-`t6` 等调用者保存寄存器在函数调用边界上不需要保持，因此由编译器生成的代码自然会在必要时保存和恢复它们。

`TaskContext` 提供了两个构造方法：

```rust
impl TaskContext {
    pub fn zero_init() -> Self {
        Self { ra: 0, sp: 0, s: [0; 12] }
    }

    pub fn goto_restore(kstack_ptr: usize) -> Self {
        extern "C" { fn __restore_sp(); }
        Self {
            ra: __restore_sp as usize,
            sp: kstack_ptr,
            s: [0; 12],
        }
    }
}
```

`zero_init` 创建一个全零的上下文，通常用作临时变量或占位符。`goto_restore` 更为关键——它创建的上下文中 `ra` 被设置为 `__restore_sp` 函数的地址（这是 Trap 上下文恢复代码的入口），`sp` 被设置为指向内核栈上预先放置好的 `TrapContext` 的位置。当任务管理器通过 `__switch` 切换到这个上下文时，`ret` 指令将跳转到 `__restore_sp`，后者将恢复保存在内核栈上的 Trap 上下文并通过 `sret` 进入用户态——这就完成了一个新任务的首次启动。

## 上下文切换的汇编实现

上下文切换是操作系统中最底层、对性能最敏感的操作之一。由于它需要直接操作寄存器，必须用汇编语言实现。`__switch` 函数定义在 `kernel/src/task/switch.S` 中：

```asm
.altmacro
.macro SAVE_SN n
    sd s\n, (\n+2)*8(a0)
.endm
.macro LOAD_SN n
    ld s\n, (\n+2)*8(a1)
.endm

    .section .text
    .globl __switch
__switch:
    # __switch(
    #     current_task_cx_ptr: *mut TaskContext,  → a0
    #     next_task_cx_ptr: *const TaskContext     → a1
    # )
    # 保存当前任务的内核栈指针
    sd sp, 8(a0)
    # 保存当前任务的 ra 和 s0~s11
    sd ra, 0(a0)
    .set n, 0
    .rept 12
        SAVE_SN %n
        .set n, n + 1
    .endr
    # 恢复下一个任务的 ra 和 s0~s11
    ld ra, 0(a1)
    .set n, 0
    .rept 12
        LOAD_SN %n
        .set n, n + 1
    .endr
    # 恢复下一个任务的内核栈指针
    ld sp, 8(a1)
    ret
```

`__switch` 接收两个参数：`a0` 指向当前任务的 `TaskContext` 存储位置，`a1` 指向下一个任务的 `TaskContext`。函数的逻辑分为两个对称的阶段：

**保存阶段**：将当前的 `ra`（返回地址）和 `sp`（栈指针）以及 `s0`-`s11` 保存到 `a0` 指向的 `TaskContext` 结构体中。在 `TaskContext` 的内存布局中，`ra` 位于偏移 0，`sp` 位于偏移 8，`s0`-`s11` 从偏移 16 开始依次排列（每个寄存器 8 字节）。

**恢复阶段**：从 `a1` 指向的 `TaskContext` 中加载目标任务的 `ra`、`s0`-`s11` 和 `sp`。最后执行 `ret` 指令，它实际上是跳转到刚刚加载的 `ra` 地址。对于一个正常被挂起的任务，`ra` 保存的是该任务上一次调用 `__switch` 后的返回地址；对于首次被调度的新任务，`ra` 指向 `__restore_sp`，后者会恢复 Trap 上下文并进入用户态。

这个两阶段的过程非常微妙：从 `__switch` 函数进入时，CPU 处于"当前任务"的上下文中；当 `ret` 执行后，CPU 实际上已经在"下一个任务"的上下文中继续运行了。对于当前任务而言，它在 `__switch` 内部"睡着了"；当它下一次被调度时，将从 `__switch` 内部的 `ret` 之后"醒来"，继续执行。

Rust 侧通过 FFI 声明引用这个汇编函数：

```rust
// kernel/src/task/switch.rs
use super::TaskContext;
use core::arch::global_asm;

global_asm!(include_str!("switch.S"));

extern "C" {
    pub fn __switch(
        current_task_cx_ptr: *mut TaskContext,
        next_task_cx_ptr: *const TaskContext
    );
}
```

## Trap 处理与用户态切换

上下文切换工作在内核态的两个任务之间，而用户态与内核态之间的切换则由 Trap 机制完成。`kernel/src/trap/trap.S` 中定义了 Trap 的入口和出口：

```asm
__alltraps:
    csrrw sp, sscratch, sp
    # 此时 sp→内核栈, sscratch→用户栈
    addi sp, sp, -34*8
    # 保存通用寄存器 x1, x3, x5-x31
    sd x1, 1*8(sp)
    sd x3, 3*8(sp)
    .set n, 5
    .rept 27
        SAVE_GP %n
        .set n, n+1
    .endr
    # 保存 sstatus、sepc 和用户栈指针
    csrr t0, sstatus
    csrr t1, sepc
    sd t0, 32*8(sp)
    sd t1, 33*8(sp)
    csrr t2, sscratch
    sd t2, 2*8(sp)
    # 调用 Rust 的 trap_handler
    mv a0, sp
    call trap_handler
```

`__alltraps` 是所有用户态陷入的统一入口。`csrrw sp, sscratch, sp` 指令原子地交换 `sp` 和 `sscratch` 的值——陷入前 `sp` 保存的是用户栈指针，`sscratch` 保存的是该任务的内核栈顶；交换后 `sp` 指向内核栈，用户栈指针被暂存到 `sscratch`。接着在内核栈上分配 34×8 = 272 字节的空间，按照 `TrapContext` 的布局依次保存 32 个通用寄存器、`sstatus` 和 `sepc`。最后将内核栈指针作为参数传给 Rust 编写的 `trap_handler` 函数。

`__restore` 完成相反的过程——从内核栈上恢复所有寄存器，然后通过 `sret` 返回用户态：

```asm
__restore:
    mv sp, a0
__restore_sp:
    # 恢复 sstatus、sepc
    ld t0, 32*8(sp)
    ld t1, 33*8(sp)
    ld t2, 2*8(sp)
    csrw sstatus, t0
    csrw sepc, t1
    csrw sscratch, t2
    # 恢复通用寄存器
    ld x1, 1*8(sp)
    ld x3, 3*8(sp)
    .set n, 5
    .rept 27
        LOAD_GP %n
        .set n, n+1
    .endr
    addi sp, sp, 34*8
    csrrw sp, sscratch, sp
    sret
```

值得注意的是 `__restore_sp` 标签的存在。`TaskContext::goto_restore` 中将 `ra` 设置为 `__restore_sp` 而非 `__restore`，这使得新任务首次被 `__switch` 切换进来时可以直接从这个标签开始执行，跳过 `mv sp, a0`（因为此时 `sp` 已经在 `__switch` 中被正确设置了）。

## `trap_handler` 的分发逻辑

Trap 处理函数 `trap_handler` 根据陷入原因分发到不同的处理逻辑：

```rust
// kernel/src/trap/mod.rs
pub fn trap_handler(cx: &mut TrapContext) -> &mut TrapContext {
    let scause = scause::read();
    let stval = stval::read();
    match scause.cause() {
        Trap::Exception(Exception::UserEnvCall) => {
            cx.sepc += 4;
            cx.x[10] = syscall(cx.x[17], [cx.x[10], cx.x[11], cx.x[12]])
                as usize;
        }
        Trap::Exception(Exception::StoreFault)
        | Trap::Exception(Exception::StorePageFault)
        | Trap::Exception(Exception::LoadFault)
        | Trap::Exception(Exception::LoadPageFault)
        | Trap::Exception(Exception::InstructionFault)
        | Trap::Exception(Exception::InstructionPageFault) => {
            println!("[kernel] PageFault in application, bad addr = {:#x}, \
                      bad instruction = {:#x}, kernel killed it.",
                      stval, cx.sepc);
            exit_current_and_run_next();
        }
        Trap::Exception(Exception::IllegalInstruction) => {
            println!("[kernel] IllegalInstruction in application, \
                      kernel killed it.");
            exit_current_and_run_next();
        }
        Trap::Interrupt(Interrupt::SupervisorTimer) => {
            set_next_trigger();
            suspend_current_and_run_next();
        }
        _ => {
            panic!("Unsupported trap {:?}, stval = {:#x}!",
                   scause.cause(), stval);
        }
    }
    cx
}
```

对于**系统调用**（`UserEnvCall`），`sepc` 需要加 4 以跳过触发陷入的 `ecall` 指令（RISC-V 中 `ecall` 是 4 字节长的指令），然后将系统调用号（`x[17]` 即 `a7`）和参数（`x[10]`-`x[12]` 即 `a0`-`a2`）传递给 `syscall` 函数，返回值写入 `x[10]`（ `a0`）。

对于**页错误和访存异常**，当前的处理策略是终止出错的应用并调度下一个任务。这在后续启用虚拟内存后可以扩展为按需分页：内核先检查访问的地址是否合法，如果合法则分配物理页帧并建立映射，然后重新执行引发异常的指令。

对于**时钟中断**（`SupervisorTimer`），内核设置下一次时钟中断的触发时间，然后挂起当前任务并调度下一个。这是**抢占式调度**的基础——即使用户程序永不主动让出 CPU，时钟中断也会定期强制切换到其他就绪任务，确保所有任务都能获得 CPU 时间。

下一篇文档将继续深入分析任务管理器 `TaskManager` 的设计与调度策略、系统调用在进程管理中的角色，以及 Ch5 实验所需实现的 `fork`、`exec`、`waitpid` 等进程管理接口。
