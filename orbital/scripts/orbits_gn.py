"""The field: one vertex per tracked object, positioned every frame by a script-built
Geometry Nodes tree that solves Kepler's equation (10 unrolled Newton steps).

Per-vertex attributes, set from field.json at build time:
  a (Earth radii), e, M0, n (rad/s), P, Q (perifocal unit vectors), elim (frame),
  amber (frame the point turns amber), base (rgb), size (relative)
Inputs read from the 'clock' empty: location.x = simulated seconds from epoch,
location.y = point radius in Blender units, location.z = trail radius.
"""
import math

import bpy

import geometry as G
import materials
import otimeline as T


class NT:
    """Tiny node-graph helper: math with sockets or constants."""

    def __init__(self, ng):
        self.ng = ng
        self.n = ng.nodes
        self.l = ng.links

    def node(self, kind, **props):
        nd = self.n.new(kind)
        for k, v in props.items():
            setattr(nd, k, v)
        return nd

    def _in(self, sock, v):
        if hasattr(v, "is_linked") or hasattr(v, "links"):
            self.l.new(v, sock)
        else:
            sock.default_value = v

    def m(self, op, a, b=None, c=None):
        nd = self.node("ShaderNodeMath", operation=op)
        self._in(nd.inputs[0], a)
        if b is not None:
            self._in(nd.inputs[1], b)
        if c is not None:
            self._in(nd.inputs[2], c)
        return nd.outputs[0]

    def v(self, op, a, b=None):
        nd = self.node("ShaderNodeVectorMath", operation=op)
        self._in(nd.inputs[0], a)
        if b is not None:
            self._in(nd.inputs[1 if op != "SCALE" else 3], b)
        return nd.outputs[0] if op != "DOT_PRODUCT" else nd.outputs["Value"]

    def attr(self, name, vec=False):
        nd = self.node("GeometryNodeInputNamedAttribute", data_type="FLOAT_VECTOR" if vec else "FLOAT")
        nd.inputs["Name"].default_value = name
        return nd.outputs["Attribute"]

    def sep(self, vec):
        nd = self.node("ShaderNodeSeparateXYZ")
        self.l.new(vec, nd.inputs[0])
        return nd.outputs

    def mix_v(self, fac, a, b):
        nd = self.node("ShaderNodeMix", data_type="VECTOR")
        self._in(nd.inputs["Factor"], fac)
        self._in(nd.inputs["A"], a)
        self._in(nd.inputs["B"], b)
        return nd.outputs["Result"]

    def clamp01(self, x):
        nd = self.node("ShaderNodeClamp")
        self._in(nd.inputs["Value"], x)
        return nd.outputs[0]


def layout(ng, dx=200, dy=170):
    """Place nodes in columns by their distance from the group input, so the tree reads left to right."""
    depth = {n: 0 for n in ng.nodes}
    for _ in range(len(ng.nodes)):
        changed = False
        for l in ng.links:
            d = depth[l.from_node] + 1
            if d > depth[l.to_node]:
                depth[l.to_node] = d
                changed = True
        if not changed:
            break
    cols = {}
    for n in ng.nodes:
        cols.setdefault(depth[n], []).append(n)
    for d, nodes in cols.items():
        for i, n in enumerate(nodes):
            n.location = (d * dx, -i * dy + len(nodes) * dy / 2)


def _group(name):
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gi = ng.nodes.new("NodeGroupInput")
    go = ng.nodes.new("NodeGroupOutput")
    return ng, NT(ng), gi, go


def _clock(nt, clock):
    oi = nt.node("GeometryNodeObjectInfo")
    oi.inputs["Object"].default_value = clock
    return nt.sep(oi.outputs["Location"])


def _colour(nt, frame, pal):
    """base -> amber at 'amber' frame -> grey at 'elim'; returns (rgb, size factor)."""
    base = nt.attr("base", True)
    on_amber = nt.m("GREATER_THAN", frame, nt.m("SUBTRACT", nt.attr("amber"), 0.5))
    col = nt.mix_v(on_amber, base, tuple(pal["amber"]))
    age = nt.m("SUBTRACT", frame, nt.attr("elim"))
    grey = nt.clamp01(nt.m("DIVIDE", nt.m("ADD", age, 1.0), 2.0))
    col = nt.mix_v(grey, col, tuple(pal["grey"]))
    return col, age


def material_attr(name="pt_attr", attr="pcol", strength=1.0):
    """Emission from a per-point colour attribute, alpha from the object colour."""
    m, nt, out = materials._base(name)
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_name = attr
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    mul = nt.nodes.new("ShaderNodeVectorMath")
    mul.operation = "MULTIPLY"
    nt.links.new(at.outputs["Vector"], mul.inputs[0])
    nt.links.new(oi.outputs["Color"], mul.inputs[1])
    materials._emit_alpha(nt, out, mul.outputs[0], oi.outputs["Alpha"], strength)
    return m


def build_field(ctx, objs, clock):
    """objs: list of dicts with orbit elements plus elim, amber, base, size."""
    coll = ctx.coll("FIELD")
    verts, P, Q = [], [], []
    for o in objs:
        p, q = T.pq(o)
        P.append(p)
        Q.append(q)
        verts.append((0, 0, 0))
    me = bpy.data.meshes.new("field")
    me.from_pydata(verts, [], [])

    def put(name, vals, kind="FLOAT"):
        a = me.attributes.new(name, kind, "POINT")
        if kind == "FLOAT":
            a.data.foreach_set("value", vals)
        else:
            a.data.foreach_set("vector", [c for v in vals for c in v])

    put("a", [o["a_er"] for o in objs])
    put("e", [o["e"] for o in objs])
    put("M0", [o["M0_epoch_rad"] for o in objs])
    put("n", [o["n_rad_s"] for o in objs])
    put("P", P, "FLOAT_VECTOR")
    put("Q", Q, "FLOAT_VECTOR")
    put("elim", [o["elim"] for o in objs])
    put("amber", [o["amber"] for o in objs])
    put("base", [o["base"] for o in objs], "FLOAT_VECTOR")
    put("size", [o["size"] for o in objs])
    ob = bpy.data.objects.new("field", me)
    G.link(ob, coll)

    ng, nt, gi, go = _group("orbits")
    ck = _clock(nt, clock)
    st = nt.node("GeometryNodeInputSceneTime")
    frame = st.outputs["Frame"]
    a, e = nt.attr("a"), nt.attr("e")
    M = nt.m("FLOORED_MODULO", nt.m("MULTIPLY_ADD", nt.attr("n"), ck["X"], nt.attr("M0")), math.tau)
    E = nt.m("MULTIPLY_ADD", nt.m("MULTIPLY", e, 0.85), nt.m("SIGN", nt.m("SINE", M)), M)
    for _ in range(10):
        f_ = nt.m("SUBTRACT", nt.m("SUBTRACT", E, nt.m("MULTIPLY", e, nt.m("SINE", E))), M)
        fp = nt.m("SUBTRACT", 1.0, nt.m("MULTIPLY", e, nt.m("COSINE", E)))
        E = nt.m("SUBTRACT", E, nt.m("DIVIDE", f_, fp))
    x = nt.m("MULTIPLY", a, nt.m("SUBTRACT", nt.m("COSINE", E), e))
    y = nt.m("MULTIPLY", nt.m("MULTIPLY", a, nt.m("SQRT", nt.m("SUBTRACT", 1.0, nt.m("MULTIPLY", e, e)))),
             nt.m("SINE", E))
    pos = nt.v("ADD", nt.v("SCALE", nt.attr("P", True), x), nt.v("SCALE", nt.attr("Q", True), y))
    sp = nt.node("GeometryNodeSetPosition")
    nt.l.new(gi.outputs[0], sp.inputs["Geometry"])
    nt.l.new(pos, sp.inputs["Position"])
    col, age = _colour(nt, frame, ctx.pal)
    store = nt.node("GeometryNodeStoreNamedAttribute", data_type="FLOAT_VECTOR", domain="POINT")
    store.inputs["Name"].default_value = "pcol"
    nt.l.new(sp.outputs[0], store.inputs["Geometry"])
    nt.l.new(col, store.inputs["Value"])
    # size: 1 until grey, then shrink to 0 over fade frames
    alive = nt.clamp01(nt.m("SUBTRACT", 1.0, nt.m("DIVIDE", nt.m("SUBTRACT", age, 1.0), float(ctx.tl.fade))))
    radius = nt.m("MULTIPLY", nt.m("MULTIPLY", alive, nt.attr("size")), ck["Y"])
    dele = nt.node("GeometryNodeDeleteGeometry", domain="POINT")
    nt.l.new(store.outputs[0], dele.inputs["Geometry"])
    nt.l.new(nt.m("LESS_THAN", radius, 1e-7), dele.inputs["Selection"])
    ico = nt.node("GeometryNodeMeshIcoSphere")
    ico.inputs["Radius"].default_value = 1.0
    ico.inputs["Subdivisions"].default_value = 1
    inst = nt.node("GeometryNodeInstanceOnPoints")
    nt.l.new(dele.outputs[0], inst.inputs["Points"])
    nt.l.new(ico.outputs["Mesh"], inst.inputs["Instance"])
    sc = nt.node("ShaderNodeCombineXYZ")
    for k in ("X", "Y", "Z"):
        nt.l.new(radius, sc.inputs[k])
    nt.l.new(sc.outputs[0], inst.inputs["Scale"])
    real = nt.node("GeometryNodeRealizeInstances")
    nt.l.new(inst.outputs[0], real.inputs[0])
    sm = nt.node("GeometryNodeSetMaterial")
    sm.inputs["Material"].default_value = material_attr()
    nt.l.new(real.outputs[0], sm.inputs["Geometry"])
    nt.l.new(sm.outputs[0], go.inputs[0])
    layout(ng)
    mod = ob.modifiers.new("orbits", "NODES")
    mod.node_group = ng
    return ob


def build_trails(ctx, objs, clock, n=128):
    """One closed polyline per object; drawn from 'on' until the object is eliminated."""
    coll = ctx.coll("FIELD")
    verts, edges, cols, elim, amber = [], [], [], [], []
    for o in objs:
        pts = T.ellipse(o, n)
        i0 = len(verts)
        verts += pts
        edges += [(i0 + k, i0 + (k + 1) % n) for k in range(n)]
        cols += [o["base"]] * n
        elim += [o["elim"]] * n
        amber += [o["amber"]] * n
    me = bpy.data.meshes.new("trails")
    me.from_pydata(verts, edges, [])
    for name, vals, kind in (("base", cols, "FLOAT_VECTOR"), ("elim", elim, "FLOAT"), ("amber", amber, "FLOAT")):
        a = me.attributes.new(name, kind, "POINT")
        if kind == "FLOAT":
            a.data.foreach_set("value", vals)
        else:
            a.data.foreach_set("vector", [c for v in vals for c in v])
    ob = bpy.data.objects.new("trails", me)
    G.link(ob, coll)
    ng, nt, gi, go = _group("trails")
    ck = _clock(nt, clock)
    frame = nt.node("GeometryNodeInputSceneTime").outputs["Frame"]
    col, age = _colour(nt, frame, ctx.pal)
    store = nt.node("GeometryNodeStoreNamedAttribute", data_type="FLOAT_VECTOR", domain="POINT")
    store.inputs["Name"].default_value = "pcol"
    nt.l.new(gi.outputs[0], store.inputs["Geometry"])
    nt.l.new(col, store.inputs["Value"])
    dele = nt.node("GeometryNodeDeleteGeometry", domain="POINT")
    nt.l.new(store.outputs[0], dele.inputs["Geometry"])
    nt.l.new(nt.m("GREATER_THAN", age, 2.0), dele.inputs["Selection"])
    m2c = nt.node("GeometryNodeMeshToCurve")
    nt.l.new(dele.outputs[0], m2c.inputs[0])
    prof = nt.node("GeometryNodeCurvePrimitiveCircle")
    prof.inputs["Resolution"].default_value = 4
    nt.l.new(ck["Z"], prof.inputs["Radius"])
    c2m = nt.node("GeometryNodeCurveToMesh")
    nt.l.new(m2c.outputs[0], c2m.inputs["Curve"])
    nt.l.new(prof.outputs[0], c2m.inputs["Profile Curve"])
    sm = nt.node("GeometryNodeSetMaterial")
    sm.inputs["Material"].default_value = material_attr("trail_attr")
    nt.l.new(c2m.outputs[0], sm.inputs["Geometry"])
    nt.l.new(sm.outputs[0], go.inputs[0])
    layout(ng)
    mod = ob.modifiers.new("trails", "NODES")
    mod.node_group = ng
    return ob
