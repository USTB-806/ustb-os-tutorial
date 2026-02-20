---
title: 前置知识
description: 在开始实验前应当知道的内容
---

尽管我们并不是完全让同学们从 `cargo new` 开始编写内核，而是提供了一套基础代码，同学们可以基于代码修改，但操作系统并不是一个容易的工程，在此之前你可能需要先回忆起你曾经学习过的这些内容。

## 如何调试

在系统开发中，遇到问题基本有如下几种方法：

- 硬看：基本没甚么用.
- 查看日志：通过添加 `log!` 来检查当前的执行状态，是最常用的方法.
- 使用 GDB/LLDB：非常有用，几乎可以完全检测内核的执行状态，但是相对复杂.

除此之外，使用 IDE 自带的调试或者查看 QEMU 的日志，也是可行的.

## Linux 基础与 Git 使用

你需要熟悉 Linux 的基本使用方法. 同时，尽管由于评测系统的限制，我们不能直接让大家提供 Git 仓库地址来评测你的 OS 内核，但墙裂建议大家使用 Git 来管理自己的代码.

想象你不使用 Git 进行代码管理，文件夹下存放了各个版本你修改过的代码，使用 `os-kernel-20260220` 这种命名方式来管理版本，这极其不方便. 过一段时间，你可能也不知道你究竟修改了哪些代码，于是只能再瞪眼看究竟改了哪些地方.

一个更具体地情况可能是，你今天发狠了、忘情了，熬了一个大夜，拉下评测机信心满满的测了一发，但是发现一个测例都没过.

但还好你使用了 Git 来管理你的代码，你可以轻易回到之前的版本状态.

回忆你曾经使用过的功能：
- `git init`
- `git add`
- `git commit -m "message"`
- `git push`

在本次实验中，你可能还需要掌握这些：

- `git checkout <chx>` 切换到分支名为 `<chx>` 的分支
- `git checkout -b <chx>` 新建一个分支名为 `<chx>`，并切换到它
- `git reset` 重置当前代码的状态，可以是哈希值也可以是 `HEAD~n`，同时可以带上参数 `--hard` 或 `--soft`

当同学们对此有需求时可以网上查阅资料或者询问 LLM.

一些参考的资料：
- [Learn Git Branching](https://learngitbranching.js.org/)
- [【USTB】计算机科学教育缺失的学期 (2025-2026) - 第一讲 - Linux基础与Git使用 - 索思科技协会](https://www.bilibili.com/video/BV1GwxNzmEB2/) 与其配套[讲义](https://www.yookoishi.com/blog/source-ms1)

## 编写 Makefile

Makefile 在小学期时大家已经接触过，这并不是本次实验的重点. 但在某些情况下，同学们可能需要自己编写 Makefile 来更好优化自己的工作流.

可以参考如下资料：
- [Makefile 简介](../reference/makefile)
- [跟我一起写 Makefile](https://seisman.github.io/how-to-write-makefile/introduction.html)
- [GNU make](https://www.gnu.org/software/make/manual/make.html)