import io, os, ctypes, time, typing, subprocess
from N10X import Editor

#This alters an autocomplete behavior where open paranethesees 
#Are added even if the next character after the autocompletion range is "<"
#This is annoying if you're changing a generic function call to another generic function call.

#IE, if you edit: 
# "MyFoo<T>()"
# And use autocomplete to replace it with a call to
# "MyBar<T>()" 
# Autocomplete will insert this behavior: 
# "MyBar(<T>()" 

#Irritating! This code works around the trivial case, where < is the next char on the same line.
#Reported the issue at https://github.com/slynch8/10x/issues/3272
class AutoBracketsTemplateWorkaround:

	#Watch for autocomplete and set a global flag 
	@staticmethod
	def WatcAutoComplete(key, s, c, a):
		global gQueueBracketsFix
		if (Editor.IsShowingAutocomplete() and
		key == 'Enter'): #My autocompelete key
			gQueueBracketsFix = True 
		
	#Apply my workaround
	@staticmethod
	def Wokaround(key, __s, __c, __a):
		global gQueueBracketsFix
		#Early out on most keypresses
		#Reset flag when we enter body
		if not gQueueBracketsFix:
			return
		gQueueBracketsFix = False
		cursorCt = Editor.GetCursorCount()
		for c in range(cursorCt):
			x, y = Editor.GetCursorPos(c)
			line = Editor.GetLine(y)
			#left (inclusive) and right (exclusive) of cursor
			substrLhs = line[:x]
			substrRhs = line[x:]
			charBeforeCursor = substrLhs[-1]
			#If we just inserted a '(' before a '<
			if (charBeforeCursor == '(' and 
			substrRhs.lstrip()[0] == "<"):
				#Replace the line
				newStr = substrLhs[:-1] + substrRhs
				Editor.SetLine(y, newStr)
				#Note: This adds an undo step for setting the line
				#Not sure if it's annoying or desirable -- leaving in for now


global gQueueBracketsFix
gQueueBracketsFix = False 

Editor.AddOnPostKeyFunction(AutoBracketsTemplateWorkaround.Wokaround) 
Editor.AddOnInterceptKeyFunction(AutoBracketsTemplateWorkaround.WatcAutoComplete)