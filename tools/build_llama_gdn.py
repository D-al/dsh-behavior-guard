# -*- coding: utf-8 -*-
"""编译最新版 llama.cpp master（含 #29307）到独立目录，保留 b12244 生产版不动。
基于 tools/build_b12244.py，仅改 SRC/BLD。
用法: python tools/build_llama_master.py configure|build
"""
import os, subprocess, sys
from pathlib import Path

MSVC = r"D:\VS2022\BuildTools\VC\Tools\MSVC\14.44.35207"
SDK = r"C:\Program Files (x86)\Windows Kits\10"
SDKVER = "10.0.26100.0"
NINJA = r"D:\VS2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja"
CUDA = r"D:\CUDA\v12.5"
USERPROFILE = os.environ.get('USERPROFILE') or r'C:\Users\Ad'
CMAKE = str(Path(USERPROFILE) / '.workbuddy' / 'binaries' / 'python' / 'envs' / 'default' / 'Lib' / 'site-packages' / 'cmake' / 'data' / 'bin' / 'cmake.exe')
SRC = r"D:/llama-gdn-src"
BLD = r"D:/llama-gdn-src/build-gdn"

env = os.environ.copy()
env["PATH"] = ";".join([
    os.path.join(MSVC, "bin", "Hostx64", "x64"),
    os.path.join(SDK, "bin", SDKVER, "x64"),
    NINJA, os.path.join(CUDA, "bin"),
    env.get("PATH", ""),
])
env["CMAKE_MT"] = os.path.join(SDK, "bin", SDKVER, "x64", "mt.exe")
env["INCLUDE"] = ";".join([
    os.path.join(MSVC, "include"),
    os.path.join(SDK, "Include", SDKVER, "ucrt"),
    os.path.join(SDK, "Include", SDKVER, "um"),
    os.path.join(SDK, "Include", SDKVER, "shared"),
    os.path.join(SDK, "Include", SDKVER, "winrt"),
])
env["LIB"] = ";".join([
    os.path.join(MSVC, "lib", "x64"),
    os.path.join(SDK, "Lib", SDKVER, "ucrt", "x64"),
    os.path.join(SDK, "Lib", SDKVER, "um", "x64"),
])
env["CUDA_PATH"] = CUDA
env["CUDACXX"] = os.path.join(CUDA, "bin", "nvcc.exe")

mode = sys.argv[1] if len(sys.argv) > 1 else "configure"

if mode == "configure":
    args = [CMAKE, "-S", SRC, "-B", BLD, "-G", "Ninja",
            "-DCMAKE_BUILD_TYPE=Release",
            "-DCMAKE_C_COMPILER=" + os.path.join(MSVC, "bin", "Hostx64", "x64", "cl.exe"),
            "-DCMAKE_CXX_COMPILER=" + os.path.join(MSVC, "bin", "Hostx64", "x64", "cl.exe"),
            "-DGGML_CUDA=ON",
            "-DCMAKE_CUDA_COMPILER=" + os.path.join(CUDA, "bin", "nvcc.exe"),
            "-DCMAKE_CUDA_HOST_COMPILER=" + os.path.join(MSVC, "bin", "Hostx64", "x64", "cl.exe"),
            "-DCUDAToolkit_ROOT=" + CUDA,
            "-DCMAKE_CUDA_ARCHITECTURES=89",
            "-DGGML_CUDA_FA_QUANTS=q4_0-q4_0,q8_0-q8_0,f16-f16,bf16-bf16,q8_0-q4_0",
            "-DGGML_CCACHE=OFF", "-DLLAMA_CURL=OFF"]
else:
    target = sys.argv[2] if len(sys.argv) > 2 else "llama-server"
    args = [CMAKE, "--build", BLD, "--target", target, "-j", "2"]

r = subprocess.run(args, capture_output=True, text=True, errors="replace", env=env, timeout=5400)
print("exit", r.returncode)
print((r.stdout or "")[-4000:])
if r.returncode != 0:
    print("STDERR", (r.stderr or "")[-4000:])
