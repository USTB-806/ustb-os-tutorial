---
title: Makefile简介
description: Makefile 是一个用于自动化构建的工具，它通过定义规则来描述如何从源文件生成目标文件。
---

## 1.规则

每条规则由三部分组成分别是`目标(target)`,`依赖(depend)`,`命令(command)`

```makefile
# 语法格式：
target1，target2...: depend1 depend2...
	command1
	command2
	...
```

### **确定目标**

当你运行 `make` 命令时，`make` 需要明确知道它的目标是什么。目标可以是：

- **默认目标**：如果你没有指定目标，`make` 默认会尝试构建 Makefile 中第一个目标（也就是第一条规则定义的目标）。

- **显式指定的目标**：你可以通过命令行参数指定目标。例如：

  ```bash
  make clean
  ```

  这里，`clean` 就是显式指定的目标。

 **示例**

假设你有一个简单的 C 程序，包含两个文件：`main.c` 和 `utils.c`。Makefile 可能如下：

```makefile
# 定义目标文件
all: main

# 定义 main 目标
main: main.o utils.o
    gcc -o main main.o utils.o

# 定义 main.o 的生成规则
main.o: main.c
    gcc -c main.c

# 定义 utils.o 的生成规则
utils.o: utils.c
    gcc -c utils.c

# 清理生成的文件
clean:
    rm -f main main.o utils.o
```

### 递归解析

1. **确定最终目标**

你运行了 `make all`，`make` 首先确定最终目标是 `all`。

2. **解析 all 的规则**

`make` 查找 `all` 的规则：

```makefile
all: main
```

这表示 `all` 依赖于 `main`。因此，`make` 需要先生成 `main`。

3. **解析 main 的规则**

`make` 接下来查找 `main` 的规则：

```makefile
main: main.o utils.o
    gcc -o main main.o utils.o
```

这表示 `main` 依赖于 `main.o` 和 `utils.o`。因此，`make` 需要先生成 `main.o` 和 `utils.o`。

4. **递归解析 main.o 的规则**

`make` 查找 `main.o` 的规则：

```makefile
main.o: main.c
    gcc -c main.c
```

这表示 `main.o` 依赖于 `main.c`。`make` 会检查 `main.c` 是否存在：

- 如果 `main.c` 存在，`make` 会比较 `main.c` 和 `main.o` 的时间戳。

- 如果 `main.c` 比 `main.o` 新，或者 `main.o` 不存在，`make` 会执行命令：

  ```bash
  gcc -c main.c
  ```

  生成 `main.o`。

5. **递归解析 utils.o 的规则**

`make` 查找 `utils.o` 的规则：

```makefile
utils.o: utils.c
    gcc -c utils.c
```

这表示 `utils.o` 依赖于 `utils.c`。`make` 会检查 `utils.c` 是否存在：

- 如果 `utils.c` 存在，`make` 会比较 `utils.c` 和 `utils.o` 的时间戳。

- 如果 `utils.c` 比 `utils.o` 新，或者 `utils.o` 不存在，`make` 会执行命令：

  ```bash
  gcc -c utils.c
  ```

  生成 `utils.o`。

6. **生成 main**

一旦 `main.o` 和 `utils.o` 都被成功生成（或者确认是最新的），`make` 会回到 `main` 的规则：

```makefile
main: main.o utils.o
    gcc -o main main.o utils.o
```

`make` 会检查 `main.o` 和 `utils.o` 是否存在，并比较它们与 `main` 的时间戳：

- 如果 `main.o` 或 `utils.o` 比 `main` 新，或者 `main` 不存在，`make` 会执行命令：

  ```bash
  gcc -o main main.o utils.o
  ```

  生成 `main`。

7. **完成 all**

最后，`main` 被成功生成后，`make` 认为 `all` 的依赖已经满足，整个构建过程完成。

## 2.变量

Makefile 支持变量的使用，可以简化规则的编写。例如：

```makefile
CC = gcc
CFLAGS = -Wall -g

all: main

main: main.o utils.o
    $(CC) $(CFLAGS) -o main main.o utils.o

main.o: main.c
    $(CC) $(CFLAGS) -c main.c

utils.o: utils.c
    $(CC) $(CFLAGS) -c utils.c

clean:
    rm -f main main.o utils.o
```

- `CC` 是编译器变量。
- `CFLAGS` 是编译选项变量。

## 3.模式规则

模式规则是 Makefile 中非常强大的功能，它可以让你为一组文件定义通用的构建规则，而无需为每个文件单独编写规则。模式规则使用 `%` 作为通配符，`%` 可以匹配任意长度的字符串。

**基本语法**

```makefile
%.target: %.dependency
    command
```

- **%.target**：目标文件的模式，`%` 表示任意文件名。
- **%.dependency**：依赖文件的模式，`%` 表示与目标文件匹配的部分。
- **command**：执行的命令。

**示例**

假设你有多个 `.c` 文件需要编译成 `.o` 文件，可以使用模式规则：

```makefile
%.o: %.c
    $(CC) $(CFLAGS) -c $< -o $@
```

- **%.o**：表示所有以 `.o` 结尾的目标文件。
- **%.c**：表示所有以 `.c` 结尾的依赖文件。
- **$<**：自动变量，表示依赖列表中的第一个依赖文件（这里是 `.c` 文件）。
- **$@**：自动变量，表示目标文件（这里是 `.o` 文件）。

**工作原理**

当你运行 `make` 时，`make` 会根据目标文件的名称自动推导出依赖文件的名称。例如：

- 如果目标是 `main.o`，`make` 会查找 `main.c`，并执行命令：

  ```bash
  gcc -c main.c -o main.o
  ```

- 如果目标是 `utils.o`，`make` 会查找 `utils.c`，并执行命令：

  ```bash
  gcc -c utils.c -o utils.o
  ```

## 4.伪目标

伪目标是 Makefile 中的特殊目标，它们不对应实际的文件。伪目标通常用于定义一些特殊的任务，如 `clean` 或 `all`。伪目标的作用是避免与同名文件冲突。

**声明伪目标**

```makefile
.PHONY: clean all
```

- **.PHONY**：告诉 `make`，`clean` 和 `all` 是伪目标，即使存在同名文件，`make` 也会执行这些目标。

**示例**

```makefile
.PHONY: clean all

all: main

main: main.o utils.o
    $(CC) $(CFLAGS) -o main main.o utils.o

main.o: main.c
    $(CC) $(CFLAGS) -c main.c

utils.o: utils.c
    $(CC) $(CFLAGS) -c utils.c

clean:
    rm -f main main.o utils.o
```

- **all**：伪目标，用于构建最终的可执行文件 `main`。
- **clean**：伪目标，用于清理生成的文件。

**工作原理**

- 如果你运行 `make all`，`make` 会构建 `main`。
- 如果你运行 `make clean`，`make` 会删除所有生成的文件。
- 即使存在名为 `clean` 或 `all` 的文件，`make` 也会正确执行伪目标的规则。

**不定义 .PHONY 的潜在问题**

假设你没有定义 `.PHONY`，`make` 会将所有目标（包括 `all` 和 `clean`）都视为可能的文件名。

**make clean**：

- 如果当前目录下没有 `clean` 文件，`make` 会执行 `clean` 目标，删除文件。
- 如果当前目录下存在一个名为 `clean` 的文件，`make` 会认为 `clean` 已经是最新的，不会执行任何命令。

## 5.条件判断

Makefile 支持条件判断，这可以在不同情况下动态调整变量或规则。条件判断的语法如下：

**ifeq 和 ifneq**

```makefile
ifeq (arg1, arg2)
    commands
endif
```

- **ifeq**：如果 `arg1` 等于 `arg2`，则执行 `commands`。
- **ifneq**：如果 `arg1` 不等于 `arg2`，则执行 `commands`。

**条件判断可以嵌套，也可以使用 `else` 分支：**

```makefile
ifeq ($(CC), gcc)
    CFLAGS += -std=c99
else
    CFLAGS += -std=c11
endif
```

- 如果 `CC` 的值是 `gcc`，则会添加编译选项 `-std=c99`。

## **6.使用 Makefile**

在命令行中运行 `make` 命令时，`make` 会读取当前目录下的 Makefile 文件，并根据规则执行任务。例如：

- `make`：默认执行第一个目标。
- `make clean`：执行 `clean` 目标。
- `make main`：执行 `main` 目标。