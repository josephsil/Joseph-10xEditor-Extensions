import io, os, time, subprocess, re
from collections import deque
from N10X import Editor

# Minimal raddbg integration for 10x editor. 
# Inspired by "RemedyBG debugger integration for 10x (10xeditor.com) Original Script author: septag@discord / septag@pm.me"
# Place in your 10x\PythonScripts folder to run

# Does not tightly integrate raddbg to 10x (10x doesn't know when breakpoints are hit), but supports launch debugger, updating breakpoints, stop debugger, etc

# The SendRaddbgCommand(str) command can be used in 10x to send an arbitrary command to raddbg
# Example usage:
# raddbg: true  #Enable the plugin  
# raddbgPath: "C:/my_install_path/raddbg.exe" #Defaults to 'raddbg.exe' if not set  
# raddbgAlwaysOverrideBreakpointsOnLaunch: false #Overwrite workspace breakpoints with breakpoints from 10x when launching the debugger
# raddbgPushBreakPointUpdates: false  #Mirror breakpoint remove/add actions from 10x to raddbg 
# raddbgProjectPath: "./MyraddbgProject" #Specify a workspace name (relative to the project) to pass to raddbg

class RADBG_Options():
    def __init__(self):
        self.enabled = Editor.GetSetting("raddbg").strip()
        if not self.enabled: 
            return
        self.executable = Editor.GetSetting("raddbgPath").strip()
        if not self.executable:
            self.executable = 'raddbg.exe'
        if os.path.isdir(self.executable):
            self.executable = os.path.join(self.executable, 'daddbg.exe')

        self.workspace = Editor.GetSetting("raddbgProjectPath").strip()
        overridebreakpointsstr = Editor.GetSetting("raddbgAlwaysOverrideBreakpointsOnLaunch").strip()
        self.pushBreakPoints = Editor.GetSetting("raddbgPushBreakPointUpdates").strip()
        self.syncBreakpointUpdatesRTo10x = Editor.GetSetting("_").strip()
        self.overrideBreakpoints =  overridebreakpointsstr.lower() == 'true'


class RADBG_Session:
    def __init__(self):
        self.process:subprocess.Popen = None
        self.commandQueue = deque()
        self.queuesize = 0

    def StartDebuggingradbgSession(self, argtgt, argcwd, executable, project):
        global RADBG_pid

        if (self.process != None and self.process.poll() is None): #Process already exists -- just send run 
            self.PushIPC("run")
            return
        
        projectArgs = ""
        if (project != ""):
            projectArgs = f" --project:{project}"
        args = f"{executable} {projectArgs} --auto_run {argtgt}" #Auto run target
      
        print(args)
        self.process = subprocess.Popen(args, cwd=argcwd)
        RADBG_pid = self.process.pid
        Editor.OnDebuggerStarted()

    def stop(self):
        global gradbgSession
        self.update() #final update to clean up 
        self.process.kill()
        Editor.OnDebuggerStopped()
        
        gradbgSession = None

    def PushIPC(self, _str):
        debug_cwd = Editor.GetDebugCommandCwd().strip()
        executable = "C:/Users/supsu/raddbg/raddbg.exe"
        args =executable + " " + "--ipc" + " " + ' '.join('"'+s+'"' for s in _str.split(' ')) #Need to wrap ipc args in quotes 
        print(args)
        print(debug_cwd)
        
        #Push ipc commands to batch
        self.commandQueue.append((args, debug_cwd))
        self.queuesize += 1
    
    #Run batched ipc commands
    def update(self):
        while(self.queuesize != 0):
            command = self.commandQueue.popleft()
            print(f"dqd {command[0]}")
            self.queuesize -= 1
            proc = subprocess.Popen(command[0], cwd=command[1])
            while(proc.poll() is None): #Wait for our command to exit
                time.sleep(1 / 10000)



def OverwriteRADBGBreakPoints():
    RadgbFunctions.QueueCommand("clear_breakpoints")
    points = Editor.GetBreakpoints()
    for bp in points:
        AddBreakpoint(bp[0], bp[1], bp[2])

def SendRaddbgCommand(str):
    RadgbFunctions.QueueCommand(str)

def radDbgGoToCursors():
    file = Editor.GetCurrentFilename()
    for i in range(Editor.GetCursorCount()):
        cursor = Editor.GetCursorPos(i)
        x, y = cursor
        RadgbFunctions.QueueCommand(f"find_code_location {file}:{y+1}:{x+1}")
        #note: column doesnt seem to work

class RadgbFunctions:

    @staticmethod
    def SessionIsActive(session):
        return session is not None and session.process.poll() is None

    @staticmethod 
    def StartDebugging(cmd, cwd, path, workspace):
        global gradbgSession
        if not RadgbFunctions.SessionIsActive(gradbgSession): #start a new session
            gradbgSession = RADBG_Session()
        gradbgSession.StartDebuggingradbgSession(cmd, cwd, path, workspace)

    @staticmethod 
    def StopDebugging():
        global gradbgSession
        if gradbgSession is None:
            return 
        gradbgSession.PushIPC("kill_all")  
        gradbgSession.PushIPC("exit")   
        gradbgSession.stop()

    @staticmethod 
    def QueueCommand(ipcarg):
        global gradbgSession
        if gradbgSession is None:
            return
        gradbgSession.PushIPC(ipcarg)

class X10Commands():
    @staticmethod
    def StartDebugging(): 
        global gRestarting
        global gOptions

        #If we're restarting, don't launch the debugger, but do the other setup work
        if gRestarting:
            gRestarting = False 
        else:
            RadgbFunctions.StartDebugging(
                Editor.GetDebugCommand().strip(), 
                Editor.GetDebugCommandCwd().strip(),
                gOptions.executable, gOptions.workspace)

        if gOptions.overrideBreakpoints:
            OverwriteRADBGBreakPoints() 

        radDbgGoToCursors()

    @staticmethod
    def StopDebugging():
        global gRestarting
        if gRestarting:
            return #Swallow the stop debbugging command which follows restart
        RadgbFunctions.StopDebugging()
        Editor.OnDebuggerStopped()

    @staticmethod
    def RestartDebugging():
        global gRestarting
        global gradbgSession
        #If we don't have an existing session, start
        if (gradbgSession is None or gradbgSession.process.poll() != None):
            print("Restart with no connection")
            #10x will fire the Stop and Start events on its own right after restart debugging 
            #So we can get the desired result by no-opping here
            return
        #If we have an existing session, restart, and suppress the 10x Start and Stop events using gRestarting
        gRestarting = True
        RadgbFunctions.QueueCommand("restart")

    @staticmethod
    def AddBreakpoint(id, filename, line):
        global suppressBreakpoints
        global gOptions
        if suppressBreakpoints:
            return 
        if gOptions.pushBreakPoints:
                RadgbFunctions.QueueCommand(f"add_breakpoint {filename}:{line}")

    @staticmethod
    def RemoveBreakpoint(id, filename, line):
        global suppressBreakpoints
        global gOptions
        if suppressBreakpoints:
            return 
        if gOptions.pushBreakPoints:
                RadgbFunctions.QueueCommand(f"toggle_breakpoint {filename}:{line}")

def Update():
    global gradbgSession
    global gOptions
    global RADBG_lostConnectionPollCounter
    global gRestarting
    if gradbgSession is None:
        return
    gradbgSession.update() 
    if RADBG_lostConnectionPollCounter == 0: #only update every 32 frames
        if gRestarting:
            return #don't do this during restart
        if gradbgSession.process.poll() != None:
            print("Lost connection to radDBG.exe")
            Editor.OnDebuggerStopped() #We lost the debugger 
            gradbgSession = None
            return
    # if gOptions.syncBreakpointUpdatesRTo10x:
        # WatchWorkspace()

    RADBG_lostConnectionPollCounter = (RADBG_lostConnectionPollCounter + 1) % 6 #only update every 6 frames
    

def nop():
    return

def InitializeRaddbg():
    global gRestarting
    global suppressBreakpoints
    global gOptions
    global gBreakpoints

   

    gOptions = RADBG_Options()
    if not gOptions.enabled:
        return

    gBreakpoints = []
    gRestarting = False
    suppressBreakpoints = False
    
    Editor.AddBreakpointAddedFunction(X10Commands.AddBreakpoint)
    Editor.AddBreakpointRemovedFunction(X10Commands.RemoveBreakpoint)
    Editor.AddBreakpointUpdatedFunction(nop)
    Editor.AddStartDebuggingFunction(X10Commands.StartDebugging)
    Editor.AddStopDebuggingFunction(X10Commands.StopDebugging)
    Editor.AddRestartDebuggingFunction(X10Commands.RestartDebugging)
    Editor.AddUpdateFunction(Update)
    
    Editor.OverrideSetting('VisualStudioSync', 'false')
   

gradbgSession:RADBG_Session = None
RADBG_pid = None 
RADBG_lostConnectionPollCounter = 0
Editor.CallOnMainThread(InitializeRaddbg)

