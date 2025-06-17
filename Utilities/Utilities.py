import io, os, ctypes, time, typing, subprocess, re
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


class ReplaceAutoFunctions:
    typeAtStartRegex = r"(\s*[^\s]+[\w\d]*)(?=.*)"
    genericTypeRegex = r"(?:<)(.*)(?=>)"
    
    @staticmethod
    def RegexTryReplaceTemplateT(inputLine, referenceSymbol):
        genericMatch = re.search(ReplaceAutoFunctions.genericTypeRegex, referenceSymbol)
        if (genericMatch):
            return inputLine.replace("auto", genericMatch.group(1).strip())
        return ""
    
    @staticmethod
    def RegexTryReplaceRegular(inputLine, referenceSymbol):
        typeMatch = re.search(ReplaceAutoFunctions.typeAtStartRegex, referenceSymbol)
        if (typeMatch):
            print(typeMatch.group(1))
            return inputLine.replace("auto", typeMatch.group(1).strip())
        return ""

    @staticmethod
    def SubstituteTypeFromIndexedAccess(inputLine, referenceSymbol):
        #TODO: Fails in cases where we index ito a generic type 
        genericReplace = ReplaceAutoFunctions.RegexTryReplaceTemplateT(inputLine, referenceSymbol)
        if (genericReplace != ""):
            return genericReplace
        #if we didnt make template T match, try regular variable match
        variableReplace = ReplaceAutoFunctions.RegexTryReplaceRegular(inputLine, referenceSymbol)
        if (variableReplace != ""):
            return variableReplace
        return "" 
    
    #Strip comments from the definition
    @staticmethod
    def GetDefinitionBody(referenceDef):
        print (f"refdef {referenceDef}")
        if (referenceDef == ""):
            return
        nonCommentDefs = [line for line in referenceDef.splitlines() if not any(line.startswith(x) for x in [r"//",r"*"])]
        realDef = next(l for l in nonCommentDefs if re.search(r"\w+", l, re.MULTILINE))
        return realDef


    #Parses what we're actually assigning by walking -> and . until the last one
    #Then returns the offset index/x line position
    @staticmethod
    def PushIndexToCorrectSymbol(inputLines, x, y):
        xOffset = 0
        yOffset = -1
        lastMatchY = -1
        inputLines[0] = inputLines[0][x:] #we only want to scan the rhs of the first line
        print(inputLines)
        for line in inputLines:
            yOffset += 1
            if yOffset == 0:
                pattern = r"((\-\>)|(\.))" 
            else:
                pattern = r"(\-\>)|(\.)|([^\S\r\n]+)" #Also search whitespace (with weird double negative regex syntax) 
                                                    #TODO: Can simplify -- this case is only LEAIDNG whitespace, so we could handle it at accumulate lines
            print(f"index search: {line}")
            splitByAccess = re.finditer(pattern, line)
            splitarr = [s for s in splitByAccess]
            if (splitarr == []): #empty iterator
               continue 
            lastSplit = splitarr[-1]
            print(lastSplit)
            lastMatchY = yOffset
            xOffset = lastSplit.end()
        if (lastMatchY < 1):
            print("one line case")
            return (x + xOffset, y) #We only read one line -- offset x relative to the rhs
        else:
            print("multi line case")
            return (xOffset, y + lastMatchY) #we read multiple lines -- xy are line coords for 10x
            
    
    #Read multiple lines to find our symbol
    def AccumulateLines(inputLine, x, y):
        openParenCt = 0 
        closeParenCt = 0
        amAtEnd = False 
        lines = []
        lines.append(inputLine)
        line = inputLine[x:] #start scanning from the rhs, so closeparen check works if we're in a loop def
        lineidx = y
        ct = 0
        while(True):
            if (";" in line):
                break 
            openParenCt += len(re.findall(r"\(", line))
            closeParenCt += len(re.findall(r"\)", line))
            if (closeParenCt > openParenCt):
                break
            lineidx += 1
            ct += 1
            line = Editor.GetLine(lineidx)
            lines.append(line)
            if (ct > 200):
                print("error")
                return
        print(len(lines))
        print(lines)
        return lines
    
#TODO: Need to also handle functions
#Replace auto keyword, sloppily. Works in the easy cases -- silently does the wrong thing in some cases
def ReplaceAuto_WIP():
    x, y = Editor.GetCursorPos(0)
    targetLine = y
    symbol = Editor.GetSymbolDefinition((x,y))
    line = Editor.GetLine(y)
    if ("auto" in line):
        pattern = r"[=:][\s*]"
        #find the : or = assignment character
        match = re.search(pattern, line)
        if (match):
            x = match.end()
            #Find the symbol 
            x, y = ReplaceAutoFunctions.PushIndexToCorrectSymbol(ReplaceAutoFunctions.AccumulateLines(line,x ,y), x,y)
            referenceSymbol =  ReplaceAutoFunctions.GetDefinitionBody(Editor.GetSymbolDefinition((x,y)))
            #Replace auto with something from the symbol definition
            #TODO This foreach/equals case separation is bad -- parse properly
            if (':' in match.group()):
                #Foreach case 
                foreachReplace = ReplaceAutoFunctions.SubstituteTypeFromIndexedAccess(line, referenceSymbol)
                if (foreachReplace != ""):
                    print(foreachReplace)
                    Editor.SetLine(targetLine, foreachReplace)
                    return 
            if ('=' in match.group()):
                #Equals case
                variableReplace = ReplaceAutoFunctions.RegexTryReplaceRegular(line, referenceSymbol)
                if (variableReplace != ""):
                    print(variableReplace)
                    Editor.SetLine(targetLine, variableReplace)
                    return
                
            
        
    

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

