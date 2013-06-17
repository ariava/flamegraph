#!/usr/bin/python

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
	if matches("^#", line):
		continue
	line = line.rstrip()

	if matches("^$", line):
		if len(stack) != 0:
			remember_stack(";".join(stack), 1)
		del stack[:]
		continue

	# Note the details skipped below, and customize as desired

	if matches(":.*:", line):
		continue	# skip summary lines

	match = re.match("\s*\w+ (\w+) (\S+)", line)
	if match is not None:
		(func, mod) = (match.group(1), match.group(2))
		if matches("\(", func):
			continue	# skip process names
		if not matches("kernel", mod):
			continue	# skip non-kernel
		stack = [func] + stack

for k in sorted(collapsed.keys()):
	print k, collapsed[k]

