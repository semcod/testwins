"""Explicit, bounded same-origin iframe surfaces; coordinates remain frame-local."""
from __future__ import annotations

import io
import re
from PIL import Image


def reason_code(exc):
    """Only our fixed diagnostic vocabulary may leave a browser exception."""
    codes = ('target_not_iframe', 'origin_or_document_unavailable', 'private',
             'transform_unsupported', 'visibility_unsupported', 'visual_viewport_unsupported',
             'not_fully_visible', 'clipped', 'occluded', 'replaced_or_nested',
             'moved_during_screenshot', 'boundary_changed', 'target_missing_or_ambiguous')
    return next(('frame_'+code for code in codes if 'frame_'+code in str(exc)), 'frame_observation_failed')


def validate_frames(cfg):
    from .config import closed
    frames = cfg.get('frames', [])
    if not isinstance(frames, list) or len(frames) > 8:
        raise ValueError('frames must be a list of at most 8 targets')
    ids = set()
    for frame in frames:
        closed(frame, {'id', 'selector'}, 'frame')
        name = frame.get('id')
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,31}', name) or name in ids:
            raise ValueError('frame ids must be unique safe identifiers')
        if not isinstance(frame.get('selector'), str) or not frame['selector'].strip():
            raise ValueError('frame selector is required')
        ids.add(name)
    for scene in cfg['routes'] + cfg['journeys']:
        selected = scene.get('frames', [])
        if not isinstance(selected, list) or any(not isinstance(x, str) for x in selected):
            raise ValueError('scene frames must be a list of ids')
        if len(set(selected)) != len(selected) or set(selected) - ids:
            raise ValueError('scene frames must reference unique declared ids')
        for step in scene.get('steps', []):
            if 'frame' not in step:
                continue
            if step['frame'] not in selected:
                raise ValueError('step frame must be selected by its scene')
            if step['action'] in {'goto', 'download'}:
                raise ValueError('frame goto/download actions are not supported')
            if 'ux' in step:
                raise ValueError('frame UX timing contracts are not yet supported')


GEOMETRY = """(el, masks) => {
  if(el.localName !== 'iframe') throw Error('frame_target_not_iframe');
  // contentDocument is null for cross-origin and sandbox-opaque documents.
  if(!el.contentDocument || !el.contentDocument.body) throw Error('frame_origin_or_document_unavailable');
  const parent = e => e.parentElement || (e.getRootNode() instanceof ShadowRoot ? e.getRootNode().host : null);
  for(let e=el;e;e=parent(e)) {
    if(masks.some(s=>e.matches(s))) throw Error('frame_private');
    const c=getComputedStyle(e);
    if(c.transform!=='none' || (c.zoom!=='normal' && Number(c.zoom)!==1) || c.rotate!=='none' || c.scale!=='none' || c.translate!=='none')
      throw Error('frame_transform_unsupported');
    if(c.visibility!=='visible' || Number(c.opacity)!==1 || c.clipPath!=='none') throw Error('frame_visibility_unsupported');
  }
  const r=el.getBoundingClientRect(), v=visualViewport;
  if(v && (v.scale!==1 || v.offsetLeft || v.offsetTop)) throw Error('frame_visual_viewport_unsupported');
  const box={x:r.x+el.clientLeft,y:r.y+el.clientTop,width:el.clientWidth,height:el.clientHeight};
  if(box.width<1 || box.height<1 || box.x<0 || box.y<0 || box.x+box.width>innerWidth || box.y+box.height>innerHeight)
    throw Error('frame_not_fully_visible');
  for(let e=parent(el);e;e=parent(e)) {
    const c=getComputedStyle(e), p=e.getBoundingClientRect();
    if(['hidden','clip','scroll','auto'].includes(c.overflowX) && (box.x<p.x+e.clientLeft || box.x+box.width>p.x+e.clientLeft+e.clientWidth)) throw Error('frame_clipped');
    if(['hidden','clip','scroll','auto'].includes(c.overflowY) && (box.y<p.y+e.clientTop || box.y+box.height>p.y+e.clientTop+e.clientHeight)) throw Error('frame_clipped');
  }
  for(const [fx,fy] of [[.5,.5],[.01,.01],[.99,.01],[.01,.99],[.99,.99]]) {
    let top=document.elementFromPoint(box.x+box.width*fx,box.y+box.height*fy), old=null;
    while(top && top!==old && top.shadowRoot) {old=top;top=top.shadowRoot.elementFromPoint(box.x+box.width*fx,box.y+box.height*fy)||top;}
    if(top!==el) throw Error('frame_occluded');
  }
  return box;
}"""


class FrameSurface:
    def __init__(self, page, handle, frame, definition, masks, box):
        self.page, self.handle, self.frame = page, handle, frame
        self.definition, self.masks, self.box = definition, masks, box

    @property
    def viewport_size(self):
        return {k: self.box[k] for k in ('width', 'height')}

    @property
    def url(self):
        return self.frame.url

    @property
    def scope(self):
        return {'kind': 'frame', 'id': self.definition['id'],
                'selector': self.definition['selector'], 'coordinates': 'frame-viewport-css',
                'parent_rect': dict(self.box)}

    async def verify(self):
        if self.frame.parent_frame != self.page.main_frame or await self.handle.content_frame() != self.frame:
            raise ValueError('frame_replaced_or_nested')
        self.box = await self.handle.evaluate(GEOMETRY, self.masks)

    async def evaluate(self, expression, arg=None):
        await self.verify()
        # Check the actual document's boundary in the same task as collection.
        wrapped = "args => {if(parent!==top || !frameElement || !parent.document) throw Error('frame_boundary_changed'); return (" + expression + ")(args); }"
        return await self.frame.evaluate(wrapped, arg)

    def locator(self, selector):
        return self.frame.locator(selector)

    async def wait_for_timeout(self, ms):
        await self.page.wait_for_timeout(ms)

    async def wait_for_function(self, expression, **kwargs):
        await self.verify()
        return await self.frame.wait_for_function(expression, **kwargs)

    async def screenshot(self, **kwargs):
        await self.verify()
        box = dict(self.box)
        # Parent privacy masks also protect an unsuccessful moving-frame sample.
        raw = await self.page.screenshot(**kwargs, mask=[self.page.locator(s) for s in self.masks], mask_color='#232323')
        await self.verify()
        if self.box != box:
            raise ValueError('frame_moved_during_screenshot')
        image = Image.open(io.BytesIO(raw))
        crop = image.transform((round(box['width']), round(box['height'])), Image.Transform.EXTENT,
                               (box['x'], box['y'], box['x']+box['width'], box['y']+box['height']))
        stream = io.BytesIO(); crop.save(stream, format='PNG')
        return stream.getvalue()


async def resolve(page, cfg, frame_id):
    definition = next(f for f in cfg['frames'] if f['id'] == frame_id)
    locator = page.locator(definition['selector'])
    if await locator.count() != 1:
        raise ValueError('frame_target_missing_or_ambiguous')
    handle = await locator.element_handle()
    box = await handle.evaluate(GEOMETRY, cfg['capture']['mask_selectors'])
    frame = await handle.content_frame()
    surface = FrameSurface(page, handle, frame, definition, cfg['capture']['mask_selectors'], box)
    await surface.verify()
    return surface
