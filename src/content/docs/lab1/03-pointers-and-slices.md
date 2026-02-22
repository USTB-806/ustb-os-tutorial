---
title: 指针与切片
description: Intro to pointers and slices
---

Rust 的安全保障建立在借用检查和类型系统之上. 然而，操作系统内核必须直接与硬件对话，诸如读写内存映射寄存器 (MMIO)、修改页表项、切换进程栈等. 从语言角度来说，这些操作是不安全的，因为这些往往意味着对于裸指针或者说对内存的直接操作.

`unsafe` 并不意味着代码是危险的，它意味着编译器无法自动验证其安全性.

## 处理裸指针

在 Rust 中，引用 `&T` 和 `&mut T` 是被编译器严格监管的. 而在 OS 底层，我们经常拿到的是一个纯粹的数字，比如 `0x8020_0000` 作为某个特定作用的地址，这就需要裸指针 `*const T` 和 `*mut T`.

它们本质上就是 C 语言的指针：
- 无视借用规则，你可以同时拥有指向同一地址的 `*const` 和 `*mut` 指针，也即别名是允许的.
- 无生命周期，编译器不跟踪它指向的数据活多久.
- 无 Drop，它只是一个地址，作用域结束时不会触发任何析构函数.

对于裸指针的解引用是 `unsafe` 的. 

```rust
let serial_port = 0x1000_1000 as *mut u8;

unsafe {
    // 写入 0xFF，硬件会将其解释为指令或数据
    *serial_port = 0xFF; 
}
```

```rust
let mut num = 5;
let r1 = &num as *const i32;
let r2 = &mut num as *mut i32;

unsafe {
    println!("r1 point to: {}", *r1);
    *r2 = 10;
}
```

物理地址通常以 `usize` 形式传递. 你需要习惯将 `usize` 强制转换为裸指针，然后操作内存.

## 理解切片

Rust 的切片 `&[T]` 是系统编程中强大的抽象. 它不仅仅是一个指针，它是一个**胖指针 (Fat Pointer)**. 胖指针是一个携带了额外元数据 (Metadata) 的指针.

普通的指针，如 `&i32` 或 `Box<i32>` 在 64 位机上只是一个 8 字节的地址. 而切片引用 `&[T]` 是一个 16 字节的结构体：

- ptr (8 bytes): 指向数据的起始内存地址.
- len (8 bytes): 元素个数.

`ptr + len * size_of<T>` 构成了内存边界.

## `from_raw_parts`

[`core::slice::from_raw_parts`](https://doc.rust-lang.org/core/slice/fn.from_raw_parts.html) 允许将任意的**物理地址**转换为符合 Rust 语义的安全切片.

```rust
use std::slice;

// manifest a slice for a single element
let x = 42;
let ptr = &x as *const _;
let slice = unsafe { slice::from_raw_parts(ptr, 1) };
assert_eq!(slice[0], 42);
```

假设 OS 启动时探测到一块物理内存 `0x8000_0000`，长度 4KB.

```rust
use core::slice;

let start_addr: usize = 0x8000_0000;
let size: usize = 4096; // 4KB

unsafe {
    let buffer: &mut [u8] = slice::from_raw_parts_mut(
        start_addr as *mut u8,
        size
    );

    // e.g. operate on physical memory
    buffer[0] = 0xAA;
    buffer.fill(0);
    // buffer[5000] = 1; // Panic!
}
```

`from_raw_parts` 要求 `data` 必须非空，对于读取 `len * size_of::<T>()` 个字节有效，并且必须正确对齐. 详见于[Safety](https://doc.rust-lang.org/core/slice/fn.from_raw_parts.html#safety).

## `'static`

在实现内存管理模块时，经常看到这种类型：

```rust
pub fn translate_addr(...) -> Vec<&'static mut [u8]>
```

这里的 `'static` 并不意味着数据永久存在.

在 unsafe 语境下，`'static` 往往被用作一种无界生命周期 ([Unbounded Lifetime](https://doc.rust-lang.org/nomicon/unbounded-lifetimes.html)).

物理页帧的生命周期是由操作系统的分配算法管理的，编译器根本无法推导. 当我们无法用常规生命周期描述一段内存时，我们通过 `unsafe` 将其强转为 `'static`. 所以这意味着我们会手动管理这个内存的使用和释放.

但风险在于，如果你回收了物理页帧，但还保留着这个 `'static` 切片并试图写入，可能会导致 Use-After-Free 的问题.

## 指针运算 offset, add, sub

在解析 ELF 格式或遍历页表项时，我们需要手动计算地址. 

Rust 提供了专门的方法处理指针的运算. 注意指针加减是按**类型大小**跳跃的.

```rust
let base = 0x1000 as *mut u32;          // u32 占 4 字节
unsafe {
    let next = base.add(1);             // 地址增加 4 字节 (1 * sizeof(u32)) 
    assert_eq!(next as usize, 0x1004);

    let byte_ptr = base as *mut u8;
    let next_byte = byte_ptr.add(1);    // 按字节偏移
    assert_eq!(next_byte as usize, 0x1001);
}
```