import unittest

from PIL import Image

from sub2lrc.cropper import crop_square


class CropperTests(unittest.TestCase):
    def test_crops_landscape_image_to_selected_square(self) -> None:
        image = Image.new("RGB", (400, 200), "red")
        image.paste("blue", (200, 0, 400, 200))
        cropped = crop_square(image, (200, 0, 400, 200))
        self.assertEqual(cropped.size, (200, 200))
        self.assertEqual(cropped.getpixel((100, 100)), (0, 0, 255))

    def test_crops_portrait_image_to_selected_square(self) -> None:
        image = Image.new("RGB", (200, 400), "white")
        image.paste("green", (0, 200, 200, 400))
        cropped = crop_square(image, (0, 200, 200, 400))
        self.assertEqual(cropped.size, (200, 200))
        self.assertEqual(cropped.getpixel((100, 100)), (0, 128, 0))

    def test_supports_smaller_manual_crop(self) -> None:
        image = Image.new("RGBA", (300, 300), (10, 20, 30, 128))
        cropped = crop_square(image, (75, 75, 225, 225))
        self.assertEqual(cropped.size, (150, 150))
        self.assertEqual(cropped.mode, "RGBA")

    def test_rejects_non_square_or_out_of_bounds_crop(self) -> None:
        image = Image.new("RGB", (100, 100))
        with self.assertRaisesRegex(ValueError, "正方形"):
            crop_square(image, (0, 0, 90, 100))
        with self.assertRaisesRegex(ValueError, "超出了图片范围"):
            crop_square(image, (-1, 0, 99, 100))


if __name__ == "__main__":
    unittest.main()
