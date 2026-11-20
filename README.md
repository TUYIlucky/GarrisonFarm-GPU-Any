# GarrisonFarm 通用加速版（A卡 / N卡 / 核显通用）

在 [UnknownGlyph/GarrisonFarm](https://github.com/UnknownGlyph/GarrisonFarm) 上游源码基础上做的性能与稳定性适配，重点解决两件事：

1. **没有 N 卡也能用 GPU 加速** —— 用 DirectML，A 卡、I 卡、核显都能跑，不需要 CUDA。
2. **截图提速 30 倍以上** —— 打开 MaaFramework 的 MuMu 原生通道，截图从 ~300ms 降到 ~8ms。

> 上游原始项目：[UnknownGlyph/GarrisonFarm](https://github.com/UnknownGlyph/GarrisonFarm)
> 个人优化版：[FJH3576/GarrisonFarm-Personal](https://github.com/FJH3576/GarrisonFarm-Personal)（轻骑可历#9000）
> N卡专用 GPU 版：[Eugerine/GarrisonFarm-GPU](https://github.com/Eugerine/GarrisonFarm-GPU)（壱津玉#0990，走 CUDA）

本项目是在**上游原始源码**上改动，不包含他人打包的 exe。请自行从上游客源仓获取源码后打补丁，或直接用本仓库的 `garrison_farm.py`。

---

## 目录

- [性能实测](#性能实测)
- [原理：两个独立的瓶颈](#原理两个独立的瓶颈)
- [适配你的电脑](#适配你的电脑)
- [显卡适配对照](#显卡适配对照)
- [MuMu 截图加速](#mumu-截图加速)
- [稳定性修复](#稳定性修复)
- [摆位逻辑改进](#摆位逻辑改进)
- [常见问题](#常见问题)

---

## 性能实测

测试机：i5-12600KF / AMD RX 6750 XT / MuMu 6.8.8.0 (Android 15) / 1920×1080。

### 截图

| 配置 | 耗时 | 说明 |
| --- | --- | --- |
| 默认 maafw（未开 MuMu 通道） | **298 ms** | 走 adb 通道 |
| 纯 adb `screencap` | 973 ms | 最慢 |
| **开启 `extras.mumu.enable`** | **8 ms** | 共享内存取帧 |

### OCR 推理

| 设备 | 耗时 | 说明 |
| --- | --- | --- |
| CPU (i5-12600KF) | 1598 ms | 默认 |
| **DirectML (RX 6750 XT)** | **533 ms** | A 卡可用 |
| DirectML 首次预热 | ~1.5 s | 冷启动开销，之后稳定 |

识别结果完全一致（同一张图都是 33 条文本），只是速度不同。

### 综合效果

单局内每回合的准备耗时（含读屏、决策、摆位）：

| 回合 | 优化前 | 优化后 |
| --- | --- | --- |
| 回合 1 | 55 s | **24 s** |
| 回合 2 | 54 s | **28 s** |
| 回合 3 | 17 s | **14 s** |
| 回合 4 | 13 s | **6 s** |
| 回合 5 | 51 s | **17 s** |

---

## 原理：两个独立的瓶颈

很多人会把「截图慢」和「显卡」混在一起，其实是两个完全不同的环节：

```
游戏画面
   ↓ ① 截图（取帧）
内存图像
   ↓ ② OCR 推理（识别文字：干员名、资金、回合数…）
结构化数据
   ↓ ③ 决策 + 摆位
模拟器操作
```

- **① 截图**：瓶颈在**帧的传输方式**。adb 通道慢（~300ms），模拟器共享内存快（~8ms）。**与显卡无关**。
- **② OCR**：瓶颈在**推理算力**。CPU 慢（1.6s），GPU 快（0.5s）。**这才需要显卡**。

所以：
- 想加快截图 → 开 `extras.mumu.enable`（任何显卡都一样）
- 想加快 OCR → 装对应显卡的 onnxruntime

两件事要分开做。

---

## 适配你的电脑

### 环境要求

- Windows 10/11 x64
- Python **3.11**（其他版本 onnxruntime/rapidocr 可能不兼容）
- MAA 已安装并能正常连接模拟器（程序会读它的 OCR 模型）
- 模拟器 1920×1080 横屏

### 步骤 1：装依赖

```powershell
# 基础依赖
python -m pip install "numpy>=2.2,<3" "opencv-python>=4.10,<5" rapidocr-onnxruntime==1.4.4 maafw==5.16.1

# 根据你的显卡选一个（见下方对照表）
python -m pip install onnxruntime-directml   # A卡 / 核显 / 任意显卡
python -m pip install onnxruntime-gpu        # N卡（CUDA）
```

**注意**：`onnxruntime`、`onnxruntime-directml`、`onnxruntime-gpu` 三者**互斥**，同时装会冲突。切换前先卸载：

```powershell
python -m pip uninstall -y onnxruntime onnxruntime-directml onnxruntime-gpu
```

装完验证：

```powershell
python -c "import onnxruntime as o; print(o.get_available_providers())"
```

- A 卡 / 核显应看到 `DmlExecutionProvider`
- N 卡应看到 `CUDAExecutionProvider`
- 只有 `CPUExecutionProvider` 说明加速包没装上

### 步骤 2：准备源码

```powershell
git clone https://github.com/UnknownGlyph/GarrisonFarm
cd GarrisonFarm
```

然后二选一：

**方式 A（推荐）**：直接用本仓库的 `garrison_farm.py` 覆盖上游的同名文件。

**方式 B**：用 `patches/` 里的补丁自己打，便于看清改了什么：

```powershell
git apply patches/0001-mumu-screencap-accel.patch
git apply patches/0002-directml-ocr.patch
git apply patches/0003-stability-and-deploy.patch
```

### 步骤 3：首次自检

```powershell
python garrison_farm.py --device emulator --maa "C:/Program Files/MAA" --check
```

正常应该看到：

```
[✔] 控制方式：MaaFramework（maafw）...
     maafw 截图方式: MuMu原生加速（8ms/帧，MuMu 路径 D:\Program Files\MuMuPlayer）
[✔] 文字识别模型：使用 MAA 的模型（DML 推理，533ms/次）
```

**这两行就是加速生效的标志。** 如果显示 `Default` 或没有「DML 推理」，回到对应章节排查。

### 步骤 4：开始运行

```powershell
# 标准模式（需自选编队）· 金色角标（每策略 3 次）
python garrison_farm.py --device emulator --maa "C:/Program Files/MAA" --profile full --target 3

# 标准模式 · 彩色角标（每策略 6 次）
python garrison_farm.py --device emulator --maa "C:/Program Files/MAA" --profile full --target 6

# 低配模式（不需要自选编队）
python garrison_farm.py --device emulator --maa "C:/Program Files/MAA" --profile low --target 3
```

常用参数：

| 参数 | 说明 |
| --- | --- |
| `--target 3\|6` | 3 = 金色角标，6 = 彩色（镀层） |
| `--profile full\|low` | full = 标准（自选编队），low = 低配（预设干员） |
| `--runs N` | 目标通关局数上限 |
| `--attempts N` | 总局数上限（胜负都算），`0` = 不限 |
| `--check` | 只做自检然后退出 |
| `--yes` | 跳过启动提醒弹窗 |
| `--no-maafw` | 不用 maafw，退回 adb 命令（慢，排查用） |

---

## 显卡适配对照

| 显卡 | 需要安装 | 自动使用 | 备注 |
| --- | --- | --- | --- |
| **AMD** (RX 系列 / APU 核显) | `onnxruntime-directml` | `DmlExecutionProvider` | 本项目主要测的就是这个 |
| **Intel 核显 / Arc** | `onnxruntime-directml` | `DmlExecutionProvider` | DirectML 对 Intel 支持良好 |
| **NVIDIA** | `onnxruntime-gpu` (CUDA 12) | `CUDAExecutionProvider` | 也可用 directml，但 CUDA 更快 |
| **无独显 / 极老显卡** | 不用装 | 自动回退 `CPUExecutionProvider` | 能用，只是慢 |

### 程序如何自动选择

源码里做了三档自动回退，**不需要手动改代码**：

```python
for accel, extra in (("DML",  {"det_use_dml": True,  "rec_use_dml": True}),
                     ("CUDA", {"det_use_cuda": True, "rec_use_cuda": True}),
                     ("CPU",  {})):
    try:
        eng = RapidOCR(**base_kwargs, **extra)
        ...
        break          # 成功就用这一档
    except Exception:
        continue       # 失败静默降级到下一档
```

所以：
- 装了 directml → 用 DML
- 装了 gpu → DML 失败后自动用 CUDA
- 都没装 → 回退 CPU，程序照常跑

### rapidocr 原生支持 DML

`rapidocr-onnxruntime` 1.4.4 内部已经支持 DirectML，无需自己替换 session：

```python
RapidOCR(det_model_path=..., rec_model_path=..., rec_keys_path=...,
         use_cls=False,
         det_use_dml=True, rec_use_dml=True)   # ← 就这两个参数
```

日志里会出现 `Windows 10 or above detected, try to use DirectML as primary provider`，说明生效。

> 常见误区：手动 `ort.InferenceSession(...)` 替换 `text_det.session` 往往只能替换一半
> （det 的 session 是延迟创建的），而且容易破坏 rapidocr 内部状态。用原生参数最稳。

---

## MuMu 截图加速

### 关键：`extras.mumu.enable`

MaaFramework 的 DLL 里有一行判断：

```
extras.mumu.enable is false, ignore
```

**这个配置项默认为空**，所以即使你指定了 `EmulatorExtras`（MuMu 原生截图方式），它也会被直接忽略，退回 adb 通道。必须显式打开：

```python
cfg = {
    "extras": {
        "mumu": {
            "enable": True,
            "path": r"D:\Program Files\MuMuPlayer",   # MuMu 安装根目录
            "index": 0,                                # 多开时的实例号
        }
    }
}
ctl = AdbController(adb_path, address, SC.EmulatorExtras, IM.Default, cfg)
```

开启后 maafw 会直接调用 MuMu 的 `nemu_capture_display`（共享内存取帧），实测 298ms → 8ms。

### 支持的模拟器

| 模拟器 | 截图方式 | 加速 |
| --- | --- | --- |
| **MuMu 12 / 新版 MuMu** | `EmulatorExtras` | ✅ 8ms |
| LDPlayer 9 | `EmulatorExtras` | ✅ 支持 |
| 雷电 / 夜神 / 蓝叠 | 默认方式 | ❌ 走 adb（~300ms） |
| 真机 / 其他 | 默认方式 | ❌ 走 adb |

其他模拟器仍然能跑（`det_use_dml` 的 OCR 加速照样生效），只是截图没那么快。

### 输入方式千万别用 EmulatorExtras

实测踩过的坑：截图用 `SC.EmulatorExtras` 没问题，但**输入方式用 `IM.EmulatorExtras` 会导致 MuMu 通道在选人/确认类点击后失效**，下一次截图直接报错。

```python
# ✅ 正确：截图走原生，输入走默认（MaaTouch 等）
AdbController(adb, addr, SC.EmulatorExtras, IM.Default, cfg)

# ❌ 错误：输入也走原生，会让你以为"随机截图失败"
AdbController(adb, addr, SC.EmulatorExtras, IM.EmulatorExtras, cfg)
```

### MuMu 安装路径怎么找

程序会自动探测这几个位置：

```
D:\Program Files\MuMuPlayer
C:\Program Files\MuMuPlayer
C:\Program Files\MuMu
E:\Program Files\MuMuPlayer
```

其他位置可以设环境变量 `MUMU_PATH`，或直接改 `_mumu_extras_config()` 里的候选列表。

注意路径要写到 **`MuMuPlayer` 这一层**，不要指到 `nx_main` 子目录。

---

## 稳定性修复

### 截图失败不再崩溃

上游 `shot()` 在 maafw 连续取帧失败时直接 `raise RuntimeError`，程序退出。

MuMu 进程重启后（PID 变化）maafw 的会话会失效，这时程序就崩了 —— **长跑时很要命**。

现在的三级容错：

```
maafw 截图失败
   ↓ 自动重连 maafw（重新握手，通常能恢复）
重连成功 → 继续
   ↓ 仍失败
降级到 adb 截图（慢但能用）
   ↓ 仍失败
才抛异常
```

实测效果：一夜长跑中触发 2 次重连，全部自动恢复，0 次崩溃。

### 相关函数

- `_adb_shot_once()` —— 直接 adb 截一张图，作为兜底
- `_maafw_reconnect()` —— 重新建立 maafw 连接
- `shot()` —— 三级容错的主入口

---

## 摆位逻辑改进

### 问题

上游规则是：**新来的 5/6 级干员只能替换场上的 1~4 级干员，绝不替换已有的 5/6 级**。

原代码：

```python
cands = sorted((value(tn, occs[tn]), grp.index(tn), tn) for tn in grp
               if occs[tn][1] < 5 and occs[tn][0] != "?" and value(tn, occs[tn]) < my)
#                 ^^^^^^^^^^^^^^^^ 只换低星
```

后果：早期刷到的**弱 5 级**（机械师、蜜蜡之类）会占死格子，后期刷到的**优先干员**（斩业星熊、逻各斯）永远上不了场，只能烂在备战席。日志里会看到大量：

```
购买 V/VI: 斩业星熊 优先
没有可用位置，留在备战席: 斩业星熊
```

### 改法

允许**优先干员替换场上的非优先 5/6 级**：

```python
new_is_prio = prio_index(name) is not None

def swappable(tn, occ):
    onm, otier = occ
    if onm == "?":                        # 未知占位者不换（避免误卖高星）
        return False
    if otier < 5:                         # 低星：可被任何更高价值的换下
        return True
    # 场上是 5/6 级：仅当新来的是优先干员、而场上不是时，才允许换
    return new_is_prio and prio_index(onm) is None
```

### 保留的安全约束

- 优先干员**不会**互相替换（避免来回换）
- 非优先干员**不会**替换场上的 5/6 级
- 未知占位者（名字读不出来）**一律不换**
- 换下的高星干员会递归尝试重新部署，不会被白白丢掉

### 验证

10 个用例全部通过：

| 场上 | 新来 | 旧版 | 新版 | 期望 |
| --- | --- | --- | --- | --- |
| 机械师 (T5) | 斩业星熊 | ❌ | ✅ | ✅ 核心修复 |
| 斩业星熊 (T5) | 逻各斯 | ❌ | ❌ | ✅ 优先不互斥 |
| 推进之王 (T5) | 机械师 | ❌ | ❌ | ✅ 非优先不换 |
| 陨星 (T1) | 机械师 | ✅ | ✅ | ✅ 低星可换 |
| ? (未知) | 斩业星熊 | ❌ | ❌ | ✅ 未知不换 |

---

## 策略名繁简归一化

### 问题

OCR 偶尔会把同一个策略读成繁体或异体字，例如：

```
伊奥莱塔·罗素   ← 一次识别
伊奧莱塔·罗素   ← 另一次识别（「奧」是繁体）
```

后果：`strategies_done.json` 里存了两条不同记录，程序以为这是两个策略，会重复刷取。

### 改法

`load_done()` / `save_done()` 都过一遍轻量繁简映射：

```python
def _norm_strategy_name(name):
    table = str.maketrans({"奧": "奥", "歐": "欧", "爾": "尔", ...})
    return name.translate(table).strip()

def load_done():
    raw = json.load(f)
    return {_norm_strategy_name(x) for x in raw}   # 归一化后去重

def save_done(s):
    norm = {_norm_strategy_name(x) for x in s}     # 写入前统一
    json.dump(sorted(norm), f, ensure_ascii=False, indent=1)
```

只映射 OCR 在策略名上实际会混淆的高频字，不引入额外依赖。

> 注意：这不影响「策略是否跳过」的判断 —— 那个靠游戏内 OCR 读到的真实通关次数决定，
> 这里只是让进度记录不重复。

---

## 界面切换与召唤物导致的无效操作

这两个问题都是长跑实测出来的，会白白拖慢速度。

### 问题一：选完编队后必然触发一次截图失败

10 小时的实测日志里，52 局共触发 **90 次截图失败**，其中 **94.3% 发生在「自选编队选择」之后**：

```
12:22:32 自选编队选择: ['维什戴尔', '斩业星熊', ...]
12:22:41 截图失败，尝试重连 maafw …        ← 9 秒后
12:34:14 自选编队选择: [...]
12:34:23 截图失败，尝试重连 maafw …        ← 9 秒后
```

**原因**：`pick_squad()` 点「确定」后只 `time.sleep(1.5)`。此时游戏正从选人页切回准备页，
MuMu 的共享内存帧缓冲在重建，取帧必然失败，于是走了重连流程（白等 2~4 秒）。

**改法**：新增 `_wait_screen_stable()`，轮询等待画面连续两帧基本一致才继续：

```python
def _wait_screen_stable(min_wait=2.0, timeout=8.0):
    """连续两次截图都成功且画面基本一致 -> 界面稳定"""
    ...
    diff = float(cv2.absdiff(prev, img).mean())
    if diff < 2.0:
        return True
```

在 `pick_squad()` 点完确定后调用，主动跳过缓冲重建的窗口，而不是撞上去再重连。

### 问题二：召唤物被当成干员，拖拽必然失败

11 次「放置失败」全部集中在这三个名字上：

| 单位 | 失败次数 | 性质 |
| --- | --- | --- |
| 变形同构体 | 8 | 战术家召唤物 |
| 狼群 | 2 | 召唤物 |
| 樱桃三号 | 1 | 召唤物 |

这些是**衍生物/召唤物**，不是可自由摆放的干员，按固定坐标拖到部署区当然会失败。

**改法**：加一份召唤物名单，识别到就放回备战席，不占格子、不参与替换判断：

```python
SUMMON_KEYS = ["变形同构体", "同构体", "狼群", "樱桃三号", "信标", "流形",
               "重构体", "汲取者之心", "拟态物质", "蜂鸣器", ...]

def _is_summon(name):
    return any(k in _norm_strategy_name(name) for k in SUMMON_KEYS)
```

在 `deploy_layout()` 取到名字后立刻判断：

```python
if _is_summon(name):
    touch("UP", lx, ly); time.sleep(0.8)
    log("跳过召唤物:", name)
    return None
```

9 个用例验证：召唤物全部识别，正常干员（维什戴尔/斩业星熊/逻各斯/机械师/陈）全部不误伤。

---

## 内存翻倍：rapidocr 的 float64 坑

长时间跑会遇到这个崩溃（不是卡死，是进程直接消失）：

```
numpy._core._exceptions._ArrayMemoryError: Unable to allocate 47.8 MiB
for an array with shape (1088, 1920, 3) and data type float64
```

**根因**在 `rapidocr_onnxruntime/ch_ppocr_det/utils.py`：

```python
self.mean = np.array([0.5, 0.5, 0.5])     # ← 默认 float64
self.std  = np.array([0.5, 0.5, 0.5])     # ← 默认 float64

def normalize(self, img):
    return (img.astype("float32") * self.scale - self.mean) / self.std
```

`img.astype("float32")` 本身是 float32，但和 **float64 的 mean/std 运算**时，
NumPy 的类型提升规则会把结果变成 **float64**，内存直接翻倍：

| 版本 | 数组大小 | dtype |
| --- | --- | --- |
| 正常 | 23.9 MB | float32 |
| **实际** | **47.8 MB** | **float64** |

报错里的 47.8 MiB 正好对上。32GB 内存的机器上，剩下的余量一旦不够就会崩。

**修复**：把 mean/std 声明为 float32。

```python
self.mean = np.array(mean, dtype=np.float32)
self.std  = np.array(std,  dtype=np.float32)
```

一行改动，内存减半，识别结果完全一致（实测 33 条文本不变），速度还略快。

仓库里提供了 `fix_rapidocr_dtype.py` 自动处理：

```powershell
python fix_rapidocr_dtype.py           # 检查并修复
python fix_rapidocr_dtype.py --check   # 只看状态
```

> 这是修改 site-packages 里的第三方库文件。重装 rapidocr 后需要重新跑一次。
> 补丁脚本会先备份成 `utils.py.bak`。

---

## 策略列表网格标定（跳过策略的真因）

### 现象

长跑日志里反复出现：

```
策略面板读取失败，跳过该格 (680, 632)
策略面板读取失败，跳过该格 (1100, 659)
策略列表下滑，继续查找（本页 4 行）
```

一晚上累积 **294 次**。表现是某些策略总被跳过，选一次策略要白花 20~40 秒。

### 根因：网格坐标与实际布局对不上

上游的网格定义（1920×1080）：

```python
GRID_X = [680, 890, 1100, 1310]
GRID_Y = [370, 580, 790, 1000]
GRID_TOP, GRID_BOTTOM = 250, 1050
```

实测（逐格截图核对）真实布局：

| 项目 | 上游值 | 实测值 | 差异 |
| --- | --- | --- | --- |
| 列中心 x | 680 / 890 / 1100 / 1310 | **600 / 800 / 1000 / 1200** | 偏 80~110 px |
| 行中心 y | 370 / 580 / 790 / 1000 | **230 / 444 / 660 / 976** | 首行偏 140 px |

卡片本身约 **170×170**，列间距 200 px。点击落在卡片边缘或格子之间，
右侧面板自然读不出策略名 → 判为「读取失败」→ 跳过整格。

另外 `GRID_TOP = 250` 会让 **第一行（y≈230）几乎在扫描范围外**，
`detect_rows()` 长期漏掉第一行。

### 修复

```python
GRID_X = [600, 800, 1000, 1200]
GRID_Y = [230, 444, 660, 976]
GRID_TOP, GRID_BOTTOM = 120, 1050
ROW_H  = 165
```

同时改了 `detect_rows()`（滚动后的行检测）：

1. 不再只看第 1 列（x 620~740）——某些行只有 1~2 个卡片，第 1 列为空时整行判不出来；
   改成扫描整个列表宽度（x 570~1250）。
2. 用「段高度接近一张卡片（110~230 px）」过滤标题行和零碎文字。
3. 两行间距异常大（>260 px）时，检查中点为是否确实有卡片，有则补一行。
4. 检测结果不合理（<2 或 >6 行）时返回空，让调用方退回固定网格。

滚动后行检测失败时，也不再直接 `break` 放弃，而是用 `grid_shift()` 测出的滚动量
平移固定网格继续找：

```python
sh2 = grid_shift(img, after)
rows = [y - sh2 for y in GRID_Y]
```

### `strategy_name()` 也放宽了

上游只在 y 520~650 的窄带里找策略名，实测策略名可能落在该范围外：

```python
# 放宽到 460~700，排除更多非策略名文案，取最靠上的一条
cand = [(y, t) for x, y, t in panel
        if 460 < y < 700
        and 汉字 and not any(b in t for b in BAD)
        and 2 <= len(t.strip()) <= 12]
cand.sort(key=lambda c: c[0])
```

### 怎么自己重新标定

如果换了分辨率、UI 主题或游戏大版本，坐标会失效。标定方法：

1. 进到「选择策略」界面，截一张图
2. 用任意画图工具在上面画网格，或者跑仓库里的思路：先按 `GRID_X` 画竖线定位列，
   再逐行找卡片上下边缘取中心
3. 把量到的值填回 `GRID_X` / `GRID_Y`
4. 复核：在截图上把所有 `(x, y)` 交点画出来，应当每一点都落在卡片正中心

> 提示：不同分辨率下要按比例换算。`GRID_X` 是 4 等分的列中心，
> 从约 31% 宽度开始、每列约 10.4% 宽度。

---

## 策略页的四个隐藏坑（实测每次都踩）

这几个问题都不会报错，只会让程序「选不到某些策略」或「反复选同一个」，
很难从日志看出来。记录在这里，换机器/换分辨率时按顺序核对。

### 坑 1：角标采样框方向反了

角标在卡片的**右上角**，实测中心相对卡片中心是 **(+53, −58)**、尺寸 49×56。

```python
# 错：往左取，完全框不到角标
x1 = gx - 75; x2 = gx - 5

# 对：往右上取
cx, cy = gx + 53, gy - 58
x1, y1, x2, y2 = cx-34, cy-34, cx+34, cy+34
```

采样框方向错时，**所有格子都被判成"无角标"**，于是已完成策略被当成未完成反复点击。
用一张真实截图逐格打印 `cyan` 占比就能发现：正常应有 0.30 左右，取错区域只有 0.00~0.06。

### 坑 2：`PANEL_BOX` 上界太高，漏掉通关次数

详情面板自上而下的实测位置：

| y | 内容 |
| --- | --- |
| **≈200** | **「已通过模拟 N 次」** ← 必须包含 |
| ≈280 | STRATEGY 标签 |
| ≈498 | 「初始生命值 N」 |
| ≈575 | 策略名 |
| ≈662 | 「【效果名】」+ 说明 |

```python
PANEL_BOX = (1400, 150, 1920, 850)   # 上界 150 才包含 y=200 的次数
```

上界写成 350 时 `passed_count()` **永远返回 0**，`if n >= TARGET: continue`
这条保护形同虚设 —— 表现为「已通关 10 次的策略还在被反复选中」。

### 坑 3：选中卡片后策略列表会左移

点中任意一张卡后，列表整体左移（右侧让出详情面板），**原先测好的 x 坐标全部失效**。
表现为：点每一格，右侧面板都停在上一张卡上，日志里出现「每格都读到同一个策略名」。

解法：**每次点击前重新实测网格**，用当前画面的坐标去点：

```python
for gx0 in xs:
    img = shot()
    xs_n, rows_n, ok = current_grid(img)      # 重测
    gx = min(xs_n, key=lambda v: abs(v - gx0))  # 取最近的真实格中心
    tap(gx, gy, 0.7)
```

### 坑 4：单字/英文策略名 OCR 读不出来

「夕」是**大号斜体单字**，「pith」是纯英文，OCR 的检测模型对这两种都不稳：

- 单字会被当成装饰图形，det 模型根本不框它
- 英文名容易被 `len(s) >= 2`、`isalpha()` 之类的过滤规则误杀

两道处理：

```python
# 1) 允许单字
#    去掉 len(s) >= 2 的限制，「夕」才能作为候选

# 2) 名字读不到时，用"面板是否出现详情"兜底
has_detail = any(("初始生命值" in t) or ("【" in t) for _x, _y, t in panel)
if has_detail:
    return "<未识别>"      # 点到了真卡片，直接选它
```

### 附带：排除干员名

策略页和自选编队页的 OCR 结果可能串味，日志里出现过
「选择策略: 维什戴尔（已通过 0 次）」——把干员名当成了策略名。

```python
for _has, _y, s in cand:
    if prio_index(s) is not None:   # 是优先干员名 -> 跳过
        continue
    if is_safe_op(s):
        continue
    return s
```

---

## 常见问题

### OCR 还是慢（>1s）

1. 确认装的是加速版 onnxruntime：
   ```powershell
   python -c "import onnxruntime as o; print(o.get_available_providers())"
   ```
   看不到 `DmlExecutionProvider` / `CUDAExecutionProvider` 就是没装对。

2. 确认自检输出里有「DML 推理」或「CUDA 推理」字样。

3. 注意**首次推理包含模型加载**（~1.5s），之后才稳定。自检里会预热两次。

### 截图还是 300ms

1. 自检输出应显示 `MuMu原生加速（8ms/帧）`。如果显示 `Default`，说明 `extras.mumu.enable` 没生效。

2. 检查 MuMu 路径是否正确（要指到 `MuMuPlayer` 这一层）。

3. 检查输入方式有没有误用 `IM.EmulatorExtras`（会导致通道失效）。

4. 非 MuMu 模拟器拿不到这个加速，属正常。

### 提示「截图失败」但程序没退出

这是容错机制在工作。日志里会看到：

```
截图失败，尝试重连 maafw …
maafw 已重新连接
```

偶尔一次不影响，会自动恢复。

### 装了 directml 后报 DLL 错误

如果之前装过 `onnxruntime`，DLL 可能被进程占用导致替换不完整。先彻底卸载再装：

```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
python -m pip uninstall -y onnxruntime onnxruntime-directml onnxruntime-gpu
python -m pip install onnxruntime-directml
```

### 第一回合总是比较慢

正常现象。第一回合要做这些额外工作：

- 从自选编队按权重选 Ⅴ/Ⅵ 各 2 名（多次 OCR）
- 首次商店刷新与判断
- 首次拖拽视角校准

优化后约 24s，后续回合 6~17s。

### 多开模拟器

```json
{"extras": {"mumu": {"enable": True, "path": "...", "index": 1}}}
```

`index` 填实例号（0 = 第一个，1 = 第二个…）。

---

## 致谢

- [UnknownGlyph/GarrisonFarm](https://github.com/UnknownGlyph/GarrisonFarm) —— 上游原始项目
- [FJH3576/GarrisonFarm-Personal](https://github.com/FJH3576/GarrisonFarm-Personal) —— MuMu 增强触控与快速截图的个人优化思路
- [Eugerine/GarrisonFarm-GPU](https://github.com/Eugerine/GarrisonFarm-GPU) —— N 卡 CUDA 加速版
- [MaaFramework](https://github.com/MaaXYZ/MaaFramework) / [MAA](https://github.com/MaaAssistantArknights/MaaAssistantArknights) / [RapidOCR](https://github.com/RapidAI/RapidOCR) / [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)

## 授权

本仓库的改动代码仅供学习交流。上游项目及其他第三方组件适用各自的许可条款，请遵守原作者要求。游戏相关内容版权归鹰角网络所有。
