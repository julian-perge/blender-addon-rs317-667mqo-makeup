# RSPS Toolkit for Old School RuneScape

A Blender 5.2 extension for importing, editing and exporting OSRS models and
creating reusable animation presentations. Future development targets OSRS
caches. Revision 317/667 support is retained as historical compatibility.

Start with [the OSRS cache workflow](docs/osrs-cache-workflow.md) for current verification and limitations,
[the animation workflow](docs/animation-workflow.md) for the completed 2013
animation feature, and [player customization research](docs/research/osrs-player-customization.md)
for the proposed later character GUI. The OSRS cache workflow also has the import,
Preserve Source export and verification commands for cache 430 (revision 149) static models.

OpenRS2 archive 430 (OSRS build 149, July 2017) is the new compatibility evaluation
cache. A successful dumper run does not establish full Blender model or animation
support: the current animation bundle contract verifies the February 2013 cache
only. The OSRS cache workflow has the measured cache-430 results.

## Historical user guide

The guide below records the original add-on workflow. Its older Blender/version
claims do not replace the current Blender 5.2 extension instructions above.

<html>
<body>
<!--StartFragment--><h1 dir="auto">RSPS TOOLKIT User Guide</h1>
<p dir="auto" style="white-space: pre-wrap;">Welcome to <strong>RSPS TOOLKIT v7.7.0</strong>—your all-in-one Blender powerhouse for RuneScape Private Server (RSPS) model development! Tailored for Blender 4.5+, this addon transforms raw meshes into polished, game-ready .dat files with effortless automation. From skeletal weighting and procedural texturing to priority painting and color tinting, it covers the full RS workflow for 317/OSRS classics and 667-era models.</p>
<p dir="auto" style="white-space: pre-wrap;">Whether you're crafting epic player gear, quirky NPCs, or wild custom assets, RSPS TOOLKIT slashes tedious tasks by auto-generating essential data layers (VSKIN, RSPRI, RSTSKIN) and delivering stunning real-time visualizations. Dive in and level up your RSPS creations!</p>
<h2 dir="auto">Key Features at a Glance</h2>

<div><div><div></div></div><div dir="auto" style="mask-image: linear-gradient(to right, black 85%, transparent 100%); mask-composite: add;"><div style="height: 100%; width: 1px; left: 0px; flex-shrink: 0;"></div>
Feature | What It Does | Why You'll Love It
-- | -- | --
Model Weighter | VSKIN vertex weighting with body-part presets & mirroring | Quick skeletal setups—no more manual bone painting!
Priority Painter | RSPRI face priorities (0-255) for render depth | Perfect overlays for transparent effects like capes.
TSKIN Painter | RSTSKIN texture groups for multi-layer sorting | Seamless texture stacking with material-matched colors.
Texture Tool | Textures with texture triangles, fitted to UV edits | Preview-only scrolling animation.
Aether Materials | RGB/HSV tinting, UV-sampling, & alpha control | Dynamic recolors + randomization for endless variations.
Exporter | .dat exports with auto-type detection & drop variants | One-click normal + _drop.dat files for inventory bliss.
Importers | 317/OSRS & 667 .dat loading with full reconstruction | Brings legacy models to life, textures included.
Visualizations | Overlays for weights, priorities, TSKINs, & UV arrows | Real-time feedback—see changes as you tweak.
RS-Style Render | Cel-shaded viewport setup | Preview your models in authentic RuneScape vibes.

<div style="height: 100%; width: 1px; right: 0px; flex-shrink: 0;"></div></div></div>
<p dir="auto" style="white-space: pre-wrap;">The toolkit lives in the 3D Viewport's N-Panel under the <strong>RSPS ADDON</strong> tab. Set the add-on preferences' texture folder to a folder of <span>&lt;id&gt;.png</span> textures.</p>
<h2 dir="auto">System Specs</h2>
<ul dir="auto">
<li><strong>Blender</strong>: 4.5.0+ (battle-tested on 4.5.2).</li>
<li><strong>OS</strong>: Windows (optimized), macOS/Linux (solid support).</li>
<li><strong>Hardware</strong>: Any decent GPU for silky overlays (NVIDIA/AMD shine here).</li>
<li><strong>Dependencies</strong>: Zero—pure Blender builtins (bmesh, gpu, mathutils).</li>
</ul>
<h2 dir="auto">Installation: Get Up &amp; Running in Minutes</h2>
<ol dir="auto">
<li><strong>Build the extension</strong> (Blender 5.2 or later):
<ul dir="auto">
<li><span>mkdir -p dist</span></li>
<li><span>blender --command extension build --source-dir src/rsps_toolkit --output-dir dist</span></li>
</ul>
</li>
<li><strong>Install it</strong>:
<ul dir="auto">
<li>Drag <span>dist/rsps_toolkit-7.7.0.zip</span> into Blender, or use <strong>Edit &gt; Preferences &gt; Get Extensions &gt; Install from Disk</strong>.</li>
</ul>
</li>
<li><strong>Test Drive</strong>:
<ul dir="auto">
<li>New scene &gt; 3D Viewport &gt; <span>N</span> key for sidebar.</li>
<li>Spot <strong>RSPS ADDON</strong>? You're golden! 🎉</li>
</ul>
</li>
</ol>
<p dir="auto" style="white-space: pre-wrap;"><strong>Trouble Shooting?</strong></p>
<ul dir="auto">
<li>Addon ghosting? Double-check Blender version (Help &gt; About). Fresh reinstall FTW.</li>
<li>Console gremlins? Window &gt; Toggle System Console (Windows) for debug deets.</li>
<li>Textures AWOL? Set the texture folder in the add-on preferences to a folder of <span>&lt;texture id&gt;.png</span> files. Missing textures show magenta.</li>
<li>Colours look darker or lighter than in game? The add-on preferences' Brightness picks the client setting imports show face colours at, 0.9 (darkest) to 0.6 (brightest, as item icons), default 0.8. It changes only new imports, never what export writes.</li>
</ul>
<h2 dir="auto">Workflow: From Sketch to Server-Ready</h2>
<ol dir="auto">
<li><strong>Import Base</strong> (Opt.): File &gt; Import &gt; RS Model (.dat) for old-format models (317 and Old School), or 667 Model (.dat) for 667 models.</li>
<li><strong>Weight It Up</strong>: Tab to Edit Mode, lasso vertices, slap on Weighter presets.</li>
<li><strong>Texture &amp; Tag</strong>: Layer PMN textures, paint priorities/TSKINs on faces.</li>
<li><strong>Color Pop</strong>: Aether panel for tints, alphas, and that fresh glow.</li>
<li><strong>Ship Out</strong>: Object Mode &gt; Set export dir &gt; Smash Export DAT.</li>
<li><strong>Eyeball It</strong>: Crank visualizations for instant vibes-checks.</li>
</ol>
<p dir="auto" style="white-space: pre-wrap;">Ready to roll? Let's break it down section by section.</p>
<h2 dir="auto">1. Model Weighter: Bone Up Your Rigs</h2>
<p dir="auto" style="white-space: pre-wrap;"><strong>Why?</strong> Gives vertices body-part labels (vertex skins, 0-255) that RS animations move. Stored as vertex groups VSKIN1: to VSKIN3: at label / 100, spilling past 1.0 into the next group; the weighter writes and reads whole labels.</p>
<p dir="auto" style="white-space: pre-wrap;"><strong>Step-by-Step</strong>:</p>
<ul dir="auto">
<li>Grab a mesh &gt; Tab to <strong>Edit Mode</strong>.</li>
<li><strong>RSPS ADDON &gt; Epic Model Weighter</strong>:
<ul dir="auto">
<li><strong>Preset Power</strong>: Lasso verts (e.g., noggin), hit buttons like "Skull (1)"; the number is the label.
<ul dir="auto">
<li><em>Hits</em>: Head/Neck, Torso/Arms, Gloves, Legs/Boots, Extras (Sword/Shield/Necklace).</li>
</ul>
</li>
<li><strong>DIY Dose</strong>: Set "Label" (0-255) &gt; "Assign Custom".</li>
</ul>
</li>
<li><strong>Full Monty Mirror</strong>: Label the half-model (+X) &gt; "Finalise &amp; Mirror Model" (<em>Destructive, save a copy!</em>). The new -X half gets the left-side labels.</li>
<li><strong>Peek Mode</strong>: "Show Labels" writes each vertex's label beside it. "Clear All Labels" removes the labels and leaves other vertex groups.</li>
</ul>
<p dir="auto" style="white-space: pre-wrap;"><strong>Pro Moves</strong>:</p>
<ul dir="auto">
<li>Half-model first, mirror second. The exporter guesses the kind of equipment from the labels (e.g., HEAD from labels 1, 2 and 3).</li>
</ul>
<h2 dir="auto">2. Priority Painter: Depth Masterclass</h2>
<p dir="auto" style="white-space: pre-wrap;"><strong>Why?</strong> Vertex-color RSPRI (0-255) for face draw order—high values front-and-center.</p>
<p dir="auto" style="white-space: pre-wrap;"><strong>Step-by-Step</strong>:</p>
<ul dir="auto">
<li>Mesh select &gt; <strong>Edit Mode</strong>.</li>
<li><strong>RSPS ADDON &gt; Priority Painter</strong>:
<ul dir="auto">
<li>Crank "Priority Value" (default 10).</li>
<li>Face-select &gt; "Apply to Selected Faces" (spawns RSPRI layer).</li>
</ul>
</li>
<li><strong>Viz It</strong>: "Priority Intensity" (0-1) for hue-shifted overlays (<em>Tweak <span>materials.py</span> for custom palettes</em>).
<ul dir="auto">
<li>Low-to-high sort; labels pop on centers.</li>
</ul>
</li>
</ul>
<p dir="auto" style="white-space: pre-wrap;"><strong>Pro Moves</strong>:</p>
<ul dir="auto">
<li>Ideal for see-throughs (e.g., capes at 200+).</li>
<li>"Test Material Loading" for color sanity-check.</li>
</ul>
<h2 dir="auto">3. TSKIN Painter: Texture Tango</h2>
<p dir="auto" style="white-space: pre-wrap;"><strong>Why?</strong> RSTSKIN groups (0-255) sort multi-tex layers like a boss.</p>
<p dir="auto" style="white-space: pre-wrap;"><strong>Step-by-Step</strong>:</p>
<ul dir="auto">
<li>Echo Priorities: Mesh &gt; Edit &gt; <strong>TSKIN Painter</strong>.
<ul dir="auto">
<li>Set "TSKIN Group".</li>
<li>Faces &gt; "Apply to Selected Faces" (RSTSKIN layer).</li>
</ul>
</li>
<li><strong>Viz It</strong>: "TSKIN Intensity" for material-tinted glows.</li>
</ul>
<p dir="auto" style="white-space: pre-wrap;"><strong>Pro Moves</strong>:</p>
<ul dir="auto">
<li>0=base, 1=overlay—exporter packs 'em if present.</li>
<li>Same debug button for color vibes.</li>
</ul>
<h2 dir="auto">4. Texture Tool: Texture Triangles</h2>
<p dir="auto" style="white-space: pre-wrap;"><strong>Why?</strong> Gives faces a texture and a texture triangle (P, M, N), which is what the game uses to lay the texture over them. The UVs only preview the triangle.</p>
<p dir="auto" style="white-space: pre-wrap;"><strong>Step-by-Step</strong>:</p>
<ul dir="auto">
<li>Set the texture folder (<span>&lt;id&gt;.png</span> files) in the add-on preferences.</li>
<li>Mesh &gt; <strong>Edit Mode</strong> &gt; <strong>Texture Tool</strong>:
<ul dir="auto">
<li><strong>Pick</strong>: choose a texture ID from the list.</li>
<li><strong>Apply</strong>: select faces, look at them the way the texture should sit, and click "Apply Texture &amp; Create UVs". P, M and N become the selected vertices nearest the top-left, top-right and bottom-left of the selection in the view. Each Apply adds its own texture triangle; a model can have 64.</li>
<li><strong>Adjust</strong>: edit the UVs, then click "Fit Texture Triangle to UVs". Export ignores UV edits that were not fitted.</li>
<li><strong>Animate</strong>: "Animate Vertically" scrolls the texture in Blender only; export ignores it. "Stop Animation" removes it.</li>
</ul>
</li>
<li><strong>Show Texture Triangles</strong>: draws the selected faces' triangles with P, M and N labelled and a green arrow along u.</li>
</ul>
<h2 dir="auto">5. Aether Materials: Hue &amp; Cry</h2>
<p dir="auto" style="white-space: pre-wrap;"><strong>Why?</strong> RGB/HSV recolors, texture-sampling, &amp; alpha finesse for vibrant variants.</p>
<p dir="auto" style="white-space: pre-wrap;"><strong>Step-by-Step</strong>:</p>
<ul dir="auto">
<li>Multi-mesh OK &gt; <strong>Aether Color Tint</strong>:
<ul dir="auto">
<li><strong>UV Magic</strong>: "Select Texture" samples colors to new mats.</li>
<li><strong>Preset Party</strong>: Buttons for "Red"/"Blue" etc. (<em>Hack <span>aether_materials.py</span> PRESETS</em>).</li>
<li><strong>Sliders</strong>: R/G/B or H/S/V—hits all selected.
<ul dir="auto">
<li>"Apply Original" / "Reset" for backups.</li>
<li>"Randomize (Varied)" = chaos mode.</li>
</ul>
</li>
<li><strong>Alpha Flex</strong>: Edit Mode &gt; Faces &gt; "Enable Alpha" (BLEND mode).
<ul dir="auto">
<li>Dial "Alpha Value" (0-1) on targets.</li>
</ul>
</li>
</ul>
</li>
</ul>
<p dir="auto" style="white-space: pre-wrap;"><strong>Pro Moves</strong>:</p>
<ul dir="auto">
<li>Saves originals in obj props—undo-proof.</li>
<li>Dye-job heaven for capes/gear.</li>
</ul>
<h2 dir="auto">6. Exporter &amp; Importer: In/Out Bound</h2>
<p dir="auto" style="white-space: pre-wrap;"><strong>Why?</strong> Frictionless .dat I/O with drop smarts.</p>
<p dir="auto" style="white-space: pre-wrap;"><strong>Step-by-Step</strong>:</p>
<ul dir="auto">
<li><strong>Export</strong> (<strong>Model Exporter</strong>, Object Mode):
<ul dir="auto">
<li>"Output Directory" set.</li>
<li>Meshes selected.</li>
<li><strong>Picks</strong>:
<ul dir="auto">
<li>"DAT (Weight-Based)": VSKIN-sniff (BODY? HEAD?), spits normal + _drop.dat.</li>
<li>"DAT (Custom Color)": RSPRI/TSKIN/VSKIN feast; drop auto.</li>
</ul>
</li>
<li>Export—<span>ModelName.dat</span> &amp; <span>_drop.dat</span> done.</li>
</ul>
</li>
<li><strong>Import</strong> (File &gt; Import):
<ul dir="auto">
<li>"RS Model (.dat)": old-format models, several files at once; layers, UVs and textures from the preferences folder.</li>
<li>"667 Model (.dat)": new-format 667 models (legacy importer).</li>
</ul>
</li>
</ul>
<p dir="auto" style="white-space: pre-wrap;"><strong>Pro Moves</strong>:</p>
<ul dir="auto">
<li>Drops twist/translate (SWORD: 90° spin).</li>
<li>Detect: Weights like {1,2,3}=HEAD.</li>
<li>"Make Render RS Style": Cel-shade viewport.</li>
</ul>
<h2 dir="auto">Power User Hacks</h2>
<ul dir="auto">
<li><strong>Perf Boost</strong>: High-poly? Kill overlays.</li>
<li><strong>Keymaps</strong>: Stock none—bless 'em in Preferences &gt; Keymap.</li>
<li><strong>Code Tweaks</strong>: .py paradise (e.g., weighter.py presets).</li>
<li><strong>Debug</strong>: Console dive for oopsies. Ping Discord @dimension5879 for fixes.</li>
<li><strong>Changelog</strong>: Importer split in v7.7—peek bl_info.</li>
</ul>
<h2 dir="auto">Shoutouts</h2>
<ul dir="auto">
<li><strong>Creator</strong>: Epic AI Game Dev (Gemini-boosted).</li>
<li><strong>License</strong>: MIT—RSPS-free, share with cred.</li>
<li><strong>Nods</strong>: RS modders for format lore.</li>
</ul>
<p dir="auto" style="white-space: pre-wrap;">Forge on, scaper! Questions? Hit the Discord. 🚀</p><!--EndFragment-->
</body>
</html>
