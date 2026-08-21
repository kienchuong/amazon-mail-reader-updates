Option Explicit

Dim shell, fso, baseDir, dataRoot, pythonw, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
dataRoot = fso.GetParentFolderName(fso.GetParentFolderName(baseDir))
pythonw = fso.BuildPath(dataRoot, "runtime\amazon-mail-reader\Scripts\pythonw.exe")

If fso.FileExists(pythonw) Then
  command = Chr(34) & pythonw & Chr(34) & " " & Chr(34) & fso.BuildPath(baseDir, "app.py") & Chr(34)
  shell.Run command, 0, False
Else
  shell.Popup "Khong tim thay runtime cua Amazon Mail Reader: " & pythonw, 0, "Amazon Mail Reader", 16
End If
