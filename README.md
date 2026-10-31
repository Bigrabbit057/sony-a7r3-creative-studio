# Creative Studio — A7R III 实验版

Windows 10/11 x64 本地小工具：浏览、编辑 Recipe Lab 配方，分配六个创意风格自定义槽，写入参数、简称和会学习手动调整的 AWB 偏移。

**版本：0.1.4-experimental。Windows 日常更新已通过参考机身写入及两遍读回；菜单验收状态见 [VERIFICATION.md](VERIFICATION.md)。新机首次安装尚未验证。**

本工具基本复刻 Recipe Lab 的配方编辑和选用方式，面向没有原厂 App 平台的 A7R III 实现六槽写入、名称显示和白平衡联动。**不同相机即使使用同一套参数，成像效果也可能明显不同；配方仅供参考，需要按机型、光线和个人喜好微调。** 它不是跨机型色彩校准工具，也不保证复现 A6000、富士或真实胶片的效果。

## 快速开始

1. 完整解压 `CreativeStudio-Windows-x64-0.1.4.zip`，不要单独移动 EXE。双击 `CreativeStudio.exe`，会打开本机浏览器界面，不需要联网或安装 Python。
2. 想先熟悉操作，双击 `Demo.cmd`。演示模式只使用模拟数据，完全不访问 USB。
3. 浏览「配方库」，修改风格、对比度、饱和度、锐度、白平衡和简称；保存或另存。
4. 在「我的六槽」选择六个配方，保存安排。
5. 已安装相机组件的机身，在「相机连接」点击「连接并读取」。第一次建议先点「保留相机当前六槽」，再导出 JSON，保留机身上已学习的偏移。
6. 点击「预览本次写入」，核对六槽原值与新值，确认后写入。等待明确显示会话已退出，再拔 USB。切换到其他槽，再选回目标槽验证。
7. 关闭窗口不等于关闭后台程序；使用页面底部「退出工具」。会话进行中不允许主动退出。

已安装相机组件的机身，**只使用日常写入，不需要再次安装**。首次使用的具体检查见 [TOMORROW.md](TOMORROW.md)。

## 支持边界

| 项目 | 当前状态 |
|---|---|
| 相机 | 仅原版 ILCE-7RM3，原厂固件 3.10，区域 CX62001_CN2 |
| 其他机身 | A7R IIIA / A7 III / 其他固件、区域和内存布局均拒绝；同型号另一台也尚未实测 |
| 配方库 | 77 条源配方，其中 64 条符合当前写入条件 |
| 六槽参数 | 风格、对比度、饱和度、锐度、AWB 的 A/B 与 G/M 偏移 |
| 名称 | 每槽独立，最多 8 个英文、数字、空格或 `+_-`；原图标不改 |
| 手动记忆 | 在机身改变 AWB 偏移后，现有联动程序学习；可读回电脑 |
| 白平衡范围 | A/B −7～+7，步长 0.5；G/M −7～+7，步长 0.25 |
| 固定色温、图片效果 | 可以查看、编辑、导出，但本版拒绝写入这些配方 |
| 曝光补偿、DRO | 仅保存参考值，须在相机手动设置，不随槽位联动 |
| PP | 日常写入会关闭 PP；保留各 PP 槽内部参数 |
| 启动 | 沿用此前已在这台相机验证的持久入口；新版分发安装流程待实机验收 |

同一参数不代表不同机型得到相同色彩。这里迁移的是配方参数，不是富士原厂胶片引擎或 3D LUT；A6000 与 A7R III 的成像差异不会被自动校准。

AWB 正数 A/B 表示琥珀 A、负数表示蓝 B；正数 G/M 表示绿 G、负数表示洋红 M。例：B2 / M0.5 在编辑器输入 −2 / −0.5。

## USB 准备

相机开机、海量存储器模式，使用数据线，电脑只连接一台索尼相机。沿用研究期间的 **libusb-win32** 驱动。只对核对过的相机设备使用 Zadig，不能给读卡器、键鼠或其他磁盘替换驱动。

这台实测设备的通常状态为 `ILCE-7RM3 / 054C:0BFF`，服务状态为 `Sony USB Device / 054C:0336`；二者分别需要对应驱动。工具不会自动安装系统驱动。更换驱动会使相机存储卡不再作为常规盘符出现；传照片可用读卡器。

如果工具提示未找到相机，先检查模式、数据线和驱动，保留错误日志，不要反复点击写入。另一型号即使使用相同服务 USB ID，也不表示兼容。

## 首次实验安装

「实验安装」是独立入口，**会修改相机原厂启动文件，可能导致无法启动**。先读 [RISK_NOTICE.md](RISK_NOTICE.md)。界面有五次顺序确认，最后需输入完整确认短语；后台也检查顺序、有效期、机身身份和原值，不能只靠前端勾选绕过。

安装只接受完全匹配的文件哈希、进程布局、启动脚本内容和底层文件身份。先把这台机身的 `/usr` 分区读取两遍并比较，在电脑保存一份完整镜像及校验记录；随后安装组件、校验、受限修改启动注释位置、恢复只读。不会自动重启，也不会向原始分区写整包镜像。首次备份可能需要较长时间，电脑至少预留 900MB 空间，建议 2GB。

已有备份**不能保证救砖**。USB 服务不可用时没有经过验证的独立恢复通道。出现错误请保留相机连接、日志和备份，不要强行重试、升级固件或套用其他人的镜像。本版不提供盲目的一键刷回功能。

## 数据与退出

- 普通数据：`%LOCALAPPDATA%\A7R3-Creative-Studio\data`；演示数据在同级 `demo`。
- `library.json`：电脑配方库；`backups`：每次读取、写入或安装的记录；`last-error.json`：最近错误；`console.log`：运行输出。
- 配方 JSON 可以导出和导入；导入会替换电脑库，写相机仍需另行确认。
- 工具仅监听 `127.0.0.1`，随机访问令牌保护接口，无遥测、无上传功能。公开日志前仍须检查机身标识、个人文件路径和完整备份。
- 不要同时运行研究脚本、PMCA 工具或另一份写入器；应用内有互斥保护，无法约束外部工具。

## 开源与重建

Recipe Lab 是开源项目，本工具使用其 GPL-3.0 配方表并保留原文件、来源和许可。详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。本项目按 GPL-3.0-only 提供，软件分发包内附匹配的 `CreativeStudio-source.zip`，尚未发布到 GitHub。

从源码目录使用 Python 3.11+（本次构建用 3.12）创建虚拟环境，安装 `requirements-dev.txt` 后：

```powershell
python -m unittest discover -s tests -v
python rebuild_runtime.py
python generate_templates.py
python app.py --self-check selfcheck.json
python app.py --demo
python build_windows.py
```

`rebuild_runtime.py` 从附带汇编重新生成并逐字比较每个 ARM 程序及名称钩子；`generate_templates.py` 只使用合成数据生成模板并做故障注入。汇编、仿真工具仅供开发，不随成品加载。无需 Sony 固件镜像即可运行这些检查。

发布源码不含完整原厂固件、相机分区备份、个人设置快照、照片或 USB 日志。技术概览见 [TECHNICAL.md](TECHNICAL.md)，测试说明见 [VERIFICATION.md](VERIFICATION.md)。

## English overview

An experimental Windows companion for the original **Sony A7R III (ILCE-7RM3), stock firmware 3.10, CX62001_CN2**. It adapts Recipe Lab's recipe-editing workflow to six built-in Creative Style slots, with short custom names, AWB-offset following, and learning of manual AWB adjustments.

**Matching settings do not imply matching images across cameras.** These recipes are starting points, not calibrated reproductions of A6000, Fujifilm, or film rendering. Fixed-Kelvin and picture-effect recipes are view-only in this release; exposure compensation and DRO remain manual reference settings.

Only one reference camera has been tested. First installation modifies a factory startup file and can brick the camera. There is no guaranteed independent recovery path. Other bodies, firmware, regions, or unknown layouts are rejected; do not bypass the guards. See the risk notice and verification record before using real hardware. Demo mode does not access USB.

Recipe Lab recipes are used under GPL-3.0, with original sources and attribution included. Sony-PMCA-RE is used under its MIT license. This is an independent community experiment, not an official port or a Sony/Fujifilm/Kodak product.
