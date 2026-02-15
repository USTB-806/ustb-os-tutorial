---
title: 进程管理（下）
description: lab5
---

# Ch5 进程管理（下）：任务管理器与调度

上篇文档介绍了任务控制块的结构设计、上下文切换的底层实现以及 Trap 处理的分发逻辑。本篇将聚焦于**任务管理器 `TaskManager`** 的完整实现，分析它如何协调多个任务的创建、调度和终止；同时介绍进程管理相关的系统调用接口，并讨论 Ch5 实验中需要实现的 `fork`、`exec`、`waitpid` 等高级进程管理功能。

## 任务管理器的整体设计

任务管理器 `TaskManager` 是本内核中管理所有用户任务的中心组件，以全局单例的形式存在。它的定义位于 `kernel/src/task/mod.rs`：

```rust
pub struct TaskManager {
    num_app: usize,
    inner: UPSafeCell<TaskManagerInner>,
}

pub struct TaskManagerInner {
    tasks: [TaskControlBlock; MAX_APP_NUM],
    current_task: usize,
    syscall_count: [SyscallTrace; MAX_APP_NUM],
}
```

`TaskManager` 采用了内外分离的设计模式：外层 `TaskManager` 持有不可变的 `num_app`（总任务数），内层 `TaskManagerInner` 包含所有需要在运行时修改的可变状态。`UPSafeCell` 是一个在单处理器环境下安全使用的包装类型，它将 Rust 的借用检查从编译期推迟到运行期。其内部使用 `RefCell`，通过 `exclusive_access()` 方法获取内部数据的独占可变引用：

```rust
// kernel/src/sync/up.rs
pub struct UPSafeCell<T> {
    inner: RefCell<T>,
}

unsafe impl<T> Sync for UPSafeCell<T> {}

impl<T> UPSafeCell<T> {
    pub unsafe fn new(value: T) -> Self {
        Self { inner: RefCell::new(value) }
    }
    pub fn exclusive_access(&self) -> RefMut<'_, T> {
        self.inner.borrow_mut()
    }
}
```

`unsafe impl Sync` 声明允许 `UPSafeCell` 被多个线程共享（作为静态变量要求实现 `Sync`），但实际上在单核场景下不存在并发访问的风险。如果在多核场景下使用，则需要替换为自旋锁等真正的同步原语。

## 任务管理器的初始化

`TASK_MANAGER` 通过 `lazy_static!` 宏实现延迟初始化——在首次被访问时才执行初始化逻辑：

```rust
lazy_static! {
    pub static ref TASK_MANAGER: TaskManager = {
        let num_app = get_num_app();
        let mut tasks = [TaskControlBlock {
            task_cx: TaskContext::zero_init(),
            task_status: TaskStatus::UnInit,
        }; MAX_APP_NUM];
        for (i, task) in tasks.iter_mut().enumerate() {
            task.task_cx = TaskContext::goto_restore(init_app_cx(i));
            task.task_status = TaskStatus::Ready;
        }
        let syscall_count = Default::default();
        TaskManager {
            num_app,
            inner: unsafe {
                UPSafeCell::new(TaskManagerInner {
                    tasks,
                    current_task: 0,
                    syscall_count,
                })
            },
        }
    };
}
```

初始化过程有清晰的结构。首先创建一个大小为 `MAX_APP_NUM` 的 `TaskControlBlock` 数组，所有元素初始化为 `UnInit` 状态、零上下文。然后遍历前 `num_app` 个任务，通过 `init_app_cx(i)` 为每个应用在其内核栈上放置初始的 `TrapContext`，再用 `TaskContext::goto_restore` 创建一个返回地址指向 `__restore_sp` 的任务上下文。当这些任务后续被 `__switch` 切换进来时，将跳转到 `__restore_sp`，从内核栈上恢复 `TrapContext` 并通过 `sret` 进入用户态——这就是任务首次启动的机制。

每个任务还关联一个 `SyscallTrace` 结构体，用于追踪该任务执行的系统调用情况：

```rust
// kernel/src/task/task.rs
#[derive(Clone)]
pub struct SyscallTrace {
    pub syscall_count: BTreeMap<usize, usize>,
}
```

`BTreeMap<usize, usize>` 以系统调用号为键、调用次数为值，记录了每个任务所执行的每种系统调用的次数。

## 首次任务启动

系统初始化完成后，`main()` 函数调用 `task::run_first_task()` 启动第一个用户任务。这个操作有些特殊——此时没有"当前任务"，需要从一个虚拟的初始状态切换到第一个真正的任务：

```rust
fn run_first_task(&self) -> ! {
    let mut inner = self.inner.exclusive_access();
    let task0 = &mut inner.tasks[0];
    task0.task_status = TaskStatus::Running;
    let next_task_cx_ptr = &task0.task_cx as *const TaskContext;
    drop(inner);
    let mut _unused = TaskContext::zero_init();
    unsafe {
        __switch(
            &mut _unused as *mut TaskContext,
            next_task_cx_ptr
        );
    }
    panic!("unreachable in run_first_task!");
}
```

函数首先将任务 0 的状态设为 `Running`，获取其 `TaskContext` 的地址。然后创建一个临时的零初始化 `TaskContext`（ `_unused`），作为 `__switch` 保存"当前上下文"的目标——这个保存结果永远不会被恢复，因为 `run_first_task` 本身永远不会返回。`drop(inner)` 确保在调用 `__switch` 前释放对 `TaskManagerInner` 的借用（否则在切换到新任务后，该借用将永远无法释放，导致之后的 `exclusive_access` 调用 panic）。

`__switch` 完成切换后，CPU 将跳转到任务 0 的 `TaskContext` 中保存的 `ra`（即 `__restore_sp`），恢复 `TrapContext` 并进入用户态。内核的初始化流程至此结束，系统进入了用户任务的执行循环。

## 任务调度算法

当一个任务需要让出 CPU 时（无论是主动调用 `sys_yield` 还是被时钟中断抢占），需要找到下一个可以运行的就绪任务。本内核采用的是**简单轮转（Round-Robin）**调度算法：

```rust
fn find_next_task(&self) -> Option<usize> {
    let inner = self.inner.exclusive_access();
    let current = inner.current_task;
    (current + 1..current + self.num_app + 1)
        .map(|id| id % self.num_app)
        .find(|id| inner.tasks[*id].task_status == TaskStatus::Ready)
}
```

从当前任务的下一个位置开始，按环形顺序遍历所有任务，找到第一个状态为 `Ready` 的任务并返回其编号。如果所有任务都不在 `Ready` 状态（即都已退出或正在运行），返回 `None`。

Round-Robin 调度是最简单的时分调度算法，它给予每个就绪任务相等的 CPU 时间片。配合时钟中断实现的抢占机制，它能保证即使某个任务进入死循环也不会饿死其他任务。然而，这种策略无法区分任务的优先级。在 Ch5 的实验中，学生将实现**步幅调度（Stride Scheduling）**算法，通过 `sys_set_priority` 系统调用为任务分配不同的优先级，使高优先级任务获得更多的 CPU 时间。

## 任务切换流程

当调度器找到下一个就绪任务后，通过 `run_next_task` 完成上下文切换：

```rust
fn run_next_task(&self) {
    if let Some(next) = self.find_next_task() {
        let mut inner = self.inner.exclusive_access();
        let current = inner.current_task;
        inner.tasks[next].task_status = TaskStatus::Running;
        inner.current_task = next;
        let current_task_cx_ptr =
            &mut inner.tasks[current].task_cx as *mut TaskContext;
        let next_task_cx_ptr =
            &inner.tasks[next].task_cx as *const TaskContext;
        drop(inner);
        unsafe {
            __switch(current_task_cx_ptr, next_task_cx_ptr);
        }
    } else {
        panic!("All applications completed!");
    }
}
```

这段代码的执行顺序值得仔细思考。首先将下一个任务标记为 `Running` 并更新 `current_task` 指针，这些操作都在借用 `inner` 的期间完成。然后获取两个任务的 `TaskContext` 指针，释放 `inner` 的借用——这一步至关重要，因为 `__switch` 返回后实际上已经是另一个任务在执行了，而那个任务也可能需要访问 `inner`。如果此时仍持有借用，将触发运行时的借用冲突 panic。

在 `__switch` 之后"返回"的代码，实际上只有在当前任务下一次被重新调度时才会执行。从当前任务的视角来看，调用 `__switch` 就像是睡着了；当它再次被调度运行时，将从 `__switch` 的返回点继续执行——对它而言，就好像中间什么都没发生过。

## 任务状态管理

任务管理器提供了两个函数来改变当前任务的状态，分别用于挂起和终止：

```rust
fn mark_current_suspended(&self) {
    let mut inner = self.inner.exclusive_access();
    let current = inner.current_task;
    inner.tasks[current].task_status = TaskStatus::Ready;
}

fn mark_current_exited(&self) {
    let mut inner = self.inner.exclusive_access();
    let current = inner.current_task;
    inner.tasks[current].task_status = TaskStatus::Exited;
}
```

这两个函数通过模块级别的包装函数暴露给外部使用，最终组合成两个高层接口：

```rust
pub fn suspend_current_and_run_next() {
    mark_current_suspended();  // 当前 → Ready
    run_next_task();           // 切换到下一个
}

pub fn exit_current_and_run_next() {
    mark_current_exited();     // 当前 → Exited
    run_next_task();           // 切换到下一个
}
```

`suspend_current_and_run_next` 用于让出 CPU 但保持就绪——之后还可以再次被调度运行。`exit_current_and_run_next` 用于永久终止一个任务——它的状态变为 `Exited` 后不会再被调度器选中。

## 系统调用追踪

本内核实现了一个系统调用追踪机制，每次系统调用入口处会更新当前任务的调用计数：

```rust
pub fn syscall(syscall_id: usize, args: [usize; 3]) -> isize {
    update_syscall_times(syscall_id);
    match syscall_id {
        SYSCALL_WRITE => sys_write(args[0], args[1] as *const u8, args[2]),
        SYSCALL_EXIT => sys_exit(args[0] as i32),
        SYSCALL_YIELD => sys_yield(),
        SYSCALL_GET_TIME => sys_get_time(args[0] as *mut TimeVal, args[1]),
        SYSCALL_TRACE => sys_trace(args[0], args[1], args[2]),
        _ => panic!("Unsupported syscall_id: {}", syscall_id),
    }
}
```

`update_syscall_times` 在 `TaskManager` 中的实现如下：

```rust
fn update_syscall_times(&self, syscall_id: usize) {
    let mut inner = self.inner.exclusive_access();
    let current_task_no = inner.current_task;
    let syscall_times = &mut inner
        .syscall_count[current_task_no]
        .syscall_count;
    syscall_times.entry(syscall_id)
        .and_modify(|count| *count += 1)
        .or_insert(1);
}
```

利用 `BTreeMap` 的 `entry` API，如果该系统调用号已存在则计数加一，否则插入初始值 1。这种设计允许以 O(log n) 的时间复杂度更新和查询，同时不浪费空间——只记录实际被调用过的系统调用。

`sys_trace` 系统调用为用户程序提供了查询追踪信息的接口，支持三种请求模式：

```rust
pub fn sys_trace(request: usize, syscall_id: usize, data: usize) -> isize {
    match request {
        TRACE_GET_SYSCALL_COUNT => {
            get_syscall_times(syscall_id) as isize
        },
        TRACE_GET_TASK_INFO => {
            let info_ptr = data as *mut TaskInfo;
            match get_current_task_info() {
                Some((status, syscall_times)) => {
                    unsafe {
                        (*info_ptr).status = status;
                        (*info_ptr).syscall_times = syscall_times;
                    }
                    0
                },
                None => -1,
            }
        },
        TRACE_GET_TOTAL_SYSCALLS => {
            get_total_syscall_count() as isize
        },
        _ => -1,
    }
}
```

## 时钟中断与抢占式调度

仅靠 `sys_yield` 的协作式调度是不够的——一个恶意或有 bug 的用户程序可能永远不调用 `sys_yield`，从而独占 CPU。因此需要**抢占式调度**：内核利用硬件定时器周期性地产生中断，强制将 CPU 控制权从用户程序夺回。

时钟相关的功能在 `kernel/src/timer.rs` 中实现：

```rust
const TICKS_PER_SEC: usize = 100;

pub fn set_next_trigger() {
    set_timer(get_time() + CLOCK_FREQ / TICKS_PER_SEC);
}
```

RISC-V 的时钟中断通过 SBI 的 `set_timer` 接口配置。`CLOCK_FREQ / TICKS_PER_SEC` 计算出每个时间片对应的时钟周期数——以 12.5MHz 的时钟频率和 100 ticks/秒为例，每 125,000 个时钟周期触发一次中断，即每 10ms 一个时间片。

在 `main()` 中，内核启动定时器并启用 S 模式的时钟中断：

```rust
trap::enable_timer_interrupt();  // 设置 sie.STIE
timer::set_next_trigger();       // 设置首次触发时间
```

当时钟中断到来时，`trap_handler` 中的处理逻辑将设置下一次中断并挂起当前任务：

```rust
Trap::Interrupt(Interrupt::SupervisorTimer) => {
    set_next_trigger();
    suspend_current_and_run_next();
}
```

## Ch5 实验要求概述

Ch5 的实验在当前已有的任务管理基础上，要求学生实现以下进程管理功能：

**`sys_fork`**：创建当前进程的副本。父进程返回子进程的 PID，子进程返回 0。子进程应该拥有父进程地址空间、文件描述符表等资源的副本，但拥有独立的 PID。这需要复制页表（或使用 Copy-on-Write 优化）。

**`sys_exec`**：将当前进程的地址空间替换为新的 ELF 程序。这涉及释放原有的页表映射，加载新的 ELF 文件，重新初始化用户栈。

**`sys_waitpid`**：等待一个子进程退出并获取其退出码。如果指定的子进程尚未退出，返回 -2 表示需要重试（用户库通过循环加 `yield` 实现阻塞等待）。

**`sys_getpid`**：返回当前进程的 PID。

**`sys_spawn`**：创建一个新进程并执行指定路径的程序，相当于 `fork` + `exec` 的组合。

**`sys_set_priority`**：设置当前进程的优先级，用于实现步幅调度。步幅调度（Stride Scheduling）的核心思想是为每个进程维护一个"步幅值"（stride），步幅与优先级成反比。每次调度时选择步幅累积值最小的进程运行，运行后增加其步幅累积值。优先级越高的进程步幅越小，因此能更频繁地被选中，获得更多 CPU 时间。

实现这些功能后，当前的扁平 `TaskControlBlock` 数组需要替换为树形的进程结构，每个进程拥有独立的 PID、父子关系、退出码等元数据。`TaskManager` 也需要相应重构为支持动态进程创建和销毁的进程管理器。
