import base64, io, struct
from PIL import Image, ImageDraw
import xml.etree.ElementTree as ET

class Convert:
    def __init__(self):
        self.colname = {}

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

    def render(self):
        if True:
            with open("Kickstart-v1.3-rev34.5-1987-Commodore-A500-A1000-A2000-CDTV.rom", "rb") as f:
                data = f.read()
        else:
            with open("kick-patch.bin", "rb") as f:
                data = f.read()

        # grab palette
        palette = data[0x2872A:0x2872A+8]
        pal = []
        for i in range(4):
            r = palette[i*2+0] & 0xF
            g = (palette[i*2+1] & 0xF0) >> 4
            b = palette[i*2+1] & 0xF
            a = 1 if i > 0 else 0

            pal.extend([r+r*16, g+g*16, b+b*16,a*254])

        self.colname = {}
        for i in range(4):
            self.colname[i] = "#%02.2x%02.2x%02.2x" % (pal[i*4+0], pal[i*4+1], pal[i*4+2])

        # grab vector data
        vectors = data[0x289d0:0x28b6c]

        # grab bitmap data
        images = data[0x28B6C:0x28C9C+6]

        # Export as bitmap:
        # print (" ".join(["%2.2x" % x for x in logo]))
        image = Image.new("P", (320, 200))
        image.putpalette(pal, "RGBX")
        draw = ImageDraw.Draw(image)

        ox = 70
        oy = 40

        cmd = 0
        col = 0
        polygon = []
        for i in range(len(vectors)//2):
            a,b = vectors[i*2],vectors[i*2+1]
            # print ("%2.2x %2.2x" % (a,b))
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
        while i < len(images):
            a,w,h,x,y = struct.unpack_from(">hBBBB", images, i)
            if a < 0:
                break
            i += 6

            bm = Image.new("P", (w*16,h))
            bm.putpalette(pal, "RGBA")

            for r in range(h):
                for c in range(w):
                    val, = struct.unpack_from(">H", images, i + r*w*2 + c*2)
                    for v in range(16):
                        if val & 0x8000 != 0:
                            bm.putpixel((c*16+v,r), a)
                        val <<= 1
            image.paste(bm, (x+ox,y+oy))

            i += w*h*2

        image.save("logo.png")

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
        g_main = ET.SubElement(svg, "g", style="image-rendering:pixelated")
        g = ET.SubElement(g_main, "g", transform="translate(%i,%i)" % (ox,oy))
        cmd = 0
        col = 0
        polygon = []
        for i in range(len(vectors)//2):
            a,b = vectors[i*2],vectors[i*2+1]
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
        while i < len(images):
            a,w,h,x,y = struct.unpack_from(">hBBBB", images, i)
            if a < 0:
                break
            i += 6

            bm = Image.new("P", (w*16,h))
            bm.putpalette(pal, "RGBA")

            for r in range(h):
                for c in range(w):
                    val, = struct.unpack_from(">H", images, i + r*w*2 + c*2)
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

        with open("logo.svg", 'wb') as f:
            ET.ElementTree(svg).write(f, encoding='utf-8', xml_declaration=True)

        print (len(vectors), len(images))

def main():
    convert = Convert()
    convert.render()

if __name__ == "__main__":
    main()
