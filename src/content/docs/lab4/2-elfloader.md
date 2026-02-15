---
title: 地址空间（下）
description: lab4
---

# Ch4 地址空间（下）：ELF 加载与用户地址空间构建

上篇文档介绍了内核堆分配器和地址空间的理论基础。本篇将聚焦于**用户程序的加载过程**，包括 ELF 文件的解析、应用程序在物理内存中的布局以及用户栈的初始化。这些机制共同构成了为用户程序构建可运行地址空间的完整流程。

## 应用程序的构建与嵌入

在本内核的设计中，用户程序的二进制文件在编译期被直接嵌入到内核映像的 `.data` 段中。这一过程由构建脚本 `build.rs` 自动完成。`build.rs` 扫描 `../user/build/` 目录下的所有应用二进制文件，为每一个应用生成对应的汇编指令，将其通过 `.incbin` 伪指令包含进内核：

```rust
// kernel/build.rs（节选）
fn insert_app_data() -> Result<()> {
    let mut f = File::create("src/link_app.S").unwrap();
    let mut apps: Vec<_> = read_dir(TARGET_PATH)
        .unwrap()
        .into_iter()
        .filter_map(|dir_entry| { /* 过滤出应用文件 */ })
        .collect();
    apps.sort();

    writeln!(f, r#"
    .align 3
    .section .data
    .global _num_app
_num_app:
    .quad {}"#, apps.len())?;

    for i in 0..apps.len() {
        writeln!(f, r#"    .quad app_{}_start"#, i)?;
    }
    writeln!(f, r#"    .quad app_{}_end"#, apps.len() - 1)?;

    for (idx, app) in apps.iter().enumerate() {
        writeln!(f, r#"
    .section .data
    .global app_{0}_start
    .global app_{0}_end
    .align 3
app_{0}_start:
    .incbin "{1}"
app_{0}_end:"#, idx, app_path)?;
    }
    Ok(())
}
```

生成的 `link_app.S` 文件定义了全局符号 `_num_app`（应用总数），以及每个应用数据的起始和终止地址 `app_i_start` / `app_i_end`。这些符号在内核运行时被 `app_loader` 模块引用，用于定位各个应用的 ELF 数据。这种将用户程序嵌入内核映像的方式避免了对文件系统的依赖，在操作系统的早期阶段非常实用。

## 应用加载器（app_loader）

`kernel/src/app_loader.rs` 是应用加载的核心模块。它承担两项任务：一是在系统初始化时将所有应用的 ELF 数据复制到各自的内存区域；二是为每个应用创建初始的 Trap 上下文。

### 内核栈与用户栈的定义

每个应用需要两个独立的栈：**内核栈**（处理系统调用和异常时使用）和**用户栈**（应用在用户态运行时使用）。它们在 `app_loader.rs` 中被定义为静态数组：

```rust
#[repr(align(4096))]
#[derive(Copy, Clone)]
struct KernelStack {
    data: [u8; KERNEL_STACK_SIZE],  // 8KB
}

#[repr(align(4096))]
#[derive(Copy, Clone)]
struct UserStack {
    data: [u8; USER_STACK_SIZE],    // 4KB
}

static mut KERNEL_STACK: [KernelStack; MAX_APP_NUM] = [KernelStack {
    data: [0; KERNEL_STACK_SIZE],
}; MAX_APP_NUM];

static mut USER_STACK: [UserStack; MAX_APP_NUM] = [UserStack {
    data: [0; USER_STACK_SIZE],
}; MAX_APP_NUM];
```

`#[repr(align(4096))]` 确保每个栈按 4KB（一页）对齐，这是硬件页表管理的要求。`KERNEL_STACK_SIZE` 为 8KB（两页），`USER_STACK_SIZE` 为 4KB（一页）。系统最多支持 `MAX_APP_NUM`（16 个）并发应用。

`KernelStack` 实现了两个关键方法：

```rust
impl KernelStack {
    fn get_sp(&self) -> usize {
        self.data.as_ptr() as usize + KERNEL_STACK_SIZE
    }
    pub fn push_context(&self, trap_cx: TrapContext) -> usize {
        let trap_cx_ptr = (self.get_sp() - core::mem::size_of::<TrapContext>())
            as *mut TrapContext;
        unsafe { *trap_cx_ptr = trap_cx; }
        trap_cx_ptr as usize
    }
}
```

`get_sp()` 返回栈顶地址（栈从高地址向低地址增长，所以栈起始于数组末尾）。`push_context()` 在内核栈顶部压入一个 `TrapContext` 结构体，并返回压入后的栈指针。这个位置将成为第一次进入该任务时 `__restore` 所使用的上下文地址。

### 加载应用到内存

`load_apps()` 函数在系统启动时被 `main()` 调用，负责将嵌入在内核映像中的所有应用二进制数据复制到各自的运行地址：

```rust
pub fn load_apps() {
    extern "C" { fn _num_app(); }
    let num_app_ptr = _num_app as usize as *const usize;
    let num_app = get_num_app();
    let app_start = unsafe {
        core::slice::from_raw_parts(num_app_ptr.add(1), num_app + 1)
    };
    for i in 0..num_app {
        let base_i = get_base_i(i);
        // 先清零目标区域
        (base_i..base_i + APP_SIZE_LIMIT)
            .for_each(|addr| unsafe { (addr as *mut u8).write_volatile(0) });
        // 将 ELF 数据从内核 .data 段复制到应用运行地址
        let src = unsafe {
            core::slice::from_raw_parts(
                app_start[i] as *const u8,
                app_start[i + 1] - app_start[i]
            )
        };
        let dst = unsafe {
            core::slice::from_raw_parts_mut(base_i as *mut u8, src.len())
        };
        dst.copy_from_slice(src);
    }
    unsafe { asm!("fence.i"); }
}
```

`get_base_i(i)` 计算第 i 个应用的加载基地址，公式为 `APP_BASE_ADDRESS + i * APP_SIZE_LIMIT`，即从 `0x80400000` 开始、每个应用占据 128KB 的空间。加载过程先将目标区域清零，再将 ELF 数据完整复制过去。最后的 `fence.i` 指令刷新指令缓存（I-Cache），因为新写入的数据将被作为代码执行，而 RISC-V 的指令缓存不会自动与数据缓存保持一致。

### 初始化应用上下文

`init_app_cx()` 函数为指定的应用创建初始 Trap 上下文并将其压入该应用的内核栈：

```rust
pub fn init_app_cx(app_id: usize) -> usize {
    let user_stack_top = unsafe { USER_STACK[app_id].get_sp() };
    unsafe {
        KERNEL_STACK[app_id].push_context(
            TrapContext::app_init_context(get_base_i(app_id), user_stack_top)
        )
    }
}
```

该函数传入应用的加载基地址（作为入口点）和用户栈栈顶指针，通过 `TrapContext::app_init_context` 构造初始上下文。返回值是内核栈上 `TrapContext` 的地址，任务管理器利用该地址在 `__restore` 时恢复该应用的状态。

## Trap 上下文与特权级切换

用户进程在运行过程中，每次陷入内核（无论是系统调用、异常还是中断），硬件和软件都需要保存和恢复完整的 CPU 状态。这些状态由 `TrapContext` 结构体表示，位于 `kernel/src/trap/context.rs`：

```rust
#[repr(C)]
#[derive(Debug, Copy, Clone)]
pub struct TrapContext {
    pub x: [usize; 32],      // 32 个通用寄存器
    pub sstatus: Sstatus,     // S 模式状态寄存器
    pub sepc: usize,          // S 模式异常程序计数器
}
```

`x[0]` 到 `x[31]` 保存了 RISC-V 的全部 32 个通用寄存器（其中 `x[0]` 恒为零，`x[2]` 是栈指针 `sp`）。`sstatus` 记录了陷入前的处理器状态，关键的字段包括 `SPP`（前一特权级，0 表示用户态，1 表示 S 态）和 `SPIE`（中断使能位）。`sepc` 记录了陷入时的程序计数器，`sret` 指令执行后将跳转到该地址继续执行。

应用初始上下文的构造通过 `app_init_context` 完成：

```rust
impl TrapContext {
    pub fn app_init_context(entry: usize, sp: usize) -> Self {
        let mut sstatus = sstatus::read();
        unsafe {
            let sstatus_ptr = &mut sstatus as *mut Sstatus as *mut usize;
            *sstatus_ptr &= !(1 << 8); // 清除 SPP 位 → 返回用户态
            *sstatus_ptr |= 1 << 5;    // 设置 SPIE 位 → 启用中断
        }
        let mut cx = Self {
            x: [0; 32],
            sstatus,
            sepc: entry,
        };
        cx.set_sp(sp);
        cx
    }
}
```

这个函数做了三件关键的事情：首先，将 `sstatus.SPP` 清零，表示当执行 `sret` 返回时应进入用户态（U 模式）；其次，设置 `sstatus.SPIE` 位，确保返回用户态后中断被启用（这对时钟中断驱动的抢占式调度至关重要）；最后，`sepc` 被设为应用入口地址，`sp` 被设为用户栈栈顶。当 `__restore` 从内核栈上恢复这个上下文并执行 `sret` 时，CPU 将跳转到用户程序的入口点，栈指针指向用户栈，处于用户态，中断启用——应用便正式开始运行。

## ELF 加载器

本内核提供了一个完整的 ELF 文件加载器，位于 `kernel/src/loader/` 目录下。虽然当前阶段的 `app_loader` 采用的是直接将整个二进制文件复制到固定地址的方式，但 ELF 加载器为后续支持虚拟内存后的按段加载做好了准备。

### ELF 文件格式简介

ELF（Executable and Linkable Format）是 Unix/Linux 系统上标准的可执行文件格式。一个 ELF 文件包含以下关键部分：

- **ELF Header**：描述文件的基本属性，如目标架构（此处为 RISC-V 64 位）、入口地址和程序头表的位置。
- **Program Header Table**：列出文件中各个**段（Segment）**的信息，包括虚拟地址、文件偏移、大小和权限。类型为 `LOAD` 的段需要被加载到内存。
- **Section Header Table**：列出各个**节（Section）**的信息，如 `.text`、`.data`、`.bss` 等，主要用于链接和调试。

ELF 加载器 `ElfLoader` 使用 `xmas-elf` crate 解析 ELF 文件：

```rust
// kernel/src/loader/mod.rs
pub struct ElfLoader<'a> {
    pub elf: ElfFile<'a>,
}

impl<'a> ElfLoader<'a> {
    pub fn new(elf_data: &'a [u8]) -> Result<Self, &'static str> {
        let elf = ElfFile::new(elf_data).map_err(|_| "Invalid ELF")?;
        if elf.header.pt1.class() != header::Class::SixtyFour {
            return Err("32-bit ELF is not supported on the riscv64");
        }
        match elf.header.pt2.machine().as_machine() {
            header::Machine::RISC_V => {}
            _ => return Err("invalid ELF arch"),
        };
        Ok(Self { elf })
    }
}
```

构造函数进行了两项安全检查：确认 ELF 文件是 64 位格式、目标架构是 RISC-V。这避免了加载不兼容二进制文件导致的未定义行为。

### 段加载

`load_segments` 方法遍历 ELF 文件的所有程序头，将类型为 `LOAD` 的段复制到内存中对应的虚拟地址处：

```rust
pub fn load_segments(&self, memory_token: usize) -> Result<(), &'static str> {
    for ph in self.elf.program_iter() {
        if ph.get_type().map_err(|_| "Invalid Segment Type")? != Type::Load {
            continue;
        }
        let vaddr = ph.virtual_addr() as usize;
        let mem_size = ph.mem_size() as usize;
        let file_size = ph.file_size() as usize;
        let offset = ph.offset() as usize;

        let data = &self.elf.input[offset..offset + file_size];
        let buffers = translated_byte_buffer(memory_token, vaddr as *const u8, mem_size);

        let mut current_offset = 0;
        for buffer in buffers {
            let buffer_len = buffer.len();
            if current_offset < file_size {
                let copy_len = core::cmp::min(
                    file_size - current_offset, buffer_len
                );
                buffer[..copy_len].copy_from_slice(
                    &data[current_offset..current_offset + copy_len]
                );
            }
            if current_offset + buffer_len > file_size {
                let start_zero = if current_offset < file_size {
                    file_size - current_offset
                } else { 0 };
                buffer[start_zero..].fill(0);
            }
            current_offset += buffer_len;
        }
    }
    Ok(())
}
```

一个 `LOAD` 段在 ELF 文件中的大小（`file_size`）可能小于在内存中的大小（`mem_size`），差值部分即是 BSS 区域（未初始化数据），需要清零。代码先将文件中的数据复制到对应的虚拟地址，再将超出文件数据的部分填充为零。`translated_byte_buffer` 在这里被用于处理可能的跨页虚拟地址翻译。

### 用户栈初始化

用户程序启动时，需要一个按照特定格式初始化的栈，其中包含命令行参数（argc/argv）、环境变量和辅助向量（Auxiliary Vector）。这个初始栈的布局遵循 Linux/ELF 标准，从栈顶（低地址）向高地址依次排列。

`init_info.rs` 中的 `InitInfo` 结构体封装了需要放置在用户栈上的所有信息：

```rust
pub struct InitInfo {
    pub args: Vec<String>,                  // 命令行参数
    pub envs: Vec<String>,                  // 环境变量
    pub auxv: BTreeMap<u8, usize>,          // 辅助向量
}
```

辅助向量（Auxiliary Vector）是 Linux 内核在加载 ELF 程序时传递给用户空间的一组键值对，包含与程序加载相关的元信息。在本内核中设置了以下辅助项：

- `AT_PHDR`：程序头表在内存中的地址
- `AT_PHENT`：每个程序头表项的大小
- `AT_PHNUM`：程序头表项的数量
- `AT_RANDOM`：指向栈上 16 字节"随机"数据的指针
- `AT_PAGESZ`：系统的页大小

`serialize` 方法将这些信息按照标准的 ELF 栈布局序列化到一个 `InitStack` 中：

```rust
pub fn serialize(&self, stack_top: usize) -> InitStack {
    let mut writer = InitStack::new(stack_top);
    let random_pos = writer.sp;
    // 环境变量字符串
    let envs: Vec<_> = self.envs.iter()
        .map(|item| writer.push_str(item.as_str())).collect();
    // 命令行参数字符串
    let argv: Vec<_> = self.args.iter()
        .map(|item| writer.push_str(item.as_str())).collect();
    // 辅助向量 (key-value 对)
    writer.push_slice(&[null::<u8>(), null::<u8>()]);
    for (&type_, &value) in self.auxv.iter() {
        match type_ {
            AT_RANDOM => writer.push_slice(&[type_ as usize, random_pos]),
            _ => writer.push_slice(&[type_ as usize, value]),
        };
    }
    // 环境变量指针数组
    writer.push_slice(&[null::<u8>()]);
    writer.push_slice(envs.as_slice());
    // 命令行参数指针数组
    writer.push_slice(&[null::<u8>()]);
    writer.push_slice(argv.as_slice());
    // argc
    writer.push_slice(&[argv.len()]);
    writer
}
```

最终栈上的布局（从低地址到高地址）为：

```
┌─────────────────────┐ ← sp (栈顶，低地址)
│      argc           │
├─────────────────────┤
│    argv[0] 指针     │
│    argv[1] 指针     │
│       ...           │
│       NULL          │
├─────────────────────┤
│    envp[0] 指针     │
│       ...           │
│       NULL          │
├─────────────────────┤
│   auxv 键值对       │
│       ...           │
│    AT_NULL (结束)    │
├─────────────────────┤
│  argv 字符串数据     │
│  envp 字符串数据     │
│  随机数据 (16B)      │
└─────────────────────┘ ← 原始栈顶（高地址）
```

`InitStack` 结构体（位于 `init_stack.rs`）封装了向栈中推入数据的操作。它维护一个从高地址向低地址增长的栈指针和底层的 `Vec<u8>` 缓冲区：

```rust
pub struct InitStack {
    pub sp: usize,          // 当前栈顶（低地址方向增长）
    pub buttom: usize,      // 栈底（高地址）
    pub data: Vec<u8>,      // 已序列化的数据
}

impl InitStack {
    pub fn push_slice<T: Copy>(&mut self, vs: &[T]) {
        self.sp -= vs.len() * size_of::<T>();
        self.sp -= self.sp % align_of::<T>();  // 对齐
        let offset = self.data.len() - (self.buttom - self.sp);
        unsafe {
            core::slice::from_raw_parts_mut(
                self.data.as_mut_ptr().add(offset) as *mut T,
                vs.len()
            ).copy_from_slice(vs);
        }
    }

    pub fn push_str(&mut self, s: &str) -> usize {
        self.push_slice(&[b'\0']);
        self.push_slice(s.as_bytes());
        self.sp
    }
}
```

每次 `push_slice` 时，栈指针先向低地址方向移动相应字节数，再进行内存对齐，然后将数据复制到缓冲区中的对应位置。`push_str` 将字符串以 C 风格（末尾追加 `\0`）压入栈中，并返回字符串在栈上的起始地址（即指针值）。

## 用户程序的入口

在用户侧，`user/rust/src/lib.rs` 中定义了用户程序的真正入口 `_start`：

```rust
#[no_mangle]
#[link_section = ".text.entry"]
pub extern "C" fn _start(argc: usize, argv: usize) -> ! {
    clear_bss();
    unsafe {
        HEAP.lock().init(HEAP_SPACE.as_ptr() as usize, USER_HEAP_SIZE);
    }
    let mut v: Vec<&'static str> = Vec::new();
    for i in 0..argc {
        let str_start = unsafe {
            ((argv + i * core::mem::size_of::<usize>()) as *const usize)
                .read_volatile()
        };
        let len = (0usize..)
            .find(|i| unsafe { ((str_start + *i) as *const u8).read_volatile() == 0 })
            .unwrap();
        v.push(core::str::from_utf8(unsafe {
            core::slice::from_raw_parts(str_start as *const u8, len)
        }).unwrap());
    }
    exit(main(argc, v.as_slice()));
}
```

`_start` 被链接到 `.text.entry` 节，确保它位于用户程序代码段的起始位置。它首先清零 BSS 段、初始化用户堆，然后从栈上解析出 `argc` 和 `argv` 数组，构造出 Rust 的字符串切片数组传递给用户编写的 `main` 函数。`main` 返回后，调用 `exit` 系统调用终止进程。

## 小结

本章的地址空间实现涵盖了从内核堆分配器到用户程序完整运行环境构建的全过程。内核堆通过伙伴系统管理，为内核自身的动态数据结构提供支持。应用加载器将嵌入内核映像中的 ELF 二进制文件复制到物理内存的指定区域，并通过精心构造的 `TrapContext` 和 `sret` 指令实现从内核态到用户态的首次跳转。ELF 加载器解析程序段并按照 Linux 标准初始化用户栈，为用户程序提供参数和辅助信息。

在后续的实验中，这些组件将进一步扩展：当启用虚拟内存后，`translated_byte_buffer` 将真正地查询页表进行地址翻译；`mmap`/`munmap`/`sbrk` 系统调用将允许用户程序动态管理自己的虚拟地址空间；每个进程将拥有独立的页表，实现真正的内存隔离。
