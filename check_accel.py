"""加速自检脚本：检查 onnxruntime 加速能力与 MuMu 截图通道

用法：
    python check_accel.py
    python check_accel.py --maa "C:/Program Files/MAA" --mumu "D:/Program Files/MuMuPlayer"
"""
import argparse
import os
import sys
import time


def line(c="-", n=64):
    print(c * n)


def check_onnxruntime():
    line("=")
    print("1. OCR 推理加速（onnxruntime）")
    line()
    try:
        import onnxruntime as ort
    except ImportError:
        print("  ✘ 未安装 onnxruntime")
        print("     AMD/Intel/核显: pip install onnxruntime-directml")
        print("     NVIDIA:         pip install onnxruntime-gpu")
        return False

    print(f"  版本: {ort.__version__}")
    providers = ort.get_available_providers()
    print(f"  可用 providers: {providers}")

    best = None
    if "DmlExecutionProvider" in providers:
        best = "DML (DirectML)"
        print("  ✔ 检测到 DirectML —— AMD / Intel / 核显可用")
    elif "CUDAExecutionProvider" in providers:
        best = "CUDA"
        print("  ✔ 检测到 CUDA —— NVIDIA 显卡可用")
    elif "ROCMExecutionProvider" in providers:
        best = "ROCm"
        print("  ✔ 检测到 ROCm")
    else:
        print("  ⚠ 只有 CPU provider，OCR 会较慢（约 1.5s/次）")
        print("     AMD/Intel: pip install onnxruntime-directml")
        print("     NVIDIA:    pip install onnxruntime-gpu")

    if best:
        print(f"  → 程序会自动使用: {best}")
    return best is not None


def check_ocr_speed(maa_dir):
    line("=")
    print("2. OCR 实测速度")
    line()
    if not maa_dir:
        print("  跳过（未指定 --maa）")
        return
    m = os.path.join(maa_dir, "resource", "PaddleOCR")
    det = os.path.join(m, "det", "inference.onnx")
    rec = os.path.join(m, "rec", "inference.onnx")
    keys = os.path.join(m, "rec", "keys.txt")
    for p in (det, rec, keys):
        if not os.path.exists(p):
            print(f"  ✘ 找不到模型文件: {p}")
            return
    try:
        import cv2
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as e:
        print(f"  ✘ 缺少依赖: {e}")
        return

    img = np.full((1080, 1920, 3), 128, dtype=np.uint8)
    for name, extra in (("DML", {"det_use_dml": True, "rec_use_dml": True}),
                        ("CUDA", {"det_use_cuda": True, "rec_use_cuda": True}),
                        ("CPU", {})):
        try:
            kw = dict(det_model_path=det, rec_model_path=rec,
                      rec_keys_path=keys, use_cls=False)
            kw.update(extra)
            eng = RapidOCR(**kw)
            t0 = time.time()
            for _ in range(2):       # 预热
                eng(img)
            warm = (time.time() - t0) * 500
            print(f"  ✔ {name:<5} 预热后约 {warm:.0f} ms/次")
            if name != "CPU":
                break
        except Exception as e:
            print(f"  - {name:<5} 不可用（{str(e)[:50]}）")


def check_mumu(mumu_dir, adb_path=None, address=None):
    line("=")
    print("3. MuMu 截图加速通道")
    line()
    if not mumu_dir:
        print("  跳过（未指定 --mumu）")
        return
    if not os.path.isdir(mumu_dir):
        print(f"  ✘ 目录不存在: {mumu_dir}")
        return
    print(f"  MuMu 路径: {mumu_dir}")

    nx = os.path.join(mumu_dir, "nx_main")
    if not os.path.isdir(nx):
        print("  ⚠ 未找到 nx_main 子目录，路径可能填错了")
        print("     应指向 MuMuPlayer 这一层，例如 D:/Program Files/MuMuPlayer")
    else:
        print("  ✔ 目录结构正常")

    if not (adb_path and address):
        print("  提示：指定 --adb 和 --address 可直接测速，")
        print("       例如 --adb \"<mumu>/nx_main/adb.exe\" --address 127.0.0.1:16384")
        return

    try:
        from maa.toolkit import Toolkit
        from maa.controller import AdbController
        from maa.define import MaaAdbScreencapMethodEnum as SC
        from maa.define import MaaAdbInputMethodEnum as IM
    except ImportError:
        print("  ✘ 未安装 maafw：pip install maafw==5.16.1")
        return

    Toolkit.init_option(os.path.join(os.path.expanduser("~"), ".garrison_check"))
    cfg = {"extras": {"mumu": {"enable": True, "path": mumu_dir, "index": 0}}}

    for tag, sc, im, c in (
        ("默认（无 mumu.enable）", SC.Default, IM.Default, {}),
        ("EmulatorExtras + mumu.enable", SC.EmulatorExtras, IM.Default, cfg),
    ):
        try:
            ctl = AdbController(adb_path, address, sc, im, c)
            if not ctl.post_connection().wait().succeeded:
                print(f"  ✘ {tag}: 连接失败")
                continue
            ctl.set_screenshot_use_raw_size(True)
            for _ in range(3):
                ctl.post_screencap().wait().get()
            ts = []
            for _ in range(8):
                t = time.time()
                ctl.post_screencap().wait().get()
                ts.append((time.time() - t) * 1000)
            print(f"  ✔ {tag}: {sum(ts)/len(ts):.0f} ms/帧")
        except Exception as e:
            print(f"  ✘ {tag}: {str(e)[:60]}")


def main():
    ap = argparse.ArgumentParser(description="GarrisonFarm 加速自检")
    ap.add_argument("--maa", default=r"C:\Program Files\MAA", help="MAA 安装目录")
    ap.add_argument("--mumu", default=r"D:\Program Files\MuMuPlayer", help="MuMu 安装根目录")
    ap.add_argument("--adb", default=None, help="adb.exe 路径（可选）")
    ap.add_argument("--address", default=None, help="adb 地址，如 127.0.0.1:16384")
    args = ap.parse_args()

    print()
    print("GarrisonFarm 加速自检")
    line("=")
    ok_ort = check_onnxruntime()
    print()
    check_ocr_speed(args.maa)
    print()
    check_mumu(args.mumu, args.adb, args.address)
    print()
    line("=")
    print("提示：运行主程序时自检输出里应能看到")
    print("  maafw 截图方式: MuMu原生加速（~8ms/帧）")
    print("  文字识别模型: 使用 MAA 的模型（DML 推理，~500ms/次）")
    print("这两行才是加速生效的标志。")
    line("=")


if __name__ == "__main__":
    main()
