Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = scriptDir
shell.Environment("PROCESS")("HANA_GUI_HIDE_CONSOLE") = "1"

venvPythonw = fso.BuildPath(scriptDir, ".venv\Scripts\pythonw.exe")

If fso.FileExists(venvPythonw) Then
    shell.Run Chr(34) & venvPythonw & Chr(34) & " -m src.gui.hana_gui --hide-console", 0, False
Else
    shell.Run "pyw.exe -3 -m src.gui.hana_gui --hide-console", 0, False
End If
