Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File " & Chr(34) & scriptDir & "\Start-DCS-AI-Copilot.ps1" & Chr(34)
exitCode = shell.Run(command, 0, True)
If exitCode <> 0 Then
    MsgBox "AI Copilot kunde inte starta. Se senaste start-loggen i " & scriptDir & "\.runtime", 16, "DCS AI Copilot"
End If
