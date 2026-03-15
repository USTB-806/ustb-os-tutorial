---
title: 为文件系统提供支持
description: lab6
---

前面的章节中，用户程序的输出被直接发送到串口终端，而程序数据被嵌入在内核映像中. 这在操作系统的早期原型中可行，但一个完整的操作系统需要提供**文件系统**来管理**持久化的数据存储**. 

本节将会介绍实现文件系统的一些前置内容.

## 理论基础

文件系统是操作系统中用于管理磁盘（或其他持久化存储设备）上数据的组织方式和访问接口. 

从用户的角度看，文件系统提供了以**文件**和**目录**为基本单位的层次化命名空间；从内核的角度看，文件系统需要将这些高层抽象映射到底层的块设备读写操作.

Unix 系统的文件系统设计遵循一个核心哲学：**一切皆文件（Everything is a file）**. 不仅磁盘上的数据被抽象为文件，标准输入/输出、管道、设备等也通过相同的文件接口 (`open`/`read`/`write`/`close`) 进行访问. 

每个打开的文件由一个非负整数标识，称为**文件描述符 (File Descriptor, fd)**. Unix 对文件描述符的分配遵循"最小未用值"原则：新打开文件时，分配当前未使用的最小的文件描述符编号.

按照惯例，每个进程启动时自动拥有三个预定义的文件描述符：

- fd 0：标准输入（stdin）
- fd 1：标准输出（stdout）
- fd 2：标准错误（stderr）

在本内核的当前实现中，只有 stdout（fd 1）得到了支持，它直接通过 SBI 调用将字符输出到 QEMU 的虚拟串口.

## 用户态文件操作接口

在用户态库 `user/rust/src/lib.rs` 中，为文件系统操作定义了一组高层封装函数和类型. 这些接口在内核侧的系统调用实现完成之前就已经设计好了，先定义接口、再实现功能.

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

这些标志与 Linux 的 `O_RDONLY`、`O_WRONLY`、`O_RDWR`、`O_CREAT`、`O_TRUNC` [各自对应](https://man7.org/linux/man-pages/man2/open.2.html). 它们可以通过位或运算组合使用，例如 `OpenFlags::CREATE | OpenFlags::WRONLY` 表示以只写方式打开文件，若文件不存在则创建.

用户态提供的文件操作函数包括：

```rust
pub fn open(path: &str, flags: OpenFlags) -> isize {
    sys_openat(AT_FDCWD as usize, path, flags.bits, OpenFlags::RDWR.bits)
}

pub fn close(fd: usize) -> isize {
    sys_close(fd)
}
```

`open` 使用了 `openat` 系统调用，其中 `AT_FDCWD`(-100) 表示相对于当前工作目录.

然后我们就会通过内核 `kernel/src/syscall/mod.rs` 的分发来调用不同的内核 syscalls 实现了.

## File Trait & UserBuffer

在内核实现层面，所有的文件访问都可以通过一个抽象接口 `File` 这一 Trait 进行，具体实现上是 `Send + Sync`. 这为文件访问提供了并发的能力，实现了[基于 Send 和 Sync 的线程安全](https://course.rs/advance/concurrency-with-threads/send-sync.html#send-%E5%92%8C-sync).

```rust
/// trait File for all file types
pub trait File: Send + Sync {
    /// the file readable?
    fn readable(&self) -> bool;
    /// the file writable?
    fn writable(&self) -> bool;
    /// read from the file to buf, return the number of bytes read
    fn read(&self, buf: UserBuffer) -> usize;
    /// write to the file from buf, return the number of bytes written
    fn write(&self, buf: UserBuffer) -> usize;
}
```

这是为相当顶层的接口部分实现的，你可以在代码中找到 `impl File for OSInode {...}` 以及对于 `Stdin` 和 `Stdout` 的实现. 善用 Rust-analyzer 的 Go to References 功能.

定义于 `mm` 模块中的 `UserBuffer` 是应用地址空间的一段缓冲区，这也可以被理解为 `&[u8]` [切片](../../lab1/03-pointers-and-slices/). 就从类型 `pub buffers: Vec<&'static mut [u8]>` 理解，这实际上是一组 UTF8 编码构成的数组. 在 `Stdout` 的 `write` 方法中直接使用了 `from_utf8(*buffer)`. 可以参考 [from_utf8](https://doc.rust-lang.org/std/str/fn.from_utf8.html). 

```rust
/// An abstraction over a buffer passed from user space to kernel space
pub struct UserBuffer {
    /// A list of buffers
    pub buffers: Vec<&'static mut [u8]>,
}
```

```rust
fn write(&self, user_buf: UserBuffer) -> usize {
    for buffer in user_buf.buffers.iter() {
        print!("{}", core::str::from_utf8(*buffer).unwrap());
    }
    user_buf.len()
}
```

`UserBuffer` 与 `translated_byte_buffer` 方法是对应的，返回向量形式的字节 (`u8`) 数组切片，内核空间可以访问. 

```rust
let buffers: Vec<&mut [u8]> = translated_byte_buffer(...);
```

使用 `UserBuffer` 在此基础上构建了 `Stdin::read` 和 `Stdout::write`.

```rust
impl File for Stdin {
    fn read(&self, mut user_buf: UserBuffer) -> usize {
        ...
        // mut user_buf: UserBuffer
        user_buf.buffers[0].as_mut_ptr().write_volatile(ch);
        ...
    }
}
```

## fd_table

每个进程都带有一个文件描述符表 `fd_table`，记录请求打开并可以读写的文件集合. 此表对应有文件描述符 (File Descriptor, `fd`) 以一个非负整数记录对应文件位置. `open` 或 `create` 会返回对应描述符，而 `close` 需要提供描述符以关闭文件.

在 `TaskControlBlockInner` 中就有 `pub fd_table: Vec<Option<Arc<dyn File + Send + Sync>>>`. 包含了共享引用和诸多特性. 其中 `dyn` 就是一种运行时多态. 在 fork 时，子进程完全继承父进程的文件描述符表，由此共享文件. 新建进程时，默认先打开标准输入文件 `Stdin` 和标准输出文件 `Stdout`.

在新建 `TaskControlBlock` 时初始化 `fd_table`:

```rust
// kernel/src/task/task.rs
let task_control_block = Self {
    pid: pid_handle,
    kernel_stack,
    inner: unsafe {
        UPSafeCell::new(TaskControlBlockInner {
            ...
            fd_table: vec![
                // 0 -> stdin
                Some(Arc::new(Stdin)),
                // 1 -> stdout
                Some(Arc::new(Stdout)),
                // 2 -> stderr
                Some(Arc::new(Stdout)),
            ],
            ...
        })
    },
};
```

`sys_write` 和 `sys_read` 及其他文件系统相关 syscalls 根据对应的文件描述符 `fd` 从当前进程的 `fd_table` 中取出文件并执行对应的读写操作. 可以参考如下代码实现：

```rust
pub fn sys_write(fd: usize, buf: *const u8, len: usize) -> isize {
    let token = current_user_token();
    let task = current_task().unwrap();
    let inner = task.acquire_inner_lock();
    if fd >= inner.fd_table.len() {
        return -1;
    }
    if let Some(file) = &inner.fd_table[fd] {
        let file = file.clone();
        // release Task lock manually to avoid deadlock
        drop(inner);
        ... 
    } else {
        -1
    }
}
```