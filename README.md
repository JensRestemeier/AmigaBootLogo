# AmigaBootLogo

This is a set of utilities to extract and insert the Amiga "workbench disk" image from a Kickstart 1.3 ROM image. This was inspired by the answer in [StackExchange](https://retrocomputing.stackexchange.com/questions/13897/why-was-the-kickstart-1-x-insert-floppy-graphic-so-bad/13901) that describes the vector format. I spent a bit of time in [Ghidra](https://ghidra-sre.org/) to decode the format for images.

The scripts require [Pillow](https://pillow.readthedocs.io/) to be installed.

```shell
python kick2svg.py [--png output.png] [--svg output.svg] kickstart.bin
```
This extracts the logo into either a PNG or an SVG file. The PNG file is just executing the draw commands with [Pillow](https://pillow.readthedocs.io/) so fill rules may be different from the ones in the built-in graphics library. The SVG is a list of draw commands that can be viewed in various web browsers or [Inkscape](https://inkscape.org/).

While I could convert fill instructions from the ROM into filled polygons in the SVG I decided to just put a sphere at each flood fill seed.

```shell
python svg2kick.py svg2kick.py [-h] [--out kick-patched.bin] kickstart.bin logo.svg
```
This extracts draw commands from the svg. Only a limited number of primitives are supported, and only fill and outline colours are used. There are 412 byte available for vector draw instructions and 310 byte for bitmaps. I am not sure if you could relocate the data into a larger unused section.


