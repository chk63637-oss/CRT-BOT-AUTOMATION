Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\chk63\Downloads\CRT_Bot_Python\crt_bot"
WshShell.Run "pythonw.exe main.py", 0, False
