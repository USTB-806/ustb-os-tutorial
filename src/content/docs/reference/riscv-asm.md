---
title: RISC-V 汇编语言语法简介
---

### 1. 基本语法格式

RISC-V 汇编指令的基本格式是：
```asm
<操作码> <目标寄存器>, <源操作数1>, <源操作数2>
```

**示例：**
```asm
add x1, x2, x3    # x1 = x2 + x3
lw x4, 0(x5)      # 从地址 x5+0 加载一个字到 x4
```

### 2. 寄存器命名

RISC-V 有 32 个通用寄存器，有两种命名方式：

**编号命名：** `x0` - `x31`
**ABI 命名（推荐）：** 具有特定含义的名称

```asm
# 常用寄存器对照
x0  = zero  # 零寄存器，恒为0
x1  = ra    # 返回地址寄存器
x2  = sp    # 栈指针
x3  = gp    # 全局指针
x4  = tp    # 线程指针
x5  = t0    # 临时寄存器
x6  = t1    # 临时寄存器
...
x10 = a0    # 函数参数/返回值
x11 = a1    # 函数参数
...
x18 = s2    # 保存寄存器
```

### 3. 指令分类详解

#### 3.1 算术运算指令
```asm
add  x1, x2, x3    # 加法：x1 = x2 + x3
sub  x1, x2, x3    # 减法：x1 = x2 - x3
addi x1, x2, 10    # 加立即数：x1 = x2 + 10
mul  x1, x2, x3    # 乘法：x1 = x2 * x3
div  x1, x2, x3    # 除法：x1 = x2 / x3
```

#### 3.2 逻辑运算指令
```asm
and  x1, x2, x3    # 与：x1 = x2 & x3
or   x1, x2, x3    # 或：x1 = x2 | x3
xor  x1, x2, x3    # 异或：x1 = x2 ^ x3
andi x1, x2, 0xFF  # 与立即数：x1 = x2 & 0xFF
```

#### 3.3 移位指令
```asm
sll  x1, x2, x3    # 逻辑左移：x1 = x2 << x3
srl  x1, x2, x3    # 逻辑右移：x1 = x2 >> x3
slli x1, x2, 5     # 立即数逻辑左移：x1 = x2 << 5
```

#### 3.4 内存访问指令
```asm
lw x1, 0(x2)       # 加载字（32位）：x1 = *(x2 + 0)
lh x1, 0(x2)       # 加载半字（16位）
lb x1, 0(x2)       # 加载字节（8位）
sw x1, 0(x2)       # 存储字：*(x2 + 0) = x1
sh x1, 0(x2)       # 存储半字
sb x1, 0(x2)       # 存储字节
```

#### 3.5 分支跳转指令
```asm
beq  x1, x2, label  # 相等跳转：if (x1 == x2) goto label
bne  x1, x2, label  # 不等跳转：if (x1 != x2) goto label
blt  x1, x2, label  # 小于跳转：if (x1 < x2) goto label
bge  x1, x2, label  # 大于等于跳转：if (x1 >= x2) goto label
jal  ra, label      # 跳转并链接：ra = PC+4, goto label
jalr ra, 0(x1)      # 寄存器跳转并链接
```

#### 3.6 CSR 原子读写指令（RMW）

```asm
csrrw  rd, csr, rs1      # 读 csr 旧值到 rd，再把 rs1 整值写入 csr
csrrs  rd, csr, rs1      # 读 csr 到 rd，并把 rs1 为 1 的位置 1
csrrc  rd, csr, rs1      # 读 csr 到 rd，并把 rs1 为 1 的位清 0
csrrwi rd, csr, imm      # 读 csr 到 rd，再把 5 位立即数写入 csr
csrrsi rd, csr, imm      # 读 csr 到 rd，并把 imm 为 1 的位置 1
csrrci rd, csr, imm      # 读 csr 到 rd，并把 imm 为 1 的位清 0
```

> #### **什么是RMW？**
>
> **RISC-V 硬件规定：所有 CSR 指令都必须“先读后改”**，顺手把读出的旧值放到 `rd`——**这是指令格式的一部分，不是可选步骤**。
>
> - 原子性由“读-改-写 整包在一条硬件微操作”保证，**与是否把旧值交给软件无关**。
> - 即使你把 `rd` 写成 `x0`（丢弃旧值），硬件**照样先读一次 CSR**，只是最后不往寄存器文件里写回而已。
>
> 所以“读旧 CSR”是 **免费附赠的副作用**，不是原子性的前提；
> 软件想不想用它都行，但硬件一定会读——这就是 RISC-V 的“RMW”编码规则。

### 4. 伪指令

RISC-V 提供了许多伪指令，让编程更方便：

```asm
li x1, 100         		# 加载立即数：x1 = 100
mv x1, x2          		# 寄存器传送：x1 = x2
nop                		# 空操作
ret                		# 返回：jalr x0, 0(x1)
j label           		# 无条件跳转：jal x0, label
call function      		# 调用函数
csrr   rd, csr           # 仅读：csrrs rd, csr, x0
csrw   csr, rs1          # 仅写：csrrw x0, csr, rs1
csrs   csr, rs1          # 位置 1：csrrs x0, csr, rs1
csrc   csr, rs1          # 位清 0：csrrc x0, csr, rs1
```

### 5. 完整示例程序

下面是一个完整的 RISC-V 汇编程序示例，计算两个数的和：

```asm
.section .text
.globl _start

_start:
    # 设置栈指针
    li sp, 0x80000000
    
    # 加载数据
    li a0, 25          # 第一个数
    li a1, 37          # 第二个数
    
    # 调用加法函数
    call add_numbers
    
    # 结果在 a0 中，这里可以添加更多处理
    # 为了简单，我们在这里停止
    
    # 退出程序（具体取决于运行环境）
    li a7, 93          # 系统调用号：退出
    li a0, 0           # 退出状态
    ecall              # 执行系统调用

# 加法函数：a0 + a1，结果返回在 a0 中
add_numbers:
    add a0, a0, a1     # a0 = a0 + a1
    ret                # 返回
```

### 6. 常用汇编器指令

```asm
.section .text      # 代码段
.section .data      # 数据段
.globl symbol       # 声明全局符号
.word value         # 定义字数据
.byte value         # 定义字节数据
.string "text"      # 定义字符串
.align 4            # 4字节对齐
```



