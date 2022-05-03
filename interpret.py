
import xml.etree.ElementTree as ET
import re
import pprint
import copy
import sys

####################################
######GLOBALS AND CONSTANTS#########
####################################

orderlist = []
opcodelist = [
	"CREATEFRAME", "PUSHFRAME", "POPFRAME", "RETURN", "BREAK", "DEFVAR",
	"POPS", "CALL", "LABEL", "JUMP", "PUSHS", "WRITE", "EXIT", "DPRINT",
	"MOVE", "INT2CHAR", "STRLEN", "TYPE", "READ", "ADD", "SUB", "MUL",
	"IDIV", "LT", "GT", "EQ", "AND", "OR", "NOT", "STRI2INT", "CONCAT",
	"GETCHAR", "SETCHAR", "JUMPIFEQ", "JUMPIFNEQ"]
opcodes_0 = ["CREATEFRAME", "PUSHFRAME", "POPFRAME", "RETURN", "BREAK"]
opcodes_v = ["DEFVAR", "POPS"]
opcodes_l = ["CALL", "LABEL", "JUMP"]
opcodes_s = ["PUSHS", "WRITE", "EXIT", "DPRINT"]
opcodes_vs = ["MOVE", "INT2CHAR", "STRLEN", "TYPE", "NOT"]
opcodes_vt = ["READ"]
opcodes_vss_arr = ["ADD", "SUB", "MUL", "IDIV"]
opcodes_vss_cmp = ["LT", "GT", "EQ"]
opcodes_vss_log = ["AND", "OR"]
opcodes_vss_other = ["STRI2INT", "CONCAT", "GETCHAR", "SETCHAR"]
opcodes_lss = ["JUMPIFEQ", "JUMPIFNEQ"]
labeldict = dict()
labels_jumped = set()
prg = dict()
vardict = dict()
pat_var = r"""^[gltGLT][fF]@[a-zA-z_\-$&%*!?][0-9a-zA-z_\-$&%*!?]*$"""
pat_int = r"""^[+-]?(([1-9][0-9]*)|(0[bB][10]*)|(0[xX][0-9a-fA-F]*)|(0[0-7]*))$"""
pat_bool = r"""^(true|false)$"""
pat_string = r"""^[^\x00-\x20\x23]*$""" # exclude ascii 0-32, 35, include 92 because esc seqs
pat_nil = r"""nil"""
pat_label = r"""^[a-zA-z_\-$&%*!?][0-9a-zA-z_\-$&%*!?]*$"""
pat_type = r"""^(int|string|bool)$"""
pat_escape_invalid = r"""\\(?![0-9]{3}).{0,3}"""
pat_escape_valid = r"""\\[0-9]{3}"""

####################################
############FUNCTIONS###############
####################################

def printhelp():
	print('This is ippcode22 interpreter')
	print('Run with:')
	print('python3 interpret.py [args]')
	print('Args:')
	print('--source=<file> :: --source is the xml representation of code to run and must follow specification')
	print('--input=<file> :: --input is input for READ instructions of said code and can be arbitrary')
	print('--help :: Prints this and exits, overrides all other args')
	print('At least one of --source or --input must be present')
	print('If only one is present, the other is read from stdin')

def eprint(ecode, errstr):
	'''
	Error print
	'''
	print("Error:", errstr, file=sys.stderr)
	exit(ecode)

def check_order(instr):
	'''
	Checks that 'order' xml attribute exists and is a positive number
	'''
	try:
		currorder = int(instr.get('order'))
	except (ValueError, TypeError):
		try:
			lastvalid = orderlist[-1]
		except IndexError:
			lastvalid = None
		eprint(32, f'Missing or invalid instruction order: {instr.get("order")}\nLast valid: {lastvalid}')
	else:
		if currorder >= 0:
			orderlist.append(currorder)
		else:
			eprint(32, f"Negative instruction order: {currorder}")

def check_opcode(instr):
	'''
	Checks that 'opcode' xml attribute exists and is valid
	'''
	try:
		opcoder = instr.get('opcode')
		opcode = opcoder.upper()
	except AttributeError:
		eprint(32, f"Invalid or missing opcode at order {instr.get('order')}")
	else:
		if opcode not in opcodelist:
			eprint(32, f"Invalid opcode at order {instr.get('order')}: {opcoder}")

def check_args_cnt(instr):
	'''
	Checks the number of args an instruction has
	'''
	opcode = instr.get('opcode').upper()
	argcnt = len(list(instr))
	if opcode in opcodes_0:
		if argcnt != 0:
			eprint(53, f"Incorrect number of ars for {opcode} at order {instr.get('order')} (got {argcnt}, expected 0)")
	elif opcode in opcodes_v + opcodes_l + opcodes_s:
		if argcnt != 1:
			eprint(53, f"Incorrect number of args for {opcode} at order {instr.get('order')} (got {argcnt}, expected 1)")
	elif opcode in opcodes_vs + opcodes_vt:
		if argcnt != 2:
			eprint(53, f"Incorrect number of args for {opcode} at order {instr.get('order')} (got {argcnt}, expected 2)")
	elif opcode in opcodes_vss_arr + opcodes_vss_cmp + opcodes_vss_log + opcodes_vss_other + opcodes_lss:
		if argcnt != 3:
			eprint(53, f"Incorrect number of args for {opcode} at order {instr.get('order')} (got {argcnt}, expected 3)")
	else:
		# should be a dead branch
		eprint(99, f"Failed to check argcnt for {opcode} at order {instr.get('order')}")

def check_args_types(instr):
	'''
	Switch that decides how to call individual argument checks 
	based on instruction subgroup
	'''
	opcode = instr.get('opcode').upper()
	if opcode in opcodes_0:
		return
	elif opcode in opcodes_v:
		check_arg_regex('v', instr[0], opcode)
	elif opcode in opcodes_l:
		check_arg_regex('l', instr[0], opcode)
	elif opcode in opcodes_s:
		check_arg_regex('s', instr[0], opcode)
	elif opcode in opcodes_vs:
		check_arg_regex('v', instr[0], opcode)
		check_arg_regex('s', instr[1], opcode)
	elif opcode in opcodes_vt:
		check_arg_regex('v', instr[0], opcode)
		check_arg_regex('t', instr[1], opcode)
	elif opcode in opcodes_vss_arr + opcodes_vss_cmp + opcodes_vss_log + opcodes_vss_other:
		check_arg_regex('v', instr[0], opcode)
		check_arg_regex('s', instr[1], opcode)
		check_arg_regex('s', instr[2], opcode)
	elif opcode in opcodes_lss:
		check_arg_regex('l', instr[0], opcode)
		check_arg_regex('s', instr[1], opcode)
		check_arg_regex('s', instr[2], opcode)
	else:
		# should be a dead branch
		eprint(99, f"Failed to check arg types for {opcode} at order {instr.get('order')}")

def check_arg_regex(switch, arg, opcode):
	'''
	Checks that argument type matches instruction and does
	a regex match to check that the value is lexically correct
	'''
	argtxt = arg.text if arg.text != None else ""
	if switch == 'v':
		argtype = ['var']
		pat = pat_var
	elif switch == 'l':
		argtype = ['label']
		pat = pat_label
	elif switch == 's':
		argtype = ['var', 'bool', 'int', 'nil', 'string']
		pat_dict = {'var':pat_var, 'bool':pat_bool, 'int':pat_int, 'nil':pat_nil, 'string':pat_string}
	elif switch == 't':
		argtype = ['type']
		pat = pat_type
	else:
		# should be a dead branch
		eprint(99, f"Invalid switch value passed to check_arg_regex")
	
	if arg.attrib['type'] not in argtype:
		eprint(100, f"Arg type {arg.attrib['type']} of {opcode} does not match expected: {argtype}")
	else:
		if switch == 's':
			if arg.attrib['type'] == 'string' and not argtxt:
				# arg is an empty string literal, re.search doesn't like it -> explicitly catching it here
				return
			else:
				pat = pat_dict[arg.attrib['type']]
	if re.search(pat, argtxt).group() != arg.text:
		eprint(100, f"Arg {argtxt} of {opcode} does not match pattern {pat}")

def labeldict_builder(instr):
	'''
	Adds new label to labeldict on LABEL instr 
	or to label check list on jump-type instr
	'''
	if instr.get('opcode').upper() == "LABEL":
		if instr[0].text not in labeldict:
			labeldict[instr[0].text] = int(instr.get('order'))
		else:
			eprint(52, f"Label redefinition: {instr[0].text} at order {instr.get('order')}")
	else:
		labels_jumped.add(instr[0].text)

def check_order_continuity():
	'''
	Checks that the instruction order does not skip numbers
	or have duplicates
	'''
	dupeset = list(set(num for num in orderlist if orderlist.count(num) > 1))
	if dupeset:
		eprint(32, f'Duplicate instruction order: {i}')
	for i in range(min(orderlist), max(orderlist)+1):
		if i not in orderlist:
			eprint(32, f'Instruction order discontinuity at {i - 1}')

def check_labels():
	'''
	Checks that all labels jumped to are properly defined
	'''
	# maybe todo: only check jumps that aren't dead code
	#print(labeldict)
	for l in labels_jumped:
		if l not in labeldict:
			eprint(52, f'Jump to undefined label: {l}')

def asmvar(vartype, varval):
	'''
	Variable constructor
	'''
	if str(vartype) == vartype and str(varval) == varval:
		return {"type":vartype, "val":varval}
	else:
		eprint(99, f"Variable constructor fail - non-string argument: {vartype}, {varval}")

class asmarg():
	def __init__(self, typearg, val):
		self.type = typearg
		self.val = val
		if self.type == 'string':
			if val == None:
				self.val = ""
			else:
				self.val = un_escape(un_xml(val))
		else:
			self.val = val
	
	def __repr__(self):
		return f"<{self.type}::{self.val}>"

def un_xml(string):
	'''
	Replaces xml representations of its control chars with them
	'''
	out = string
	out = re.sub("&amp", "&", out)
	out = re.sub("&lt", "<", out)
	out = re.sub("&gt", ">", out)
	out = re.sub("&quot", '"', out)
	out = re.sub("&apos", "'", out)
	return out

def un_escape(string):
	'''
	Replaces \xyz escape sequences in string with the corresponding char
	'''
	invalid_seq = re.search(pat_escape_invalid, string)
	if invalid_seq:
		eprint(53, f"Invalid escape sequence in string literal: {string}")
	valid_seq = set(re.findall(pat_escape_valid, string))
	#print(valid_seq)
	out = string
	for esc in valid_seq:
		out = re.sub(esc[1:], chr(int(esc[1:])), out)
		out = re.sub(r"\\", "", out)
	return out

def is_var(string):
	'''
	Check if a string is a variable name
	'''
	return upper(string[:3]) in ['GF@', 'LF@', 'TF@']

def get_base(numstring):
	'''
	Get base of a numeric string
	'''
	#print(numstring)
	if len(numstring) > 1:
		try:
			first, second = [numstring[0], numstring[1]] if numstring[0] not in '+-' else [numstring[1], numstring[2]]
		except IndexError:
			return 10
		if first == '0':
			if second == 'b':
				return 2
			elif second == 'x':
				return 16
			else:
				return 8
	return 10


def is_2_3_eql(line, fdd):
	'''
	Checks if 2nd and 3rd argument of an instr are equal
	'''
	# get arg2
	src1pref, src1name = line['args'][1].val.split('@') if line['args'][1].type == 'var' else [line['args'][1].type, line['args'][1].val]
	if src1pref in fdd:
		# arg2 var
		src1frame = fdd[src1pref]
		if src1frame != None:
			if src1name in src1frame:
				if src1frame[src1name] != None:
					num1 = src1frame[src1name]['val']
					num1type = src1frame[src1name]['type']
				else:
					eprint(54, f"Attempted {instr} from uninitialized variable: {line['args'][1].val} at order {ip}")
			else:
				eprint(54, f"Attempted {instr} from undefined variable: {line['args'][1].val} at order {ip}")
		else:
			eprint(54, f"Attempted {instr} from undefined frame: {line['args'][1].val} at order {ip}")
	else:
		# arg2 literal
		num1type = src1pref
		if src1pref == 'int':
			num1 = int(src1name, get_base(src1name))
		elif src1pref == 'bool':
			num1 = True if src2name == 'true' else False
		elif src1pref == 'string':
			num1 = src1name
		elif src1pref == 'nil':
			num1 = None
	
	# get arg3
	src2pref, src2name = line['args'][2].val.split('@') if line['args'][2].type == 'var' else [line['args'][2].type, line['args'][2].val]
	if src2pref in fdd:
		# arg3 var
		src2frame = fdd[src2pref]
		if src2frame != None:
			if src2name in src2frame:
				if src2frame[src2name] != None:
					num2 = src2frame[src2name]['val']
					num2type = src2frame[src2name]['type']
				else:
					eprint(54, f"Attempted {instr} from uninitialized variable: {line['args'][2].val} at order {ip}")
			else:
				eprint(54, f"Attempted {instr} from undefined variable: {line['args'][2].val} at order {ip}")
		else:
			eprint(54, f"Attempted {instr} from undefined frame: {line['args'][2].val} at order {ip}")
	else:
		# arg3 literal
		num2type = src2pref
		if src2pref == 'int':
			num2 = int(src2name, get_base(src2name))
		elif src2pref == 'bool':
			num2 = True if src2name == 'true' else False
		elif src2pref == 'string':
			num2 = src2name
		elif src2pref == 'nil':
			num2 = None
	
	# do the thing
	return (num1 == num2)



####################################
###############MAIN#################
####################################


def main(argv):
	global orderlist
	global labeldict
	global labels_jumped
	global prg
	global vardict
	read_fp = None
	xml_fname = None
	read_list = []
	#print(argv)
	
	for a in argv:
		if a[:6] == "--help":
			printhelp()
			exit(0)
		if a[:8] == "--input=":
			try:
				read_fp = open(a[8:], 'r')
			except:
				pass
			else:
				read_list = [l.rstrip() for l in read_fp]
				read_fp.close()
		if a[:9] == "--source=":
			xml_fname = a[9:]

	if not (read_fp or xml_fname):
		eprint(10, "At least one of --input or --source must be specified")

	#print("Opening file...")
	try:
		#tree = ET.parse('C:/Users/zekug/Desktop/vs/ipp/php/turing.xml')
		if xml_fname:
			tree = ET.parse(xml_fname)
		else:
			tree = ET.fromstring(input())
	except FileNotFoundError:
		eprint(31, "XML file not found")
	except Exception as e:
		eprint(31, f"Failed opening or reading xml file: {e}")
	root = tree.getroot()

	#print("Running analysis...")
	for instr in root:
		if instr.tag.lower() != 'instruction':
			eprint(32, "Unexpected element at instruction level")
		
		check_order(instr)
		check_opcode(instr)
		check_args_cnt(instr)
		check_args_types(instr)
		if instr.get('opcode').upper() in opcodes_l + opcodes_lss:
			labeldict_builder(instr)
		prg[int(instr.get('order'))] = {"instr":instr.get('opcode').upper(), "args":[asmarg(typearg = arg.get('type'), val = arg.text) for arg in instr]}
		
		
	check_order_continuity()
	check_labels()
	#pprint.pp(labeldict)
	#print("Analysis OK")
	#print("Running code...\n")
	#pprint.pp(prg)

	# control structure setup	
	framestack = []
	gf = dict()
	lf = None
	tf = None
	datastack = []
	callstack = []
	ip = min(orderlist)
	# frame decision dict
	fdd = {'GF':gf, 'LF':lf, 'TF':tf}

	# main loop
	#  (づ｡◕ヮ◕｡)づ wavy code so pretty
	icnt = 0
	while ip in range(min(orderlist), max(orderlist)+1):
		icnt += 1
		#pprint.pp(gf)
		line = prg[ip]
		instr = line['instr']
		#print(line)
		if instr == 'MOVE':
			destpref, destname = line['args'][0].val.split('@')
			destframe = fdd[destpref.upper()]
			if destframe != None:
				if destname in destframe:
					srcpref, srcname = line['args'][1].val.split('@') if line['args'][1].type == 'var' else [line['args'][1].type, line['args'][1].val]
					if srcpref in fdd:
						# copying var
						srcframe = fdd[srcpref]
						if srcframe != None:
							if srcname in srcframe:
								if srcframe[srcname] != None:
									destframe[destname] = copy.deepcopy(srcframe[srcname])
								else:
									eprint(54, f"Attempted {instr} from uninitialized variable: {line['args'][1].val} at order {ip}")
							else:
								eprint(54, f"Attempted {instr} from undefined variable: {line['args'][1].val} at order {ip}")
						else:
							eprint(54, f"Attempted {instr} from undefined frame: {line['args'][1].val} at order {ip}")
					else:
						# copying literal
						if srcpref == 'int':
							destframe[destname] = {'type':srcpref, 'val':int(srcname, get_base(srcname))}
						elif srcpref == 'bool':
							destframe[destname] = {'type':srcpref, 'val':True if srcname == 'true' else False}
						elif srcpref == 'string':
							destframe[destname] = {'type':srcpref, 'val':srcname}
						elif srcpref == 'nil':
							destframe[destname] = {'type':'nil', 'val':None}
				else:
					eprint(54, f"Attempted {instr} to undefined variable: {line['args'][0].val} at order {ip}")
			else:
				eprint(54, f"Attempted {instr} to undefined frame: {line['args'][0].val} at order {ip}")
		elif instr == 'CREATEFRAME':
			tf = []
		elif instr == 'PUSHFRAME':
			if tf != None:
				framestack.append(tf)
				lf = framestack[-1]
				tf = None
			else:
				eprint(54, f"Attempted {instr} undefined TF at order {ip}")
		elif instr == 'POPFRAME':
			if framestack != []:
				tf = lf
				del(framestack[-1])
				lf = framestack[-1] if framestack != [] else None
			else:
				eprint(55, "Attempted to {instr} with empty framestack")
		elif instr == 'DEFVAR':
			framename, varname = line['args'][0].val.split('@')
			frame = fdd[framename]
			if frame != None:
				if varname not in frame:
					frame[varname] = None
				else:
					eprint(52, f"Variable redefinition: {line['args'][0].val} at order {ip}")
		elif instr == 'CALL':
			callstack.append(ip)
			ip = labeldict[line['args'][0].val]
		elif instr == 'RETURN':
			if callstack != []:
				ip = callstack[-1]
				del(callstack[-1])
			else:
				eprint(54, f"RETURN with empty callstack at order {ip}")
		elif instr == 'PUSHS':
			srcpref, srcname = line['args'][0].val.split('@') if line['args'][0].type == 'var' else [line['args'][0].type, line['args'][0].val]
			if srcpref in fdd:
				# pushing var
				srcframe = fdd[srcpref]
				if srcframe != None:
					if srcname in srcframe:
						if srcframe[srcname] != None:
							dataframe.append(copy.deepcopy(srcframe[srcname]))
						else:
							eprint(54, f"Attempted to {instr} uninitialized variable: {line['args'][0].val} at order {ip}")
					else:
						eprint(54, f"Attempted to {instr} undefined variable: {line['args'][0].val} at order {ip}")
				else:
					eprint(54, f"Attempted to {instr} from undefined frame: {line['args'][0].val} at order {ip}")
			else:
				# pushing literal
				if srcpref == 'int':
					dataframe.append({'type':srcpref, 'val':int(srcname, get_base(srcname))})
				elif srcpref == 'bool':
					dataframe.append({'type':srcpref, 'val':True if srcname == 'true' else False})
				elif srcpref == 'string':
					dataframe.append({'type':srcpref, 'val':srcname})
				elif srcpref == 'nil':
					dataframe.append({'type':'nil', 'val':'nil'})
		elif instr == 'POPS':
			if datastack != []:
				destpref, destname = line['args'][0].val.split('@')
				destframe = fdd[destpref.upper()]
				if destframe != None:
					if destname in destframe:
						destframe[destname] = datastack[-1]
						del(datastack[-1])
					else:
						eprint(54, f"Attempted {instr} to undefined variable: {line['args'][0].val} at order {ip}")
				else:
					eprint(54, f"Attempted {instr} to undefined frame: {line['args'][0].val} at order {ip}")
			else:
				eprint(54, f"Attempted {instr} from empty stack at order {ip}")
		elif instr == 'ADD' or instr == 'SUB' or instr == 'MUL' or instr == 'IDIV':
			destpref, destname = line['args'][0].val.split('@')
			destframe = fdd[destpref.upper()]
			if destframe != None:
				if destname in destframe:
					
					# get arg2
					src1pref, src1name = line['args'][1].val.split('@') if line['args'][1].type == 'var' else [line['args'][1].type, line['args'][1].val]
					if src1pref in fdd:
						# arg2 var
						src1frame = fdd[src1pref]
						if src1frame != None:
							if src1name in src1frame:
								if src1frame[src1name] != None:
									if src1frame[src1name]['type'] == 'int':
										num1 = src1frame[src1name]['val']
									else:
										eprint(53, f"Attempted {instr} with {src1frame[src1name]['type']} variable: {line['args'][1].val} at order {ip}")
								else:
									eprint(54, f"Attempted {instr} from uninitialized variable: {line['args'][1].val} at order {ip}")
							else:
								eprint(54, f"Attempted {instr} from undefined variable: {line['args'][1].val} at order {ip}")
						else:
							eprint(54, f"Attempted {instr} from undefined frame: {line['args'][1].val} at order {ip}")
					else:
						# arg2 literal
						if src1pref == 'int':
							num1 = int(src1name, get_base(src1name))
						else:
							eprint(53, f"Attempted {instr} with {src1pref} literal: {line['args'][1].val} at order {ip}")
					
					# get arg3
					src2pref, src2name = line['args'][2].val.split('@') if line['args'][2].type == 'var' else [line['args'][2].type, line['args'][2].val]
					if src2pref in fdd:
						# arg3 var
						src2frame = fdd[src2pref]
						if src2frame != None:
							if src2name in src2frame:
								if src2frame[src2name] != None:
									if src2frame[src2name]['type'] == 'int':
										num2 = src2frame[src2name]['val']
									else:
										eprint(53, f"Attempted {instr} with {src2frame[src2name]['type']} variable: {line['args'][2].val} at order {ip}")
								else:
									eprint(54, f"Attempted {instr} from uninitialized variable: {line['args'][2].val} at order {ip}")
							else:
								eprint(54, f"Attempted {instr} from undefined variable: {line['args'][2].val} at order {ip}")
						else:
							eprint(54, f"Attempted {instr} from undefined frame: {line['args'][2].val} at order {ip}")
					else:
						# arg3 literal
						if src2pref == 'int':
							num2 = int(src2name, get_base(src2name))
						else:
							eprint(53, f"Attempted {instr} with {src2pref} literal: {line['args'][2].val} at order {ip}")
					
					# do the thing
					if instr == 'ADD':
						destframe[destname] = {'type':'int', 'val':(num1 + num2)}
					elif instr == 'SUB':
						destframe[destname] = {'type':'int', 'val':(num1 - num2)}
					elif instr == 'MUL':
						destframe[destname] = {'type':'int', 'val':(num1 * num2)}
					elif instr == 'IDIV':
						if num2 != 0:
							destframe[destname] = {'type':'int', 'val':(num1 // num2)}
						else:
							eprint(57, f"Zero division at order {ip}")
				else:
					eprint(54, f"Attempted {instr} to undefined variable: {line['args'][0].val} at order {ip}")
			else:
				eprint(54, f"Attempted {instr} to undefined frame: {line['args'][0].val} at order {ip}")
		elif instr == 'LT' or instr == 'GT' or instr == 'EQ':
			destpref, destname = line['args'][0].val.split('@')
			destframe = fdd[destpref.upper()]
			if destframe != None:
				if destname in destframe:
					
					# get arg2
					src1pref, src1name = line['args'][1].val.split('@') if line['args'][1].type == 'var' else [line['args'][1].type, line['args'][1].val]
					if src1pref in fdd:
						# arg2 var
						src1frame = fdd[src1pref]
						if src1frame != None:
							if src1name in src1frame:
								if src1frame[src1name] != None:
									num1 = src1frame[src1name]['val']
									num1type = src1frame[src1name]['type']
								else:
									eprint(54, f"Attempted {instr} from uninitialized variable: {line['args'][1].val} at order {ip}")
							else:
								eprint(54, f"Attempted {instr} from undefined variable: {line['args'][1].val} at order {ip}")
						else:
							eprint(54, f"Attempted {instr} from undefined frame: {line['args'][1].val} at order {ip}")
					else:
						# arg2 literal
						num1type = src1pref
						if src1pref == 'int':
							num1 = int(src1name, get_base(src1name))
						elif src1pref == 'bool':
							num1 = True if src2name == 'true' else False
						elif src1pref == 'string':
							num1 = src1name
						elif src1pref == 'nil':
							num1 = None
					
					# get arg3
					src2pref, src2name = line['args'][2].val.split('@') if line['args'][2].type == 'var' else [line['args'][2].type, line['args'][2].val]
					if src2pref in fdd:
						# arg3 var
						src2frame = fdd[src2pref]
						if src2frame != None:
							if src2name in src2frame:
								if src2frame[src2name] != None:
									num2 = src2frame[src2name]['val']
									num2type = src2frame[src2name]['type']
								else:
									eprint(54, f"Attempted {instr} from uninitialized variable: {line['args'][2].val} at order {ip}")
							else:
								eprint(54, f"Attempted {instr} from undefined variable: {line['args'][2].val} at order {ip}")
						else:
							eprint(54, f"Attempted {instr} from undefined frame: {line['args'][2].val} at order {ip}")
					else:
						# arg3 literal
						num2type = src2pref
						if src2pref == 'int':
							num2 = int(src2name, get_base(src2name))
						elif src2pref == 'bool':
							num2 = True if src2name == 'true' else False
						elif src2pref == 'string':
							num2 = src2name
						elif src2pref == 'nil':
							num2 = None
					
					# do the thing
					if num1type == num2type:
						if instr == 'LT':
							destframe[destname] = {'type':'int', 'val':(num1 < num2)}
						elif instr == 'GT':
							destframe[destname] = {'type':'int', 'val':(num1 > num2)}
						elif instr == 'EQ':
							destframe[destname] = {'type':'int', 'val':(num1 == num2)}
					elif (num1type == 'nil' or num2type == 'nil'):
						if instr == 'EQ':
							destframe[destname] = {'type':'int', 'val':(num1 == num2)}
						else:
							eprint(54, f"Non-EQ nil comparison at order {ip}")
				else:
					eprint(54, f"Attempted {instr} to undefined variable: {line['args'][0].val} at order {ip}")
			else:
				eprint(54, f"Attempted {instr} to undefined frame: {line['args'][0].val} at order {ip}")
		elif instr == 'AND' or instr == 'OR':
			destpref, destname = line['args'][0].val.split('@')
			destframe = fdd[destpref.upper()]
			if destframe != None:
				if destname in destframe:
					
					# get arg2
					src1pref, src1name = line['args'][1].val.split('@') if line['args'][1].type == 'var' else [line['args'][1].type, line['args'][1].val]
					if src1pref in fdd:
						# arg2 var
						src1frame = fdd[src1pref]
						if src1frame != None:
							if src1name in src1frame:
								if src1frame[src1name] != None:
									if src1frame[src1name]['type'] == 'bool':
										num1 = src1frame[src1name]['val']
									else:
										eprint(53, f"Attempted {instr} with {src1frame[src1name]['type']} variable: {line['args'][1].val} at order {ip}")
								else:
									eprint(54, f"Attempted {instr} from uninitialized variable: {line['args'][1].val} at order {ip}")
							else:
								eprint(54, f"Attempted {instr} from undefined variable: {line['args'][1].val} at order {ip}")
						else:
							eprint(54, f"Attempted {instr} from undefined frame: {line['args'][1].val} at order {ip}")
					else:
						# arg2 literal
						if src1pref == 'bool':
							num1 = True if src1name == 'true' else False
						else:
							eprint(53, f"Attempted {instr} with {src1pref} literal: {line['args'][1].val} at order {ip}")
					
					# get arg3
					src2pref, src2name = line['args'][2].val.split('@') if line['args'][2].type == 'var' else [line['args'][2].type, line['args'][2].val]
					if src2pref in fdd:
						# arg3 var
						src2frame = fdd[src2pref]
						if src2frame != None:
							if src2name in src2frame:
								if src2frame[src2name] != None:
									if src2frame[src2name]['type'] == 'bool':
										num2 = src2frame[src2name]['val']
									else:
										eprint(53, f"Attempted {instr} with {src2frame[src2name]['type']} variable: {line['args'][2].val} at order {ip}")
								else:
									eprint(54, f"Attempted {instr} from uninitialized variable: {line['args'][2].val} at order {ip}")
							else:
								eprint(54, f"Attempted {instr} from undefined variable: {line['args'][2].val} at order {ip}")
						else:
							eprint(54, f"Attempted {instr} from undefined frame: {line['args'][2].val} at order {ip}")
					else:
						# arg3 literal
						if src2pref == 'bool':
							num2 = True if src2name == 'true' else False
						else:
							eprint(53, f"Attempted {instr} with {src2pref} literal: {line['args'][2].val} at order {ip}")
					
					# do the thing
					if instr == 'AND':
						destframe[destname] = {'type':'bool', 'val':(num1 and num2)}
					elif instr == 'OR':
						destframe[destname] = {'type':'bool', 'val':(num1 or num2)}
				else:
					eprint(54, f"Attempted {instr} to undefined variable: {line['args'][0].val} at order {ip}")
			else:
				eprint(54, f"Attempted {instr} to undefined frame: {line['args'][0].val} at order {ip}")
		elif instr == 'NOT':
			destpref, destname = line['args'][0].val.split('@')
			destframe = fdd[destpref.upper()]
			if destframe != None:
				if destname in destframe:
					
					# get arg2
					src1pref, src1name = line['args'][1].val.split('@') if line['args'][1].type == 'var' else [line['args'][1].type, line['args'][1].val]
					if src1pref in fdd:
						# arg2 var
						src1frame = fdd[src1pref]
						if src1frame != None:
							if src1name in src1frame:
								if src1frame[src1name] != None:
									if src1frame[src1name]['type'] == 'bool':
										num1 = src1frame[src1name]['val']
									else:
										eprint(53, f"Attempted {instr} with {src1frame[src1name]['type']} variable: {line['args'][1].val} at order {ip}")
								else:
									eprint(54, f"Attempted {instr} from uninitialized variable: {line['args'][1].val} at order {ip}")
							else:
								eprint(54, f"Attempted {instr} from undefined variable: {line['args'][1].val} at order {ip}")
						else:
							eprint(54, f"Attempted {instr} from undefined frame: {line['args'][1].val} at order {ip}")
					else:
						# arg2 literal
						if src1pref == 'bool':
							num1 = True if src1name == 'true' else False
						else:
							eprint(53, f"Attempted {instr} with {src1pref} literal: {line['args'][1].val} at order {ip}")

					# do the thing
					destframe[destname] = {'type':'bool', 'val':(not num1)}
				else:
					eprint(54, f"Attempted {instr} to undefined variable: {line['args'][0].val} at order {ip}")
			else:
				eprint(54, f"Attempted {instr} to undefined frame: {line['args'][0].val} at order {ip}")
		elif instr == 'INT2CHAR':
			destpref, destname = line['args'][0].val.split('@')
			destframe = fdd[destpref.upper()]
			if destframe != None:
				if destname in destframe:
					
					# get arg2
					src1pref, src1name = line['args'][1].val.split('@') if line['args'][1].type == 'var' else [line['args'][1].type, line['args'][1].val]
					if src1pref in fdd:
						# arg2 var
						src1frame = fdd[src1pref]
						if src1frame != None:
							if src1name in src1frame:
								if src1frame[src1name] != None:
									try:
										destframe[destname] = {'type':'string', 'val':chr(src1frame[src1name]['val'])}
									except TypeError:
										eprint(58, f"Attempted {instr} with {src1frame[src1name]['type']} variable: {line['args'][1].val} at order {ip}")
								else:
									eprint(54, f"Attempted {instr} from uninitialized variable: {line['args'][1].val} at order {ip}")
							else:
								eprint(54, f"Attempted {instr} from undefined variable: {line['args'][1].val} at order {ip}")
						else:
							eprint(54, f"Attempted {instr} from undefined frame: {line['args'][1].val} at order {ip}")
					else:
						# arg2 literal
						try:
							destframe[destname] = {'type':'string', 'val':chr(src1name)}
						except TypeError:
							eprint(58, f"Attempted {instr} with {src1pref} literal: {line['args'][1].val} at order {ip}")
				else:
					eprint(54, f"Attempted {instr} to undefined variable: {line['args'][0].val} at order {ip}")
			else:
				eprint(54, f"Attempted {instr} to undefined frame: {line['args'][0].val} at order {ip}")
		elif instr == 'STRI2INT':
			destpref, destname = line['args'][0].val.split('@')
			destframe = fdd[destpref.upper()]
			if destframe != None:
				if destname in destframe:
					
					# get arg2
					src1pref, src1name = line['args'][1].val.split('@') if line['args'][1].type == 'var' else [line['args'][1].type, line['args'][1].val]
					if src1pref in fdd:
						# arg2 var
						src1frame = fdd[src1pref]
						if src1frame != None:
							if src1name in src1frame:
								if src1frame[src1name] != None:
									if src1frame[src1name]['type'] == 'string':
										num1 = src1frame[src1name]['val']
									else:
										eprint(53, f"Attempted {instr} with {src1frame[src1name]['type']} variable: {line['args'][1].val} at order {ip}")
								else:
									eprint(54, f"Attempted {instr} from uninitialized variable: {line['args'][1].val} at order {ip}")
							else:
								eprint(54, f"Attempted {instr} from undefined variable: {line['args'][1].val} at order {ip}")
						else:
							eprint(54, f"Attempted {instr} from undefined frame: {line['args'][1].val} at order {ip}")
					else:
						# arg2 literal
						if src1pref == 'string':
							num1 = True if src1name == 'true' else False
						else:
							eprint(53, f"Attempted {instr} with {src1pref} literal: {line['args'][1].val} at order {ip}")
					
					# get arg3
					src2pref, src2name = line['args'][2].val.split('@') if line['args'][2].type == 'var' else [line['args'][2].type, line['args'][2].val]
					if src2pref in fdd:
						# arg3 var
						src2frame = fdd[src2pref]
						if src2frame != None:
							if src2name in src2frame:
								if src2frame[src2name] != None:
									if src2frame[src2name]['type'] == 'int':
										num2 = src2frame[src2name]['val']
									else:
										eprint(53, f"Attempted {instr} with {src2frame[src2name]['type']} variable: {line['args'][2].val} at order {ip}")
								else:
									eprint(54, f"Attempted {instr} from uninitialized variable: {line['args'][2].val} at order {ip}")
							else:
								eprint(54, f"Attempted {instr} from undefined variable: {line['args'][2].val} at order {ip}")
						else:
							eprint(54, f"Attempted {instr} from undefined frame: {line['args'][2].val} at order {ip}")
					else:
						# arg3 literal
						if src2pref == 'int':
							num2 = True if src2name == 'true' else False
						else:
							eprint(53, f"Attempted {instr} with {src2pref} literal: {line['args'][2].val} at order {ip}")
					
					# do the thing
					if num2 in range(len(num1)):
						destframe[destname] = {'type':'int', 'val':ord(num1[num2])}
					else:
						eprint(58, f"{instr} index out of bounds at order {ip}")
				else:
					eprint(54, f"Attempted {instr} to undefined variable: {line['args'][0].val} at order {ip}")
			else:
				eprint(54, f"Attempted {instr} to undefined frame: {line['args'][0].val} at order {ip}")
		elif instr == 'READ':
			destpref, destname = line['args'][0].val.split('@')
			destframe = fdd[destpref.upper()]
			if destframe != None:
				if destname in destframe:
					srctype = line['args'][1].val
					if srctype in ['int', 'string', 'bool']:
						if read_list == []:
							src = input()
						else:
							src = read_list[0]
							del(read_list[0])
						if srctype == 'int':
							try:
								destframe[destname] = {'type':srctype, 'val':int(src, get_base(src))}
							except ValueError:
								destframe[destname] = {'type':'nil', 'val':None}
						elif srctype == 'string':
							destframe[destname] = {'type':srctype, 'val':src}
						elif srctype == 'bool':
							destframe[destname] = {'type':srctype, 'val':True if src == 'true' else False}
					else:
						eprint(53, f"Attempted {instr} with invalid type: {srctype} at order {ip}")
				else:
					eprint(54, f"Attempted {instr} to undefined variable: {line['args'][0].val} at order {ip}")
			else:
				eprint(54, f"Attempted {instr} to undefined frame: {line['args'][0].val} at order {ip}")
		elif instr == 'WRITE':
			srcpref, srcname = line['args'][0].val.split('@') if line['args'][0].type == 'var' else [line['args'][0].type, line['args'][0].val]
			if srcpref in fdd:
				# writing var
				srcframe = fdd[srcpref]
				if srcframe != None:
					if srcname in srcframe:
						if srcframe[srcname] != None:
							print(srcframe[srcname]['val'], end='')
						else:
							eprint(54, f"Attempted {instr} from uninitialized variable: {line['args'][0].val} at order {ip}")
					else:
						eprint(54, f"Attempted {instr} from undefined variable: {line['args'][0].val} at order {ip}")
				else:
					eprint(54, f"Attempted {instr} from undefined frame: {line['args'][0].val} at order {ip}")
			else:
				# writing literal
				print(srcname, end='')
		elif instr == 'CONCAT':
			destpref, destname = line['args'][0].val.split('@')
			destframe = fdd[destpref.upper()]
			if destframe != None:
				if destname in destframe:
					
					# get arg2
					src1pref, src1name = line['args'][1].val.split('@') if line['args'][1].type == 'var' else [line['args'][1].type, line['args'][1].val]
					if src1pref in fdd:
						# arg2 var
						src1frame = fdd[src1pref]
						if src1frame != None:
							if src1name in src1frame:
								if src1frame[src1name] != None:
									if src1frame[src1name]['type'] == 'string':
										num1 = src1frame[src1name]['val']
									else:
										eprint(53, f"Attempted {instr} with {src1frame[src1name]['type']} variable: {line['args'][1].val} at order {ip}")
								else:
									eprint(54, f"Attempted {instr} from uninitialized variable: {line['args'][1].val} at order {ip}")
							else:
								eprint(54, f"Attempted {instr} from undefined variable: {line['args'][1].val} at order {ip}")
						else:
							eprint(54, f"Attempted {instr} from undefined frame: {line['args'][1].val} at order {ip}")
					else:
						# arg2 literal
						if src1pref == 'string':
							num1 = True if src1name == 'true' else False
						else:
							eprint(53, f"Attempted {instr} with {src1pref} literal: {line['args'][1].val} at order {ip}")
					
					# get arg3
					src2pref, src2name = line['args'][2].val.split('@') if line['args'][2].type == 'var' else [line['args'][2].type, line['args'][2].val]
					if src2pref in fdd:
						# arg3 var
						src2frame = fdd[src2pref]
						if src2frame != None:
							if src2name in src2frame:
								if src2frame[src2name] != None:
									if src2frame[src2name]['type'] == 'string':
										num2 = src2frame[src2name]['val']
									else:
										eprint(53, f"Attempted {instr} with {src2frame[src2name]['type']} variable: {line['args'][2].val} at order {ip}")
								else:
									eprint(54, f"Attempted {instr} from uninitialized variable: {line['args'][2].val} at order {ip}")
							else:
								eprint(54, f"Attempted {instr} from undefined variable: {line['args'][2].val} at order {ip}")
						else:
							eprint(54, f"Attempted {instr} from undefined frame: {line['args'][2].val} at order {ip}")
					else:
						# arg3 literal
						if src2pref == 'string':
							num2 = src2name
						else:
							eprint(53, f"Attempted {instr} with {src2pref} literal: {line['args'][2].val} at order {ip}")
					
					# do the thing
					destframe[destname] = {'type':'string', 'val':num1 + num2}
				else:
					eprint(54, f"Attempted {instr} to undefined variable: {line['args'][0].val} at order {ip}")
			else:
				eprint(54, f"Attempted {instr} to undefined frame: {line['args'][0].val} at order {ip}")
		elif instr == 'STRLEN':
			destpref, destname = line['args'][0].val.split('@')
			destframe = fdd[destpref.upper()]
			if destframe != None:
				if destname in destframe:
					
					# get arg2
					src1pref, src1name = line['args'][1].val.split('@') if line['args'][1].type == 'var' else [line['args'][1].type, line['args'][1].val]
					if src1pref in fdd:
						# arg2 var
						src1frame = fdd[src1pref]
						if src1frame != None:
							if src1name in src1frame:
								if src1frame[src1name] != None:
									#print(src1frame[src1name])
									if src1frame[src1name]['type'] == 'string':
										num1 = src1frame[src1name]['val']
									else:
										eprint(53, f"Attempted {instr} with {src1frame[src1name]['type']} variable: {line['args'][1].val} at order {ip}")
								else:
									eprint(54, f"Attempted {instr} from uninitialized variable: {line['args'][1].val} at order {ip}")
							else:
								eprint(54, f"Attempted {instr} from undefined variable: {line['args'][1].val} at order {ip}")
						else:
							eprint(54, f"Attempted {instr} from undefined frame: {line['args'][1].val} at order {ip}")
					else:
						# arg2 literal
						if src1pref == 'string':
							num1 = src1name
						else:
							eprint(53, f"Attempted {instr} with {src1pref} literal: {line['args'][1].val} at order {ip}")

					
					# do the thing
					destframe[destname] = {'type':'int', 'val':len(num1)}
				else:
					eprint(54, f"Attempted {instr} to undefined variable: {line['args'][0].val} at order {ip}")
		elif instr == 'GETCHAR':
			destpref, destname = line['args'][0].val.split('@')
			destframe = fdd[destpref.upper()]
			if destframe != None:
				if destname in destframe:
					
					# get arg2
					src1pref, src1name = line['args'][1].val.split('@') if line['args'][1].type == 'var' else [line['args'][1].type, line['args'][1].val]
					if src1pref in fdd:
						# arg2 var
						src1frame = fdd[src1pref]
						if src1frame != None:
							if src1name in src1frame:
								if src1frame[src1name] != None:
									#print(src1frame[src1name])
									if src1frame[src1name]['type'] == 'string':
										num1 = src1frame[src1name]['val']
									else:
										eprint(53, f"Attempted {instr} with {src1frame[src1name]['type']} variable: {line['args'][1].val} at order {ip}")
								else:
									eprint(54, f"Attempted {instr} from uninitialized variable: {line['args'][1].val} at order {ip}")
							else:
								eprint(54, f"Attempted {instr} from undefined variable: {line['args'][1].val} at order {ip}")
						else:
							eprint(54, f"Attempted {instr} from undefined frame: {line['args'][1].val} at order {ip}")
					else:
						# arg2 literal
						if src1pref == 'string':
							num1 = src1name
						else:
							eprint(53, f"Attempted {instr} with {src1pref} literal: {line['args'][1].val} at order {ip}")
					
					# get arg3
					src2pref, src2name = line['args'][2].val.split('@') if line['args'][2].type == 'var' else [line['args'][2].type, line['args'][2].val]
					if src2pref in fdd:
						# arg3 var
						src2frame = fdd[src2pref]
						if src2frame != None:
							if src2name in src2frame:
								if src2frame[src2name] != None:
									if src2frame[src2name]['type'] == 'int':
										num2 = src2frame[src2name]['val']
									else:
										eprint(53, f"Attempted {instr} with {src2frame[src2name]['type']} variable: {line['args'][2].val} at order {ip}")
								else:
									eprint(54, f"Attempted {instr} from uninitialized variable: {line['args'][2].val} at order {ip}")
							else:
								eprint(54, f"Attempted {instr} from undefined variable: {line['args'][2].val} at order {ip}")
						else:
							eprint(54, f"Attempted {instr} from undefined frame: {line['args'][2].val} at order {ip}")
					else:
						# arg3 literal
						if src2pref == 'int':
							num2 = int(src2name, get_base(src2name))
						else:
							eprint(53, f"Attempted {instr} with {src2pref} literal: {line['args'][2].val} at order {ip}")
					
					# do the thing
					#print(num2, num1, len(num1))
					if num2 in range(len(num1)):
						destframe[destname] = {'type':'string', 'val':num1[num2]}
					else:
						eprint(58, f"{instr} index out of bounds at order {ip}")
				else:
					eprint(54, f"Attempted {instr} to undefined variable: {line['args'][0].val} at order {ip}")
			else:
				eprint(54, f"Attempted {instr} to undefined frame: {line['args'][0].val} at order {ip}")
		elif instr == 'SETCHAR':
			destpref, destname = line['args'][0].val.split('@')
			destframe = fdd[destpref.upper()]
			if destframe != None:
				if destname in destframe:
					if destframe[destname]['type'] == 'string':
						# get arg2
						src1pref, src1name = line['args'][1].val.split('@') if line['args'][1].type == 'var' else [line['args'][1].type, line['args'][1].val]
						if src1pref in fdd:
							# arg2 var
							src1frame = fdd[src1pref]
							if src1frame != None:
								if src1name in src1frame:
									if src1frame[src1name] != None:
										if src1frame[src1name]['type'] == 'int':
											num1 = src1frame[src1name]['val']
										else:
											eprint(53, f"Attempted {instr} with {src1frame[src1name]['type']} variable: {line['args'][1].val} at order {ip}")
									else:
										eprint(54, f"Attempted {instr} from uninitialized variable: {line['args'][1].val} at order {ip}")
								else:
									eprint(54, f"Attempted {instr} from undefined variable: {line['args'][1].val} at order {ip}")
							else:
								eprint(54, f"Attempted {instr} from undefined frame: {line['args'][1].val} at order {ip}")
						else:
							# arg2 literal
							if src1pref == 'int':
								num1 = int(src1name, get_base(src2name))
							else:
								eprint(53, f"Attempted {instr} with {src1pref} literal: {line['args'][1].val} at order {ip}")
						
						# get arg3
						src2pref, src2name = line['args'][2].val.split('@') if line['args'][2].type == 'var' else [line['args'][2].type, line['args'][2].val]
						if src2pref in fdd:
							# arg3 var
							src2frame = fdd[src2pref]
							if src2frame != None:
								if src2name in src2frame:
									if src2frame[src2name] != None:
										if src2frame[src2name]['type'] == 'string':
											num2 = src2frame[src2name]['val']
										else:
											eprint(53, f"Attempted {instr} with {src2frame[src2name]['type']} variable: {line['args'][2].val} at order {ip}")
									else:
										eprint(54, f"Attempted {instr} from uninitialized variable: {line['args'][2].val} at order {ip}")
								else:
									eprint(54, f"Attempted {instr} from undefined variable: {line['args'][2].val} at order {ip}")
							else:
								eprint(54, f"Attempted {instr} from undefined frame: {line['args'][2].val} at order {ip}")
						else:
							# arg3 literal
							if src2pref == 'string':
								num2 = src2name
							else:
								eprint(53, f"Attempted {instr} with {src2pref} literal: {line['args'][2].val} at order {ip}")
						
						# do the thing
						if num1 in range(len(destframe[destname]['val'])) and num1 != '':
							destframe[destname] = {'type':'string', 'val':(destframe[destname]['val'][:num1] + num2[0] + destframe[destname]['val'][num1+1:])}
						else:
							eprint(58, f"{instr} index out of bounds at order {ip}")
					else:
						eprint(54, f"Attempted {instr} to {destframe[destname]['type']} variable: {line['args'][0].val} at order {ip}")
				else:
					eprint(54, f"Attempted {instr} to undefined variable: {line['args'][0].val} at order {ip}")
			else:
				eprint(54, f"Attempted {instr} to undefined frame: {line['args'][0].val} at order {ip}")
		elif instr == 'TYPE':
			destpref, destname = line['args'][0].val.split('@')
			destframe = fdd[destpref.upper()]
			if destframe != None:
				if destname in destframe:
					srcpref, srcname = line['args'][1].val.split('@') if line['args'][1].type == 'var' else [line['args'][1].type, line['args'][1].val]
					if srcpref in fdd:
						# typechecking var
						srcframe = fdd[srcpref]
						if srcframe != None:
							if srcname in srcframe:
								if srcframe[srcname] != None:
									destframe[destname] = {'type':'string', 'val':srcframe[srcname]['type']}
								else:
									destframe[destname] = {'type':'string', 'val':""}
							else:
								eprint(54, f"Attempted {instr} from undefined variable: {line['args'][1].val} at order {ip}")
						else:
							eprint(54, f"Attempted {instr} from undefined frame: {line['args'][1].val} at order {ip}")
					else:
						# typechecking literal
						destframe[destname] = {'type':'string', 'val':srcpref}
				else:
					eprint(54, f"Attempted {instr} to undefined variable: {line['args'][0].val} at order {ip}")
			else:
				eprint(54, f"Attempted {instr} to undefined frame: {line['args'][0].val} at order {ip}")
		elif instr == 'LABEL':
			# do nothing
			None
		elif instr == 'JUMP':
			ip = labeldict[line['args'][0].val]
		elif instr == 'JUMPIFEQ':
			ip = labeldict[line['args'][0].val] if is_2_3_eql(line, fdd) else ip
		elif instr == 'JUMPIFNEQ':
			ip = labeldict[line['args'][0].val] if not is_2_3_eql(line, fdd) else ip
		elif instr == 'EXIT':
			srcpref, srcname = line['args'][0].val.split('@') if line['args'][0].type == 'var' else [line['args'][0].type, line['args'][0].val]
			if srcpref in fdd:
				# exit with var
				srcframe = fdd[srcpref]
				if srcframe != None:
					if srcname in srcframe:
						if srcframe[srcname] != None:
							print(srcframe[srcname]['val'], end='')
							if srcframe[srcname]['type'] == 'int':
								out = srcframe[srcname]['val']
								if out in range(50):
									exit(out)
								else:
									eprint(57, f"Invalid EXIT code at order {ip}")
							else:
								eprint(54, f"Attempted {instr} with {srcframe[srcname]['type']} type variable: {line['args'][0].val} at order {ip}")
						else:
							eprint(54, f"Attempted {instr} from uninitialized variable: {line['args'][0].val} at order {ip}")
					else:
						eprint(54, f"Attempted {instr} from undefined variable: {line['args'][0].val} at order {ip}")
				else:
					eprint(54, f"Attempted {instr} from undefined frame: {line['args'][0].val} at order {ip}")
			else:
				# exit with literal
				if srcpref == 'int':
					out = int(srcname, get_base(src_name))
					if out in range(50):
						exit(out)
					else:
						eprint(57, f"Invalid EXIT code at order {ip}")
				else:
					eprint(54, f"Attempted {instr} with {srcpref} type literal: {line['args'][0].val} at order {ip}")
		elif instr == 'DPRINT':
			srcpref, srcname = line['args'][0].val.split('@') if line['args'][0].type == 'var' else [line['args'][0].type, line['args'][0].val]
			if srcpref in fdd:
				# writing var
				srcframe = fdd[srcpref]
				if srcframe != None:
					if srcname in srcframe:
						if srcframe[srcname] != None:
							print(srcframe[srcname]['val'], end='', file=sys.stderr)
						else:
							eprint(54, f"Attempted {instr} from uninitialized variable: {line['args'][0].val} at order {ip}")
					else:
						eprint(54, f"Attempted {instr} from undefined variable: {line['args'][0].val} at order {ip}")
				else:
					eprint(54, f"Attempted {instr} from undefined frame: {line['args'][0].val} at order {ip}")
			else:
				# writing literal
				print(srcname, end='', file=sys.stderr)
		elif instr == 'BREAK':
			print('###### BREAK instr ######', file=sys.stderr)
			print(f'ip = {ip}', file=sys.stderr)
			print(f'instr count = {icnt}', file=sys.stderr)
			print('### framestack ###', file=sys.stderr)
			print(pprint.pformat(framestack), file=sys.stderr)
			print('### GF ###', file=sys.stderr)
			print(pprint.pformat(gf), file=sys.stderr)
			print('### LF ###', file=sys.stderr)
			print(pprint.pformat(lf), file=sys.stderr)
			print('### TF ###', file=sys.stderr)
			print(pprint.pformat(tf), file=sys.stderr)
			print('### datastack ###', file=sys.stderr)
			print(pprint.pformat(datastack), file=sys.stderr)
			print('### callstack ###', file=sys.stderr)
			print(pprint.pformat(callstack), file=sys.stderr)
			print('###### end of BREAK instr ######', file=sys.stderr)
			
		ip += 1
	#pprint.pp(gf)
	labeldict = dict()
	labels_jumped = set()
	prg = dict()
	vardict = dict()
	orderlist = []

if __name__ == "__main__":
	main(sys.argv)
