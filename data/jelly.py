__author__ = 'awhite'

from kivy.core.image import Image as CoreImage

class JellyData:

    def __init__(self):
        self.bell_image_filename = 'media/images/jelly.png'
        # Lazy-load?
        self.bell_image = CoreImage(self.bell_image_filename, mipmap=True)



