---
title: Docker 环境配置
description: 环境配置指导.
---


:::note
如果想要详细了解更多关于Docker的内容可以参考[Docker 官方文档](https://docs.docker.com/).

同时也建议去看b站视频[40分钟的Docker实战攻略，一期视频精通Docker](https://www.bilibili.com/video/BV1THKyzBER6/?share_source=copy_web&vd_source=f5cc4fbf0b97583045564a1d258b698b)
:::
## Docker 下载与安装
 ### Windows 11

 ### Linux
以下是命令的所有过程，我们已经在ubuntu 22.04 上验证成功。
```bash
#安装前先卸载操作系统默认安装的docker，
sudo apt-get remove docker docker-engine docker.io containerd runc

#安装必要支持
sudo apt install apt-transport-https ca-certificates curl software-properties-common gnupg lsb-release

# 阿里源（推荐使用阿里的gpg KEY）
curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

#阿里apt源
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://mirrors.aliyun.com/docker-ce/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

#更新源
sudo apt update
sudo apt-get update

#安装最新版本的Docker
sudo apt install docker-ce docker-ce-cli containerd.io
#等待安装完成

#查看Docker版本
sudo docker version

#查看Docker运行状态
sudo systemctl status docker

```


 ### MacOs


