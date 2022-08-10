import io, struct, math, argparse
import re
from PIL import Image, ImageDraw
import xml.etree.ElementTree as ET
from urllib.request import urlopen

# convert an SVG file into an Amiga Boot logo
# This is by no means a proper SVG renderer/converter, it is just enough that you can edit the art in Inkscape and convert it back into the correct vector format.
# There are 412 byte available for the vector and 310 byte for bitmaps. You COULD probably relocate it into an area with more space or use a larger EPROM, but I don't know enough about the Kickstart to do this.

# (right now I'm not converting bitmap data!)

def add(a, b):
    return (a[0]+b[0], a[1]+b[1])
   
def add_cond(cond, a, b):
    if cond:
        return a
    else:
        return add(a,b)

def round_vec(v):
    return (int(round(v[0])), int (round(v[1])))

def clamp(v,l,h):
    if v < l:
        return l
    if v > h:
        return h
    return v

def diff(a,b):
    d1,d2 = a[0]-b[0],a[1]-b[1]
    return d1*d1+d2*d2

def project(v):
    p = clamp(v[0] - 70, 0, 253), clamp(v[1] - 40, 0, 255)
    return list(p)

def remap_col(remap, col, used_cols, pal):
    try:
        return remap[col]
    except KeyError:
        bestIdx = -1
        bestDiff = -1
        for idx,val in enumerate(used_cols):
            d = diff(col, val)
            if bestIdx < 0 or d < bestDiff:
                bestIdx = idx
                bestDiff = d
        idx = len(pal)
        remap[col] = idx
        pal.append(used_cols[bestIdx])
        return idx

class Convert:
    def __init__(self):
        # we render the temporary image to RGBA
        self.im = Image.new("RGB", (320, 200), color=(255,255,255))
        self.draw = ImageDraw.Draw(self.im)
        self.strokeColor = (0,0,0)
        self.fillColor = None
        self.ops = []
        self.bitmaps = []

    def line(self, p):
        x1,y1,x2,y2 = p
        self.draw.line((x1, y1, x2, y2) , fill=self.strokeColor)
        draw = [0xFF, self.strokeColor]
        draw.extend(project((x1, y1)))
        draw.extend(project((x2, y2)))
        self.op.append(draw)

    def rect(self, p):
        x,y,w,h = p
        self.poly([(x,y), (x+w,y), (x+w,y+h), (x,y+h), (x,y)])

    def poly(self, p):
        if self.fillColor != None:
            self.draw.polygon(p, outline=self.fillColor)

            draw = [0xFF, self.fillColor]
            for point in p:
                draw.extend(project(point))
            self.ops.append(draw)

            imCopy = self.im.copy()
            imDraw = ImageDraw.Draw(imCopy)
            imDraw.polygon(p, fill=self.fillColor)
            width = self.im.width
            height = self.im.height
            for y in range(height):
                for x in range(width):
                    if self.im.getpixel((x,y)) != imCopy.getpixel((x,y)):
                        # ImageDraw.polygon may fill outside the boundary, so we need to test if the fill leaks
                        imTest = self.im.copy()
                        ImageDraw.floodfill(imTest, (x,y), self.fillColor)
                        valid = True
                        for ty in range(height):
                            for tx in range(width):
                                testPixel = imTest.getpixel((tx,ty))
                                copyPixel = imCopy.getpixel((tx,ty))
                                if testPixel != copyPixel and testPixel == self.fillColor:
                                    valid = False
                                    break
                        if valid:
                            ImageDraw.floodfill(self.im, (x,y), self.fillColor)
                            draw = [0xFE, self.fillColor]
                            draw.extend(project((x,y)))
                            self.ops.append(draw)

        if self.strokeColor != None and self.strokeColor != self.fillColor:
            for i in range(len(p)-1):
                self.draw.line(p[i] + p[i+1], fill=self.strokeColor)
            # self.draw.polygon(p, outline=self.strokeColor)

            draw = [0xFF, self.strokeColor]
            for point in p:
                draw.extend(project(point))
            self.ops.append(draw)

    def fill(self, c):
        if len(c) > 0:
            if c == "none":
                self.fillColor = None
            elif c[0] == "#":
                self.fillColor = (int(c[1:3],16) & 0xF0,int(c[3:5],16) & 0xF0,int(c[5:7],16) & 0xF0)

    def stroke(self, c):
        if len(c) > 0:
            if c == "none":
                self.strokeColor = None
            elif c[0] == "#":
                self.strokeColor = (int(c[1:3],16) & 0xF0,int(c[3:5],16) & 0xF0,int(c[5:7],16) & 0xF0)

    def style(self, s):
        for cmd in s.split(";"):
            ops = cmd.split(":")
            if len(ops) == 2:
                s,v = ops
                if s == "fill":
                    self.fill(v)
                elif s == "stroke":
                    self.stroke(v)

    def get_style(self, e):
        self.style(e.get("style", ""))
        self.stroke(e.get("stroke", ""))
        self.fill(e.get("fill", ""))

    def render(self, cmd, ofs):
        if cmd.tag == "{http://www.w3.org/2000/svg}g":
            backup_ofs = self.ofs
            transform = cmd.get("transform", "")
            # good enough:
            m = re.match(".*translate.*\(([0-9]+),([0-9]+)\)", transform)
            if m:
                self.ofs = (self.ofs[0] + float(m.group(1)), self.ofs[1] + float(m.group(2)))
            for x in cmd:
                self.render(x, ofs)
            self.ofs = backup_ofs
        elif cmd.tag == "{http://www.w3.org/2000/svg}polygon":
            self.get_style(cmd)
            points = " ".join(cmd.get("points", "").split(",")).split(" ")
            p = []
            for i in range(len(points)//2):
                p.append(round_vec(float(points[i*2]), float(points[i*2+1])))
            self.poly(p + [p[0]])
        elif cmd.tag == "{http://www.w3.org/2000/svg}polyline":
            self.get_style(cmd)
            points = " ".join(cmd.get("points", "").split(",")).split(" ")
            p = []
            for i in range(len(points)//2):
                p.append(round_vec(float(points[i*2]), float(points[i*2+1])))
            self.poly(p)
        elif cmd.tag == "{http://www.w3.org/2000/svg}rect":
            self.get_style(cmd)
            pos = round_vec((float(cmd.get("x","0")), float(cmd.get("y", "0"))))
            size = round_vec((float(cmd.get("width","0")), float(cmd.get("height", "0"))))
            self.rect(pos+size)
        elif cmd.tag == "{http://www.w3.org/2000/svg}path":
            self.get_style(cmd)
            d = " ".join(cmd.get("d", "").split(",")).split(" ")
            pos = (0,0)
            start = pos
            ofs = 0
            poly = []
            while ofs < len(d):
                op = d[ofs] 
                absolute = op.isupper()
                ofs += 1
                if op.lower() == "m":
                    pos = add_cond(absolute, tuple([float(x) for x in d[ofs:ofs+2]]), pos)
                    ofs += 2
                    start = pos
                    poly = [round_vec(pos)]
                    while ofs < len(d) and not d[ofs].isalpha():
                        p2 = add_cond(absolute, tuple([float(x) for x in d[ofs:ofs+2]]), pos)
                        ofs += 2
                        poly.append(round_vec(p2))
                        pos = p2
                elif op.lower() == "l":
                    while ofs < len(d) and not d[ofs].isalpha():
                        p2 = add_cond(absolute, tuple([float(x) for x in d[ofs:ofs+2]]), pos)
                        ofs += 2
                        poly.append(round_vec(p2))
                        pos = p2
                elif op.lower() == "h":
                    while ofs < len(d) and not d[ofs].isalpha():
                        if absolute:
                            p2 = float(d[ofs]),pos[1]
                        else:
                            p2 = float(d[ofs])+pos[0],pos[1]
                        ofs += 1
                        poly.append(round_vec(p2))
                        pos = p2
                elif op.lower() == "v":
                    while ofs < len(d) and not d[ofs].isalpha():
                        if absolute:
                            p2 = pos[0],float(d[ofs])
                        else:
                            p2 = pos[0],float(d[ofs])+pos[1]
                        ofs += 1
                        poly.append(round_vec(p2))
                        pos = p2
                elif op.lower() == 'z':
                    poly.append(round_vec(start))
                    self.poly(poly)
                    poly = []
                    pos = start
                elif op.lower() == 'c':
                    # this is a curve, but we're just drawing a line - if you need to approximate a curve you need to manually turn it into line segments
                    while ofs < len(d) and not d[ofs].isalpha():
                        p2 = add_cond(absolute, tuple([float(x) for x in d[ofs+4:ofs+6]]), pos)
                        ofs += 6
                        poly.append(round_vec(p2))
                        pos = p2
                elif op.lower() == 's':
                    # this is a curve, but we're just drawing a line - if you need to approximate a curve you need to manually turn it into line segments
                    while ofs < len(d) and not d[ofs].isalpha():
                        p2 = add_cond(absolute, tuple([float(x) for x in d[ofs+2:ofs+4]]), pos)
                        ofs += 4
                        poly.append(round_vec(p2))
                        pos = p2
                else:
                    print ("unknown op %s" % op)
            if len(poly) > 0:
                self.poly(poly)
        elif cmd.tag == "{http://www.w3.org/2000/svg}circle":
            self.get_style(cmd)
            pos = round_vec((float(cmd.get("cx", 0)), float(cmd.get("cy", 0))))

            ImageDraw.floodfill(self.im, pos, self.fillColor)
            draw = [0xFE, self.fillColor]
            draw.extend(project(pos))
            self.ops.append(draw)
        elif cmd.tag == "{http://www.w3.org/2000/svg}image":
            pos = round_vec((float(cmd.get("x","0")), float(cmd.get("y", "0"))))
            size = round_vec((float(cmd.get("width","0")), float(cmd.get("height", "0"))))
            data_uri = cmd.get("{http://www.w3.org/1999/xlink}href", "")

            if len(data_uri) > 0:
                with urlopen(data_uri) as response:
                    image_data = response.read()
                image = Image.open(io.BytesIO(image_data))
                if image.size != size:
                    image = image.resize(size, Image.Resampling.NEAREST)
                self.bitmaps.append((pos, image))

        else:
            print (cmd.tag)

    def process(self, path):
        self.ofs = (0,0)
        svg = ET.parse(path).getroot()
        for cmd in svg:
            self.render(cmd, (0,0))
        im = self.im.convert("P", colors=4, dither=Image.Dither.NONE)
        pal = im.getpalette()
        used_cols = [(pal[x*3+0],pal[x*3+1],pal[x*3+2]) for x in set(im.getdata())]
        remap = {}
        self.out_pal = []
        bg_col = remap_col(remap, self.im.getpixel((0,0)), used_cols, self.out_pal)
        self.vectors = []
        for op in self.ops:
            self.vectors.extend([op[0], remap_col(remap, op[1], used_cols, self.out_pal)])
            self.vectors.extend(op[2:])
        self.vectors.extend([255,255])

        self.images=[]
        self.images.extend([255,255])

        if len(self.vectors) > 412:
            print("warning: Vector data too large, %i > 412 byte" % len(self.vectors))
        # print (vectors, len(vectors))
        if len(self.images) > 310:
            print("warning: Image data too large, %i > 310 byte" % len(self.images))
        # print (images, len(images))

    def patch(self, path):
        # load original kickstart
        with open(path, "rb") as f:
            self.data = bytearray(f.read())

        # patch draw instructions:
        for i in range(len(self.vectors)):
            self.data[i+0x289d0] = self.vectors[i]
        for i in range(len(self.images)):
            self.data[i+0x28B6C] = self.images[i]

        # patch palette
        for i in range(len(self.out_pal)):
            col = self.out_pal[i]
            col = (col[0] >> 4) << 8 | (col[1] >> 4) << 4 | (col[2] >> 4)
            # print ("%4.4x" % col)
            struct.pack_into(">H", self.data, 0x2872A + i * 2, col)

        # patch checksum (not really required for ROMs, but silences the checksum warning in UAE.)
        struct.pack_into(">I", self.data, len(self.data) - 24, 0)
        checksum = 0
        for i in range(len(self.data)//4):
            val, = struct.unpack_from(">I", self.data, i*4)
            checksum += val
            # checksum is calculated with carry, so if we overflow we wrap around and add the carry
            if checksum > 0xFFFFFFFF:
                checksum -= 0xFFFFFFFF
        if checksum != 0xFFFFFFFF:
            struct.pack_into(">I", self.data, len(self.data) - 24,  0xFFFFFFFF - checksum)

    def save(self, path):
        # write patched kickstart
        with open(path, "wb") as f:
            f.write(self.data)

def main():
    parser = argparse.ArgumentParser(description='Extract Amiga boot logo from Kickstart 1.3 ROM')
    parser.add_argument('kick', type=str, help='Kickstart ROM image')
    parser.add_argument('svg',  type=str, help='SVG file')
    parser.add_argument('--out', type=str, help='patched ROM image')

    args = parser.parse_args()

    convert = Convert()
    convert.process(args.svg)
    convert.patch(args.kick)
    if args.out != None:
        convert.save(args.out)
    else:
        convert.save("kick-patched.bin")

if __name__ == "__main__":
    main()
