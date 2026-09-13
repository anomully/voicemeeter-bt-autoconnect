' Launches bt_switcher.py with no console window.
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
CreateObject("WScript.Shell").Run "pythonw.exe """ & scriptDir & "\bt_switcher.py""", 0, False
