# 补丁说明

本目录的补丁基于 [UnknownGlyph/GarrisonFarm](https://github.com/UnknownGlyph/GarrisonFarm) 的 `garrison_farm.py`（2022 行版本，对应上游 v1.2 / v1.3 期间源码）。

## 文件说明

| 文件 | 说明 | 新增行 |
| --- | --- | --- |
| `garrison-farm-any-gpu-all.patch` | **完整补丁**，一次应用全部改动 | 205 |
| `0001-directml-ocr.patch` | DirectML / CUDA 自动回退的 OCR 加速 | 51 |
| `0002-mumu-screencap-accel.patch` | MuMu 原生截图加速（`extras.mumu.enable`） | 76 |
| `0003-stability-and-deploy.patch` | 截图容错重连 + 摆位逻辑改进 | 78 |

## 应用方式

### 方式一：完整补丁（推荐）

```powershell
cd GarrisonFarm
git apply /path/to/garrison-farm-any-gpu-all.patch
```

如果 git 不可用，也可以用 `patch`：

```bash
patch -p1 < garrison-farm-any-gpu-all.patch
```

或者最简单：直接用本仓库根目录的 `garrison_farm.py` 覆盖上游同名文件。

### 方式二：分项应用

想只取某一部分改动时：

```powershell
git apply /path/to/0001-directml-ocr.patch        # 只要 GPU 加速
git apply /path/to/0002-mumu-screencap-accel.patch # 只要截图加速
git apply /path/to/0003-stability-and-deploy.patch # 只要稳定性+摆位
```

三个分项补丁都基于**原始文件**生成，可单独应用，但**不要叠加应用**（会冲突）。需要全部改动时请用完整补丁。

## 各补丁改了什么

### 0001-directml-ocr.patch

在自检的 OCR 初始化处，把单一的 `RapidOCR(...)` 改成三档自动回退：

```python
for accel, extra in (("DML",  {"det_use_dml": True,  "rec_use_dml": True}),
                     ("CUDA", {"det_use_cuda": True, "rec_use_cuda": True}),
                     ("CPU",  {})):
    try:
        eng = RapidOCR(**kw, **extra)
        ...
        break
    except Exception:
        continue
```

涉及两处：模拟器自检路径和 PC 端自检路径。

输出会标明实际用的是哪一档：

```
[✔] 文字识别模型：使用 MAA 的模型（DML 推理，533ms/次）
```

### 0002-mumu-screencap-accel.patch

新增 `_mumu_extras_config()`，自动探测 MuMu 安装目录并注入：

```python
{"extras": {"mumu": {"enable": True, "path": "<MuMu>", "index": 0}}}
```

改造 `maafw_adb()` 为多级尝试，优先用 `SC.EmulatorExtras`，并实测一帧确认可用。

**关键坑**：输入方式不要用 `IM.EmulatorExtras`，否则 MuMu 通道会在选人/确认后失效。

### 0003-stability-and-deploy.patch

**稳定性**：新增 `_adb_shot_once()` 和 `_maafw_reconnect()`，`shot()` 改为三级容错（重连 → adb 降级 → 才报错）。原来 maafw 取帧失败会直接 `raise` 导致程序退出。

**摆位**：新增 `swappable()` 判断，允许优先干员替换场上的非优先 Ⅴ/Ⅵ 干员。原来只允许替换 1~4 星，导致弱 5 星占死格子、优先干员上不了场。

## 兼容性

- 上游后续如果改动较大，补丁可能无法直接 `git apply`，此时用 `--3way` 或手动合并。
- 三个补丁都用 `difflib.unified_diff` 生成，上下文 3 行。
- 已验证：完整补丁应用于原始文件后，与开发所用文件逐字节一致（2187 行）。
