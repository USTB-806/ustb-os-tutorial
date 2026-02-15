---
title: 文件系统（上）
description: lab6
---

# Ch6 文件系统（上）：系统调用接口与 I/O 抽象

前面的章节中，用户程序的输出被直接发送到串口终端，而程序数据被嵌入在内核映像中。这种方式在操作系统的早期原型中可行，但一个完整的操作系统需要提供**文件系统**来管理持久化的数据存储。本章将从系统调用接口出发，分析内核如何处理 I/O 操作，并介绍 Ch6 实验中需要实现的文件系统功能。

## 文件系统的理论基础

文件系统是操作系统中用于管理磁盘（或其他持久化存储设备）上数据的组织方式和访问接口。从用户的角度看，文件系统提供了以**文件**和**目录**为基本单位的层次化命名空间；从内核的角度看，文件系统需要将这些高层抽象映射到底层的块设备读写操作。

Unix 系统的文件系统设计遵循一个核心哲学：**一切皆文件（Everything is a file）**。不仅磁盘上的数据被抽象为文件，标准输入/输出、管道、设备等也通过相同的文件接口（`open`/`read`/`write`/`close`）进行访问。每个打开的文件由一个非负整数标识，称为**文件描述符（File Descriptor, fd）**。Unix 对文件描述符的分配遵循"最小可用"原则：新打开文件时，分配当前未使用的最小的文件描述符编号。

按照惯例，每个进程启动时自动拥有三个预定义的文件描述符：

- fd 0：标准输入（stdin）
- fd 1：标准输出（stdout）
- fd 2：标准错误（stderr）

在本内核的当前实现中，只有 stdout（fd 1）得到了支持，它直接通过 SBI 调用将字符输出到 QEMU 的虚拟串口。

## 当前的 I/O 实现

内核目前支持的 I/O 操作仅限于标准输出的写入，通过 `sys_write` 系统调用实现。该系统调用定义在 `kernel/src/syscall/fs.rs` 中：

```rust
// kernel/src/syscall/fs.rs
const FD_STDOUT: usize = 1;

pub fn sys_write(fd: usize, buf: *const u8, len: usize) -> isize {
    match fd {
        FD_STDOUT => {
            let slice = unsafe {
                core::slice::from_raw_parts(buf, len)
            };
            let str = core::str::from_utf8(slice).unwrap();
            print!("{}", str);
            len as isize
        }
        _ => {
            panic!("Unsupported fd in sys_write!");
        }
    }
}
```

当用户程序调用 `sys_write(1, buf, len)` 时，内核将 `buf` 指针处长度为 `len` 的字节序列解释为 UTF-8 字符串，通过 `print!` 宏输出到控制台。`print!` 宏最终调用了 SBI 的 `console_putchar` 接口，将每个字符逐一发送到 QEMU 虚拟机的 UART 设备：

```rust
// kernel/src/utils/sbi.rs
pub fn console_putchar(c: usize) {
    sbi_call(SBI_CONSOLE_PUTCHAR, c, 0, 0);
}
```

`sbi_call` 通过 `ecall` 指令陷入 M 模式的 SBI 固件（如 RustSBI），由 SBI 完成实际的硬件操作。这个调用链展示了一个完整的 I/O 路径：用户态 `write()` → `ecall` → 内核 `trap_handler` → `sys_write` → SBI `console_putchar` → UART 硬件。

对于其他文件描述符，当前实现直接 panic。这正是 Ch6 实验需要扩展的地方——支持真正的文件操作。

## 系统调用分发机制

所有系统调用通过统一的 `syscall` 函数入口进行分发：

```rust
// kernel/src/syscall/mod.rs
const SYSCALL_WRITE: usize = 64;
const SYSCALL_EXIT: usize = 93;
const SYSCALL_YIELD: usize = 124;
const SYSCALL_GET_TIME: usize = 169;
const SYSCALL_TRACE: usize = 410;

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

系统调用号遵循 RISC-V Linux 的 ABI 约定。用户程序将系统调用号放入 `a7` 寄存器、参数放入 `a0`-`a2`，然后执行 `ecall` 指令。在用户态库 `user/rust/src/syscall.rs` 中，这个过程被封装为 Rust 函数：

```rust
pub fn syscall(id: usize, args: [usize; 3]) -> isize {
    let mut ret: isize;
    unsafe {
        core::arch::asm!(
            "ecall",
            inlateout("x10") args[0] => ret,
            in("x11") args[1],
            in("x12") args[2],
            in("x17") id
        );
    }
    ret
}
```

`ecall` 触发 `UserEnvCall` 异常，陷入内核的 `trap_handler`，后者提取寄存器中的参数并调用 `syscall` 分发函数。返回值通过 `a0`（即 `x[10]`）传回用户态。

对于需要 6 个参数的系统调用（如 `openat`、`linkat`），用户库提供了 `syscall6` 变体，使用 `a0`-`a5` 传递参数：

```rust
pub fn syscall6(id: usize, args: [usize; 6]) -> isize {
    let mut ret: isize;
    unsafe {
        core::arch::asm!("ecall",
            inlateout("x10") args[0] => ret,
            in("x11") args[1],
            in("x12") args[2],
            in("x13") args[3],
            in("x14") args[4],
            in("x15") args[5],
            in("x17") id
        );
    }
    ret
}
```

## 用户态文件操作接口

在用户态库 `user/rust/src/lib.rs` 中，为文件系统操作定义了一组高层封装函数和类型。这些接口在内核侧的系统调用实现完成之前就已经设计好了，体现了**先定义接口、再实现功能**的工程方法。

文件打开标志通过 `bitflags` 宏定义：

```rust
bitflags! {
    pub struct OpenFlags: u32 {
        const RDONLY = 0;
        const WRONLY = 1 << 0;
        const RDWR = 1 << 1;
        const CREATE = 1 << 9;
        const TRUNC = 1 << 10;
    }
}
```

这些标志与 Linux 的 `O_RDONLY`、`O_WRONLY`、`O_RDWR`、`O_CREAT`、`O_TRUNC` 一一对应。它们可以通过位或运算组合使用，例如 `OpenFlags::CREATE | OpenFlags::WRONLY` 表示以只写方式打开文件，若文件不存在则创建。

用户态提供的文件操作函数包括：

```rust
pub fn open(path: &str, flags: OpenFlags) -> isize {
    sys_openat(AT_FDCWD as usize, path, flags.bits, OpenFlags::RDWR.bits)
}

pub fn close(fd: usize) -> isize {
    sys_close(fd)
}

pub fn read(fd: usize, buf: &mut [u8]) -> isize {
    sys_read(fd, buf)
}

pub fn write(fd: usize, buf: &[u8]) -> isize {
    sys_write(fd, buf)
}

pub fn link(old_path: &str, new_path: &str) -> isize {
    sys_linkat(AT_FDCWD as usize, old_path, AT_FDCWD as usize, new_path, 0)
}

pub fn unlink(path: &str) -> isize {
    sys_unlinkat(AT_FDCWD as usize, path, 0)
}

pub fn fstat(fd: usize, st: &mut Stat) -> isize {
    sys_fstat(fd, st)
}
```

`open` 使用了 `openat` 系统调用（调用号 56），其中 `AT_FDCWD`（-100）表示相对于当前工作目录。文件的元信息通过 `Stat` 结构体获取：

```rust
#[repr(C)]
pub struct Stat {
    pub dev: u64,        // 设备 ID
    pub ino: u64,        // inode 编号
    pub mode: StatMode,  // 文件类型和权限
    pub nlink: u32,      // 硬链接数
    pad: [u64; 7],       // 填充
}

bitflags! {
    pub struct StatMode: u32 {
        const NULL  = 0;
        const DIR   = 0o040000;   // 目录
        const FILE  = 0o100000;   // 普通文件
    }
}
```

这些数据结构遵循 POSIX 标准的定义，确保了与标准 Unix 工具链的兼容性。

## 控制台输出的底层实现

要完整理解 I/O 路径，还需要了解内核控制台的实现。`kernel/src/utils/console.rs` 定义了 `print!` 和 `println!` 宏：

```rust
struct Stdout;

impl Write for Stdout {
    fn write_str(&mut self, s: &str) -> fmt::Result {
        for c in s.chars() {
            console_putchar(c as usize);
        }
        Ok(())
    }
}

pub fn _print(args: Arguments) {
    Stdout.write_fmt(args).unwrap();
}

#[macro_export]
macro_rules! print {
    ($($arg:tt)*) => {
        $crate::console::_print(format_args!("{}", format_args!($($arg)*)))
    };
}

#[macro_export]
macro_rules! println {
    () => ($crate::print!("\n"));
    ($($arg:tt)*) => {
        $crate::print!($($arg)*);
        $crate::print!("\n")
    };
}
```

`Stdout` 结构体实现了 `core::fmt::Write` trait，这使得它可以与 Rust 的格式化机制集成。每个字符通过 `console_putchar` 逐一输出到 SBI。虽然逐字符输出的效率较低，但对于调试输出和简单的控制台交互已经足够。在后续实现块设备驱动和文件系统后，文件 I/O 将通过更高效的批量块读写来完成。

## 虚拟地址翻译与安全的用户空间访问

当内核启用虚拟内存后，`sys_write` 中直接使用用户空间指针将不再安全——用户传入的是虚拟地址，而内核不能简单地解引用它。`mm` 模块中的 `translated_byte_buffer` 函数用于处理这个问题：

```rust
pub fn translated_byte_buffer(
    token: usize, ptr: *const u8, len: usize
) -> Vec<&'static mut [u8]> {
    let mut buffers = Vec::new();
    unsafe {
        buffers.push(core::slice::from_raw_parts_mut(ptr as *mut u8, len));
    }
    buffers
}
```

在当前实现中，由于内核和用户程序共享同一物理地址空间，虚拟地址等于物理地址，该函数直接返回原始指针对应的内存切片。在 Ch4/Ch6 实验的完整实现中，该函数需要：

1. 从 `token` 中解析出根页表的物理页号。
2. 对于给定的虚拟地址范围 `[ptr, ptr+len)`，逐页查询页表获取对应的物理页帧号。
3. 将每个物理页帧上的数据切片加入返回的 `Vec` 中。

这样 `sys_write` 才能安全地读取位于用户进程虚拟地址空间中的数据。

下一篇文档将深入分析 easy-fs 文件系统的设计思路和块设备的交互模型，并详细说明 Ch6 实验需要实现的文件系统操作。
