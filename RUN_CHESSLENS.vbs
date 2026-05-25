Option Explicit

Dim oShell, oFSO, sDir, sPythonW, sBase, aVers, v, sCandidate, sCmd, q

Set oShell = CreateObject("WScript.Shell")
Set oFSO   = CreateObject("Scripting.FileSystemObject")
sDir = oFSO.GetParentFolderName(WScript.ScriptFullName)
q    = Chr(34)

' ── Find pythonw ──────────────────────────────────────────────────────────
sPythonW = ""

If oShell.Run("where pythonw", 0, True) = 0 Then
    sPythonW = "pythonw"
End If

If sPythonW = "" Then
    If oShell.Run("where pyw", 0, True) = 0 Then
        sPythonW = "pyw"
    End If
End If

If sPythonW = "" Then
    sBase  = oShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\"
    aVers  = Array("Python314", "Python313", "Python312", "Python311", "Python310")
    For Each v In aVers
        sCandidate = sBase & v & "\pythonw.exe"
        If oFSO.FileExists(sCandidate) Then
            sPythonW = sCandidate
            Exit For
        End If
    Next
End If

If sPythonW = "" Then
    MsgBox "Python not found." & vbCrLf & "Install Python 3.10+ from https://www.python.org/downloads/", _
           vbCritical, "ChessLens"
    WScript.Quit 1
End If

' ── Launch silently (window style 0 = hidden, bWaitOnReturn = False) ──────
sCmd = q & sPythonW & q & " " & q & sDir & "\main.py" & q
oShell.CurrentDirectory = sDir
oShell.Run sCmd, 0, False
