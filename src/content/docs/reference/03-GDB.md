---
title: GDB简介
---
## 学习资源

- [GDB Tutorial (RMS)](http://www.unknownroad.com/rtfm/gdbtut/gdbtoc.html)
- [Online GDB](https://www.onlinegdb.com/)

## 基础交互

- **缩写支持**：GDB 命令支持缩写，只要唯一即可。例如 `i b` 等同于 `info breakpoints`。
- **自动补全**：使用 `Tab` 键补全命令或符号。
- **重复命令**：直接按 `Enter` 键可重复上一条命令（在单步调试 `step`/`next` 时非常有用）。

## 核心命令速查

### 1. 启动与控制

| 命令 | 简写 | 说明 |
| :--- | :--- | :--- |
| `target remote :1234` | | **连接 QEMU 等远程调试目标** (OS 开发常用) |
| `file <path>` | | 加载可执行文件符号表 |
| `run` | `r` | 启动程序 (本地用户态调试) |
| `quit` | `q` | 退出 GDB |
| `kill` | `k` | 终止当前程序 |
| `Ctrl + C` | | 中断正在运行的程序 |

### 2. 断点管理 (Breakpoint)

| 命令 | 简写 | 示例与说明 |
| :--- | :--- | :--- |
| `break` | `b` | `b main` (函数名) <br> `b *0x80200000` (地址) <br> `b file.c:10` (文件名:行号) |
| `delete` | `d` | `d` (删除所有) <br> `d 1` (删除编号为1的断点) |
| `info breakpoints` | `i b` | 查看所有断点状态 |
| `disable`/`enable` | | `dis 1` / `en 1` (临时禁用/启用断点) |
| **条件断点** | | `b 10 if i==5` (仅当 i 等于 5 时触发) |

### 3. 执行控制 (Execution)

| 命令 | 简写 | 说明 |
| :--- | :--- | :--- |
| `continue` | `c` | 继续运行直到下一个断点 |
| `step` | `s` | **源码级**单步进入 (跟进函数调用) |
| `next` | `n` | **源码级**单步跳过 (不进入函数) |
| `stepi` | `si` | **汇编级**单步进入 (OS 调试常用) |
| `nexti` | `ni` | **汇编级**单步跳过 |
| `finish` | | 执行直到当前函数返回 |
| `until` | `u` | 执行直到行号增加 (常用于跳出循环) |

### 4. 信息查看 (Inspection)

| 命令 | 简写 | 说明 |
| :--- | :--- | :--- |
| `print` | `p` | `p var` (打印变量) <br> `p/x var` (十六进制) <br> `p *ptr` (解引用) |
| `info registers` | `i r` | 查看通用寄存器 |
| `backtrace` | `bt` | 查看函数调用栈 |
| `frame` | `f` | `f 1` 切换到上一层栈帧查看变量 |
| `info locals` | | 查看当前栈帧的局部变量 |
| `list` | `l` | 查看源代码上下文 |
| `display` | | `display $pc` (每次停下时自动打印 PC 寄存器) |

### 5. 内存检查 (`x` 命令)

最强大的内存查看命令，格式：`x/[数量][格式][单位] <地址>`

*   **格式**：`x` (十六进制), `d` (十进制), `i` (指令), `s` (字符串)
*   **单位**：`b` (1字节), `h` (2字节), `w` (4字节), `g` (8字节)

**常用组合：**

```gdb
x/10i $pc        # 反汇编查看 PC 后的 10 条指令
x/20gx $sp       # 查看栈顶 20 个 8字节(g) 的十六进制(x) 数据
x/s 0x80001000   # 查看指定地址的字符串
x/wx &count      # 查看变量 count 的原始内存(4字节 hex)
```

## 高级技巧

### TUI 模式 (图形化界面)
GDB 自带的基于文本的图形界面，非常适合查看代码与寄存器状态。
*   **启动/切换**：启动时加 `-tui` 参数，或在 GDB 中按 `Ctrl + X + A`。
*   **常用布局**：
    *   `layout split`：同时显示源代码和汇编代码。
    *   `layout regs`：显示寄存器窗口。
*   **刷新**：如果屏幕显示错乱，按 `Ctrl + L` 刷新。

### 监视点 (Watchpoint)
当不知道变量在哪里被修改时使用。
*   `watch var`：当 `var` 的值发生变化时暂停。
*   `watch *0x80210000`：当内存地址 `0x80210000` 的内容变化时暂停。

### 常用配置
可以直接在 GDB 中输入，或写入 `~/.gdbinit` 文件：
```gdb
set print pretty on      # 结构体打印更美观
set history save on      # 保存命令历史
set pagination off       # 很多输出时不暂停
```