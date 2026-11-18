# 发布说明草稿（供 GitHub Release 使用）

## 标题建议

```
GarrisonFarm 通用加速版 v1.0 —— A卡/N卡/核显均可，截图提速30倍
```

## 简介（一句话）

在上游源码基础上做了显卡无关的 OCR 加速（DirectML）与 MuMu 原生截图加速，单局耗时明显下降，并修复了长跑崩溃和干员摆位问题。

## 正文

### 为什么做这个版本

现有的几个版本各有局限：

- 上游原版：CPU 推理，OCR 约 1.6 秒/次，慢
- 个人优化版：MuMu SDK 直连很快，但闭源打包，无法改逻辑
- GPU 加速版：只支持 NVIDIA（CUDA），A 卡用户用不了

所以做了这个**显卡无关**的版本：用 DirectML，AMD / Intel / 核显都能加速。

### 核心改进

**1. OCR 加速（A卡可用）**

三档自动回退，不用改代码：

```
DirectML（任意显卡） → CUDA（N卡） → CPU（兜底）
```

实测（RX 6750 XT）：

| | 耗时 |
| --- | --- |
| CPU | 1598 ms |
| DirectML | 533 ms |

识别结果完全一致，只是速度不同。

**2. 截图加速（MuMu 用户）**

关键发现：MaaFramework 的 `extras.mumu.enable` 默认为空，导致 MuMu 原生截图接口被忽略，一直走慢速 adb 通道。

打开后：

| | 耗时 |
| --- | --- |
| 默认 | 298 ms |
| `extras.mumu.enable` | 8 ms |

**3. 稳定性修复**

maafw 连续取帧失败时，上游会直接抛异常退出程序。MuMu 进程重启后会话失效，长跑必炸。

现在三级容错：自动重连 → adb 降级 → 才报错。实测一夜长跑触发 2 次重连，全部自动恢复。

**4. 摆位逻辑改进**

上游规则「新干员只能替换低星，绝不替换已有 5/6 星」会导致早期刷到的弱 5 星占死格子，后期强干员永远上不了场：

```
购买 V/VI: 斩业星熊 优先
没有可用位置，留在备战席: 斩业星熊   ← 强干员进不来
```

改为允许优先干员替换场上的**非优先** 5/6 星，同时保留安全约束（优先不互斥、未知占位不换、换下的高星会递归重部署）。

### 实测效果

| 项目 | 优化前 | 优化后 |
| --- | --- | --- |
| 截图 | 298 ms | 8 ms |
| OCR | 1598 ms | 533 ms |
| 回合 1 准备 | 55 s | 24 s |
| 回合 4 准备 | 13 s | 6 s |
| **单局总时长** | ~15-16 分钟 | **~11 分钟** |

测试环境：i5-12600KF / RX 6750 XT / MuMu 6.8.8.0 / 1920×1080。

### 怎么用

详见 README。基本流程：

```powershell
python -m pip install "numpy>=2.2,<3" "opencv-python>=4.10,<5" rapidocr-onnxruntime==1.4.4 maafw==5.16.1 onnxruntime-directml
python garrison_farm.py --device emulator --maa "C:/Program Files/MAA" --check
python garrison_farm.py --device emulator --maa "C:/Program Files/MAA" --profile full --target 6
```

N 卡用户把 `onnxruntime-directml` 换成 `onnxruntime-gpu` 即可。

有人可能会问为什么不做成 exe：上游的打包配置不在源码仓里，重新打包会引入额外风险；而且改代码需要源码。所以推荐直接用 Python 跑。

### 已知限制

- **非 MuMu 模拟器**：OCR 加速照样生效，但截图拿不到 8ms 的加速（走 adb ~300ms）
- **需要 Python 3.11**：其他版本 onnxruntime/rapidocr 可能不兼容
- **第一次推理慢**：约 1.5s，是模型加载开销，之后稳定
- **`IM.EmulatorExtras` 不能用**：输入方式用它会破坏 MuMu 通道，必须用默认输入

### 致谢

- [UnknownGlyph/GarrisonFarm](https://github.com/UnknownGlyph/GarrisonFarm) —— 上游原始项目
- [FJH3576/GarrisonFarm-Personal](https://github.com/FJH3576/GarrisonFarm-Personal) —— MuMu 增强思路
- [Eugerine/GarrisonFarm-GPU](https://github.com/Eugerine/GarrisonFarm-GPU) —— N 卡 CUDA 版
- MaaFramework / MAA / RapidOCR / PaddleOCR

---

## 附：README 中待补充的段落

你写项目介绍时，可以在 README 开头「项目介绍」处补充背景，例如：

```markdown
## 项目介绍

（在这里写你的内容：为什么做这个、解决的痛点、适用人群、
和原版/其他分支的区别、使用场景等）
```
