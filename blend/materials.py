#!/usr/bin/env python3
# Blender materials for Sky130 PDK layers
# WORK IN PROGRESS
import bpy

bpy.ops.object.delete(use_global=False, confirm=False)
bpy.ops.object.delete(use_global=False, confirm=False)
bpy.context.space_data.recent_folders_active = 1
bpy.context.space_data.params.filename = "sample.blend"
bpy.context.space_data.show_word_wrap = True
bpy.context.space_data.show_word_wrap = False
bpy.context.object.data.clip_end = 10000
bpy.context.space_data.context = 'WORLD'
bpy.context.space_data.context = 'RENDER'
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.space_data.context = 'WORLD'
bpy.data.worlds["World"].node_tree.nodes["Sky Texture"].sun_disc = False
bpy.ops.outliner.item_activate(deselect_all=True)
bpy.context.space_data.shading.type = 'SOLID'
bpy.context.space_data.context = 'MATERIAL'
bpy.ops.material.new()
bpy.context.object.active_material.name = "prbndry"
bpy.data.materials["prbndry"].node_tree.nodes["Principled BSDF"].inputs[0].default_value = (0.0144437, 0, 0.21586, 1)
bpy.context.space_data.shading.type = 'MATERIAL'
bpy.ops.material.new()
bpy.context.object.active_material.name = "nwell"
bpy.data.materials["nwell"].node_tree.nodes["Principled BSDF"].inputs[0].default_value = (0, 0, 0.21586, 1)
