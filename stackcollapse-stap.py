#!/usr/bin/python2

import fileinput
import re

collapsed = {}

def remember_stack (stack, count):
	global collapsed
	if stack in collapsed.keys():
		collapsed[stack] = int(collapsed[stack]) + int(count)
	else:
		collapsed[stack] = int(count)

def matches (rexp, line):
	match = re.search(rexp, line)
	if match is not None:
		return True
	return False

stack = []

for line in fileinput.input():
	line = line.rstrip()

	match = re.match(r'^\s*(\d+)+$', line)	# search?
	if match is not None:
		remember_stack(";".join(stack), match.group(1))
		del stack[:]
		continue

	if matches("^\s*$", line):
		continue

	line = re.sub(r'^\s*','', line)
	line = re.sub(r'\+[^+]*$', '', line)
	line = re.sub(r'.* : ', '', line)
	if line == "": 	# not line?
		line = "-"
	stack = [line] + stack

for k in sorted(collapsed.keys()):
	print k, collapsed[k]

