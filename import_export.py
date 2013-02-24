#!BPY

import bpy
import os
import sys

n = sys.argv.index("--")

if len(sys.argv) > n + 3:
	tmf = sys.argv[n + 3] == "-s" or sys.argv[n + 3] == "-tmf"
else:
	tmf = False

for object in bpy.context.scene.objects:
	bpy.context.scene.objects.unlink(object)

loaded = False

if len(sys.argv) > n + 1:
	path = sys.argv[n + 1]
	ext = os.path.splitext(path)[1]
	if ext == ".obj":
		bpy.ops.import_scene.obj(filepath=path)
		object = bpy.context.scene.objects[0]
		bpy.context.scene.objects.active = object
		object.select = True
		loaded = True
	else:
		print("Unknown extension: %s" % ext)
else:
	print("Specify input file.")

if loaded and len(sys.argv) > n + 2:
	bpy.ops.export_mesh.hab(filepath=sys.argv[n + 2], saveToTMF=tmf)
else:
	print("Specify output file.")