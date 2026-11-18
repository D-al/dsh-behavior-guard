# -*- coding: utf-8 -*-
"""verify_agent —— 独立验收角色（2604.11465 的 inference-time 纠正器思路）

依据：
  - 三角色编排（arXiv 2604.11465）：同一冻结模型分饰三角（总结/主agent/独立纠正），
    纠正器**看不到对话历史**以打破"重复失败循环"；AppWorld 上 8B 脚手架后超过 33B。
  - claudelab 实战：独立验收员消除作者偏差（同一模型自查自己写的代码会放水）。
  - Q4@0.7 曾出现 1/3 假完成（把文件内容贴正文、不调 write 就宣布完成）——
    独立验收是该缺陷的环境级判定（对应守卫 L1 的"verified finish"思路）。

用法：
  python verify_agent.py <产物路径> "<验收标准>" [--json]
  退出码: 0=PASS, 1=FAIL, 2=基础设施错误

原理：第二次独立调用（无对话历史、temperature=0），只看产物与标准。
"""
import sys, json, urllib.request, os

BASE = "http://127.0.0.1:8081"
MAX_PRODUCT_CHARS = 4000

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    as_json = '--json' in sys.argv
    if len(args) < 2:
        print(__doc__)
        sys.exit(2)
    path, criteria = args[0], args[1]

    # 产物读取（文本；不存在 = 直接 FAIL，这也是验收的一部分）
    if not os.path.exists(path):
        verdict, reason = "FAIL", "产物文件不存在: %s" % path
    else:
        try:
            body = open(path, encoding='utf-8', errors='replace').read()
        except Exception as e:
            body = ""
            verdict, reason = "FAIL", "产物读取失败: %s" % e
        else:
            truncated = len(body) > MAX_PRODUCT_CHARS
            if truncated:
                body = body[:MAX_PRODUCT_CHARS] + "\n…[重要：产物在此处被截断！全文共 %d 字符，你只能看到前 %d。标准涉及的内容若尚未出现，不代表它不存在于全文。]" % (len(body), MAX_PRODUCT_CHARS)
            prompt = (
                "你是独立验收员。你没有参与产生以下产物，请只依据产物本身与验收标准判定。\n"
                "验收标准：%s\n\n"
                "产物内容（来自 %s）：%s\n\n"
                "判定规则（按顺序执行）：\n"
                "1. 若产物含「[重要：产物在此处被截断」标记，且标准涉及的内容尚未在已展示部分出现，"
                "必须输出 INCONCLUSIVE——禁止凭部分内容否定全文。\n"
                "2. 已展示的证据足以支持达标 → 输出 PASS。\n"
                "3. 已展示的证据足以支持不达标（如文件不存在、明确缺失且无截断）→ 输出 FAIL。\n"
                "输出格式（严格遵守，共两行）：第一行 PASS 或 FAIL 或 INCONCLUSIVE；第二行一句话理由。"
            ) % (criteria, path, body)
            req = urllib.request.Request(
                BASE + "/v1/chat/completions",
                data=json.dumps({
                    "model": "Qwen3.6-35B-A3B-UD-Q4_K_XL",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 3000, "temperature": 0.0, "top_k": 1,
                }).encode('utf-8'),
                headers={"Content-Type": "application/json"})
            try:
                resp = json.loads(urllib.request.urlopen(req, timeout=600).read())
            except Exception as e:
                print("验收调用失败: %s" % e)
                sys.exit(2)
            out = (resp["choices"][0]["message"].get("content") or "").strip()
            first = out.splitlines()[0].strip().upper() if out else ""
            verdict = "PASS" if first.startswith("PASS") else "FAIL"
            if "INCONCLUSIVE" in first:
                verdict = "INCONCLUSIVE"
            reason = out.splitlines()[1].strip() if len(out.splitlines()) > 1 else out[:100]

    if as_json:
        print(json.dumps({"verdict": verdict, "reason": reason, "product": path},
                         ensure_ascii=False))
    else:
        print("[%s] %s" % (verdict, reason))
    sys.exit(0 if verdict == "PASS" else 1)

if __name__ == "__main__":
    main()
