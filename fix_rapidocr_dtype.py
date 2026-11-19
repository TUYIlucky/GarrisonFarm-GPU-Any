"""修复 rapidocr 的 float64 内存翻倍问题

问题：rapidocr_onnxruntime 的 DetPreProcess 用 np.array([0.5,0.5,0.5]) 创建 mean/std，
默认是 float64。它和 float32 的输入运算时会把结果提升成 float64，
导致 (1088,1920,3) 的数组从 23.9MB 变成 47.8MB，内存紧张时抛 MemoryError。

修复：把 mean/std 显式声明为 float32。

用法：
    python fix_rapidocr_dtype.py          # 检查+修复
    python fix_rapidocr_dtype.py --check  # 只检查
"""
import argparse
import importlib.util
import os
import sys


def find_utils():
    try:
        spec = importlib.util.find_spec("rapidocr_onnxruntime.ch_ppocr_det.utils")
        return spec.origin if spec else None
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只检查，不修改")
    args = ap.parse_args()

    path = find_utils()
    if not path or not os.path.exists(path):
        print("✘ 找不到 rapidocr_onnxruntime/ch_ppocr_det/utils.py")
        print("  请先安装：pip install rapidocr-onnxruntime==1.4.4")
        return 1

    print(f"文件: {path}")
    src = open(path, encoding="utf-8").read()

    OLD_A = "self.mean = np.array(mean)"
    OLD_B = "self.std = np.array(std)"
    NEW_A = "self.mean = np.array(mean, dtype=np.float32)"
    NEW_B = "self.std = np.array(std, dtype=np.float32)"

    already = NEW_A in src and NEW_B in src
    if already:
        print("✅ 已经是 float32，无需修改")
        return 0

    if OLD_A not in src or OLD_B not in src:
        print("⚠ 源码结构和预期不一样，请手动检查：")
        for i, line in enumerate(src.splitlines(), 1):
            if "self.mean" in line or "self.std" in line:
                print(f"  L{i}: {line.strip()}")
        return 2

    if args.check:
        print("⚠ 需要修复：mean/std 当前是 float64，会把中间数组内存翻倍")
        print("  运行不带 --check 即可修复")
        return 1

    backup = path + ".bak"
    if not os.path.exists(backup):
        open(backup, "w", encoding="utf-8").write(src)
        print(f"已备份: {backup}")

    src = src.replace(OLD_A, NEW_A).replace(OLD_B, NEW_B)
    # 加注释说明原因
    src = src.replace(
        "        self.mean = np.array(mean, dtype=np.float32)",
        "        # float32: 避免与 float32 输入运算时提升为 float64，内存翻倍\n"
        "        self.mean = np.array(mean, dtype=np.float32)",
    )
    open(path, "w", encoding="utf-8").write(src)
    print("✅ 已修复")

    # 验证
    import numpy as np
    from rapidocr_onnxruntime.ch_ppocr_det.utils import DetPreProcess
    p = DetPreProcess()
    img = np.zeros((1088, 1920, 3), dtype=np.uint8)
    r = p.normalize(img)
    mb = r.nbytes / 1024 / 1024
    print(f"验证: normalize 输出 {mb:.1f} MB  dtype={r.dtype}")
    print("✅ 正确" if r.dtype == np.float32 else "❌ 仍不正确")
    return 0


if __name__ == "__main__":
    sys.exit(main())
