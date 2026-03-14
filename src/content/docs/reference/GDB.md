---
title: GDB简介
---
## 零、 GDB学习网站

[RMS's gdb Tutorial](http://www.unknownroad.com/rtfm/gdbtut/gdbtoc.html)

[GDB online Debugger | Compiler - Code, Compile, Run, Debug online C, C++](https://www.onlinegdb.com/)



## 一、GDB 命令基础结构

### 命令缩写规则
GDB 支持命令缩写，只要输入的字符能唯一识别命令即可：
```gdb
(gdb) info breakpoints    # 完整命令
(gdb) i b                 # 常用缩写
(gdb) i break             # 也可以
```

### 命令补全
按 `Tab` 键自动补全：
```gdb
(gdb) break mai<Tab>      # 自动补全为 break main
(gdb) p va<Tab>           # 自动补全变量名
```

### 重复上条命令
直接按 `Enter` 键重复执行上一条命令（对 `step`, `next`, `continue` 等特别有用）

---

## 二、核心命令详解（按功能分类）

### 1. 程序启动与控制

| 命令     | 缩写 | 语法         | 说明                              |
| -------- | ---- | ------------ | --------------------------------- |
| `run`    | `r`  | `r [参数]`   | 启动程序                          |
| `start`  |      | `start`      | 停在 main 第一行（比 run 更友好） |
| `attach` |      | `attach PID` | 附加到运行中的进程                |
| `detach` |      | `detach`     | 分离，保留进程运行                |
| `kill`   | `k`  | `kill`       | 终止调试中的程序                  |
| `quit`   | `q`  | `q`          | 退出 GDB                          |

**高级用法：**
```gdb
# 带参数启动
(gdb) run arg1 arg2 < input.txt > output.txt

# 设置启动参数（下次 run 自动使用）
(gdb) set args arg1 arg2
(gdb) show args

# 指定环境变量
(gdb) set environment PATH=/usr/local/bin:$PATH
```

---

### 2. 断点管理（Breakpoint）

#### 基础断点
| 命令               | 缩写  | 语法                                    | 说明         |
| ------------------ | ----- | --------------------------------------- | ------------ |
| `break`            | `b`   | `b 函数名` / `b 行号` / `b 文件名:行号` | 设置断点     |
| `delete`           | `d`   | `d 编号` / `d`（全部）                  | 删除断点     |
| `disable`          | `dis` | `dis 编号`                              | 禁用断点     |
| `enable`           | `en`  | `en 编号`                               | 启用断点     |
| `info breakpoints` | `i b` |                                         | 查看所有断点 |
| `clear`            |       | `clear 行号`                            | 清除某行断点 |

**高级断点语法：**
```gdb
# 条件断点（最常用的高级特性）
(gdb) break 10 if i == 5
(gdb) break func if ptr != NULL
(gdb) break main.c:20 if x > 10 && y < 20

# 临时断点（只停一次）
(gdb) tbreak 15           # 简写 tb

# 忽略前 N 次
(gdb) ignore 1 10         # 断点1忽略前10次

# 断点命中时自动执行命令
(gdb) break 20
(gdb) commands 1          # 为断点1设置命令
> silent                  # 不显示断点信息
> print x
> continue                # 自动继续
> end

# 正则表达式设置断点
(gdb) rbreak ^foo         # 所有以 foo 开头的函数
(gdb) rbreak file.c:.     # file.c 中所有函数
```

---

### 3. 执行控制

| 命令       | 缩写  | 说明                     |
| ---------- | ----- | ------------------------ |
| `continue` | `c`   | 继续运行到下一个断点     |
| `step`     | `s`   | 单步进入（进入函数）     |
| `next`     | `n`   | 单步跳过（不进入函数）   |
| `finish`   | `fin` | 运行到当前函数返回       |
| `until`    | `u`   | 运行到指定行（跳出循环） |
| `advance`  | `adv` | 前进到指定位置           |
| `stepi`    | `si`  | 单条汇编指令（进入）     |
| `nexti`    | `ni`  | 单条汇编指令（跳过）     |

**高级用法：**
```gdb
# until 的妙用：跳出循环
(gdb) u 25                # 直接运行到第25行（跳出循环）

# 指定次数的单步
(gdb) step 5              # 执行5次 step

# 反向调试（需要先 record）
(gdb) record full
(gdb) reverse-step        # 反向单步
(gdb) reverse-continue    # 反向继续

# 调用函数
(gdb) call printf("x=%d\n", x)
(gdb) call malloc(1024)
```

---

### 4. 查看与打印（Inspection）

#### 基础打印
| 命令        | 缩写   | 语法             | 说明             |
| ----------- | ------ | ---------------- | ---------------- |
| `print`     | `p`    | `p 表达式`       | 打印表达式值     |
| `display`   | `disp` | `disp 表达式`    | 每次停下自动显示 |
| `undisplay` |        | `undisplay 编号` | 取消自动显示     |
| `x`         |        | `x/格式 地址`    | 检查内存         |

**print 高级语法：**
```gdb
# 打印数组
(gdb) p arr               # 打印整个数组（如果知道大小）
(gdb) p *arr@10           # 打印 arr 前10个元素
(gdb) p arr[2]@5          # 从 arr[2] 开始打印5个

# 打印结构体
(gdb) p struct_var        # 打印整个结构体
(gdb) p struct_var.field  # 打印特定字段
(gdb) p *ptr_struct       # 通过指针打印

# 指定输出格式
(gdb) p/x var             # 十六进制
(gdb) p/d var             # 十进制（有符号）
(gdb) p/u var             # 十进制（无符号）
(gdb) p/o var             # 八进制
(gdb) p/t var             # 二进制
(gdb) p/f var             # 浮点数
(gdb) p/c var             # 字符
(gdb) p/s var             # 字符串
(gdb) p/a var             # 地址

# 打印历史值
(gdb) p $1                # 打印之前的结果（$1 是历史编号）
(gdb) p $$                # 上次的值
(gdb) p $_->next          # 假设上次是链表节点，打印 next

# 修改变量
(gdb) set var x = 10
(gdb) set var ptr = (int*)malloc(100)
(gdb) set var arr[0] = 99
```

#### 内存检查（x 命令）
```gdb
# 语法：x/[数量][格式][单位] 地址
(gdb) x/10x $esp          # 查看栈顶10个4字节（十六进制）
(gdb) x/20bx arr          # 查看20个字节（十六进制）
(gdb) x/5i $pc            # 查看接下来5条汇编指令
(gdb) x/s ptr             # 查看字符串
(gdb) x/wx &var           # 查看变量地址的4字节

# 格式：x(十六进制), d(十进制), u(无符号), o(八进制), 
#       t(二进制), a(地址), i(指令), c(字符), s(字符串)
# 单位：b(字节), h(半字2字节), w(字4字节), g( giant 8字节)
```

---

### 5. 栈帧管理（Stack Frame）

| 命令          | 缩写 | 说明             |
| ------------- | ---- | ---------------- |
| `backtrace`   | `bt` | 查看调用栈       |
| `frame`       | `f`  | 切换到指定栈帧   |
| `up`          |      | 向上一层栈帧     |
| `down`        |      | 向下一层栈帧     |
| `info frame`  |      | 查看当前栈帧详情 |
| `info args`   |      | 查看函数参数     |
| `info locals` |      | 查看局部变量     |

**高级用法：**
```gdb
# 查看完整调用栈
(gdb) bt                  # 简要
(gdb) bt full             # 包含局部变量
(gdb) bt 10               # 只显示前10层
(gdb) bt -10              # 只显示后10层

# 切换栈帧
(gdb) f 2                 # 切换到第2层（0是最顶层）
(gdb) up 3                # 向上3层
(gdb) down                # 向下1层

# 在特定栈帧中执行命令
(gdb) f 2
(gdb) p local_var         # 查看第2层的局部变量
(gdb) info locals         # 查看第2层的所有局部变量
```

---

### 6. 线程调试

| 命令               | 缩写    | 说明               |
| ------------------ | ------- | ------------------ |
| `info threads`     | `i thr` | 查看所有线程       |
| `thread`           | `thr`   | 切换到指定线程     |
| `thread apply`     |         | 对所有线程执行命令 |
| `break ... thread` |         | 线程特定断点       |

**高级用法：**
```gdb
# 查看线程
(gdb) i thr
  Id   Target Id         Frame 
* 1    Thread 0x7f...    main () at test.c:10
  2    Thread 0x7f...    thread_func () at test.c:25
  3    Thread 0x7f...    thread_func () at test.c:25

# 切换线程
(gdb) thread 2

# 对所有线程执行命令
(gdb) thread apply all bt          # 查看所有线程的栈
(gdb) thread apply 1 2 3 p x       # 对线程1,2,3执行 print x

# 线程特定断点
(gdb) break 20 thread 2            # 只在线程2中生效
(gdb) break 20 thread 2 if x > 10  # 线程2的条件断点

# 设置线程锁（避免切换时混乱）
(gdb) set scheduler-locking on     # 只运行当前线程
(gdb) set scheduler-locking off    # 恢复所有线程
(gdb) set scheduler-locking step   # 单步时锁定，其他时候不锁定
```

---

## 三、高级功能与语法

### 1. 监视点（Watchpoint）

监视点比断点更强大，**在数据变化时触发**：

```gdb
# 软件监视点（变量变化时停止）
(gdb) watch var                    # 写时停止
(gdb) rwatch var                   # 读时停止  
(gdb) awatch var                   # 读写都停止

# 硬件监视点（更快，但数量有限）
(gdb) watch -l var                 # 强制使用硬件监视点

# 监视表达式
(gdb) watch ptr->field
(gdb) watch arr[5]
(gdb) watch (int*)0x601040         # 监视特定地址

# 条件监视点
(gdb) watch var if var > 100

# 查看监视点
(gdb) info watchpoints
```

---

### 2. 捕获点（Catchpoint）

捕获**事件**而非位置：

```gdb
# 捕获系统调用
(gdb) catch syscall open           # 捕获 open 系统调用
(gdb) catch syscall                # 捕获所有系统调用

# 捕获 C++ 异常
(gdb) catch throw                  # 抛出异常时停止
(gdb) catch catch                  # 捕获异常时停止
(gdb) catch exception MyException  # 特定异常

# 捕获加载/卸载库
(gdb) catch load                   # 加载动态库时
(gdb) catch unload                 # 卸载动态库时

# 捕获信号
(gdb) catch signal SIGSEGV         # 捕获段错误信号
(gdb) catch signal all             # 捕获所有信号
```

---

### 3. 反向调试（Reverse Debugging）

**时光倒流调试** - 需要 `record` 支持：

```gdb
# 开始记录
(gdb) record full                  # 完整记录（内存+寄存器）
(gdb) record btrace                # 仅记录控制流（更快）

# 反向执行
(gdb) reverse-continue    # 反向继续（倒跑到上一个断点）
(gdb) reverse-step        # 反向单步
(gdb) reverse-next        # 反向单步跳过
(gdb) reverse-finish      # 反向运行到函数开始

# 检查记录状态
(gdb) info record         # 查看记录状态
(gdb) record stop         # 停止记录
```

**使用场景：** 崩溃后想知道"怎么走到这里的"

---

### 4. 脚本与自动化

#### 命令脚本
```bash
# 创建 gdb_script.txt
set pagination off
break main
run
bt
info locals
continue
quit
```

```bash
# 执行脚本
gdb -x gdb_script.txt ./program

# 或在 GDB 内
(gdb) source gdb_script.txt
```

#### GDB 内置脚本语言（类似 Python 但简化）
```gdb
# 定义命令
(gdb) define print_array
> set $i = 0
> while $i < $arg0
  > p arr[$i]
  > set $i = $i + 1
  > end
> end

# 使用
(gdb) print_array 10      # 打印 arr[0] 到 arr[9]

# 带参数的自定义命令
(gdb) define print_hex
> p/x $arg0
> end

(gdb) print_hex var
```

#### Python 脚本（现代 GDB 支持）
```python
# 在 GDB 中使用 Python
(gdb) python print("Hello from Python")

# 定义 Python 命令
(gdb) python
import gdb

class PrintNodes(gdb.Command):
    def __init__(self):
        super().__init__("print-nodes", gdb.COMMAND_DATA)
    
    def invoke(self, arg, from_tty):
        args = gdb.string_to_argv(arg)
        node = gdb.parse_and_eval(args[0])
        count = int(args[1])
        for i in range(count):
            print(f"Node {i}: {node}")
            node = node['next']
            
PrintNodes()
end

# 使用
(gdb) print-nodes head 10
```

---

### 5. 核心转储（Core Dump）分析

```gdb
# 分析 core 文件
gdb ./program core
gdb ./program core.1234

# 常用命令
(gdb) bt full               # 查看崩溃时的完整栈
(gdb) info registers        # 查看寄存器状态
(gdb) x/20x $sp             # 查看栈内容
(gdb) info proc mappings    # 查看内存映射
(gdb) p $_siginfo           # 查看信号信息

# 生成 core 文件
(gdb) generate-core-file    # 在调试时生成 core
```

---

### 6. 多进程调试

```gdb
# 默认行为：调试父进程，子进程自由运行
(gdb) set follow-fork-mode parent   # 默认
(gdb) set follow-fork-mode child    # 调试子进程
(gdb) set follow-fork-mode ask      # 询问

# 同时调试多个进程
(gdb) set detach-on-fork off        # fork 时不分离
(gdb) info inferiors                # 查看所有进程
(gdb) inferior 2                    # 切换到进程2
(gdb) detach inferior 1             # 分离进程1
```

---

### 7. 远程调试

```bash
# 目标机器（被调试端）
gdbserver :1234 ./program           # 监听端口1234
gdbserver :1234 --attach PID        # 附加到运行中的进程

# 调试机器（GDB端）
gdb ./program
(gdb) target remote 192.168.1.100:1234

# 远程断点、单步等命令与本地相同
```

---

### 8. TUI（文本用户界面）模式

```bash
# 启动时进入
gdb -tui ./program

# 或 GDB 内切换
(gdb) layout src          # 显示源代码
(gdb) layout asm          # 显示汇编
(gdb) layout split        # 源码+汇编
(gdb) layout regs         # 显示寄存器

# 窗口控制
(gdb) focus cmd           # 聚焦命令窗口
(gdb) focus src           # 聚焦源码窗口
Ctrl+X+A                  # 切换 TUI 模式
Ctrl+X+2                  # 切换布局
Ctrl+L                    # 刷新屏幕
```

---

## 四、快速参考卡

```
┌─────────────────────────────────────────────────────────┐
│  启动：gdb ./prog │ gdb -tui ./prog │ gdb ./prog core  │
├─────────────────────────────────────────────────────────┤
│  运行：r(un) │ s(tart) │ c(ontinue) │ k(ill) │ q(uit)  │
├─────────────────────────────────────────────────────────┤
│  断点：b(reak) │ d(elete) │ dis(able) │ en(able) │ i b │
│        tb │ b 10 if x>5 │ watch var │ catch throw       │
├─────────────────────────────────────────────────────────┤
│  执行：s(tep) │ n(ext) │ fin(ish) │ u(ntil) │ adv     │
│        si │ ni │ reverse-step │ record full            │
├─────────────────────────────────────────────────────────┤
│  查看：p(rint) │ p/x │ p *arr@10 │ x/10x addr │ disp   │
│        bt │ f │ up │ down │ i locals │ i args │ i reg  │
├─────────────────────────────────────────────────────────┤
│  线程：i thr │ thr 2 │ thr apply all bt │ b 20 thr 1   │
├─────────────────────────────────────────────────────────┤
│  内存：x/10wx $esp │ x/s $rdi │ info proc mappings     │
└─────────────────────────────────────────────────────────┘
```

---

需要我针对某个特定高级功能（如 Python 脚本编写、内核调试、或嵌入式远程调试）深入展开吗？