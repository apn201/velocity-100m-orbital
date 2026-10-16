"""v3 HUD. Reuses v2's Hud (camera-parented pixel plane, text and line helpers,
validation bookkeeping) with a new layout and a new build().

Every number on screen is registered with meta={"kind": "q", "source": ...}."""
import hud as H
import oconfig
from timeline import clamp, ease_in_out


def thousands(n):
    return f"{n:,}"


class Hud3(H.Hud):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.lay = oconfig.load("hud_layout.json")

    # ------------------------------------------------------------------ helpers
    def show(self, ob, a, b, fade_in=0, fade_out=0):
        t = self.track(ob)
        t.show(a, b)
        base = ob.color[3]
        for i in range(fade_in):
            t.set_alpha(a + i, base * (i + 1) / (fade_in + 1))
        for i in range(fade_out):
            t.set_alpha(b - i, base * (i + 1) / (fade_out + 1))
        return t

    def flash_amber(self, ob, a, frames=14, blend=6):
        t = self.track(ob)
        pal = self.c.pal
        for f in range(a, a + frames):
            t.set_rgb(f, pal["amber"])
        for j in range(blend + 1):
            k = j / blend
            t.set_rgb(a + frames + j, tuple(pal["amber"][m] * (1 - k) + pal["white"][m] * k for m in range(3)))

    def roll(self, name, values, pos, size, color, align="LEFT", essential=True, meta=None):
        """values: {frame: text}. One text object per run of identical text."""
        runs = []
        for f in sorted(values):
            s = values[f]
            if runs and runs[-1][2] == s and runs[-1][1] == f - 1:
                runs[-1][1] = f
            else:
                runs.append([f, f, s])
        obs = []
        for i, (a, b, s) in enumerate(runs):
            ob = self.text(f"{name}_{i:03d}", s, pos, size, color, align, essential=essential, meta=meta)
            self.track(ob).show(a, b)
            obs.append(ob)
        return obs

    def caption(self, key, l1, l2, a, b, source=None):
        """Top-left caption block. Spans are recorded; validation fails if two overlap."""
        self.cap_spans = getattr(self, "cap_spans", []) + [(key, a, b)]
        c = self.lay["caption"]
        pal = self.c.pal
        meta = {"kind": "q", "source": source} if source else {"kind": "label"}
        o1 = self.text(f"cap_{key}_1", l1, c["pos"], c["size"], pal["white"], essential=True, meta={"kind": "label"})
        self.show(o1, a, b, 4, 4)
        if l2:
            o2 = self.text(f"cap_{key}_2", l2, c["line2"], c["size2"], pal["muted"], essential=True, meta=meta)
            self.show(o2, a + 3, b, 4, 4)

    # ------------------------------------------------------------------ build
    def build(self):
        self.build_title()
        self.build_qualifying()
        self.build_cards()
        self.build_dive()
        self.build_dash()
        self.build_meanwhile()
        self.build_results()
        self.build_final()

    def build_title(self):
        c, tl, pal, L = self.c, self.c.tl, self.c.pal, self.lay
        a, b = tl.d["title"]
        ob = self.text("title", "VELOCITY // 100 M ORBITAL", L["title"]["pos"], L["title"]["size"], pal["white"],
                       "CENTER", essential=True, meta={"kind": "label"})
        self.show(ob, a, b, 6, 8)
        self.caption("field", "EVERY TRACKED PIECE OF SPACE JUNK",
                     f"{thousands(c.field_count)} DEBRIS FRAGMENTS AND SPENT ROCKET STAGES", 26, 62,
                     source="field.json:count")
        fp = L["fineprint"]
        ob = self.text("fineprint_orbits", f"REAL ORBITS, EPOCH {c.epoch[:10]}. TWO-BODY, FOR DISPLAY",
                       fp["pos"], fp["size"], pal["muted"], "RIGHT", meta={"kind": "q", "source": "field.json:epoch"})
        self.show(ob, 12, tl.seg["dive"]["start"] - 1, 6, 6)

    def build_qualifying(self):
        c, tl, pal, L = self.c, self.c.tl, self.c.pal, self.lay["heat"]
        q0, q1 = tl.seg["qualifying"]["start"], tl.seg["finalists"]["start"] + 20
        heats = tl.heats
        for i, h in enumerate(heats):
            a = h["start"]
            b = heats[i + 1]["start"] - 1 if i + 1 < len(heats) else q1
            lab = self.text(f"heat_label_{i}", h["label"], L["label"], L["label_size"], pal["white"], essential=True,
                            meta={"kind": "label"})
            self.show(lab, a, b, 0, 4)
            self.flash_amber(lab, a)
            note = self.text(f"heat_note_{i}", h["note"], L["note"], L["note_size"], pal["muted"], essential=True,
                             meta={"kind": "q", "source": "heats.json:threshold"})
            self.show(note, a + 4, b, 4, 4)
        # threshold readout and survivor counter, every frame
        thr, rem = {}, {}
        for f in range(q0, q1 + 1):
            h = tl.heat_at(f)
            v = tl.threshold(f)
            thr[f] = f"v > {v:.2f} km/s"
            rem[f] = f"{thousands(c.survivors(v))} REMAIN" if f < h["start"] + h["ramp"] or h["label"] != "FINAL" \
                else "5 REMAIN"
        self.roll("heat_thr", thr, L["thr"], L["thr_size"], pal["white"],
                  meta={"kind": "q", "source": "heats.json:threshold"})
        self.roll("heat_remain", rem, L["remain"], L["remain_size"], pal["white"],
                  meta={"kind": "q", "source": "field.json:vp"})
        # plain-language captions
        h2, h3, fin = heats[1], heats[2], heats[3]
        self.caption("q1", "QUALIFYING", "TOO SLOW AND YOU'RE OUT", 64, h2["start"] + h2["ramp"] + 10)
        self.caption("q2", "LOW ORBIT IS PACKED, BUT IT'S ALL THE SAME SPEED",
                     f"THE ISS GOES {c.iss['vp_km_s']:.2f} km/s. SO DOES EVERYONE AROUND IT",
                     h2["start"] + h2["ramp"] + 14, h3["start"] + 2, source="finalists.json:iss")
        self.caption("q3", "WHAT'S LEFT: OLD ROCKET STAGES",
                     "ON LONG ELLIPSES, DIVING THROUGH THE BOTTOM AT PERIGEE",
                     h3["start"] + h3["ramp"] + 2, tl.seg["finalists"]["start"] - 1)

    def build_cards(self):
        c, tl, pal, L = self.c, self.c.tl, self.c.pal, self.lay["cards"]
        a0, b0 = tl.seg["finalists"]["start"], tl.seg["dive"]["start"] + 10
        self.caption("final", "THE FINAL: 100 m AT PERIGEE SPEED", "FIVE FINALISTS. THE ISS RUNS AS REFERENCE",
                     a0 + 2, tl.seg["dive"]["start"] + 4)
        head = self.text("cards_head", "FINALIST                LAUNCHED   SPEED", (L["x"], L["y"] - 56),
                         L["head_size"], pal["muted"], "RIGHT", meta={"kind": "label"})
        self.show(head, a0 + 4, b0, 4, 4)
        rows = c.lanes[:6]
        for i, ln in enumerate(rows):
            y = L["y"] + i * L["step"] + (24 if ln["lane"] == 6 else 0)
            name = "ISS (REFERENCE)" if ln["lane"] == 6 else ln["name"]
            body = f"{ln['lane']}  {name:<20}  {ln['launch_year']}   {ln['v_km_s']:.2f} km/s"
            col = pal["white"] if ln["lane"] == 6 else pal["amber"]
            ob = self.text(f"card_{i}", body, (L["x"], y), L["size"], col, "RIGHT", essential=True,
                           meta={"kind": "q", "source": "race.json:lanes"})
            a = a0 + 8 + i * 5
            self.show(ob, a, b0, 3, 4)
            for f in range(a, a + 6):
                self.track(ob).key("location", f, (ob.location.x + 60 * (1 - ease_in_out((f - a) / 5)),
                                                   ob.location.y, 0))

    def build_dive(self):
        c, tl, pal = self.c, self.c.tl, self.c.pal
        dv = tl.seg["dive"]
        self.caption("dive", "ZOOMING IN ON THE WINNER'S PERIGEE", "STRAIGHTENING 100 m OF ARC INTO A TRACK",
                     dv["start"] + 8, dv["end"] - 2)
        W, Hh = oconfig.RES
        fl = self.lines("flash", lambda g: g.rect(*self.P(-20, -20), *self.P(W + 20, Hh + 20)), pal["white"])
        fl.location.z = -0.5  # behind the text plane
        n = tl.d["flash_frames"]
        t = self.track(fl)
        a = dv["end"] - n + 1
        t.show(a, dv["end"] + n)
        for i, f in enumerate(range(a, dv["end"] + n + 1)):
            t.set_alpha(f, min(1.0, (i + 1) / n) if f <= dv["end"] else max(0.0, 1 - (f - dv["end"]) / (n + 1)))

    def build_dash(self):
        c, tl, pal, L = self.c, self.c.tl, self.c.pal, self.lay
        a, b = tl.seg["dash"]["start"], tl.seg["dash"]["end"]
        rs, fin = tl.race_start, tl.winner_finish
        # ms counter: real elapsed time since the leader crossed the start line
        vals = {}
        for f in range(a, b + 1):
            t_ms = max(tl.real_t(f), 0.0) * 1000
            vals[f] = f"{min(t_ms, c.race['winner_time_ms']):.2f} ms"
        cl = L["counter"]
        self.roll("ms", vals, cl["pos"], cl["size"], pal["white"], "CENTER",
                  meta={"kind": "q", "source": "race.json:winner_time_ms"})
        lab = self.text("ms_label", "REAL TIME SINCE THE START", cl["label"], cl["label_size"], pal["muted"], "CENTER",
                        essential=True, meta={"kind": "label"})
        self.show(lab, a + 4, b, 4, 0)
        sm = self.text("slowmo", f"SLOW MOTION {tl.slowmo:.0f}x", L["slowmo"]["pos"], L["slowmo"]["size"],
                       pal["amber"], "RIGHT", essential=True, meta={"kind": "q", "source": "timeline:slowmo"})
        self.show(sm, a + 6, b, 4, 0)
        fp = L["fineprint"]
        ob = self.text("fineprint_race", "FLYING START / PERIGEE SPEED / EARTH-CENTRED. TOKENS NOT TO SCALE",
                       fp["pos"], fp["size"], pal["muted"], "RIGHT", meta={"kind": "label"})
        self.show(ob, a + 8, b, 6, 0)
        # lane labels on the right, aligned with each lane on screen; times freeze as each lane finishes
        ll = L["lanes"]
        for ln in c.lanes:
            y = c.lane_px[ln["lane"]] + ll["size"] * 0.35
            short = "ISS" if ln["lane"] == 6 else ("WR PACE" if ln["lane"] == 7 else ln["name"])
            ob = self.text(f"lane_label_{ln['lane']}", f"{ln['lane']}  {short}", (ll["x"] - 230, y), ll["size"],
                           pal["white"] if ln["lane"] >= 6 else pal["amber"], "RIGHT", essential=True,
                           meta={"kind": "q", "source": "race.json:lanes"})
            self.show(ob, a + 10 + ln["lane"], b, 4, 0)
            vals = {}
            for f in range(a + 10 + ln["lane"], b + 1):
                if ln.get("dns"):
                    vals[f] = "--"
                elif f >= fin:
                    vals[f] = f"{ln['time_ms']:.2f} ms" if ln["lane"] == 1 else f"{ln['gap_m']:.1f} m BACK"
                else:
                    vals[f] = f"{ln['v_km_s'] * 1000 * max(tl.real_t(f), 0.0):.0f} m"
            obs = self.roll(f"lane_val_{ln['lane']}", vals, (ll["x"], y), ll["size"], pal["white"], "RIGHT",
                            meta={"kind": "q", "source": "race.json:lanes"})
            obs[-1].color = (*(pal["amber"] if ln["lane"] == 1 else pal["white"]), 1.0)
        self.photo = self.text("photo_finish", "PHOTO FINISH", (960, 330), 48, pal["amber"], "CENTER", essential=True,
                               meta={"kind": "label"})
        self.show(self.photo, fin, b)

    def build_meanwhile(self):
        c, tl, pal = self.c, self.c.tl, self.c.pal
        a, b = tl.seg["meanwhile"]["start"], tl.seg["meanwhile"]["end"]
        r = c.race
        self.caption("mw", "MEANWHILE, AT THE START LINE", f"FROZEN AT {r['winner_time_ms']:.2f} ms. THE WINNER IS ACROSS",
                     a + 2, b, source="race.json:winner_time_ms")
        for name, body, pos, col, d in (
                ("mw_sound", f"SOUND OF THE PISTOL: {r['sound_m_at_finish']:.1f} m", c.mw_px["sound"], pal["amber"], 10),
                ("mw_lane7", "LANE 7, WORLD RECORD PACE (9.58 s):", c.mw_px["runner"], pal["white"], 26),
                ("mw_lane7b", "HAS NOT HEARD THE GUN YET", (c.mw_px["runner"][0], c.mw_px["runner"][1] + 44),
                 pal["white"], 30)):
            ob = self.text(name, body, pos, 36, col, "LEFT", essential=True,
                           meta={"kind": "q", "source": "race.json:sound_m_at_finish" if "SOUND" in body
                                 else "sources.md#world-record"})
            self.show(ob, a + d, b, 4, 4)
        ob = self.text("mw_reaction", "REACTION TIME (~0.15 s) NOT YET ELAPSED EITHER", (120, 1000), 30, pal["muted"],
                       essential=True, meta={"kind": "q", "source": "sources.md#reaction-time"})
        self.show(ob, a + 36, b, 4, 4)

    def build_results(self):
        c, tl, pal, L = self.c, self.c.tl, self.c.pal, self.lay["results"]
        a, b = tl.seg["results"]["start"], tl.seg["results"]["end"]
        head = self.text("res_head", "RESULTS  100 m", (L["x0"], L["y"] - 70), L["head_size"], pal["muted"],
                         meta={"kind": "label"})
        self.show(head, a, b, 4, 4)
        order = sorted(c.lanes, key=lambda ln: ln["time_ms"] if not ln.get("dns") else 1e12)
        for i, ln in enumerate(order):
            y = L["y"] + i * L["step"]
            name = f"{ln['name']:<14}{ln['launch_year']}" if ln["lane"] <= 5 else (
                "ISS" if ln["lane"] == 6 else "WORLD RECORD PACE")
            if ln.get("dns"):
                right = "DID NOT START"
            elif i == 0:
                right = f"{ln['time_ms']:.2f} ms"
            else:
                right = f"{ln['time_ms']:.2f} ms   +{ln['gap_m']:.1f} m"
            col = pal["amber"] if i == 0 else pal["white"]
            o1 = self.text(f"res_{i}_l", f"{i + 1}  {name}", (L["x0"], y), L["size"], col, essential=True,
                           meta={"kind": "q", "source": "race.json:lanes"})
            o2 = self.text(f"res_{i}_r", right, (L["x1"], y), L["size"], col, "RIGHT", essential=True,
                           meta={"kind": "q", "source": "race.json:lanes"})
            for ob in (o1, o2):
                self.show(ob, a + 4 + i * 3, b, 3, 4)
        iss = c.lanes[5]
        note = self.text("res_note", f"THE ISS WAS {iss['gap_m']:.0f} m BEHIND. AND IT GOES {iss['v_km_s']:.2f} km/s", (L["x0"], L["y"] + 7 * L["step"] + 20),
                         32, pal["muted"], essential=True, meta={"kind": "q", "source": "race.json:lanes"})
        self.show(note, a + 30, b, 4, 4)

    def build_final(self):
        c, tl, pal, L = self.c, self.c.tl, self.c.pal, self.lay["final"]
        a, b = tl.seg["final"]["start"], tl.f1 - 1
        w = c.lanes[0]
        x, y = L["pos"]
        lines = [(f"WINNER: {w['name']}", pal["white"], 0), (f"LAUNCHED {w['launch_year']}.", pal["white"], 12),
                 ("NOBODY IS STEERING IT.", pal["amber"], 30)]
        for i, (body, col, d) in enumerate(lines):
            ob = self.text(f"final_{i}", body, (x, y - (len(lines) - 1 - i) * L["gap"]), L["size"], col, essential=True,
                           meta={"kind": "q", "source": "race.json:lanes"})
            self.show(ob, a + d, b, 3, 0)
