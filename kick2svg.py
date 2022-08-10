import base64, io, struct, argparse
from PIL import Image, ImageDraw
import xml.etree.ElementTree as ET

class Convert:
    def __init__(self):
        self.colname = {}
        self.pal = []

    def polygon(self, g, polygon, col):
        if len(polygon) == 2:
            line = ET.SubElement(g, "line", x1=str(polygon[0][0]), y1=str(polygon[0][1]), x2=str(polygon[1][0]), y2=str(polygon[1][1]), stroke=self.colname[col])
            line.set("stroke-width", "1")
        elif polygon[0] == polygon[-1]:
            poly = ET.SubElement(g, "polygon", points=" ".join(["%i,%i" % (x,y) for x,y in polygon[0:len(polygon)-1]]), fill="none", stroke=self.colname[col])
            poly.set("stroke-width", "1")
        else:
            poly = ET.SubElement(g, "polyline", points=" ".join(["%i,%i" % (x,y) for x,y in polygon]), fill="none", stroke=self.colname[col])
            poly.set("stroke-width", "1")

    def fill(self, g, pos, col):
        x,y = pos
        # While it would probably be possible to translate flood fills into a filled polygon by searching edges I don't think the effort is really worth it... The edge cases alone would probably drive someone insane.
        circle = ET.SubElement(g, "circle", cx=str(x), cy=str(y), r="0.5", fill=self.colname[col], stroke="none")

    def load(self, path):
        with open(path, "rb") as f:
            data = f.read()

        # grab palette
        palette = data[0x2872A:0x2872A+8]
        self.pal = []
        for i in range(4):
            r = palette[i*2+0] & 0xF
            g = (palette[i*2+1] & 0xF0) >> 4
            b = palette[i*2+1] & 0xF
            a = 1 if i > 0 else 0

            self.pal.extend([r+r*16, g+g*16, b+b*16,a*254])

        # grab vector data
        self.vectors = data[0x289d0:0x28b6c]

        # grab bitmap data
        self.images = data[0x28B6C:0x28C9C+6]

        # print (len(vectors), len(images))

    def save_png(self, path):
        # Export as bitmap:
        image = Image.new("P", (320, 200))
        image.putpalette(self.pal, "RGBX")
        draw = ImageDraw.Draw(image)

        ox = 70
        oy = 40

        cmd = 0
        col = 0
        polygon = []
        for i in range(len(self.vectors)//2):
            a,b = self.vectors[i*2],self.vectors[i*2+1]
            if (a,b) == (0xFF,0xFF):
                break
            elif a == 0xFF or a == 0xFE:
                if len(polygon) > 0:
                    for i in range(len(polygon)-1):
                        draw.line(polygon[i:i+2], fill=col)
                polygon = []

                (cmd,col) = a,b
            else:
                if cmd == 0xFF:
                    polygon.append((a+ox, b+oy))
                elif cmd == 0xFE:
                    ImageDraw.floodfill(image, (a+ox, b+oy), col)

        if len(polygon) > 0:
            for i in range(len(polygon)-1):
                draw.line(polygon[i:i+2], fill=col)

        i = 0
        while i < len(self.images):
            a,w,h,x,y = struct.unpack_from(">hBBBB", self.images, i)
            if a < 0:
                break
            i += 6

            bm = Image.new("P", (w*16,h))
            bm.putpalette(self.pal, "RGBA")

            for r in range(h):
                for c in range(w):
                    val, = struct.unpack_from(">H", self.images, i + r*w*2 + c*2)
                    for v in range(16):
                        if val & 0x8000 != 0:
                            bm.putpixel((c*16+v,r), a)
                        val <<= 1
            image.paste(bm, (x+ox,y+oy))

            i += w*h*2

        image.save(path)

    def save_svg(self, path):
        # create lookup from pen index to colour:
        self.colname = {}
        for i in range(4):
            self.colname[i] = "#%02.2x%02.2x%02.2x" % (self.pal[i*4+0], self.pal[i*4+1], self.pal[i*4+2])

        ox = 70
        oy = 40

        # export as SVG:
        svg = ET.Element("svg", {
            "width":"320",
            "height":"200",
            "viewBox":"0 0 320 200",
            "version":"1.1",
            "xmlns":"http://www.w3.org/2000/svg",
            "xmlns:xlink":"http://www.w3.org/1999/xlink",
            "xmlns:svg":"http://www.w3.org/2000/svg",
        })
        g = ET.SubElement(svg, "g", style="image-rendering:pixelated", transform="translate(%i,%i)" % (ox,oy))

        cmd = 0
        col = 0
        polygon = []
        for i in range(len(self.vectors)//2):
            a,b = self.vectors[i*2],self.vectors[i*2+1]
            # print ("%2.2x %2.2x" % (a,b))
            if (a,b) == (0xFF,0xFF):
                break
            elif a == 0xFF or a == 0xFE:
                if len(polygon) > 0:
                    self.polygon(g, polygon, col)
                    polygon = []
                (cmd,col) = a,b
            else:
                if cmd == 0xFF:
                    polygon.append((a,b))
                elif cmd == 0xFE:
                    if len(polygon) > 0:
                        self.polygon(g, polygon, col)
                        polygon = []
                    self.fill(g, (a,b), col)

        i = 0
        while i < len(self.images):
            a,w,h,x,y = struct.unpack_from(">hBBBB", self.images, i)
            if a < 0:
                break
            i += 6

            bm = Image.new("P", (w*16,h))
            bm.putpalette(self.pal, "RGBA")

            for r in range(h):
                for c in range(w):
                    val, = struct.unpack_from(">H", self.images, i + r*w*2 + c*2)
                    for v in range(16):
                        if val & 0x8000 != 0:
                            bm.putpixel((c*16+v,r), a)
                        val <<= 1
            with io.BytesIO() as output:
                bm.save(output, format="PNG")
                bmdata = output.getvalue()

            image = ET.SubElement(g, "image", x=str(x), y=str(y), width=str(bm.width), height=str(bm.height))
            image.set("xlink:href", "data:image/png;base64," + base64.b64encode(bmdata).decode("utf-8"))

            i += w*h*2

        with open(path, 'wb') as f:
            ET.ElementTree(svg).write(f, encoding='utf-8', xml_declaration=True)

def main():
    parser = argparse.ArgumentParser(description='Extract Amiga boot logo from Kickstart 1.3 ROM')
    parser.add_argument('kick', type=str, help='Kickstart ROM image')
    parser.add_argument('--png',  type=str, help='output as PNG file')
    parser.add_argument('--svg',  type=str, help='output as SVG file')

    args = parser.parse_args()
    if args.kick != None:
        convert = Convert()
        convert.load(args.kick)

        if args.png != None:
            convert.save_png(args.png)
        if args.svg != None:
            convert.save_svg(args.svg)
        if args.png == None and args.svg == None:
            convert.save_svg("logo.svg")

if __name__ == "__main__":
    main()
