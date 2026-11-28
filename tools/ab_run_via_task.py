# -*- coding: utf-8 -*-
"""通过计划任务跑 A/B 实验（绕过沙箱 CPU 限速，降低冻死率）

项目记忆：沙箱派生进程被 CPU 限速；测真实速度/长跑实验应走计划任务。

用法（PowerShell 管理员）:
  $action = New-ScheduledTaskAction -Execute 'D:\Python\python.exe' -Argument '-B D:\Brain\publish\dsh-behavior-guard\tools\ab_randomized_runner.py 78 20261128b --append'
  $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(10)
  Register-ScheduledTask -TaskName ABExperiment -Action $action -Trigger $trigger -Force
  Start-ScheduledTask -TaskName ABExperiment
"""
# 这个模块只做说明；实际执行直接调 runner（由计划任务的 Argument 指定）
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ab_randomized_runner import main

if __name__ == '__main__':
    main()
