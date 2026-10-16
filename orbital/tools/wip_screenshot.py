"""Blender UI screenshot for the WIP image: camera view mid-elimination next to the
generated Geometry Nodes tree. Run with the interface (not -b):

    blender orbital/project/velocity_100m.blend --python orbital/tools/wip_screenshot.py
"""
import sys
from pathlib import Path

import bpy

OUT = Path(__file__).resolve().parents[1] / "submission" / "wip_blender.png"
FRAME = 110


def setup():
    """Blender's own Geometry Nodes workspace: viewport, spreadsheet, node editor."""
    win = bpy.context.window_manager.windows[0]
    win.workspace = bpy.data.workspaces["Geometry Nodes"]
    return None


def arrange():
    win = bpy.context.window_manager.windows[0]
    scr = win.screen
    sc = bpy.context.scene
    sc.frame_set(FRAME)
    field = bpy.data.objects["field"]
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    field.select_set(True)
    bpy.context.view_layer.objects.active = field
    for a in scr.areas:
        s = a.spaces.active
        if a.type == "NODE_EDITOR":
            s.pin = True
            s.node_tree = bpy.data.node_groups["orbits"]
            s.show_region_ui = False
            for r in a.regions:
                if r.type == "WINDOW":
                    with bpy.context.temp_override(window=win, screen=scr, area=a, region=r):
                        bpy.ops.node.view_all()
        elif a.type == "VIEW_3D":
            s.region_3d.view_perspective = "CAMERA"
            s.shading.type = "MATERIAL"
            s.overlay.show_overlays = False
            s.show_region_ui = False
            s.show_region_toolbar = False
            for r in a.regions:
                if r.type == "WINDOW":
                    with bpy.context.temp_override(window=win, screen=scr, area=a, region=r):
                        bpy.ops.view3d.view_center_camera()
        elif a.type == "SPREADSHEET":
            if hasattr(s, "object_evaluation_state"):
                s.object_evaluation_state = "ORIGINAL"   # one row per tracked object
    return None


def fit_nodes():
    win = bpy.context.window_manager.windows[0]
    for a in win.screen.areas:
        if a.type == "NODE_EDITOR":
            for r in a.regions:
                if r.type == "WINDOW":
                    with bpy.context.temp_override(window=win, screen=win.screen, area=a, region=r):
                        bpy.ops.node.view_all()
    return None


def shoot():
    win = bpy.context.window_manager.windows[0]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with bpy.context.temp_override(window=win, screen=win.screen):
        bpy.ops.screen.screenshot(filepath=str(OUT))
    print(f"[wip] {OUT}")
    bpy.ops.wm.quit_blender()


bpy.app.timers.register(setup, first_interval=2.0)
bpy.app.timers.register(arrange, first_interval=4.0)
bpy.app.timers.register(fit_nodes, first_interval=7.0)
bpy.app.timers.register(shoot, first_interval=11.0)
