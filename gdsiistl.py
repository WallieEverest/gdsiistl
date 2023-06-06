#!/usr/bin/env python3
"""
Description:
    This program converts a GDSII 2D layout file to multiple 3D STL files that can
    be visualized in an external program (e.g., Blender).

Note:
    This application removes all labels and paths from the processng list,
    as they do not have a 3D equivalant in the 3D mesh of the STL file.

Usage:
    - edit the "layerstack" variable in the "CONFIGURATION" section below
    - run "gdsiistl file.gds"

    or
    - run "gdsiistl' for the default file "./gds/sample.gds"

    and/or
    - include the file "./gds/layerstack.json" to override the default configuration values

    Output:
        - the files ./stl/layername1.stl, ./stl/layername2.stl, ...

Operation:
    The program takes one argument, a path to a GDSII file. It reads shapes from
    each layer of the GDSII file, converts them to polygon boundaries, then makes
    a triangle mesh for each GDSII layer by extruding the polygons to given sizes.

    All units, including the units of the exported file, are the GDSII file's
    user units (often microns).

License:
    GNU General Public License v3.0 

History:
    1.) Original script by David Teal
        https://github.com/dteal/gdsiistl
    2.) Forked by Maximo Balestrini for SkyWater130. Added (layer, dataset) tuple filtering.
        https://github.com/mbalestrini/gdsiistl
    3.) Forked by Wallace Everest for Blender 3.1 and large data sets. Added function calls, polygon merge and memory handling.
        https://github.com/WallieEverest/gdsiistl

To do:
    1.) Filter for-each-loop on tuples
    2.) Detect external layerstack.json in the gds folder
    3.) Create Blender scripts for default fabric settings
"""

import sys # read command-line arguments
import gdspy # open gds file
from stl import mesh # write stl file (python package name is "numpy-stl")
import numpy as np # fast math on lots of points
import triangle # triangulate polygons
import collections

# get the input file name
if len(sys.argv) < 2: # sys.argv[0] is the name of the program
    #print("Error: need exactly one file as a command line argument.")
    #sys.exit(0)
    gdsii_file_path = './gds/sample.gds'
else:
    gdsii_file_path = sys.argv[1]

########## CONFIGURATION (EDIT THIS PART) #####################################
# choose which GDSII layers to use
layerstack = {
    # (layernumber, datatype) : (zmin, zmax, 'layername'),
    (235,4): (0, 0.1, 'sub'),
    (64,20): (0, 0.1, 'nwell'),    
    (65,44): (0, 0.1, 'tap'),    
    (65,20): (0, 0.1, 'diff'),    
    (66,20): (0, 0.1, 'poly'),    
    (66,44): (0, 0.1, 'licon'),    
    (67,20): (0, 0.1, 'li1'),    
    (67,44): (0, 0.1, 'mcon'),    
    (68,20): (0, 0.1, 'met1'),    
    (68,44): (0, 0.1, 'via'),    
    (69,20): (0, 0.1, 'met2'),    
    (69,44): (0, 0.1, 'via2'),    
    (70,20): (0, 0.1, 'met3'),    
    (70,44): (0, 0.1, 'via3'),    
    (71,20): (0, 0.1, 'met4'),    
    (71,44): (0, 0.1, 'via4'),    
    (72,20): (0, 0.1, 'met5'),
    # (83,44): (0, 0.1, 'text'),
}

def filter_layer(layer_num):
    """Function to filter layers"""
    print(f'Filtering layer {layer_num}')
    for name, cell in gdsii.cells.items():
        cell.remove_labels(lambda text: any)
        cell.remove_paths(lambda points: any)
        cell.remove_polygons(lambda points, layer, datatype: layer != layer_num)

def flatten_layer():
    """Function to flatten layers"""
    for cell in gdsii.top_level():
        cell_name = cell.name  # save top-level name, assumed only one top-level cell in GDS file
        print('Before - Labels:{} References:{} Polygons:{} Paths:{}'.format( \
            len(cell.labels),len(cell.references),len(cell.polygons),len(cell.paths)))
        print(f'Flattening...')
        cell.flatten()
        print('After  - Labels:{} References:{} Polygons:{} Paths:{}'.format( \
            len(cell.labels),len(cell.references),len(cell.polygons),len(cell.paths)))

    # removing flattened standard cells
    for cell in gdsii.top_level():
        if cell.name != cell_name:
            gdsii.remove(cell)

def merge_layers_and_datatypes(cell):
    """Function to merge polygons"""
    # copy unordered polygonSets into a layered dict structure
    polydict = collections.defaultdict(list)
    for polyset in cell.polygons:
        for l, d, polyarray in zip(polyset.layers, polyset.datatypes, polyset.polygons):
            polydict[(l, d)].append(polyarray)

    # merge polygons on each layer
    # transfer layer-ordered polygons back into a polygonSet
    cell.polygons = []
    for lnum, polyarray in polydict.items():
        if lnum in layerstack.keys():
            _, _, layername = layerstack[lnum]
            sys.stdout.write(f"Layer {layername}: {len(polyarray)} polygons")
            result = gdspy.boolean(polyarray, None, "or")
            if result is not None:
                for polygon in result.polygons:
                    # append a new polygonSet object and assign an individual polygon
                    cell.add(gdspy.PolygonSet([[0,0]], layer=lnum[0], datatype=lnum[1]))
                    index = len(cell.polygons)
                    cell.polygons[index-1].polygons[0] = polygon
                print(f" merged to {len(result.polygons)}")
        else:
            print(f"Layer {lnum}: {len(polyarray)} polygons")

        polydict[lnum] = []

def layers_to_polygons():
    """Function to extract polygons to a dictionary"""
    cells = gdsii.top_level() # get all cells that aren't referenced by another
    for cell in cells: # loop through cells to read paths and polygons

        # $$$CONTEXT_INFO$$$ is a separate, non-standard compliant cell added
        # optionally by KLayout to store extra information not needed here.
        # see https://www.klayout.de/forum/discussion/1026/very-
        # important-gds-exported-from-k-layout-not-working-on-cadence-at-foundry
        if cell.name == '$$$CONTEXT_INFO$$$':
            continue # skip this cell

        # combine will all referenced cells (instances, SREFs, AREFs, etc.)
        #cell = cell.flatten()
        print(f"Processing cell {cell.name}")

        # Boolean merge overlaping polygons
        sys.stdout.write('Pass 1 - ')
        merge_layers_and_datatypes(cell)
        sys.stdout.write('Pass 2 - ')
        merge_layers_and_datatypes(cell)
        sys.stdout.write('Pass 3 - ')
        merge_layers_and_datatypes(cell)
        sys.stdout.write('Pass 4 - ')
        merge_layers_and_datatypes(cell)

        # loop through paths in cell
        for path in cell.paths:
            lnum = (path.layers[0],path.datatypes[0]) # GDSII layer number
            # create empty array to hold layer polygons if it doesn't yet exist
            layers[lnum] = [] if not lnum in layers else layers[lnum]
            # add paths (converted to polygons) that layer
            for poly in path.get_polygons():
                layers[lnum].append((poly, None, False))

        # loop through polygons (and boxes) in cell
        for polygon in cell.polygons:
            lnum = (polygon.layers[0],polygon.datatypes[0]) # same as before...
            layers[lnum] = [] if not lnum in layers else layers[lnum]
            for poly in polygon.polygons:
                layers[lnum].append((poly, None, False))

"""
At this point, "layers" is a Python dictionary structured as follows:

layers = {
   0 : [ ([[x1, y1], [x2, y2], ...], None, False), ... ]
   1 : [ ... ]
   2 : [ ... ]
   ...
}

Each dictionary key is a GDSII layer number (0-255), and the value of the
dictionary at that key (if it exists; keys were only created for layers with
geometry) is a list of polygons in that GDSII layer. Each polygon is a 3-tuple
whose first element is a list of points (2-element lists with x and y
coordinates), second element is None (for the moment; this will be used later),
and third element is False (whether the polygon is clockwise; will be updated).
"""

########## TRIANGULATION ######################################################

# An STL file is a list of triangles, so the polygons need to be filled with
# triangles. This is a surprisingly hard algorithmic problem, especially since
# there are few limits on what shapes GDSII file polygons can be. So we use the
# Python triangle library (documentation is at https://rufat.be/triangle/),
# which is a Python interface to a fast and well-written C library also called
# triangle (with documentation at https://www.cs.cmu.edu/~quake/triangle.html).

def polygon_to_triangles():
    """Function to convert polygons to triangles"""
    # loop through all layers
    for layer_number, polygons in layers.items():

        # but skip layer if it won't be exported
        if not layer_number in layerstack.keys():
            continue

        num_triangles[layer_number] = 0

        # loop through polygons in layer
        for index, (polygon, _, _) in enumerate(polygons):

            num_polygon_points = len(polygon)

            # determine whether polygon points are CW or CCW
            area = 0
            for i, v1 in enumerate(polygon): # loop through vertices
                v2 = polygon[(i+1) % num_polygon_points]
                area += (v2[0]-v1[0])*(v2[1]+v1[1]) # integrate area
            clockwise = area > 0

            # GDSII implements holes in polygons by making the polygon edge
            # wrap into the hole and back out along the same line. However,
            # this confuses the triangulation library, which fills the holes
            # with extra triangles. Avoid this by moving each edge back a
            # very small amount so that no two edges of the same polygon overlap.
            delta = 0.00001 # inset each vertex by this much (smaller has broken one file)
            points_i = polygon # get list of points
            points_j = np.roll(points_i, -1, axis=0) # shift by 1
            points_k = np.roll(points_i, 1, axis=0) # shift by -1
            # calculate normals for each edge of each vertex (in parallel, for speed)
            normal_ij = np.stack((points_j[:, 1]-points_i[:, 1],
                                points_i[:, 0]-points_j[:, 0]), axis=1)
            normal_ik = np.stack((points_i[:, 1]-points_k[:, 1],
                                points_k[:, 0]-points_i[:, 0]), axis=1)
            length_ij = np.linalg.norm(normal_ij, axis=1)
            length_ik = np.linalg.norm(normal_ik, axis=1)
            normal_ij /= np.stack((length_ij, length_ij), axis=1)
            normal_ik /= np.stack((length_ik, length_ik), axis=1)
            if clockwise:
                normal_ij = -1*normal_ij
                normal_ik = -1*normal_ik
            # move each vertex inward along its two edge normals
            polygon = points_i - delta*normal_ij - delta*normal_ik

            # In an extreme case of the above, the polygon edge doubles back on
            # itself on the same line, resulting in a zero-width segment. I've
            # seen this happen, e.g., with a capital "N"-shaped hole, where
            # the hole split line cuts out the "N" shape but splits apart to
            # form the triangle cutout in one side of the shape. In any case,
            # simply moving the polygon edges isn't enough to deal with this;
            # we'll additionally mark points just outside of each edge, between
            # the original edge and the delta-shifted edge, as outside the polygon.
            # These parts will be removed from the triangulation, and this solves
            # just this case with no adverse affects elsewhere.
            hole_delta = 0.00001 # small fraction of delta
            holes = 0.5*(points_j+points_i) - hole_delta*delta*normal_ij
            # HOWEVER: sometimes this causes a segmentation fault in the triangle
            # library. I've observed this as a result of certain various polygons.
            # Frustratingly, the fault can be bypassed by *rotating the polygons*
            # by like 30 degrees (exact angle seems to depend on delta values) or
            # moving one specific edge outward a bit. I have absolutely no idea
            # what is wrong. In the interest of stability over full functionality,
            # this is disabled. TODO: figure out why this happens and fix it.
            use_holes = False

            # triangulate: compute triangles to fill polygon
            point_array = np.arange(num_polygon_points)
            edges = np.transpose(np.stack((point_array, np.roll(point_array, 1))))
            if use_holes:
                triangles = triangle.triangulate(dict(vertices=polygon,
                                                    segments=edges,
                                                    holes=holes), opts='p')
            else:
                triangles = triangle.triangulate(dict(vertices=polygon,
                                                    segments=edges), opts='p')

            if not 'triangles' in triangles.keys():
                triangles['triangles'] = []

            # each line segment will make two triangles (for a rectangle), and the polygon
            # triangulation will be copied on the top and bottom of the layer.
            num_triangles[layer_number] += num_polygon_points*2 + \
                                        len(triangles['triangles'])*2
            polygons[index] = (polygon, triangles, clockwise)

"""
At this point, "layers" is as follows:

layers = {
   0 : [ ([[x1, y1], [x2, y2], ...],
          {'vertices': [[x1, y1], ...], 'triangles': [[0, 1, 2], ...], ...},
          clockwise), ... ]
   1 : [ ... ]
   2 : [ ... ]
   ...
}

Each dictionary key is a GDSII layer number (0-255), and the value of the
dictionary at that key (if it exists; keys were only created for layers with
geometry) is a list of polygons in that GDSII layer. Each polygon has 3 parts:
First, a list of vertices, as before. Second, a dictionary with triangulation
information: the 'vertices' element contains vertex information stored the
same way as the main polygon vertices, and the 'triangles' element is a list
of which vertices correspond to which triangle (in counterclockwise order).
Third and finally, a boolean value that indicates whether the polygon was
defined clockwise (so that the STL triangles are oriented correctly).
"""

########## EXTRUSION ##########################################################

# Finally, now that we have polygon boundaries and triangulations, we can
# write it to an STL file. To make this fast (given there could be tens of
# thousands of triangles), we use the numpy-stl library, which uses numpy
# for somewhat accelerated vector math. See the documentation at
# (https://numpy-stl.readthedocs.io/en/latest/)

def extrude_triangles():
    "Function to exrude triangles"
    for layer in layers:

        # but skip layer if it won't be exported
        if not layer in layerstack.keys():
            continue

        # Make a list of triangles.
        # This data contains vertex xyz position data as follows:
        # layer_mesh_data['vectors'] = [ [[x1,y1,z1], [x2,y2,z1], [x3,y3,z3]], ...]
        layer_mesh_data = np.zeros(num_triangles[layer], dtype=mesh.Mesh.dtype)

        layer_pointer = 0
        for index, (polygon, triangles, clockwise) in enumerate(layers[layer]):

            # The numpy-stl library expects counterclockwise triangles. That is,
            # one side of each triangle is the outside surface of the STL file
            # object (assuming a watertight volume), and the other side is the
            # inside surface. If looking at a triangle from the outside, the
            # vertices should be in counterclockwise order. Failure to do so may
            # cause certain STL file display programs to not display the
            # triangles correctly (e.g., the backward triangles will be invisible).

            zmin, zmax, layername = layerstack[layer]

            # make a list of triangles around the polygon boundary
            points_i = polygon # list of 2D vertices
            if clockwise: # order polygon 2D vertices counter-clockwise
                points_i = np.flip(polygon, axis=0)
            points_i_min = np.insert(points_i, 2, zmin, axis=1) # bottom left
            points_i_max = np.insert(points_i, 2, zmax, axis=1) # top left
            points_j_min = np.roll(points_i_min, -1, axis=0) # bottom right
            points_j_max = np.roll(points_i_max, -1, axis=0) # top right
            rights = np.stack((points_i_min, points_j_min, points_j_max), axis=1)
            lefts = np.stack((points_j_max, points_i_max, points_i_min), axis=1)

            # make a list of polygon interior (face) triangles
            vs = triangles['vertices']
            ts = triangles['triangles']
            if len(ts) > 0:
                face_tris = np.take(vs, ts, axis=0)
                top = np.insert(face_tris, 2, zmax, axis=2) # list of top triangles
                bottom = np.insert(face_tris, 2, zmin, axis=2) # list of bottom ~
                bottom = np.flip(bottom, axis=1) # reverse vertex order to make CCW
                faces = np.concatenate((lefts, rights, top, bottom), axis=0)
            else: # didn't generate any triangles! (degenerate edge case)
                faces = np.concatenate((lefts, rights), axis=0)

            # add side and face triangles to layer mesh
            layer_mesh_data['vectors'][layer_pointer:(layer_pointer+len(faces))] = faces
            layer_pointer += len(faces)

        # save layer to STL file
        #filename = gdsii_file_path + '_{}.stl'.format(layername)
        filename = './stl/{}.stl'.format(layername)
        print('    ({}, {}) to {}'.format(layer, layername, filename))
        layer_mesh_object = mesh.Mesh(layer_mesh_data, remove_empty_areas=False)
        layer_mesh_object.save(filename)

def not_in_layer_list(layer_index):
    result = True
    for (layer_number,_) in layerstack.keys():
        if (layer_index == layer_number):
            result = False
    return result

########## INPUT ##############################################################
# First, the input file is read using the gdspy library, which interprets the
# GDSII file and formats the data Python-style.
# See https://gdspy.readthedocs.io/en/stable/index.html for documentation.
# Second, the boundaries of each shape (polygon or path) are extracted for
# further processing.

# --- Main Routine ---
print('Reading GDSII file {}...'.format(gdsii_file_path))
gdsii = gdspy.GdsLibrary()
gdsii.read_gds(gdsii_file_path, units='import')
top_cells = gdsii.top_level()
for layer_index in top_cells[0].get_layers():  # presumes only one top-level cell
    if not_in_layer_list(layer_index):
        continue
    gdsii = gdspy.GdsLibrary()
    gdsii.read_gds(gdsii_file_path, units='import')
    filter_layer(layer_index)
    gdsii.write_gds('temp.gds')  # only cells from the selected layr are contained in the file

    gdsii = gdspy.GdsLibrary()  # Renew library configuration
    gdsii.read_gds('temp.gds', units='import')
    flatten_layer()
    gdsii.write_gds('temp.gds')

    gdsii = gdspy.GdsLibrary()  # Renew library configuration
    gdsii.read_gds('temp.gds', units='import')

    print('Extracting polygons...')
    layers = {} # array to hold all geometry, sorted into layers
    layers_to_polygons()

    print('Triangulating polygons...')
    num_triangles = {} # will store the number of triangles for each layer
    polygon_to_triangles()

    print('Extruding polygons and writing to files...')
    extrude_triangles()

print('Done.')
