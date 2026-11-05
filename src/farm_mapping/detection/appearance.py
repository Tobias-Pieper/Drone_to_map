"""Conservative, optional illumination hypotheses using only the current RGB image."""
import math
import numpy as np
from PIL import Image, ImageFilter
from rasterio.features import shapes, rasterize
from shapely.geometry import shape


def shadow_hypotheses(rgb, labels, valid, affine, factor):
    """Find smooth dark pixels whose chromaticity matches nearby lit vegetation.

    Compact crown-sized dark components are protected. Matching appearance is
    only a hypothesis; tree/grass shadows cannot be resolved generally from RGB.
    Returns a mask, leaving classification and review policy to the caller.
    """
    image = rgb.transpose(1, 2, 0).astype(np.float32) / 255
    brightness = image.mean(axis=2)
    chroma = image / np.maximum(image.sum(axis=2, keepdims=True), .03)
    pixel_m = math.sqrt(abs(affine.a * affine.e - affine.b * affine.d)) * factor
    radius = min(50, max(1, 2 / pixel_m))

    def blur(values):
        # PIL's 8-bit Gaussian implementation is bounded and needs no new package.
        plane = Image.fromarray(np.uint8(np.clip(values, 0, 1) * 255))
        return np.asarray(plane.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32) / 255

    lit = (labels == 1) & valid & (brightness >= .25)
    support = blur(lit.astype(np.float32))
    reference = np.stack([blur(chroma[:, :, c] * lit) / np.maximum(support, .01)
                          for c in range(3)], axis=2)
    # Invalid pixels must not contribute black samples to the texture estimate.
    weight = np.maximum(blur(valid.astype(np.float32)), .01)
    mean = blur(brightness * valid) / weight
    variance = np.maximum(0, blur(brightness**2 * valid) / weight - mean**2)
    relative_texture = np.sqrt(variance) / np.maximum(mean, .03)
    match = (np.max(np.abs(chroma - reference), axis=2) < .045)
    eligible = valid & np.isin(labels, [0, 4]) & (brightness > .03) & (brightness < .25)
    eligible &= (support >= .15) & match & (relative_texture < .5)

    protected = []
    for geometry, _ in shapes((labels == 4).astype('uint8'), mask=labels == 4, transform=affine):
        polygon = shape(geometry)
        rectangle = polygon.minimum_rotated_rectangle
        coords = list(rectangle.exterior.coords)
        sides = [math.dist(coords[i], coords[i+1]) for i in range(4)]
        if polygon.area * factor**2 <= 55 and min(sides) > 0 and max(sides)/min(sides) <= 3:
            protected.append((geometry, 1))
    if protected:
        mask = rasterize(protected, out_shape=labels.shape, transform=affine, dtype='uint8')
        eligible &= mask == 0
    return eligible
