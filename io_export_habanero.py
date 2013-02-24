import bpy
from operator import attrgetter
import os

from struct import pack

bl_info = {
    "name": "Habanero exporter (.saf and .smf)",
    "author": "Michal Zochowski",
    "version": (2,2),
    "blender": (2,5,9),
    "location": "File > Export...",
    "description": "Export to Habanero binary formats (2nd version)",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Import-Export"}
	
exportMessage = "Finished"
maxStrLen = 32

def equal(a, b):
	return abs(a - b) < 1e-6

class DumpableList(list):
	"""
		Strukturka, będąca listą obiektów, które mają metodę dump,
		dzięki temu możemy dumpować całą listę jednym poleceniem.
		Można też tak robić z dump_tmf. Dodatkowo przy dodawaniu
		obiektów automatycznie uzupełniane są ich pola id.
	"""
	def dump(self):
		data = pack("")
		for i in self:
			data += i.dump()
		return data

	def dump_tmf(self):
		data = pack("")
		for i in self:
			data += i.dump_tmf()
		return data

	def append(self, p_object):
		p_object.id = len(self)
		super(DumpableList, self).append(p_object)

class Quaternionf:
	def __init__(self):
		self.w = 1.
		self.x = 0.
		self.y = 0.
		self.z = 0.

	def set_coords(self, w, x, y, z):
		self.w = w
		self.x = x
		self.y = y
		self.z = z

	def __eq__(self, other):
		return equal(self.w, other.w) and \
			   equal(self.x, other.x) and \
			   equal(self.y, other.y) and \
			   equal(self.z, other.z)

	def set_values(self, array):
		if len(array) == 4:
			self.w = array[0]
			self.x = array[1]
			self.y = array[2]
			self.z = array[3]

	def dump(self):
		data = pack('ffff', self.w, self.x, self.y, self.z)
		return data

class Vector3f:
	def __init__(self):
		self.x = 0.
		self.y = 0.
		self.z = 0.

	def set_values(self, x, y, z):
		self.x = x
		self.y = y
		self.z = z

	def set_values(self, array):
		if len(array) == 3:
			self.x = array[0]
			self.y = array[1]
			self.z = array[2]

	def __eq__(self, other):
		return equal(self.x, other.x) and \
			   equal(self.y, other.y) and \
			   equal(self.z, other.z)

	def __hash__(self):
		return hash((self.x, self.y, self.z))

	def __str__(self):
		return str((self.x, self.y, self.z))

	def dump(self):
		data = pack('fff', self.x, self.y, self.z)
		return data

class Vector2f:
	def __init__(self, x = 0., y = 0.):
		self.x = x
		self.y = y

	def set_values(self, x, y):
		self.x = x
		self.y = y

	def set_values(self, array):
		if len(array) == 2:
			self.x = array[0]
			self.y = array[1]

	def __eq__(self, other):
		return self.x == other.x and self.y == other.y

	def __hash__(self):
		return hash((self.x, self.y))

	def __str__(self):
		return str((self.x, self.y))

	def dump(self):
		data = pack('ff', self.x, self.y)
		return data

class Color:
	def __init__(self, array = None):
		self.r = 0.
		self.g = 0.
		self.b = 0.
		self.a = 0.
		if array:
			self.set_color(array)

	def set_color(self, array):
		if len(array) == 3: #jako, że kolory w blenderze nie mają alpha
			self.r = array[0]
			self.g = array[1]
			self.b = array[2]
			self.a = 1.

	def dump(self):
		data = pack('ffff', self.r, self.g, self.b, self.a)
		return data

class SkinnedMesh:
	def __init__(self):
		self.vertices = DumpableList()
		self.sub_meshes = DumpableList()

	def dump(self):
		print("Packing %d vertices, %d submeshes" % (len(self.vertices), len(self.sub_meshes)))
		data = pack('II', len(self.vertices), len(self.sub_meshes)) + self.vertices.dump() + self.sub_meshes.dump()
		return data

	def dump_tmf(self):
		print("Packing %d vertices, %d submeshes" % (len(self.vertices), len(self.sub_meshes)))
		data = pack('II', len(self.vertices), len(self.sub_meshes)) + self.vertices.dump_tmf() + self.sub_meshes.dump()
		return data

class Empty():
	def dump(self):
		return pack('')


class SkinVertex4:
	def __init__(self):
		self.id = 0
		self.position = Vector3f()
		self.normal = Vector3f()
		self.tex_coord = Vector2f()
		self.joints = [] # Z początku trzymamy listę jointów (a nie indexów).
		self.joint_weights = []
		self.cloned = {}

	def set_joints(self, groups, object_id, all_groups):
		if len(groups) > 4:
			print("Vertex belonging to more than 4 bones detected...")
			# Bierzemy 4 o najwiekszych wagach
			groups = sorted(groups, key=attrgetter('weight'), reverse=True)[:4]
		for group in groups:
			self.joints.append(all_groups.by_id[(object_id, group.group)])
			self.joint_weights.append(group.weight)
		for i in range(4 - len(groups)): #uzupełniamy do 4 pustymi
			self.joints.append(SkeletonJoint())
			self.joint_weights.append(0.)

	def set_parent_bone(self, parent_bone, all_groups):
		if parent_bone == '':
			self.set_joints([], 1, all_groups)
			print("Warning: Vertex with no bones detected")
			return
		self.joints.append(all_groups.by_name[parent_bone])
		self.joint_weights.append(1.)
		for i in range(3):
			self.joints.append(SkeletonJoint())
			self.joint_weights.append(0.)

	def dump_tmf(self):
		data = self.position.dump() + self.normal.dump() + self.tex_coord.dump()
		return data

	def dump(self):
		joint_indices = []
		for joint in self.joints:
			joint_indices.append(joint.id)
		data = self.position.dump() + self.normal.dump() + self.tex_coord.dump()
		for i in range(4):
			data += pack("I", joint_indices[i])
		for i in range(4):
			data += pack("f", self.joint_weights[i])
		return data

	def __eq__(self, other):
		joint_indices1 = []
		for joint in self.joints:
			joint_indices1.append(joint.id)
		joint_indices2 = []
		for joint in other.joints:
			joint_indices2.append(joint.id)
		return self.position == other.position and \
			   self.normal == other.normal and \
			   self.tex_coord == other.tex_coord and \
			   self.joint_weights == other.joint_weights and \
			   joint_indices1 == joint_indices2

	def __hash__(self):
		return hash(self.position) + hash(self.tex_coord)

	def __str__(self):
		joint_indices = []
		for joint in self.joints:
			joint_indices.append(joint.id)
		return "Vertex: " + str(self.id) + \
			   "\nPosition: " + str(self.position) + \
			   "\nNormal: " + str(self.normal) + \
			   "\nTex: " + str(self.tex_coord) + \
			   "\nJoint indices: " + str(joint_indices) + \
			   "\nJoint weights: " + str(self.joint_weights)


class Material:
	def __init__(self, sub_mesh):
		self.id = 0
		self.sub_mesh = sub_mesh
		self.values = [None] * 32
		# 0. ambient
		# 1. diffuse
		# 2. specular
		# 3. emissive
		# 4. transparency
		# 5. ambient_tex
		# 6. diffuse_tex
		# 7. specular_tex
		# 8. normal_tex
		# 9. displacement_tex
		# 10. transparency_tex
		# 11. tajemnicza_tex
		self.name = ""

	def set(self, textures, bl_material):
		self.name = bl_material.name
		for texture_slot in bl_material.texture_slots:
			if texture_slot is not None:
				filename = texture_slot.texture.image.filepath
				if (filename[0:2] == '//'):
					filename = filename[2:]
				textures.append(filename)
				texture_id = len(textures) # po dodaniu, bo numerujemy od 1
				if texture_slot.use_map_ambient:
					self.values[0] = texture_id
				if texture_slot.use_map_diffuse or texture_slot.use_map_color_diffuse:
					self.values[1] = texture_id
				if texture_slot.use_map_specular:
					self.values[2] = texture_id
				if texture_slot.use_map_translucency:
					self.values[4] = texture_id
				if texture_slot.use_map_normal:
					self.values[5] = texture_id
				if texture_slot.use_map_displacement:
					self.values[6] = texture_id
		if self.values[0] is None:
			self.values[0] = Color([bl_material.ambient] * 3)
		if self.values[1] is None:
			self.values[1] = Color(bl_material.diffuse_color)
		if self.values[2] is None:
			self.values[2] = Color(bl_material.specular_color)
			self.values[2].a = bl_material.specular_alpha
		self.values[3] = Color([bl_material.emit] * 3)
		if self.values[4] is None:
			self.values[4] = bl_material.alpha

	def dump(self):
		flags = 0
		counter = 0
		for val in self.values:
			if counter == 3 or counter > 4:
				flags += (val is not None) << counter
			else:
				flags += (not isinstance(val, int)) << counter
			counter += 1
		data = pack("I", flags)
		for i in range(4):
			if isinstance(self.values[i], int):
				data += pack("I", self.values[i])
			else:
				data += self.values[i].dump()
		if isinstance(self.values[4], int):
			data += pack("I", self.values[4])
		else:
			data += pack("f", self.values[4])
		for i in range(5, 8):
			if self.values[i] is not None:
				data += pack("I", self.values[i])
		return data

class BoundingVolume:
	"""
		Na razie będzie to zawsze AABB
	"""
	def __init__(self):
		self.bounding_volume_type = 1 # AABB
		self.xmin = float("inf")
		self.ymin = float("inf")
		self.zmin = float("inf")
		self.xmax = float("-inf")
		self.ymax = float("-inf")
		self.zmax = float("-inf")

	def update(self, vertex):
		pos = vertex.position
		if pos.x < self.xmin:
			self.xmin = pos.x
		if pos.y < self.ymin:
			self.ymin = pos.y
		if pos.z < self.zmin:
			self.zmin = pos.z
		if pos.x > self.xmax:
			self.xmax = pos.x
		if pos.y > self.ymax:
			self.ymax = pos.y
		if pos.z > self.zmax:
			self.zmax = pos.z

	def dump(self):
		data = pack('B', self.bounding_volume_type) + \
			   pack('ffffff', self.xmin, self.ymin, self.zmin, self.xmax, self.ymax, self.zmax)
		return data

class SubMesh:
	def __init__(self):
		self.material = Material(self)
		self.vertices = []

	def dump(self):
		indices = []
		for vertex in self.vertices:
			indices.append(vertex.id)
		data = pack('II', self.material.id, len(indices))
		for index in indices:
			data += pack('I', index)
		return data

class RTf:
	def __init__(self):
		self.rotation = Quaternionf()
		self.translation = Vector3f()

	def get_from_matrix(self, matrix): # wyciąga info z blenderowej macierzy 4x4
		self.rotation.set_values(matrix.to_quaternion())
		self.translation.set_values(matrix.to_translation())

	def __eq__(self, other):
		if other is None:
			return False
		return self.rotation == other.rotation and self.translation == other.translation

	def dump(self):
		data = self.rotation.dump() + self.translation.dump()
		return data

class SkeletonJoint:
	def __init__(self):
		self.id = 0
		self.parent = None # też jest SkeletonJointem
		self.bind_pose = RTf()
		self.name = ""

	def dump(self):
		global all_groups
		if self.parent:
			parent_index = self.parent.id
		else:
			parent_index = 0xFFFFFFFF
		data = pack("I", parent_index) + self.bind_pose.dump() #+ packString(self.name)
		return data

def packString(string):
	"""
		Dumpuje stringa do char[maxStrLen]
	"""
	data = pack("")
	for i in range(len(string)):
		data += pack("B", ord(string[i]))
	for i in range(maxStrLen - len(string)):
		data += pack("B", 0)
	return data

class Skeleton:
	def __init__(self):
		self.name = ""
		self.id = 1
		self.joints = DumpableList()
		self.animations = DumpableList()

	def dump(self):
		data = pack("III", len(self.joints), len(self.animations), self.id) + \
			   self.joints.dump() + self.animations.dump()
		return data

class SkeletalAnimation:
	def __init__(self):
		self.name = ""
		self.keyframe_sequences = DumpableList()

	def dump(self):
		data = self.keyframe_sequences.dump()
		return data

class SkeletonJointKeyframeSequence:
	def __init__(self):
		self.frames = DumpableList()

	def dump(self):
		data = pack("I", len(self.frames)) + self.frames.dump()
		return data

class SkeletonJointKeyframe:
	def __init__(self):
		self.beginTime = 0.
		self.pose = RTf()

	def dump(self):
		data = pack("f", self.beginTime) + self.pose.dump()
		return data


class Materials:
	def __init__(self, exp_mesh):
		self.exported_mesh = exp_mesh
		self.materials = DumpableList() # mapping from blender material id to Habanero material
		self.materials.append(Empty()) # zaślepka, żeby numerować od 1
		self.by_name = {}

	def add(self, bl_material):
		if bl_material.name not in self.by_name:
			print(bl_material.name)
			sub_mesh = SubMesh()
			sub_mesh.material.set(self.exported_mesh.textures, bl_material)
			self.exported_mesh.mesh.sub_meshes.append(sub_mesh)
			self.materials.append(sub_mesh.material)
			self.by_name[bl_material.name] = sub_mesh.material

class ExportedMesh:
	def __init__(self):
		self.textures = []
		self.vertex_bl_to_hab = {} # vertex_bl_to_hab[blender_vertex_id] = Vertex object
		self.mesh = SkinnedMesh()
		self.bb = BoundingVolume()
		self.materials = Materials(self)

# Zaczerpnięte z io_export_unreal_psk_psa.py (jednego ze skryptów rozpowszechnianych razem z blenderem)
# Jeśli to konieczne to kopiuje obiekt i wykonuje triangulację. Dlatego potem usuwamy ten obiekt.
def triangulateMesh(object):
	triangulated = False
	need_triangulate = False
	print("Selecting mesh %s" % object.name)
	scene = bpy.context.scene
	for i in scene.objects: i.select = False #deselect all objects
	object.select = True
	scene.objects.active = object #set the mesh object to current
	bpy.ops.object.mode_set(mode='OBJECT')
	print("Checking mesh if needs to convert quad to Tri...")
	for face in object.data.faces:
		if len(face.vertices) > 3:
			need_triangulate = True
			break

	bpy.ops.object.mode_set(mode='OBJECT')
	if need_triangulate:
		print("Converting quad to tri mesh...")
		me_da = object.data.copy() #copy data
		me_ob = object.copy() #copy object
		me_ob.data = me_da
		bpy.context.scene.objects.link(me_ob) #link the object to the scene #current object location
		for i in scene.objects: i.select = False #deselect all objects
		me_ob.select = True
		scene.objects.active = me_ob #set the mesh object to current
		bpy.ops.object.mode_set(mode='EDIT') #Operators
		bpy.ops.mesh.select_all(action='SELECT')#select all the face/vertex/edge
		bpy.ops.mesh.quads_convert_to_tris() #Operators
		bpy.context.scene.update()
		bpy.ops.object.mode_set(mode='OBJECT') # set it in object
		triangulated = True
		print("Triangulate Mesh Done!")
	else:
		print("No need to convert tri mesh.")
		me_ob = object
	return triangulated, me_ob

def writeTMFFile(mesh, bv, file_path):
	tmf_filename = os.path.splitext(file_path)[0] + ".tmf"
	file = open(tmf_filename, "wb")
	file.write(pack('BBBB', ord('T'), ord('M'), ord('F'), ord('2')))
	file.write(mesh.dump_tmf())
	file.write(bv.dump())
	file.close()

def writeSMFFile(mesh, bv, file_path):
	smf_filename = os.path.splitext(file_path)[0] + ".smf"
	file = open(smf_filename, "wb")
	file.write(pack('BBBBI', ord('S'), ord('M'), ord('F'), ord('2'), 1))
	file.write(mesh.dump())
	file.write(bv.dump())
	file.close()

def writeSAFFile(skeleton, file_path):
	saf_filename = os.path.splitext(file_path)[0] + ".saf"
	file = open(saf_filename, "wb")
	file.write(pack('BBBB', ord('S'), ord('A'), ord('F'), ord('2')))
	file.write(skeleton.dump())
	file.close()

def writeMTFFile(material, file_path):
	mtf_filename = os.path.dirname(file_path) + "/" + material.name + ".mtf"
	file = open(mtf_filename, "wb")
	file.write(pack('BBBB', ord('M'), ord('T'), ord('F'), ord('2')))
	file.write(material.dump())
	file.close()

def write_materials(materials, file_path):
	for material in materials.materials:
		if isinstance(material, Material):
			writeMTFFile(material, file_path)

def write_i2n(exported_mesh, file_path, skeleton = None):
		i2n_filename = os.path.dirname(file_path) + "/i2n"
		skeleton_name = os.path.basename(file_path)
		skeleton_name = os.path.splitext(skeleton_name)[0]
		file = open(i2n_filename, "w")
		file.write("#materials\n")
		materials = exported_mesh.materials.materials
		for i in range(len(materials)):
			if isinstance(materials[i], Material):
				file.write("%d. %s\n" % (i, materials[i].name))
		file.write("#textures\n")
		for i in range(len(exported_mesh.textures)):
			file.write("%d. %s\n" % (i + 1, exported_mesh.textures[i]))
		if skeleton:
			file.write("#skeleton\n1. %s\n" % skeleton_name)
			file.write("#joints\n")
			for i in range(len(skeleton.joints)):
				file.write("%d. %s\n" % (i, skeleton.joints[i].name))
			file.write("#animations\n")
			for i in range(len(skeleton.animations)):
				file.write("%d. %s\n" % (i, skeleton.animations[i].name))

def create_vertex(bl_vertex, object, object_id, mesh, cloning = False):
	hab_vertex = SkinVertex4()
	matrix = object.matrix_local.inverted()
	par = object.parent
	while par:
		matrix = matrix * par.matrix_local.inverted()
		par = par.parent
	hab_vertex.position.set_values(matrix.inverted() * bl_vertex.co)
	hab_vertex.normal.set_values(matrix.to_3x3().transposed() * bl_vertex.normal)
	if len(bl_vertex.groups):
		hab_vertex.set_joints(bl_vertex.groups, object_id, mesh.groups) # set joints and weights
	else:
		hab_vertex.set_parent_bone(object.parent_bone, mesh.groups) # set one joint and weight = 1
	if not cloning:
		mesh.vertex_bl_to_hab[(object_id, bl_vertex.index)] = hab_vertex
	return hab_vertex

def getMesh(exported_mesh, object, object_id):
	print("Parsing mesh.")
	bl_mesh = object.data
	hab_mesh = exported_mesh.mesh
	bb = exported_mesh.bb
	print("Reading Vertices.")
	for bl_vertex in bl_mesh.vertices:
		hab_vertex = create_vertex(bl_vertex, object, object_id, exported_mesh)
		hab_mesh.vertices.append(hab_vertex)
		bb.update(hab_vertex)
	print("Bounding volume:")
	print("%f %f %f %f %f %f" % (bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax))

	print("Getting material info.")
	for bl_material in bl_mesh.materials:
		exported_mesh.materials.add(bl_material)

	uv_layer = bl_mesh.uv_textures.active # for texture coords
	print("Reading %d faces." % len(bl_mesh.faces))
	for bl_face in bl_mesh.faces:
		face_index = bl_face.index
		material_name = bl_mesh.materials[bl_face.material_index].name
		sub_mesh = exported_mesh.materials.by_name[material_name].sub_mesh
		counter = 0
		for bl_vertex in bl_face.vertices:
			coord_x = 0.
			coord_y = 0.
			if uv_layer is not None:
				coord_x = uv_layer.data[face_index].uv[counter][0]
				coord_y = 1.0 - uv_layer.data[face_index].uv[counter][1] # taka przypadłość blendera
			vertex = exported_mesh.vertex_bl_to_hab[(object_id, bl_vertex)]
			if ( equal(vertex.tex_coord.x, coord_x) and equal(vertex.tex_coord.y, coord_y)
				or vertex.tex_coord == Vector2f(0.0, 0.0) ):
				
				sub_mesh.vertices.append(vertex)
				vertex.tex_coord.set_values([coord_x, coord_y])
			else:# wierzchołek już ma przypisane koordynaty, sprawdzamy czy musimy zduplikować
				if (coord_x, coord_y) in vertex.cloned:
					sub_mesh.vertices.append(vertex.cloned[(coord_x, coord_y)])
				else: #trzeba zduplikować
					new_vertex = create_vertex(bl_mesh.vertices[bl_vertex], object, object_id, exported_mesh, True)
					hab_mesh.vertices.append(new_vertex)
					new_vertex.tex_coord.set_values([coord_x, coord_y])
					sub_mesh.vertices.append(new_vertex)
					vertex.cloned[(coord_x, coord_y)] = new_vertex
			counter += 1
	for sub_mesh in exported_mesh.mesh.sub_meshes:
		print("Read submesh with material %s: %d indices" % (sub_mesh.material.name, len(sub_mesh.vertices)))

def getSkeletalAnimation(exported_mesh, armature_obj, all_groups):
	print("Parsing animations.")
	armature = armature_obj.data
	hab_skeleton = exported_mesh.skeleton
	hab_skeleton.name = armature.name
	print("Getting bones from armature " + armature.name)
	for bone in armature.bones:
		if bone.name not in all_groups.by_name:
			all_groups.add_empty(bone.name)
		joint = all_groups.by_name[bone.name]
		if bone.parent is None:
			joint.parent = None
			joint.matrix = armature_obj.matrix_local * bone.matrix_local
			joint.bind_pose.get_from_matrix(joint.matrix)
			for child_bone in bone.children:
				SetJointsPose(child_bone, all_groups)
	hab_skeleton.joints = all_groups.joints

	scene = bpy.context.scene
	fps = scene.render.fps
	frame_length = (1. / fps)

	for object in scene.objects:
		object.select = False
	armature_obj.select = True
	scene.objects.active = armature_obj
	bpy.ops.object.mode_set(mode='POSE')
	print("Reading animations:")
	for action in bpy.data.actions:
		armature_obj.animation_data.action = action
		animation = SkeletalAnimation()
		animation.name = action.name
		print(animation.name)
		sequences = animation.keyframe_sequences
		for _ in hab_skeleton.joints: # creating sequences
			seq = SkeletonJointKeyframeSequence()
			sequences.append(seq)
		frame = -100000
		bpy.ops.screen.frame_jump()
		while frame < scene.frame_current: # filling sequences
			frame = scene.frame_current
			scene.frame_set(frame)
			print("Jumped to frame %d" % frame)
			time = frame_length * frame
			for sequence in sequences: #creating keyframes
				keyframe = SkeletonJointKeyframe()
				keyframe.beginTime = time
				sequence.frames.append(keyframe)
			for bone in armature_obj.pose.bones:
				sequences[all_groups.by_name[bone.name].id].frames[-1].pose.translation.set_values(bone.location)
				sequences[all_groups.by_name[bone.name].id].frames[-1].pose.rotation.set_values(bone.rotation_quaternion)
			bpy.ops.screen.keyframe_jump()
		hab_skeleton.animations.append(animation)
	return hab_skeleton

def SetJointsPose(bone, all_groups):
	if bone.name not in all_groups.by_name:
		all_groups.add_empty(bone.name)
	joint = all_groups.by_name[bone.name]
	joint.parent = all_groups.by_name[bone.parent.name]
	matrix = bone.parent.matrix_local.inverted() * bone.matrix_local # compute relative RTf matrix
	joint.bind_pose.get_from_matrix(matrix)
	joint.matrix = matrix
	for child_bone in bone.children:
		SetJointsPose(child_bone, all_groups)

def OptimizeAnimations(skeleton):
	print("Optimizing animations.")
	for animation in skeleton.animations:
		for sequence in animation.keyframe_sequences:
			actual = None
			equal = False
			i = 0
			while i < len(sequence.frames):
				if actual == sequence.frames[i].pose:
					if equal:
						del sequence.frames[i - 1]
					else:
						equal = True
						i += 1
				else:
					equal = False
					i+= 1
				actual = sequence.frames[i - 1].pose
			if len(sequence.frames) == 2: # jak zostały tylko 2 takie same, to je usuwamy
				if sequence.frames[0].pose == sequence.frames[1].pose:
					del sequence.frames[1]

class Groups:
	"""
		Lista tak naprawdę jointów (w blenderze jest rozróżnienie na kości i grupy wierzchołków,
		ale jest powiązanie 1-1 przez nazwę)
	"""
	def __init__(self):
		self.by_name = {}
		self.by_id = {}
		self.joints = DumpableList()

	def add(self, object_id, group):
		if group.name not in self.by_name:
			joint = SkeletonJoint()
			joint.name = group.name
			self.joints.append(joint)
			self.by_name[group.name] = joint
			self.by_id[(object_id, group.index)] = joint
		else:
			self.by_id[(object_id, group.index)] = self.by_name[group.name]

	def add_empty(self, name):
		joint = SkeletonJoint()
		joint.name = name
		self.joints.append(joint)
		self.by_name[name] = joint

def getGroups(object, index, all_groups):
	for group in object.vertex_groups:
		all_groups.add(index, group)


def writeFiles(filename, toTMF):
	print("Saving scene to %s" % filename)
	objects = []
	triangulates = []
	for object in bpy.data.objects:
		if object.type == 'MESH':
			triangulated, obj = triangulateMesh(object)
			objects.append(obj)
			triangulates.append(triangulated)

	exported_mesh = ExportedMesh()

	all_groups = Groups()
	for i in range(len(objects)):
		getGroups(objects[i], i, all_groups)
	print("Number of groups: %d" % len(all_groups.joints))
	exported_mesh.groups = all_groups
	for i in range(len(objects)):
		getMesh(exported_mesh, objects[i], i)
	if toTMF:
		try:
			writeTMFFile(exported_mesh.mesh, exported_mesh.bb, filename)
			write_materials(exported_mesh.materials, filename)
			write_i2n(exported_mesh, filename)
		except IOError:
			print("IOError.")
	else:
		exported_mesh.skeleton = Skeleton()
		for object in bpy.data.objects:
			if object.type == 'ARMATURE':
				getSkeletalAnimation(exported_mesh, object, all_groups)
		OptimizeAnimations(exported_mesh.skeleton)
		try:
			writeSMFFile(exported_mesh.mesh, exported_mesh.bb, filename)
			writeSAFFile(exported_mesh.skeleton, filename)
			write_materials(exported_mesh.materials, filename)
			write_i2n(exported_mesh, filename, exported_mesh.skeleton)
		except IOError:
			print("IOError.")

	vertices = {}
	for vertex in exported_mesh.mesh.vertices:
		if (vertex.position, vertex.tex_coord) in vertices:
			print("Duplicated vertex detected!")
			print(vertex)
			print(vertices[(vertex.position, vertex.tex_coord)])
		else:
			vertices[(vertex.position, vertex.tex_coord)] = vertex

	scene = bpy.context.scene
	for i in scene.objects: i.select = False #deselect all objects

	for i in range(len(objects)):
		object = objects[i]
		if triangulates[i]:
			print("Removing triangulated object...")
			object.select = True
			scene.objects.active = object #set the mesh object to current
	bpy.ops.object.mode_set(mode='OBJECT')
	bpy.ops.object.delete()

class ExportToHabanero(bpy.types.Operator):
	"""Export Skeleton Mesh / Skeletal Animation file(s)"""
	global exportMessage
	bl_idname = "export_mesh.hab"
	bl_label = "Export SMF/SAF"
	__doc__ = """Select one mesh to be exported."""
	
	filepath = bpy.props.StringProperty(
			name="File Path",
			description="Filepath used for exporting the SAF file",
			maxlen= 1024,
			subtype='FILE_PATH'
			)

	saveToTMF = bpy.props.BoolProperty(
		name="To TMF",
		description="Indicates if model will be saved to TMF file",
		default = False
	)

	@classmethod
	def poll(cls, context):
		return True

	def execute(self, context):
		writeFiles(self.filepath, self.saveToTMF)
		self.report({'WARNING', 'INFO'}, exportMessage)
		return {'FINISHED'}
	
	def invoke(self, context, event):
		wm = context.window_manager
		wm.fileselect_add(self)
		return {'RUNNING_MODAL'}

def menu_func(self, context):
	default_path = os.path.splitext(bpy.data.filepath)[0] + ".saf"
	self.layout.operator(ExportToHabanero.bl_idname, text="Skeleton Mesh / Skeletal Animation (.smf/.saf)").filepath = default_path

def register():
	bpy.utils.register_module(__name__)
	bpy.types.INFO_MT_file_export.append(menu_func)

def unregister():
	bpy.utils.unregister_module(__name__)
	bpy.types.INFO_MT_file_export.remove(menu_func)

if __name__ == "__main__":
	register()