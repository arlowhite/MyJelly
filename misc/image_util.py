__author__ = 'awhite'

# Potential Issues:
# If tentacle changes width rapidly, layout_circles could happen to land on a narrow width
# and make a smaller circle than wanted. Fairly easy to read back and forth and create a better average
# if needed.

def determine_colored_rows(core_image):
    """Takes CoreImage, may fail if keep_data=False?
    Returns list of rows that have colored pixels.
    :returns [(row_y, left_x, right_x), ...]
    Note: Image coordinates y=0 top
    """
    colored_rows = []
    for y in range(core_image.height):
        left = None
        right = None
        for x in range(core_image.width):
            pixel = core_image.read_pixel(x, y)
            # alpha > 0
            if pixel[3] > 0.0:
                # print('{0}, {1} pixel={2}'.format(x, y, pixel))
                if left is None:
                    left = x
                    right = x
                else:
                    # left set, update rightmost pixel
                    right = x

        if left is not None:
            # pixels in this row
            colored_rows.append((y, left, right))

    return colored_rows

# bodies at mean of row

# FIXME need to guarentee circle at the bottom
# Different algorithm maybe...
def layout_circles_on_rows(pixel_rows, radius_spacing=1.0):
    """Layout circles along the rows as returned from determine_colored_rows.
    :param radius_spacing The spacing between the next circle as percentage of current radius.
    [(x, y, radius), ...]
    """
    radius_multiplier = radius_spacing + 1.0
    circles = []
    next_y = -1
    for row in pixel_rows:
        y = row[0]
        # Check if it's too soon to make a new circle (based on radius_spacing)
        if y < next_y:
            continue

        # round?
        x = (row[1] + row[2]) / 2.0

        radius = row[2] + 1 - row[1]
        circles.append((x, y, radius))

        # problem is we don't know the radius of the next circle, so can't determine it's y coord
        # Value of radius_multiplier just assumes same radius.
        next_y = y + radius * radius_multiplier

    return circles
