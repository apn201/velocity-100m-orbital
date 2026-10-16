"""Materials. Flat linework reads its colour and alpha from the object colour,
so one material serves every line and every fade is an object-level track."""
import bpy

_cache = {}


def _base(name, method="BLENDED"):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.surface_render_method = method
    m.use_backface_culling = False
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    return m, nt, out


def _emit_alpha(nt, out, color_socket, alpha_socket, strength=1.0):
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    nt.links.new(color_socket, em.inputs["Color"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(alpha_socket, mix.inputs["Fac"])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])


def _math(nt, op, a, b=None, v=None):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    if hasattr(a, "links"):
        nt.links.new(a, n.inputs[0])
    else:
        n.inputs[0].default_value = a
    if b is not None:
        if hasattr(b, "links"):
            nt.links.new(b, n.inputs[1])
        else:
            n.inputs[1].default_value = b
    return n.outputs[0]


def flat():
    if "flat" not in _cache:
        m, nt, out = _base("flat")
        oi = nt.nodes.new("ShaderNodeObjectInfo")
        _emit_alpha(nt, out, oi.outputs["Color"], oi.outputs["Alpha"])
        _cache["flat"] = m
    return _cache["flat"]


def streak():
    """Alpha falls off along U: 1 at the head (u=0), 0 at the tail (u=1)."""
    if "streak" not in _cache:
        m, nt, out = _base("streak")
        oi = nt.nodes.new("ShaderNodeObjectInfo")
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(tc.outputs["UV"], sep.inputs[0])
        inv = _math(nt, "SUBTRACT", 1.0, sep.outputs["X"])
        sq = _math(nt, "POWER", inv, 1.6)
        a = _math(nt, "MULTIPLY", sq, oi.outputs["Alpha"])
        _emit_alpha(nt, out, oi.outputs["Color"], a)
        _cache["streak"] = m
    return _cache["streak"]


def points():
    """Per-vertex brightness from the 'Col' attribute times the object colour."""
    if "points" not in _cache:
        m, nt, out = _base("points")
        oi = nt.nodes.new("ShaderNodeObjectInfo")
        at = nt.nodes.new("ShaderNodeAttribute")
        at.attribute_name = "Col"
        mul = nt.nodes.new("ShaderNodeVectorMath")
        mul.operation = "MULTIPLY"
        nt.links.new(oi.outputs["Color"], mul.inputs[0])
        nt.links.new(at.outputs["Color"], mul.inputs[1])
        a = _math(nt, "MULTIPLY", at.outputs["Fac"], oi.outputs["Alpha"])
        _emit_alpha(nt, out, mul.outputs[0], a)
        _cache["points"] = m
    return _cache["points"]


def metal(rgb):
    m, nt, out = _base("bullet_jacket", "DITHERED")
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = (*rgb, 1)
    p.inputs["Metallic"].default_value = 1.0
    p.inputs["Roughness"].default_value = 0.26
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    nt.links.new(oi.outputs["Alpha"], p.inputs["Alpha"])
    nt.links.new(p.outputs[0], out.inputs["Surface"])
    return m


def globe(rgb):
    m, nt, out = _base("globe_surface", "DITHERED")
    p = nt.nodes.new("ShaderNodeBsdfDiffuse")
    p.inputs["Color"].default_value = (*rgb, 1)
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(oi.outputs["Alpha"], mix.inputs["Fac"])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(p.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return m


def dipole(green, amber, direction, strength=0.15):
    """colour = mix(green, amber, 0.5 + 0.5 * dot(n, dipole_dir)), n from object coordinates."""
    m, nt, out = _base("cmb_dipole", "BLENDED")
    m.use_backface_culling = True
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nrm = nt.nodes.new("ShaderNodeVectorMath")
    nrm.operation = "NORMALIZE"
    nt.links.new(tc.outputs["Object"], nrm.inputs[0])
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    nt.links.new(nrm.outputs[0], dot.inputs[0])
    dot.inputs[1].default_value = direction
    fac = _math(nt, "MULTIPLY_ADD", dot.outputs["Value"], 0.5)
    fac.node.inputs[2].default_value = 0.5
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(fac, mix.inputs["Factor"])
    mix.inputs["A"].default_value = (*green, 1)
    mix.inputs["B"].default_value = (*amber, 1)
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    a = _math(nt, "MULTIPLY", oi.outputs["Alpha"], 0.75)
    _emit_alpha(nt, out, mix.outputs["Result"], a, strength)
    return m
