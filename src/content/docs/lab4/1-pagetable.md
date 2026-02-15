---
title: 地址空间（上）
description: lab4
---

# Ch4 地址空间（上）：内存管理基础与内核堆

在前面的章节中，内核运行在物理地址空间中，应用程序被直接加载至固定的物理地址。这种方式虽然简单，但存在严重的安全隐患——应用程序可以随意读写内核数据乃至修改其他应用的内存。为了实现进程间的**内存隔离**，操作系统需要引入**虚拟地址空间**的概念，并借助处理器硬件提供的页表机制来完成虚拟地址到物理地址的翻译。本章将围绕地址空间的实现展开，从内核堆分配器的初始化、物理内存的管理，逐步深入到页表映射和虚拟地址翻译等核心功能。

## 虚拟内存的理论基础

现代操作系统普遍采用**分页（Paging）**机制来管理内存。其核心思想是将虚拟地址空间和物理地址空间划分为等大的**页（Page）**和**页帧（Frame）**，通常大小为 4KB（即 4096 字节）。当 CPU 执行指令访问某个虚拟地址时，MMU（内存管理单元）会根据当前进程的**页表（Page Table）**，将虚拟地址翻译为物理地址。如果页表中找不到对应的映射关系，硬件将触发**缺页异常（Page Fault）**，陷入内核进行处理。

RISC-V 架构在 64 位模式下支持 Sv39 和 Sv48 等多级页表方案。本内核采用的是 **Sv39** 模式，使用三级页表结构，虚拟地址的有效位宽为 39 位，可寻址 512GB 的虚拟地址空间。Sv39 虚拟地址由以下几部分组成：

- **[38:30]** 一级页表索引（VPN[2]），9 位
- **[29:21]** 二级页表索引（VPN[1]），9 位
- **[20:12]** 三级页表索引（VPN[0]），9 位
- **[11:0]** 页内偏移（Offset），12 位

每一级页表包含 512 个页表项（PTE），每个 PTE 占 8 字节，恰好占满一个 4KB 的物理页。三级页表形成树状结构，由 `satp` CSR 中保存的根页表物理页号指向最顶层的页表页。

## 内核常量配置

在了解具体实现之前，有必要先认识内核中与内存管理相关的常量定义。这些常量在 `kernel/src/config.rs` 中集中配置：

```rust
// kernel/src/config.rs
pub const PAGE_SIZE: usize = 4096;
pub const PAGE_SIZE_BITS: usize = 12;

pub const USER_STACK_SIZE: usize = 4096;
pub const KERNEL_STACK_SIZE: usize = 4096 * 2;
pub const KERNEL_HEAP_SIZE: usize = 0x20000;
pub const MAX_APP_NUM: usize = 16;
pub const APP_BASE_ADDRESS: usize = 0x80400000;
pub const APP_SIZE_LIMIT: usize = 0x20000;
pub const CLOCK_FREQ: usize = 12500000;
pub const MEMORY_END: usize = 0x88000000;
```

`PAGE_SIZE` 定义了页的大小为 4096 字节，与 RISC-V Sv39 一致。`KERNEL_HEAP_SIZE` 为内核堆分配了 128KB 的空间，这是内核在运行期间动态分配内存（如创建 `Vec`、`BTreeMap` 等数据结构）所使用的区域。`APP_BASE_ADDRESS` 是应用程序加载的起始物理地址，当前阶段的内核将多个应用连续放置于该地址之后，每个应用最多占据 `APP_SIZE_LIMIT`（128KB）的空间。`MEMORY_END` 标识了物理内存的终止地址，从内核末尾到该地址之间的区域将由物理页帧分配器管理。

## 内核堆初始化

操作系统内核本身也需要动态内存分配。例如，任务管理模块中的系统调用追踪信息使用了 `BTreeMap`，ELF 加载器需要 `Vec` 来保存段信息。Rust 标准的 `alloc` crate 提供了 `Box`、`Vec`、`BTreeMap` 等堆上数据结构，但需要开发者提供一个全局的内存分配器。在本内核中，内存管理模块 `mm` 的核心职责之一就是初始化这个内核堆分配器。

内核堆的实现位于 `kernel/src/mm/mod.rs`，采用了 `buddy_system_allocator` crate 提供的伙伴系统分配器：

```rust
// kernel/src/mm/mod.rs
use buddy_system_allocator::LockedHeap;
use crate::config::KERNEL_HEAP_SIZE;

const HEAP_ORDER: usize = 32;

#[global_allocator]
static HEAP_ALLOCATOR: LockedHeap<HEAP_ORDER> = LockedHeap::empty();

static mut HEAP_SPACE: [u8; KERNEL_HEAP_SIZE] = [0; KERNEL_HEAP_SIZE];

pub fn init() {
    unsafe {
        HEAP_ALLOCATOR.lock().init(
            HEAP_SPACE.as_ptr() as usize,
            KERNEL_HEAP_SIZE
        );
    }
}
```

`#[global_allocator]` 属性将 `HEAP_ALLOCATOR` 标记为 Rust 运行时使用的全局分配器。`LockedHeap` 是自带自旋锁的伙伴系统分配器，泛型参数 `HEAP_ORDER` 为 32，代表伙伴系统内部维护的空闲链表层数。`HEAP_SPACE` 是一个位于 BSS 段中的静态数组，大小为 `KERNEL_HEAP_SIZE`（128KB），充当内核堆的后备存储。

**伙伴系统（Buddy System）**是一种经典的内存分配算法。它将可用内存按 2 的幂次进行分层管理，当需要分配 n 字节内存时，找到能容纳该大小的最小的 2^k 块。如果当前层没有空闲块，则从更高层分裂一个大块为两个"伙伴"。当内存释放时，检查其伙伴是否也处于空闲状态，若是则合并为更大的块。这种策略能有效减少外部碎片，且分配和释放的时间复杂度均为 O(log n)。

`init()` 函数在内核启动时被调用。此后，内核中所有使用 `alloc` crate 的动态分配操作（如 `Vec::new()`、`Box::new()` 等）都将通过伙伴系统从 `HEAP_SPACE` 中分配内存。如果堆空间耗尽，将触发 `handle_alloc_error` 导致内核 panic：

```rust
#[alloc_error_handler]
pub fn handle_alloc_error(layout: core::alloc::Layout) -> ! {
    panic!("Heap allocation error, layout = {:?}", layout);
}
```

## 地址翻译辅助函数

在支持虚拟内存的操作系统中，用户态的指针携带的是虚拟地址，内核需要将其翻译为物理地址才能访问对应的数据。`mm` 模块提供了 `translated_byte_buffer` 函数来完成这项工作：

```rust
pub fn translated_byte_buffer(
    token: usize, ptr: *const u8, len: usize
) -> Vec<&'static mut [u8]> {
    let mut buffers = Vec::new();
    unsafe {
        buffers.push(core::slice::from_raw_parts_mut(
            ptr as *mut u8, len
        ));
    }
    buffers
}
```

当前实现中，该函数直接将用户态指针视为物理地址使用，这是因为目前内核尚未启用页表（即使用恒等映射）。在后续的实验中，当内核真正启用虚拟内存后，该函数需要根据 `token`（即 `satp` 寄存器的值，包含根页表的物理页号）逐页查询页表，将虚拟地址翻译为物理地址。由于虚拟地址连续的区域在物理上可能分布在不同的页帧中，因此返回值是一个 `Vec`，其中每个元素对应一个物理页上的数据切片。

这个函数在系统调用实现中被大量使用。例如 `sys_write` 需要访问用户传入的缓冲区数据，`sys_get_time` 需要向用户空间写入时间信息，ELF 加载器需要将程序段复制到用户空间——这些场景都依赖 `translated_byte_buffer` 来完成跨地址空间的数据传输。

## 内核堆的正确性验证

`mm` 模块中还包含一个用于验证堆分配器正确性的测试函数 `heap_test`。该函数通过分配 `Box` 和 `Vec` 对象，并验证它们的地址确实落在 BSS 段的范围内（因为 `HEAP_SPACE` 被声明为静态变量，位于 BSS 段），来确认堆分配的正确性：

```rust
pub fn heap_test() {
    use alloc::boxed::Box;
    use alloc::vec::Vec;
    extern "C" {
        fn sbss();
        fn ebss();
    }
    let bss_range = sbss as usize..ebss as usize;
    let a = Box::new(5);
    assert_eq!(*a, 5);
    assert!(bss_range.contains(&(a.as_ref() as *const _ as usize)));
    drop(a);
    let mut v: Vec<usize> = Vec::new();
    for i in 0..500 {
        v.push(i);
    }
    for (i, val) in v.iter().take(500).enumerate() {
        assert_eq!(*val, i);
    }
    assert!(bss_range.contains(&(v.as_ptr() as usize)));
    drop(v);
    println!("heap_test passed!");
}
```

这个测试涉及的一个细节值得注意：`sbss` 和 `ebss` 是链接脚本 `linker.ld` 中导出的符号，标记了 BSS 段的起始和终止地址。通过检查分配的内存地址是否在 `[sbss, ebss)` 范围内，可以确认伙伴系统确实在预期的内存区域中工作。

## 内核内存布局

理解内核的内存布局有助于把握地址空间管理的全貌。链接脚本 `linker.ld` 定义了内核在内存中的排列方式：

```
OUTPUT_ARCH(riscv)
ENTRY(_start)
BASE_ADDRESS = 0x80200000;

SECTIONS
{
    . = BASE_ADDRESS;
    skernel = .;

    stext = .;
    .text : { *(.text.entry) *(.text .text.*) }

    . = ALIGN(4K);
    etext = .;
    srodata = .;
    .rodata : { *(.rodata .rodata.*) *(.srodata .srodata.*) }

    . = ALIGN(4K);
    erodata = .;
    sdata = .;
    .data : { *(.data .data.*) *(.sdata .sdata.*) }

    . = ALIGN(4K);
    edata = .;
    .bss : {
        *(.bss.stack)
        sbss = .;
        *(.bss .bss.*)  *(.sbss .sbss.*)
    }
    . = ALIGN(4K);
    ebss = .;
    ekernel = .;
}
```

内核从 `0x80200000` 开始加载（这是 QEMU virt 平台上 SBI 将控制权交给 Supervisor 的约定地址），依次排列 `.text`（代码段）、`.rodata`（只读数据段）、`.data`（可读写数据段）和 `.bss`（零初始化数据段）。每个段之间通过 `ALIGN(4K)` 保证按页对齐，这为后续实现页粒度的权限控制奠定了基础——代码段可以映射为"可执行"，只读数据段映射为"只读"，而数据段映射为"可读写"。

`ekernel` 符号标记了内核映像的末尾。在启用了虚拟内存的版本中，从 `ekernel` 到 `MEMORY_END`（`0x88000000`）之间的物理内存区域将由页帧分配器统一管理，用于分配页表页、用户程序的物理页帧等。

## Ch4 实验要求概述

在本章的实验中，学生需要实现以下核心功能来支持地址空间：

1. **实现 `sys_mmap` 和 `sys_munmap` 系统调用**：`sys_mmap` 在用户进程的虚拟地址空间中映射一段新的内存区域，`sys_munmap` 则解除映射。这两个系统调用是用户程序动态管理内存的基础接口。

2. **实现 `sys_sbrk` 系统调用**：该调用用于扩展或收缩用户程序的堆空间。调用者传入一个增量值（可为负），返回旧的堆顶地址。当增量为 0 时，仅返回当前堆顶地址而不做修改。

3. **完善页表和地址翻译机制**：在 `translated_byte_buffer` 等函数中正确实现基于页表的虚拟地址到物理地址的翻译，使内核能正确读写用户空间的数据。

这些功能的验证通过自动化测试完成。例如 `ch4_mmap0` 测试会调用 `mmap` 在 `0x10000000` 处映射一个页，然后逐字节写入并读回验证；`ch4b_sbrk` 测试会调用 `sbrk` 分配页面、写入数据、再释放，并验证访问已释放页面会触发页错误。

下一篇文档将深入分析 ELF 加载器与用户栈初始化的实现，讲解内核如何将用户程序从 ELF 二进制文件加载到内存并为其构建完整的运行环境。
