---
name: 3d
description: Cria elementos e cenas 3D (texto 3D, logo girando, objeto, fundo 3D) com Blender em modo headless via script Python, e renderiza para compor no vídeo. Use para /3d, "texto 3D", "logo 3D girando", "objeto 3D".
---

# /3d — Blender headless

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` (pastas, nomes de saída, loudness, privacidade). Dependências: `${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh`.

Blender é GPL e roda por linha de comando sem abrir a interface.

## Passos
1. Confirme `blender --version`. Se não houver, peça para instalar (blender.org).
2. Escreva `cena3d.py` usando `bpy`. Base para **texto 3D girando** com fundo transparente:
   ```python
   import bpy, math
   bpy.ops.wm.read_factory_settings(use_empty=True)
   s = bpy.context.scene
   v = bpy.app.version
   s.render.engine = "BLENDER_EEVEE_NEXT" if (4, 2, 0) <= v < (5, 0, 0) else "BLENDER_EEVEE"  # nome mudou em 4.2 e voltou em 5.0
   s.render.resolution_x, s.render.resolution_y = 1080, 1920
   s.render.fps, s.frame_start, s.frame_end = 30, 1, 90
   s.render.film_transparent = True
   s.render.image_settings.file_format = "PNG"; s.render.image_settings.color_mode = "RGBA"
   s.render.filepath = "//render3d/"
   bpy.ops.object.text_add(); t = bpy.context.object
   t.data.body = "TEXTO"; t.data.extrude = 0.15; t.data.bevel_depth = 0.02; t.data.align_x = "CENTER"
   m = bpy.data.materials.new("m"); m.use_nodes = True
   m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (1, 0.8, 0.1, 1)
   t.data.materials.append(m)
   t.rotation_euler = (math.radians(90), 0, 0)
   t.keyframe_insert("rotation_euler", frame=1)
   t.rotation_euler[2] = math.radians(360); t.keyframe_insert("rotation_euler", frame=90)
   bpy.ops.object.camera_add(location=(0, -9, 0.4), rotation=(math.radians(90), 0, 0)); s.camera = bpy.context.object
   bpy.ops.object.light_add(type="AREA", location=(2, -4, 4)); bpy.context.object.data.energy = 800
   ```
3. Renderize e monte o .mov com alpha:
   ```bash
   blender -b -P cena3d.py -a
   ffmpeg -framerate 30 -i render3d/%04d.png -c:v prores_ks -profile:v 4444 -pix_fmt yuva444p10le cena3d.mov
   ```
4. Sobreponha no vídeo (mesma receita do `/animacao`, `overlay` com `-itsoffset T0`).
5. Mostre um frame (`render3d/0045.png`) ao usuário antes do render completo — renderize primeiro só esse frame com `-f 45`.

## Extra
Para controle interativo do Blender pelo Claude, existe o blender-mcp (MIT): `claude mcp add blender -- uvx blender-mcp` + addon no Blender. É código de terceiro com acesso total ao Blender: revise o repositório antes de instalar.
