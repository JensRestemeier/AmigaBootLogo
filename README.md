# AmigaBootLogo

This is a set of utilities to extract and insert the Amiga "workbench disk" image from a Kickstart 1.3 ROM image. This was inspired by the answer in https://retrocomputing.stackexchange.com/questions/13897/why-was-the-kickstart-1-x-insert-floppy-graphic-so-bad/13901 that describes the vector format. I spend a bit in Ghidra to decode the format for images.

```shell
kick2svg.py -k <kickstart> -p <output_png> -s <output_svg>
```
This extracts the logo into either a PNG or an SVG file. The PNG file is just executing the draw commands with [Pillow](https://pillow.readthedocs.io/) so fill rules may be different from the ones in the built-in graphics library. The SVG is a list of draw commands that can be viewed in various web browsers or [Inkscape](https://inkscape.org/)

```shell
svg2kick.py -k <kickstart> -s <svg> -o <output>
```
This extracts draw commands from the svg - only a limited number of primitives are supported, and only fill and outline colours are used.

