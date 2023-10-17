

__all__ = ('FingerMotionEventProvider', )

from kivy.base import EventLoop
from collections import deque
from kivy.logger import Logger
from kivy.input.provider import MotionEventProvider
from kivy.input.factory import MotionEventFactory
from kivy.input.motionevent import MotionEvent

# late binding
Color = Ellipse = None


class FingerMotionEvent(MotionEvent):

    def depack(self, args):
        profile = self.profile
        # don't overwrite previous profile
        if not profile:
            profile.extend(('pos'))
        self.is_touch = True
        self.sx, self.sy = args[:2]
        if len(args) >= 3:
            self.button = args[2]
        if len(args) == 4:
            self.multitouch_sim = args[3]
            profile.append('multitouch_sim')
        super(FingerMotionEvent, self).depack(args)

    #
    # Create automatically touch on the surface.
    #
    def update_graphics(self, win, create=False):
        global Color, Ellipse
        de = self.ud.get('_drawelement', None)
        if de is None and create:
            if Color is None:
                from kivy.graphics import Color, Ellipse
            with win.canvas.after:
                de = (
                    Color(.8, .2, .2, .7),
                    Ellipse(size=(20, 20), segments=15))
            self.ud._drawelement = de
        if de is not None:
            self.push()

            # use same logic as WindowBase.on_motion() so we get correct
            # coordinates when _density != 1
            w, h = win._get_effective_size()

            self.scale_for_screen(w, h, rotation=win.rotation)

            de[1].pos = self.x - 10, self.y - 10
            self.pop()

    def clear_graphics(self, win):
        de = self.ud.pop('_drawelement', None)
        if de is not None:
            win.canvas.after.remove(de[0])
            win.canvas.after.remove(de[1])


class FingerMotionEventProvider(MotionEventProvider):
    __handlers__ = {}

    def __init__(self, device, args):
        super(FingerMotionEventProvider, self).__init__(device, args)
        self.waiting_event = deque()
        self.touches = {}
        self.counter = 0
        self.current_drag = None
        self.alt_touch = None
        self.disable_on_activity = False
        self.disable_multitouch = False
        self.multitouch_on_demand = False

        # split arguments
        args = args.split(',')
        for arg in args:
            arg = arg.strip()
            if arg == '':
                continue
            elif arg == 'disable_on_activity':
                self.disable_on_activity = True
            elif arg == 'disable_multitouch':
                self.disable_multitouch = True
            elif arg == 'multitouch_on_demand':
                self.multitouch_on_demand = True
            else:
                Logger.error('Touch: unknown parameter <%s>' % arg)

    def start(self):
        '''Start the mouse provider'''
        if not EventLoop.window:
            return
        EventLoop.window.bind(
            on_finger_move=self.on_finger_motion,
            on_finger_down=self.on_finger_press,
            on_finger_up=self.on_finger_release)

    def stop(self):
        '''Stop the mouse provider'''
        if not EventLoop.window:
            return
        EventLoop.window.unbind(
            on_finger_move=self.on_finger_motion,
            on_finger_down=self.on_finger_press,
            on_finger_up=self.on_finger_release)

    def test_activity(self):
        if not self.disable_on_activity:
            return False
        # trying to get if we currently have other touch than us
        # discard touches generated from kinetic
        touches = EventLoop.touches
        for touch in touches:
            # discard all kinetic touch
            if touch.__class__.__name__ == 'KineticMotionEvent':
                continue
            # not our instance, stop mouse
            if touch.__class__ != FingerMotionEvent:
                return True
        return False

    def find_touch(self, x, y):
        factor = 10. / EventLoop.window.system_size[0]
        for t in self.touches.values():
            if abs(x - t.sx) < factor and abs(y - t.sy) < factor:
                return t
        return False

    def create_touch(self, rx, ry, is_double_tap, do_graphics):
        self.counter += 1
        id = 'touch' + str(self.counter)
        args = [rx, ry]
        if do_graphics:
            args += [not self.multitouch_on_demand]
        self.current_drag = cur = FingerMotionEvent(self.device, id=id,
                                                   args=args)
        cur.is_double_tap = is_double_tap
        self.touches[id] = cur
        if do_graphics:
            # only draw red circle if multitouch is not disabled, and
            # if the multitouch_on_demand feature is not enable
            # (because in that case, we wait to see if multitouch_sim
            # is True or not before doing the multitouch)
            create_flag = (
                (not self.disable_multitouch) and
                (not self.multitouch_on_demand)
            )
            cur.update_graphics(EventLoop.window, create_flag)
        self.waiting_event.append(('begin', cur))
        return cur

    def remove_touch(self, cur):
        if cur.id not in self.touches:
            return
        del self.touches[cur.id]
        cur.update_time_end()
        self.waiting_event.append(('end', cur))
        cur.clear_graphics(EventLoop.window)

    def on_finger_motion(self, win, x, y, modifiers):
        # width, height = EventLoop.window.system_size
        rx = x
        ry = 1. - y
        if self.current_drag:
            cur = self.current_drag
            cur.move([rx, ry])
            cur.update_graphics(win)
            self.waiting_event.append(('update', cur))
        elif self.alt_touch is not None and 'alt' not in modifiers:
            # alt just released ?
            is_double_tap = 'shift' in modifiers
            cur = self.create_touch(rx, ry, is_double_tap, True)
        return True

    def on_finger_press(self, win, x, y, modifiers):
        if self.test_activity():
            return
        # width, height = EventLoop.window.system_size
        rx = x
        ry = 1. - y
        new_me = self.find_touch(rx, ry)
        if new_me:
            self.current_drag = new_me
        else:
            is_double_tap = 'shift' in modifiers
            do_graphics = (not self.disable_multitouch) and ('ctrl' in modifiers)
            cur = self.create_touch(rx, ry, is_double_tap, do_graphics)
            if 'alt' in modifiers:
                self.alt_touch = cur
                self.current_drag = None
        return True

    def on_finger_release(self, win, x, y, modifiers):
        # special case, if button is all, then remove all the current mouses.

        cur = self.current_drag
        if cur:
            not_ctrl = not ('ctrl' in modifiers)
            not_multi = (
                self.disable_multitouch or
                'multitouch_sim' not in cur.profile or
                not cur.multitouch_sim
            )

            if (not_ctrl or not_multi):
                self.remove_touch(cur)
                self.current_drag = None
            else:
                cur.update_graphics(EventLoop.window, True)

        if self.alt_touch:
            self.remove_touch(self.alt_touch)
            self.alt_touch = None
        return True

    def update(self, dispatch_fn):
        '''Update the mouse provider (pop event from the queue)'''
        try:
            while True:
                event = self.waiting_event.popleft()
                dispatch_fn(*event)
        except IndexError:
            pass


# registers
MotionEventFactory.register('finger', FingerMotionEventProvider)
