# -*- coding: utf-8 -*-
"""计划任务专用入口：参数写死，避免任务参数解析问题。
改 rounds/seed 时直接编辑本文件。
"""
import sys, os
ROOT = r'D:/Brain/publish/dsh-behavior-guard'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
os.chdir(ROOT)

# 构造 sys.argv 让 runner.main() 读取
sys.argv = ['ab_randomized_runner.py', '78', '20261129', '--append']

from ab_randomized_runner import main
main()
