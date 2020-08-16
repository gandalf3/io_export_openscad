A simple, as yet largely untested addon for managing exact booleans in blender by offloading them to [OpenSCAD](https://www.openscad.org/). (Until the [newboolean branch](https://developer.blender.org/T67744) is ready that is!)

1. Model a thing using boolean modifiers in blender. Ignore any weird boolean problems, just leave those vertices exactly where they should be.
2. Export to OpenSCAD (in *File > Export*). The exporder will create a directory at the name specified, containing a `.scad` file and a directory named `objects` containing `stl` files. Currently the exporter will only export the active object and whatever is needed to make the active object's boolean operations work.
3. Use OpenSCAD to compute beautiful booleans with CGAL.

I imagine if you have any modifiers after boolean modifiers, then they will break with this workflow.
But for e.g. a few bevel modifiers or an array or something, then oodles of booleans after those, it should be okay.
