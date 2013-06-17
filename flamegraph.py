#!/usr/bin/python

import argparse
import fileinput
import re
import sys
import random
from pprint import pprint

# tunables
timemax = None             # (override the) sum of the counts

parser = argparse.ArgumentParser()
parser.add_argument("-f", "--fonttype", help="font type (default \"Verdana\")", action="store", default="Verdana")
parser.add_argument("-w", "--width", help="width of image (default 1200)", action="store", default=1200)
parser.add_argument("-H", "--height", help="height of each frame (default 16)", action="store", default=16)
parser.add_argument("-s", "--fontsize", help="font size (default 12)", action="store", default=12)
parser.add_argument("-i", "--fontwidth", help="font width (defailt 0.55)", action="store", default=0.55)
parser.add_argument("-m", "--minwidth", help="omit smaller functions (default 0.1 pixels)", action="store", default=0.1)
parser.add_argument("-t", "--titletext", help="change title text", action="store", default="Flame Graph")
parser.add_argument("-n", "--nametype", help="name type label (default \"Function:\")", action="store", default="Function:")
parser.add_argument("-c", "--countname", help="count type label (default \"samples\")", action="store", default="samples")
parser.add_argument("-a", "--nameattrfile", help="file holding function attributes", action="store", default="")
parser.add_argument("-o", "--factor", help="factor to scale counts by", action="store", default=1)
args = parser.parse_args()

fonttype = args.fonttype
imagewidth = args.width
frameheight = args.height
fontsize = args.fontsize
fontwidth = args.fontwidth
minwidth = args.minwidth
titletext = args.titletext
nametype = args.nametype
countname = args.countname
nameattrfile = args.nameattrfile
factor = args.factor

# internals
ypad1 = fontsize * 4      # pad top, include title
ypad2 = fontsize * 2 + 10 # pad bottom, include labels
xpad = 10                  # pad lefm and right
depthmax = 0
Events = None
nameattr = {}

if nameattrfile != "":
	# The name-attribute file format is a function name followed by a tab then
	# a sequence of tab separated name=value pairs.
	for line in open(nameattrfile):
		line = line.rstrip()
		(funcname, attrstr) = line.strip()
		if attrstr == "":
			print "Invalid format in", nameattrfile
			exit(1)
		nameattr[funcname] = [l.strip('\t') for l in line.strip('=')[:2]] # XXX

class SVG:

	svgstring = ""

	def __init__(self):
		pass

	def header(self, w, h):
		self.svgstring += '<?xml version="1.0" standalone="no"?>'\
'<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">'\
'<svg version="1.1" width="' + str(w) + '" height="' + str(h) + '" onload="init(evt)" viewBox="0 0 ' + str(w) + ' ' + str(h) + '" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'

	def include(self, content):
		self.svgstring += str(content)

	def colorAllocate(self, r, g, b):
		return 'rgb(' + str(r) + ',' + str(g) + ',' + str(b) + ')'

	def group_start(self, attr):
		g_attr = []
		for (key, value) in attr.iteritems():
			if key != "title":
				g_attr.append('%s="%s"' % (key, value))

		if "g_extra" in attr.keys():
			g_attr.append(attr["g_extra"])

		self.svgstring += "<g %s>\n" % ' '.join(g_attr)

		if "title" in attr.keys():
			self.svgstring += "<title>%s</title>" % attr["title"] # should be first element within g container

		if "href" in attr.keys():
			a_attr = "xlink:href=\"%s\"" % attr["href"]
			# default target=_top else links will open within SVG <object>
			if "target" in attr.keys():
				a_attr.append("target=\"%s\"" % attr["target"])
			else:
				a_attr.append("target=\"_top\"")
			if "a_extra" in attr.keys():
				a_attr.append(attr["a_extra"])
			self.svgstring += "<a %s>" % ' '.join(a_attr)

	def group_end(self, attr):
		if "href" in attr.keys():
			self.svgstring += "</a>\n"
		self.svgstring += "</g>\n"

	def filledRectangle(self, x1, y1, x2, y2, fill, extra):
		x1 = "%0.1f" % x1
		x2 = "%0.1f" % x2
		w = ("%0.1f" % (float(x2) - float(x1)))
		h = ("%0.1f" % (float(y2) - float(y1)))
		if extra == None:
			extra = ""
		self.svgstring += '<rect x="' + str(x1) + '" y="' + str(y1) + '" width="' + str(w) + '" height="' + str(h) + '" fill="' + str(fill) + '" ' + str(extra) + '/>\n'

	def stringTTF(self, color, font, size, angle, x, y, st, loc, extra):
		if loc == None:
			loc = "left"
		if extra == None:
			extra = ""
		self.svgstring += '<text text-anchor="' + str(loc) + '" x="' + str(x) + '" y="' + str(y) + '" font-size="' + str(size) + '" font-family="' + str(font) + '" fill="' + str(color) + '" ' + str(extra) + '>' + str(st) + '</text>\n'

	def svg(self):
		return self.svgstring + "</svg>\n"

def color(ty):
	if ty == "hot":
		r = 205 + int(random.randrange(0,50))
		g = 0 + int(random.randrange(0,230))
		b = 0 + int(random.randrange(0,55))
		return "rgb(" + str(r) + "," + str(g) + "," + str(b) + ")"
	return "rgb(0,0,0)"

Node = {}
Tmp = {}

def flow(last, this, v):
	global Node
	global Tmp

	len_a = len(last) - 1
	len_b = len(this) - 1

	i = 0
	while i <= len_a:
		if i > len_b:
			break
		if last[i] != this[i]:
			break
		i += 1
	len_same = i

	i = len_a
	while i >= len_same:
		k = str(last[i]) + ";" + str(i)
		# a unique ID is constructed from "func;depth;etime";
		# func-depth isn't unique, it may be repeated later.
		Node[str(k) + ";" + str(v)] = {}
		Node[str(k) + ";" + str(v)]["stime"] = Tmp[k]["stime"]
		#print str(k) + ";" + str(v), Node[str(k) + ";" + str(v)]["stime"]
		del Tmp[str(k)]["stime"]
		del Tmp[str(k)]
		i -= 1

	i = len_same
	while i <= len_b:
		k = this[i] + ";" + str(i)
		Tmp[k] = {}
		Tmp[k]["stime"] = v
		i += 1

	return this

last = []
time = 0
ignored = 0
Data = fileinput.input()
for line in sorted(Data):
        line = line.rstrip()
	match = re.match(r"^(.*)\s+(\d+(?:\.\d*)?)$", str(line))
	if match is not None:
		(stack, samples) = (match.group(1), match.group(2))
	else:
		(stack, samples) = (None, None)
        if samples == None:
		ignored += 1
		continue
	stack = stack.replace('(', '<')
	stack = stack.replace(')', '>')
	splitted = stack.split(';')
	if splitted == ['']:
		splitted = []
	last = flow(last, [''] + splitted, time)
        time += int(samples)

flow(last, [], time)
if ignored > 0:
	print >> sys.stderr, "Ignored %d lines with invalid format\n" % ignored
if time == 0:
	print "ERROR: No stack counts found\n"
	exit(1)

if timemax != None:
	if timemax < time:
		if timemax/time > 0.02: # only warn is significant (e.g., not rounding etc)
			print "Specified --total %d is less than actual total %d, so ignored\n" % (timemax, time)
		timemax = None
if timemax == None:
	timemax = time

widthpertime = float(imagewidth - 2 * xpad) / float(timemax)
minwidth_time = minwidth / widthpertime

# prune blocks that are too narrow and determine max depth
for (id, node) in Node.iteritems():
	(func, depth, etime) = id.split(';')
	stime = node["stime"]
	if stime == None:
		print "missing start for %s" % str(id)

	if (float(etime) - float(stime)) < float(minwidth_time):
		del Node[id]
		continue

	if int(depth) > int(depthmax):
		depthmax = int(depth)

# Draw canvas
imageheight = (float(depthmax) * float(frameheight)) + float(ypad1) + float(ypad2)
im = SVG()
im.header(imagewidth, imageheight)
inc = """<defs >
        <linearGradient id="background" y1="0" y2="1" x1="0" x2="0" >
                <stop stop-color="#eeeeee" offset="5%" />
                <stop stop-color="#eeeeb0" offset="95%" />
        </linearGradient>
</defs>
<style type="text/css">
        .func_g:hover { stroke:black; stroke-width:0.5; }
</style>
<script type="text/ecmascript">
<![CDATA[
        var details;
        function init(evt) { details = document.getElementById("details").firstChild; }
        function s(info) { details.nodeValue = " """ + str(nametype) + """ " + info; }
        function c() { details.nodeValue = ' '; }
]]>
</script>"""
im.include(inc);
im.filledRectangle(0, 0, float(imagewidth), float(imageheight), 'url(#background)', "")
(white, black, vvdgrey, vdgrey) = (
	im.colorAllocate(255, 255, 255),
	im.colorAllocate(0, 0, 0),
	im.colorAllocate(40, 40, 40),
	im.colorAllocate(160, 160, 160),
	)
im.stringTTF(black, fonttype, fontsize + 5, 0.0, int(imagewidth / 2), fontsize * 2, titletext, "middle", "")
im.stringTTF(black, fonttype, fontsize, 0.0, xpad, imageheight - (ypad2 / 2), " ", "", 'id="details"')

# Draw frames

nameattr = {}

for (id, node) in Node.iteritems():
	(func, depth, etime) = id.split(';')
	stime = node["stime"]
	#print func, depth, etime

	if func == "" and depth == 0:
		etime = timemax

	x1 = float(xpad) + float(stime) * float(widthpertime)
	x2 = float(xpad) + float(etime) * float(widthpertime)
	y1 = float(imageheight) - float(ypad2) - (float(depth) + 1) * float(frameheight) + 1
	y2 = float(imageheight) - float(ypad2) - float(depth) * float(frameheight)

	samples = (float(etime) - float(stime)) * float(factor)
	samples_txt = samples	# add commas per perlfaq5
	#rx = re.compile(r'(^[-+]?\d+?(?=(?>(?:\d{3})+)(?!\d))|\G\d{3}(?=\d))')
	rx = re.compile(r'(^[-+]?\d+?(?=((?:\d{3})+)(?!\d))|\G\d{3}(?=\d))')
	samples_txt = rx.sub(r'\g<1>,', str(samples_txt))

	if (func == "") and (depth == 0):
		info = "all (" + samples_txt + " " + countname + ", 100%)"
	else:
		pct = "%.2f" % ((100 * samples) / (timemax * factor))
		escaped_func = func
		escaped_func = re.sub("&", "&amp;", escaped_func)
		escaped_func = re.sub("<", "&lt;", escaped_func)
		escaped_func = re.sub(">", "&gt;", escaped_func)
		info = escaped_func + " (" + samples_txt + " " + countname + ", " + pct + "%)"

	if func not in nameattr.keys():
		nameattr[func] = {}
	if "class" not in nameattr[func].keys():
		nameattr[func]["class"] = "func_g"
	if "onmouseover" not in nameattr[func].keys():
		nameattr[func]["onmouseover"] = "s('" + info + "')"
	if "onmouseout" not in nameattr[func].keys():
		nameattr[func]["onmouseout"] = "c()"
	if "title" not in nameattr[func].keys():
		nameattr[func]["title"] = info
	im.group_start(nameattr[func])

	im.filledRectangle(float(x1), float(y1), float(x2), float(y2), color("hot"), 'rx="2" ry="2"')

	chars = int((x2 - x1) / (fontsize * fontwidth))
	if chars >= 3:
		text = func[:chars]
		if chars < len(func):
			list(text)[-2:2] = ['.', '.']
		text = re.sub("&", "&amp;", text)
		text = re.sub("<", "&lt;", text)
		text = re.sub(">", "&gt;", text)
		im.stringTTF(black, fonttype, fontsize, 0.0, x1 + 3, 3 + (y1 + y2) / 2, text, None, None)

	im.group_end(nameattr[func])

print im.svg()

