#!BPY

import bpy
import sys

n = sys.argv.index("--")

if len(sys.argv) > n + 2:
	tmf = sys.argv[n + 2] == "-s" or sys.argv[n + 2] == "-tmf"
else:
	tmf = False

if len(sys.argv) > n + 1:
	bpy.ops.export_mesh.hab(filepath=sys.argv[n + 1], saveToTMF=tmf)
else:
	print("Specify output file.")