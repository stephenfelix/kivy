

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
        super(FingerMotionEvent, self).depack(args)


class FingerMotionEventProvider(MotionEventProvider):
    __handlers__ = {}

    def __init__(self, device, args):
        super(FingerMotionEventProvider, self).__init__(device, args)
        self.waiting_event = deque()
        self.touches = {}
        self.touches_sent = []

        # split arguments
        args = args.split(',')
        for arg in args:
            arg = arg.strip()
            if arg == '':
                continue
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

    def find_touch(self, idx):
        return self.touches.get(idx, None)

    def create_touch(self, idx, rx, ry):
        args = [rx, ry]
        touch = FingerMotionEvent(self.device, id=idx,
                                                   args=args)
        self.touches[idx] = touch
        self.touches_sent.append(idx)
        self.waiting_event.append(('begin', touch))
        return touch

    def remove_touch(self, idx):
        if idx not in self.touches:
            return
        touch = self.touches[idx]

        del self.touches[idx]
        self.touches_sent.remove(idx)
        touch.update_time_end()

        self.waiting_event.append(('end', touch))

    def on_finger_motion(self, win, idx, x, y):
        rx = x
        ry = 1. - y
        touch = self.find_touch(idx)
        if touch is not None:
            touch.move([rx, ry])
            self.waiting_event.append(('update', touch))
        return True

    def on_finger_press(self, win, idx, x, y):
        rx = x
        ry = 1. - y
        touch = self.find_touch(idx)
        if touch is None:
            touch = self.create_touch(idx, rx, ry)
        return True

    def on_finger_release(self, win, idx, x, y):
        self.remove_touch(idx)
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
