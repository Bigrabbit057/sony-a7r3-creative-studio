# 第三方来源与许可

## Recipe Lab

- 项目：https://github.com/voxivoid/recipe-lab-sony-pmca
- 原作者/维护者：voxivoid 及上游贡献者，以原项目记录为准。
- 许可：GNU GPL version 3，全文保留在 `LICENSE` 与 `assets/upstream/LICENSE`。
- 使用的配方源：`Recipes.java`，提交 `fc746fb286f98cab96ba2a2cb04187747fc763ae`（v1.9.0 配方快照）。
- 源文件 SHA-256：`a18c23e347cacc933e210a33465c47eb47c4f4918dece29bebbfac040e300646`。
- 原文件保留在 `assets/upstream/Recipes.java`。改动包括：转换为 JSON、加入简称/来源/备注、标注本程序不支持的参数。并非原作者提供或认证的 A7R III 移植版本。

分发本工具及改编配方时保留许可、版权与来源，按 GPL 提供相应源码。Windows 包内附与此版一致的源码压缩包。项目自身新增代码也按 GPL-3.0-only 提供。

## Sony-PMCA-RE

- 项目：https://github.com/ma1co/Sony-PMCA-RE
- Copyright (c) 2015 ma1co，MIT License。
- USB 服务模式及属性访问代码保留在 `vendor/pmca`，原许可在 `vendor/LICENSE.txt`。
- 沿用本地研究所用源码快照，未宣称为上游最新发布版。`THIRD_PARTY_LICENSES` / 分发校验清单记录实际构建内容。
- 本项目修改 `vendor/pmca/usb/sony.py` 的服务协议序号递增：按无符号 16 位回绕，避免长会话在第 65,536 次请求时打包溢出。保留响应序号匹配检查；边界已经通过参考机身的只读请求验证。

## Python 与打包依赖

Python 标准库及运行时采用 PSF 相关许可；PyInstaller 采用 GPL 与其 bootloader 分发例外。USB、ASN.1、密码、Windows 接口等依赖保留各自许可。构建程序从本机安装包元数据收集实际版本及可用许可到 `THIRD_PARTY_LICENSES`，不改变原许可。

Keystone（汇编）和 Unicorn（仿真）只用于开发时生成/验证本项目 ARM 程序，**不包含在 Windows 成品运行库中**。开发者安装它们时适用各自上游许可。不要把模板自检或离线仿真视为实机测试。

系统相机驱动由用户单独安装。本包不重分发 libusb-win32 系统驱动，也不代表 Zadig 或相关驱动作者提供支持。

## Sony 材料边界

发布材料包含逆向研究得出的地址、哈希、属性编号，以及识别/回退所必需的少量指令和预期字节。**不包含完整 Sony 固件、系统分区、系统快照、中文资源库或个人相机备份**。首次安装使用目标机身自己的数据核对和备份。

社区配方中的胶片和相机名称属于各自权利人；名称不表示授权、认证或相同成像。
