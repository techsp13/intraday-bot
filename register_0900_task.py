import subprocess

ps_script = """
$Action = New-ScheduledTaskAction -Execute 'python' -Argument 'main.py --top2' -WorkingDirectory 'C:\\Users\\ASUS\\.gemini\\antigravity\\scratch\\intraday-bot'
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 09:00AM
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName 'NSE_Intraday_Bot_0900' -Action $Action -Trigger $Trigger -Settings $Settings -Force
"""

res = subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True)
print("TASK REGISTRATION STATUS:")
print("Stdout:", res.stdout)
print("Stderr:", res.stderr)
