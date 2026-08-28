import subprocess

ps_script = """
Unregister-ScheduledTask -TaskName 'NSE_Intraday_Bot_Morning' -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName 'NSE_Intraday_Bot_0845' -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName 'NSE_Intraday_Bot_0900' -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName 'NSE_Intraday_Bot_Picks' -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName 'NSE_Intraday_Bot' -Confirm:$false -ErrorAction SilentlyContinue
"""

res = subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True)
print("LOCAL TASK SCHEDULER CLEANUP COMPLETED.")
