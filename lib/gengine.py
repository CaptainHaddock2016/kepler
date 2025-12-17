from vectorio import Polygon
from adafruit_display_shapes.line import Line
from adafruit_display_shapes.circle import Circle
from displayio import Palette
from ulab import numpy as np
import math

def HorizontalGrid(x,y,z, dx,dz, nx,nz):
    """ Returns a nx by nz wireframe grid that starts at (x,y,z) with width dx.nx and depth dz.nz. """
    
    grid = Wireframe()
    grid.addNodes([[x+n1*dx, y, z+n2*dz] for n1 in range(nx+1) for n2 in range(nz+1)])
    grid.addEdges([(n1*(nz+1)+n2,n1*(nz+1)+n2+1) for n1 in range(nx+1) for n2 in range(nz)])
    grid.addEdges([(n1*(nz+1)+n2,(n1+1)*(nz+1)+n2) for n1 in range(nx) for n2 in range(nz+1)])
    
    return grid

def FractalLandscape(origin=(0,0,0), dimensions=(400,400), iterations=4, height=40):
    import random
    
    def midpoint(nodes):
        m = 1.0/ len(nodes)
        x = m * sum(n[0] for n in nodes) 
        y = m * sum(n[1] for n in nodes) 
        z = m * sum(n[2] for n in nodes) 
        return [x,y,z]
    
    (x,y,z) = origin
    (dx,dz) = dimensions
    nodes = [[x, y, z], [x+dx, y, z], [x+dx, y, z+dz], [x, y, z+dz]]
    edges = [(0,1), (1,2), (2,3), (3,0)]
    size = 2

    for i in range(iterations):
        # Add nodes midway between each edge
        for (n1, n2) in edges:
            nodes.append(midpoint([nodes[n1], nodes[n2]]))

        # Add nodes to the centre of each square
        squares = [(x+y*size, x+y*size+1, x+(y+1)*size+1, x+(y+1)*size) for y in range(size-1) for x in range(size-1)]
        for (n1,n2,n3,n4) in squares:
            nodes.append(midpoint([nodes[n1], nodes[n2], nodes[n3], nodes[n4]]))
        
        # Sort in order of grid
        nodes.sort(key=lambda node: (node[2],node[0]))
        
        size = size*2-1
        # Horizontal edge
        edges = [(x+y*size, x+y*size+1) for y in range(size) for x in range(size-1)]
        # Vertical edges
        edges.extend([(x+y*size, x+(y+1)*size) for x in range(size) for y in range(size-1)])
        
        # Shift node heights
        scale = height/2**(i*0.8)
        for node in nodes:
            node[1] += (random.random()-0.5)*scale
    
    grid = Wireframe(nodes)
    grid.addEdges(edges)
    
    return grid

def Cuboid(x,y,z,w,h,d, colour=(255, 255, 255)):
    """ Return a wireframe cuboid starting at (x,y,z)
        with width, w, height, h, and depth, d. """

    cuboid = Wireframe()
    cuboid.addNodes(np.array([[nx,ny,nz] for nx in (x,x+w) for ny in (y,y+h) for nz in (z,z+d)]))
    cuboid.addFaces([(0,1,3,2), (7,5,4,6), (4,5,1,0), (2,3,7,6), (0,2,6,4), (5,7,3,1)], face_colour=colour)
    
    return cuboid

def Spheroid(x,y,z, rx, ry, rz, resolution=10, colour=(255, 255, 255), strip_color=(255, 0, 0), show_strips=True):
    #  From Pygame

    spheroid   = Wireframe()
    latitudes  = [n*np.pi/resolution for n in range(1,resolution)]
    longitudes = [n*2*np.pi/resolution for n in range(resolution)]

    spheroid.addNodes([(x + rx*np.sin(n)*np.sin(m), y - ry*np.cos(m), z - rz*np.cos(n)*np.sin(m)) for m in latitudes for n in longitudes])

    num_nodes = resolution*(resolution-1)
    spheroid.addFaces([(m+n, (m+resolution)%num_nodes+n, (m+resolution)%resolution**2+(n+1)%resolution, m+(n+1)%resolution) for n in range(resolution) for m in range(0,num_nodes-resolution,resolution)], colour)

    spheroid.addNodes([(x, y+ry, z),(x, y-ry, z)])
    spheroid.addFaces([(n, (n+1)%resolution, num_nodes+1) for n in range(resolution)], colour)
    start_node = num_nodes-resolution
    spheroid.addFaces([(num_nodes, start_node+(n+1)%resolution, start_node+n) for n in range(resolution)], colour)

    if show_strips:
        faces = spheroid.faces
        for i in range(resolution//4):
            for j in range(resolution*2-4):
                f = i*(resolution*4-8) +j
                faces[f][1][0] = strip_color[0]
                faces[f][1][1] = strip_color[1]
                faces[f][1][2] = strip_color[2]


    return spheroid

def hstack(x, y):
    x_rows, x_cols = len(x), len(x[0])
    y_rows, y_cols = len(y), len(y[0])

    combined_array = [[0] * (x_cols + y_cols) for _ in range(x_rows)]

    for i in range(x_rows):
        for j in range(x_cols):
            combined_array[i][j] = x[i][j]

    for i in range(y_rows):
        for j in range(y_cols):
            combined_array[i][x_cols + j] = y[i][j]

    return np.array(combined_array)

def vstack(arrays):
    num_cols = arrays[0].shape[1]

    # init an empty array to store the output
    output_array = np.empty((0, num_cols), dtype=arrays[0].dtype)

    #  concatenate() to concatenate the input arrays along the first axis
    for array in arrays:
        output_array = np.concatenate((output_array, array), axis=0)

    return output_array

class Wireframe:
    """ An array of vectors in R3 and list of edges connecting them. """
    
    def __init__(self, nodes=None):
        self.nodes = np.zeros((0, 4))
        self.edges = []
        self.faces = []
        
        if nodes:
            self.addNodes(nodes)

    def addNodes(self, node_array):
        
        ones_added = hstack(node_array, np.ones((len(node_array),1)))
        self.nodes = vstack((self.nodes, ones_added))
    
    def addEdges(self, edge_list):
        """ Add edges as a list of 2-tuples. """
        
        self.edges += [edge for edge in edge_list if edge not in self.edges]

    def addFaces(self, face_list, face_colour=(255,255,255)):
        for node_list in face_list:
            num_nodes = len(node_list)
            if all((node < len(self.nodes) for node in node_list)):
                #self.faces.append([self.nodes[node] for node in node_list])
                self.faces.append((node_list, np.array(face_colour, dtype=np.uint8)))
                self.addEdges([(node_list[n-1], node_list[n]) for n in range(num_nodes)])
 
    
    def transform(self, transformation_matrix):
        
        self.nodes = np.dot(self.nodes, transformation_matrix)
    
    def findCentre(self):

        min_values = self.nodes[:,:-1].min(axis=0)
        max_values = self.nodes[:,:-1].max(axis=0)
        return 0.5*(min_values + max_values)
    
    def sortedFaces(self):
        return sorted(self.faces, key=lambda face: min(self.nodes[f][2] for f in face[0]))
    
    def update(self):
        pass

class WireframeGroup:
    
    def __init__(self):
        self.wireframes = {}
    
    def addWireframe(self, name, wireframe):
        self.wireframes[name] = wireframe
    
    def output(self):
        for name, wireframe in self.wireframes.items():
            print(name)
            wireframe.output()    
    
    def outputNodes(self):
        for name, wireframe in self.wireframes.items():
            print(name)
            wireframe.outputNodes()
    
    def outputEdges(self):
        for name, wireframe in self.wireframes.items():
            print(name)
            wireframe.outputEdges()
    
    def findCentre(self):
        min_values = min(np.array([min(wireframe.nodes[:,:-1]) for wireframe in self.wireframes.values()]))
        max_values = max(np.array([max(wireframe.nodes[:,:-1]) for wireframe in self.wireframes.values()]))
        return 0.5*(min_values + max_values)
    
    def transform(self, matrix):
        for wireframe in self.wireframes.values():
            wireframe.transform(matrix)

    def update(self):
        for wireframe in self.wireframes.values():
            wireframe.update()

def translationMatrix(dx=0, dy=0, dz=0):
    
    return np.array([[1,0,0,0],
                     [0,1,0,0],
                     [0,0,1,0],
                     [dx,dy,dz,1]])

def scaleMatrix(s, cx=0, cy=0, cz=0):
    
    return np.array([[s,0,0,0],
                     [0,s,0,0],
                     [0,0,s,0],
                     [cx*(1-s), cy*(1-s), cz*(1-s), 1]])

def rotateXMatrix(radians):
    
    c = math.cos(radians)
    s = math.sin(radians)
    return np.array([[1,0, 0,0],
                     [0,c,-s,0],
                     [0,s, c,0],
                     [0,0, 0,1]])

def rotateYMatrix(radians):
    
    c = math.cos(radians)
    s = math.sin(radians)
    return np.array([[ c,0,s,0],
                     [ 0,1,0,0],
                     [-s,0,c,0],
                     [ 0,0,0,1]])

def rotateZMatrix(radians):
    
    c = math.cos(radians)
    s = math.sin(radians)
    return np.array([[c,-s,0,0],
                     [s, c,0,0],
                     [0, 0,1,0],
                     [0, 0,0,1]])

def linalg_norm(arr):
    sum_of_squares = 0
    for val in arr:
        sum_of_squares += val ** 2
    norm = math.sqrt(sum_of_squares)
    return norm

class WireframeViewer(WireframeGroup):
    
    def __init__(self, group, width=0, height=0, colour=(255, 255, 255), shading=True):
        self.group = group
        
        self.width = width
        self.height = height

        self.first_run = True
        self.colour = colour

        self.wireframes = {}
        self.wireframe_colours = {}
        self.object_to_update = []
        
        self.displayNodes = False
        self.displayEdges = True
        self.displayFaces = True
        
        self.perspective = True #300.
        self.eyeY = 100
        self.view_vector = np.array([0, 0, -1])
        
        self.light = Wireframe()
        self.light.addNodes([[0, -1, 0]])
        
        if shading:
            self.min_light = 0.5
            self.max_light = 1.0
            self.light_range = self.max_light - self.min_light
        else:
            self.min_light = 1.0
            self.max_light = 1.0
            self.light_range = self.max_light - self.min_light
        
        self.background = (10,10,50)
        self.nodeColour = (250,250,250)
        self.nodeRadius = 4
        
        self.control = 0
    
    def addWireframe(self, name, wireframe):
        self.wireframes[name] = wireframe
        self.wireframe_colours[name] = (250,250,250)
    
    def addWireframeGroup(self, wireframe_group):
        for name, wireframe in wireframe_group.wireframes.items():
            self.addWireframe(name, wireframe)
    
    def scale(self, scale):
        
        scale_matrix = scaleMatrix(scale, self.width/2, self.height/2, 0)
        self.transform(scale_matrix)

    def rotate(self, axis, amount):
        (x, y, z) = self.findCentre()
        translation_matrix1 = translationMatrix(-x, -y, -z)
        translation_matrix2 = translationMatrix(x, y, z)
        
        if axis == 'x':
            rotation_matrix = rotateXMatrix(amount)
        elif axis == 'y':
            rotation_matrix = rotateYMatrix(amount)
        elif axis == 'z':
            rotation_matrix = rotateZMatrix(amount)
            
        rotation_matrix = np.dot(np.dot(translation_matrix1, rotation_matrix), translation_matrix2)
        self.transform(rotation_matrix)

    def display(self):
        light = self.light.nodes[0][:3]
        spectral_highlight = self.light.nodes[0][:3] + self.view_vector
        spectral_highlight /= linalg_norm(spectral_highlight)
        
        queue = []
        
        for name, wireframe in self.wireframes.items():
            nodes = wireframe.nodes
            
            if self.displayFaces:
                for (face, colour) in wireframe.sortedFaces():
                    v1 = (nodes[face[1]] - nodes[face[0]])[:3]
                    v2 = (nodes[face[2]] - nodes[face[0]])[:3]
                    
                    normal = np.cross(v1, v2)
                    towards_us = np.dot(normal, self.view_vector)
                    
                    # Only draw faces that face us
                    if towards_us > 0:
                        normal /= np.linalg.norm(normal)
                        theta = np.dot(normal, light)
                        #catchlight_face = np.dot(normal, spectral_highlight) ** 25

                        c = 0
                        if theta < 0:
                            shade = self.min_light * colour
                        else:
                            shade = (theta * self.light_range + self.min_light) * colour
                        coords = [(int(nodes[node][0]), int(nodes[node][1])) for node in face]
                        shade = tuple(shade)
                        palette = Palette(1)
                        palette[0] = tuple(map(int, shade))
                        queue.append(Polygon(points=coords, pixel_shader=palette, color_index=0))
                        del palette
            
                if self.displayEdges:
                    for (n1, n2) in wireframe.edges:
                        if self.perspective:
                            if wireframe.nodes[n1][2] > -self.perspective and nodes[n2][2] > -self.perspective:
                                z1 = self.perspective/ (self.perspective + nodes[n1][2])
                                x1 = self.width/2  + z1*(nodes[n1][0] - self.width/2)
                                y1 = self.height/2 + z1*(nodes[n1][1] - self.height/2)
                    
                                z2 = self.perspective/ (self.perspective + nodes[n2][2])
                                x2 = self.width/2  + z2*(nodes[n2][0] - self.width/2)
                                y2 = self.height/2 + z2*(nodes[n2][1] - self.height/2)  
                                
                                queue.append(Line(int(x1), int(y1), int(x2), int(y2), color=tuple(map(int, self.colour))))
                        else:
                            queue.append(Line(int(nodes[n1][0]), int(nodes[n1][1]), int(nodes[n2][0]), int(nodes[n2][1]), color=tuple(map(int, shade))))

            if self.displayNodes:
                for node in nodes:
                     queue.append(Circle(int(node[0]), int(node[1]), r=self.nodeRadius, fill=0xffffff))

        if self.first_run:
            for obj in queue:
                self.group.append(obj)
            self.first_run = False
        else:
            self.group.hidden = True
            # 1. Clear the group efficiently
            while len(self.group):
                self.group.pop()

            # 2. Append new objects in one go
            for obj in queue:
                self.group.append(obj)

            # 3. Done — restore visibility
            self.group.hidden = False