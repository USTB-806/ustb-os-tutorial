---
title: 环境配置
description: 环境配置指导.
---

工欲善其事, 必先利其器. 在开始操作系统之前, 你应该先完成相关环境的配置, 这是十分重要的.

为了减轻同学们配环境的负担, 我们决定使用 Docker 环境。Docker 是一个开源的容器化平台, 可以帮助开发者将应用程序及其依赖项打包到一个独立的容器中, 并在任何环境中运行。

:::note
我们建议使用 vscode + docker 进行实验。

如果你已经拥有这两个工具, 则可以跳过这一步，直接开始实验。
:::

首先，我们建议你下载轻量级代码编辑器 vscode, 并安装 docker 插件。
- [vscode 下载与安装](../vscode/)



其次，我们需要你的操作系统支持 Docker ，如果你之前没有安装过 Docker ，请先参考 [**Docker 环境配置**](../docker/) 章节进行 Docker 的配置。 如果你之前有使用过 Docker ，则可以跳过这一步。

:::tip 
验证你的操作系统支持 Docker: 
#### windows
按 win + R 打开运行窗口，输入 `cmd` 打开命令行窗口。
```shell
C:\Users\noonering>docker --version
Docker version 28.1.1, build 4eba377
```
#### linux
打开终端, 输入以下命令验证 Docker 是否安装成功:
```shell
$ docker --version
Docker version 28.1.1, build 4eba377
```
#### macos
打开终端, 输入以下命令验证 Docker 是否安装成功:
```shell
$ docker --version
Docker version 28.1.1, build 4eba377
```
如果输出了 Docker 的版本信息, 则说明你的操作系统支持 Docker 。
> 注意：我们建议你安装和教程相同的版本的 Docker 或 更高的版本，因为我们还没有测试过旧版本是否兼容。
:::

完成上述配置之后就可以开始实验了。

