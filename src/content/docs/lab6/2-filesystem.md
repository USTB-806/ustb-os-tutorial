---
title: 文件系统（下）
description: lab6
---

# Ch6 文件系统（下）：文件系统架构与实验指导

上篇文档分析了内核当前的 I/O 系统调用实现和用户态文件操作接口。本篇将介绍 easy-fs 文件系统的整体架构设计，讨论块设备与文件系统的交互模型，并详细说明 Ch6 实验需要实现的各项文件系统功能。

## 文件系统的层次结构

一个完整的文件系统实现通常包含多个层次，每层解决不同的抽象问题。从底向上依次为：

**块设备层（Block Device Layer）**负责与硬件交互，提供按块（通常 512 字节）读写磁盘的接口。在 QEMU 虚拟机中，块设备通常是一个 VirtIO Block 设备，内核通过 MMIO（内存映射 I/O）与其通信。块设备驱动需要实现一个 `BlockDevice` trait，提供 `read_block` 和 `write_block` 方法。

**块缓存层（Block Cache Layer）**在内存中维护一组最近使用的磁盘块的缓存副本，减少直接访问块设备的次数。当上层请求读取某个磁盘块时，块缓存层先检查该块是否已在缓存中；如果是则直接返回内存中的副本，否则从块设备读取并加入缓存。当缓存满时，使用 LRU（最近最少使用）等策略驱逐旧的缓存块。写操作通常先修改缓存中的副本，在适当时机（如块被驱逐或显式 `sync`）才写回磁盘。

**磁盘布局层（Disk Layout Layer）**定义了数据在磁盘上的组织方式。典型的 Unix 文件系统将磁盘划分为以下区域：超级块（Superblock）保存文件系统的全局元数据；inode 位图和数据块位图用于追踪 inode 和数据块的分配状态；inode 区域存储所有文件和目录的元信息；数据块区域存储文件的实际内容。

**虚拟文件系统层（VFS Layer）**向更上层提供统一的文件操作接口（open、read、write、close 等），屏蔽底层不同文件系统实现的差异。在本内核中，easy-fs 是唯一的文件系统实现，因此 VFS 层相对简化。

## easy-fs 的设计理念

easy-fs 是专为教学操作系统设计的轻量级文件系统。与 ext4、XFS 等生产级文件系统相比，easy-fs 做了大量简化：

- **不支持目录层次**：所有文件都在根目录下，不支持子目录。
- **inode 采用直接索引和间接索引**：类似于经典的 Unix 文件系统，每个 inode 包含若干直接数据块指针、一级间接索引块指针和二级间接索引块指针。
- **不支持权限控制**：没有文件权限位、用户/组等概念。
- **不支持符号链接**：只支持普通文件和目录两种类型。

尽管做了这些简化，easy-fs 完整地展示了一个文件系统的核心概念：磁盘布局、空间管理（位图）、索引结构（inode）、目录项管理以及文件的读写操作。

## 磁盘布局详解

easy-fs 的磁盘布局按照以下顺序组织：

```
┌───────────┬──────────┬──────────┬──────────┬──────────┐
│ Superblock │ Inode    │ Data     │ Inode    │  Data    │
│ (1 block)  │ Bitmap   │ Bitmap   │ Area     │  Area    │
└───────────┴──────────┴──────────┴──────────┴──────────┘
     ↑            ↑          ↑          ↑          ↑
   块 0        块 1~n     块 n+1~m   块 m+1~k   块 k+1~end
```

**超级块（Superblock）**占据磁盘的第一个块，记录文件系统的全局信息：magic number（用于识别文件系统类型）、总块数、各区域的起始块号和大小等。内核挂载文件系统时首先读取超级块，验证 magic number 是否匹配，然后据此定位其他区域。

**Inode 位图**用一个位对应一个 inode，标记该 inode 是否处于使用状态。分配新 inode 时，在位图中查找第一个为 0 的位，将其置 1 并返回对应的 inode 号。释放 inode 时将对应位复位为 0。

**数据块位图**的作用与 inode 位图类似，用于追踪数据块的分配状态。文件的内容存储在数据块中，每个数据块的大小等于磁盘块大小（通常为 512 字节）。

**Inode 区域**存储所有 inode 的元数据。每个 inode 包含文件类型、文件大小、直接索引块指针（指向数据块）、间接索引块指针等。inode 号就是该 inode 在 inode 区域中的偏移位置。根目录通常使用 inode 0。

**数据块区域**存储文件的实际内容以及目录项数据。

## Inode 的索引结构

文件的数据分散在多个数据块中，需要一种索引结构来记录这些块的位置。easy-fs 采用了经典的多级索引方案：

**直接索引**：inode 中包含若干个直接指针，每个指针直接指向一个数据块。对于小文件，只需要直接索引就足够了。

**一级间接索引**：inode 中有一个指针指向一个"间接索引块"，该块中存储了一组数据块指针。假设每个块 512 字节、每个指针 4 字节，则一个间接索引块可以存储 128 个数据块指针。

**二级间接索引**：inode 中有一个指针指向一个"二级间接索引块"，该块中的每个指针指向一个一级间接索引块。这进一步扩展了可寻址的文件大小。

这种分层的索引设计在小文件和大文件之间取得了平衡。小文件只需访问 inode 就能定位所有数据块（无需额外的磁盘访问）；大文件虽然需要多次间接访问，但能支持极大的文件大小。

## 目录结构

在 easy-fs 中，目录本质上也是一个文件，只是它的数据块中存储的不是用户数据，而是一组**目录项（Directory Entry）**。每个目录项包含：

- **文件名**：定长字符串（例如 28 字节）
- **Inode 号**：该文件对应的 inode 编号

查找文件时，内核读取目录文件的所有数据块，逐个比较目录项中的文件名与目标文件名。找到匹配项后，取出对应的 inode 号，即可定位到该文件的元数据和内容。

创建新文件时，在目录的数据中追加一个新的目录项。如果名为 "filea" 的文件被创建，则在根目录的数据中写入一个 `(name="filea", inode=N)` 形式的目录项，其中 N 是新分配的 inode 号。

## 文件系统镜像的生成

easy-fs 的磁盘镜像通过 `easy-fs-fuse` 工具在宿主机上预先生成。该工具的工作流程是：

1. 创建一个指定大小的空文件作为磁盘镜像。
2. 在镜像上初始化 easy-fs 的磁盘布局（写入超级块、初始化位图等）。
3. 将用户程序的二进制文件逐一写入文件系统，创建对应的目录项和 inode。
4. 生成的镜像文件通过 QEMU 的 `-drive` 参数挂载为虚拟块设备。

从 Ch4 的 Makefile 中可以看到镜像生成的命令：

```makefile
fs-img:
	@rm -f $(FS_IMG)
	@cd ../temp-easy-fs-fuse && cargo run --release -- -t ../temp-user/build/
```

## 内核中的文件描述符管理

在完整的文件系统实现中，每个进程维护一个**文件描述符表（File Descriptor Table）**，将文件描述符编号映射到内核中的文件对象。文件对象通常实现一个公共的 trait：

```rust
// 典型的文件 trait 设计（教学示例）
pub trait File: Send + Sync {
    fn readable(&self) -> bool;
    fn writable(&self) -> bool;
    fn read(&self, buf: UserBuffer) -> usize;
    fn write(&self, buf: UserBuffer) -> usize;
}
```

不同类型的文件对象——如磁盘文件、标准 I/O、管道——各自实现这个 trait。进程的文件描述符表则用 `Vec<Option<Arc<dyn File>>>` 来存储，其中 `Arc` 允许多个描述符（或多个进程的描述符）共享同一个文件对象。

当前内核中，`sys_write` 只支持 fd=1（标准输出），其他 fd 会 panic。在 Ch6 实验中，需要将这个硬编码的方式替换为完整的文件描述符管理机制。

## Ch6 实验要求详解

Ch6 实验要求学生在内核中实现以下文件系统功能：

### sys_openat

```rust
pub fn sys_openat(dirfd: usize, path: &str, flags: u32, mode: u32) -> isize
```

打开（或创建）一个文件，返回文件描述符。`dirfd` 通常为 `AT_FDCWD`（-100），表示相对于当前工作目录。`flags` 指定打开模式：只读、只写、读写、创建、截断等。实现要点：

- 在文件系统中根据路径查找文件的 inode。如果设置了 `CREATE` 标志且文件不存在，则创建新文件。
- 分配一个文件描述符（进程 fd 表中最小的空闲位置），将其关联到一个新建的文件对象。
- 如果设置了 `TRUNC` 标志，将文件内容清空。

### sys_read 和 sys_write

```rust
pub fn sys_read(fd: usize, buf: *mut u8, len: usize) -> isize
pub fn sys_write(fd: usize, buf: *const u8, len: usize) -> isize
```

从文件描述符读取或向其写入数据。实现需要通过文件描述符表找到对应的文件对象，调用其 `read` 或 `write` 方法。对于磁盘文件，`read` 需要根据 inode 的索引定位数据块，将数据复制到用户缓冲区；`write` 需要在文件末尾追加或覆盖数据，必要时分配新的数据块。

### sys_close

```rust
pub fn sys_close(fd: usize) -> isize
```

关闭一个文件描述符。将进程 fd 表中对应位置设为 `None`，如果该文件对象没有其他引用者，其资源将被释放（Rust 的 `Arc` 引用计数会自动处理）。

### sys_linkat 和 sys_unlinkat

```rust
pub fn sys_linkat(old_dirfd: usize, old_path: &str,
                  new_dirfd: usize, new_path: &str, flags: usize) -> isize
pub fn sys_unlinkat(dirfd: usize, path: &str, flags: usize) -> isize
```

`linkat` 创建硬链接——在目录中创建一个新的目录项，指向已有文件的 inode。硬链接意味着两个路径名指向同一个 inode，对其中任何一个的修改都会反映到另一个上。实现时需要增加 inode 的 `nlink` 计数。

`unlinkat` 删除一个目录项（硬链接）。如果该 inode 的 `nlink` 计数降为零，且没有进程打开该文件，则释放 inode 及其所有数据块。

### sys_fstat

```rust
pub fn sys_fstat(fd: usize, st: &mut Stat) -> isize
```

获取文件的元信息。通过文件描述符找到对应的 inode，将设备号、inode 号、文件类型和硬链接数填入 `Stat` 结构体。

### sys_dup

```rust
pub fn sys_dup(fd: usize) -> isize
```

复制文件描述符。在进程的 fd 表中分配一个新的描述符编号，指向与原 fd 相同的文件对象。复制后两个 fd 共享同一个文件对象和偏移量。

### sys_pipe

```rust
pub fn sys_pipe(pipe: &mut [usize]) -> isize
```

创建管道。管道是一对相互连接的文件对象，写入一端的数据可以从另一端读出。`pipe[0]` 是管道的读端 fd，`pipe[1]` 是写端 fd。管道在父子进程间传递数据时非常有用。

## 测试用例分析

Ch6 的核心测试 `ch6_filetest_simple` 验证了最基本的文件操作：

```rust
let test_str = "Hello, world!";
let filea = "filea\0";
let fd = open(filea, OpenFlags::CREATE | OpenFlags::WRONLY);
assert!(fd > 0);
write(fd as usize, test_str.as_bytes());
close(fd as usize);

let fd = open(filea, OpenFlags::RDONLY);
assert!(fd > 0);
let mut buffer = [0u8; 100];
let read_len = read(fd as usize, &mut buffer) as usize;
close(fd as usize);

assert_eq!(test_str,
    core::str::from_utf8(&buffer[..read_len]).unwrap());
println!("file_test passed!");
```

测试首先以"创建 + 只写"模式打开文件 "filea"，写入 "Hello, world!"，关闭后再以只读模式重新打开，读取内容并比对。这个测试覆盖了文件创建、写入、关闭、重新打开和读取的完整生命周期。

## 块设备与 VirtIO

在 QEMU virt 平台上，磁盘通过 VirtIO Block 设备协议提供。VirtIO 是一种半虚拟化 I/O 标准，虚拟设备和驱动程序通过共享内存中的"虚拟队列（Virtqueue）"进行通信，避免了每次 I/O 操作都需要陷入 hypervisor 的开销。

VirtIO Block 设备驱动需要实现以下步骤：

1. 在设备发现阶段，扫描设备树（Device Tree）找到 VirtIO Block 设备的 MMIO 地址。
2. 初始化设备：协商功能位、分配和配置虚拟队列。
3. 提交读写请求：将请求描述符加入虚拟队列，通知设备处理。
4. 处理完成中断：设备完成 I/O 后触发中断，驱动从虚拟队列中回收已完成的描述符。

内核的 Makefile 中 QEMU 启动参数配置了块设备：

```makefile
QEMU_EXEC = qemu-system-riscv64 -machine virt \
    -kernel ${KERNEL} \
    -nographic \
    -smp 1 \
    -bios ../bootloader/rustsbi-qemu.bin \
    -drive file=$(FS_IMG),if=none,format=raw,id=x0 \
    -device virtio-blk-device,drive=x0,bus=virtio-mmio-bus.0
```

`-drive` 指定磁盘镜像文件，`-device virtio-blk-device` 将其作为 VirtIO 块设备暴露给虚拟机。内核的块设备驱动通过 MMIO 与该设备交互。

## 小结

本章从系统调用接口出发，自顶向下分析了文件 I/O 的完整路径。当前内核实现了基于 SBI 的简单控制台输出，用户态库已经定义了完整的文件操作接口。Ch6 实验要求在此基础上：

1. 实现 VirtIO 块设备驱动，使内核能够读写磁盘。
2. 集成 easy-fs 文件系统，支持从磁盘镜像中读取文件。
3. 在每个进程中维护文件描述符表，支持 `open`、`read`、`write`、`close` 等标准文件操作。
4. 实现硬链接（`link`/`unlink`）和文件元信息查询（`fstat`）。
5. 实现管道（`pipe`）和文件描述符复制（`dup`），为进程间通信提供基础设施。

这些功能的实现将内核从一个简单的任务加载器提升为一个具备基本文件管理能力的操作系统，能够像 Linux 一样通过统一的文件接口访问各种数据源。
