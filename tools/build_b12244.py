# -*- coding: utf-8 -*-
"""手工注入 MSVC 环境后调用 CMake/Ninja 构建 llama-server（沙箱里 cmd.exe 被拦）。

用法: python bench/build_b12244.py configure|build

根治（2026-11-27）：
  1. SRC 自动探测（旧 D:\\llama-b12244-src 已失效 → D:\\Brain\\engine\\llama-b12244-src）
  2. configure 前自动幂等打 autoparser 空白补丁（函数体限定 + fail-fast）
     ——消除"每次升级重打"的人工步骤
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

# SRC 自动探测：优先环境变量，其次已知路径
SRC_CANDIDATES = [
    os.environ.get('LLAMA_SRC', ''),
    r"D:\Brain\engine\llama-b12244-src",
    r"D:\llama-b12244-src",
]
SRC = next((p for p in SRC_CANDIDATES if p and os.path.isdir(p)), None)
if not SRC:
    print("FATAL: llama source not found. Set LLAMA_SRC env var. Candidates:")
    for p in SRC_CANDIDATES: print("  ", p)
    sys.exit(2)
BLD = os.path.join(SRC, "build")


def ensure_autoparser_patch():
    """幂等应用 autoparser 空白补丁；按函数体限定，避免误改 build_tool_parser。"""
    src_file = os.path.join(SRC, "common", "chat-auto-parser-generator.cpp")
    if not os.path.isfile(src_file):
        # 老版本可能在 src/common/ 下
        alt = os.path.join(SRC, "src", "common", "chat-auto-parser-generator.cpp")
        if os.path.isfile(alt): src_file = alt
        else:
            print("WARN autoparser source not found, skip patch:", src_file)
            return "skip"
    s = open(src_file, encoding="utf-8", errors="replace").read()

    # 定位 build_tool_parser_tag_tagged 函数体（只在这个函数内改）
    fn_marker = "build_tool_parser_tag_tagged"
    fn = s.find(fn_marker)
    if fn < 0:
        print("FAIL autoparser: function marker not found (upstream refactor?)")
        sys.exit(3)
    head, tail = s[:fn], s[fn:]

    new1 = "p.optspace(format.per_call_start)"
    new2 = "p.until(trim_whitespace(trigger_marker))"
    old1 = "format.per_call_start + p.space()"
    old2 = "p.until(trigger_marker)"

    if new1 in tail and new2 in tail:
        return "already-applied"

    # fail-fast：目标漂移就报错，不静默跳过
    if old1 not in tail or old2 not in tail:
        print("FAIL autoparser: patch targets drifted (upstream changed). "
              "old1=%s old2=%s" % (old1 in tail, old2 in tail))
        sys.exit(3)

    tail = tail.replace(old1, new1, 1)
    tail = tail.replace(old2, new2, 1)
    open(src_file, "w", encoding="utf-8", newline="").write(head + tail)
    return "applied"


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
    print("SRC =", SRC)
    st = ensure_autoparser_patch()
    print("autoparser patch:", st)
    args = [CMAKE, "-S", SRC, "-B", BLD, "-G", "Ninja",
            "-DCMAKE_BUILD_TYPE=Release",
            "-DCMAKE_C_COMPILER=" + os.path.join(MSVC, "bin", "Hostx64", "x64", "cl.exe"),
            "-DCMAKE_CXX_COMPILER=" + os.path.join(MSVC, "bin", "Hostx64", "x64", "cl.exe"),
            "-DGGML_CUDA=ON",
            "-DCMAKE_CUDA_COMPILER=" + os.path.join(CUDA, "bin", "nvcc.exe"),
            # nvcc 默认靠注册表探测 MSVC，沙箱里 reg.exe 被拦；显式给 host 编译器即可绕开
            "-DCMAKE_CUDA_HOST_COMPILER=" + os.path.join(MSVC, "bin", "Hostx64", "x64", "cl.exe"),
            "-DCUDAToolkit_ROOT=" + CUDA,
            "-DCMAKE_CUDA_ARCHITECTURES=89",
            # 必须显式包含 q8_0-q4_0：生产 KV 是 K=q8_0 / V=q4_0，缺这个组合会在运行期
            # 把 K/V 转成 f16 再算（日志每层刷 converting），解码从 ~24 掉回 ~17。
            "-DGGML_CUDA_FA_QUANTS=q4_0-q4_0,q8_0-q8_0,f16-f16,bf16-bf16,q8_0-q4_0",
            "-DGGML_CCACHE=OFF", "-DLLAMA_CURL=OFF"]
else:
    target = sys.argv[2] if len(sys.argv) > 2 else "llama-server"
    args = [CMAKE, "--build", BLD, "--target", target, "-j", "10"]

r = subprocess.run(args, capture_output=True, text=True, errors="replace", env=env, timeout=5400)
print("exit", r.returncode)
print((r.stdout or "")[-4000:])
if r.returncode != 0:
    print("STDERR", (r.stderr or "")[-4000:])
