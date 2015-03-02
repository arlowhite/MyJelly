__author__ = 'awhite'

# Fix/Hacks to Kivy

from kivy.uix.carousel import Carousel

# Carousel w,h bugfix (already in master)
# Also make jump less when on end

class FixedCarousel(Carousel):

    def load_next(self, mode='next'):
        '''Animate to next slide.

        .. versionadded:: 1.7.0
        '''
        w, h = self.size
        _direction = {
            'top': -h / 2,
            'bottom': h / 2,
            'left': w / 2,
            'right': -w / 2}
        _offset = _direction[self.direction]

        if mode == 'prev':
            _offset = -_offset
            on_end = self.index == 0
        else:
            on_end = self.index == len(self.slides) - 1


        if on_end and not self.loop:
            # Reduce jump
            _offset *= 0.15

        self._offset = _offset
        self._start_animation()
