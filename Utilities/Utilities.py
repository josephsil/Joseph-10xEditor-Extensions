import io, os, ctypes, time, typing, subprocess
from N10X import Editor

def Launch_Powershell(args = ""):
    global proc 
    cwd = Editor.GetDebugCommandCwd().strip()
    if (proc is None or proc.poll() is None):
        proc = subprocess.Popen("powershell.exe" + f" {args}",  cwd=cwd)


def TogglePreviousTab():
    global _prev_toggle
    global _expect_focus_change
    global _expect_focus_change_time
    _expect_focus_change = True
    _expect_focus_change_time = time.time_ns()
    Editor.FocusFile(_prev_toggle)
    Editor.AddUpdateFunction(PreviousTabFunctions.ExpectFocusChangeHandler)
    
class PreviousTabFunctions:
    @staticmethod 
    def ExpectFocusChangeHandler():
        global _prev_toggle
        global _expect_focus_change
        global _expect_focus_change_time
        if not _expect_focus_change:
            #done 
            Editor.RemoveUpdateFunction(PreviousTabFunctions.ExpectFocusChangeHandler)
            return
        if (time.time_ns() - _expect_focus_change_time > 6* 100000): #3ms timeout
            #We are expecting a focus change which never came. 
            #Fallback methods
            _expect_focus_change = False
            if (_prev_toggle != ""):
                #File probably isn't open
                Editor.OpenFile(_prev_toggle)
            if (_prev_toggle == ""):
                #We probably have a non-file panel set 
                Editor.ExecuteCommand("PrevPanelTab")

    @staticmethod 
    def ToggleStoreLast():
        global _prev_toggle
        global _expect_focus_change
        if _expect_focus_change:
            _expect_focus_change = False
        _prev_toggle = Editor.GetCurrentFilename()

    @staticmethod 
    def InitializeTogglePrevious():
        Editor.AddOnFileLosingFocusFunction(PreviousTabFunctions.ToggleStoreLast)

#powershell command setup
global proc  
proc = None

#Toggle last command setup
global _prev_toggle
global _expect_focus_change
global _expect_focus_change_time
_prev_toggle = ""
_expect_focus_change = False
Editor.CallOnMainThread(PreviousTabFunctions.InitializeTogglePrevious)
