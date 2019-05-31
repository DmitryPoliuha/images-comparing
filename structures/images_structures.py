import numpy as np
from PIL import Image
from PIL.ImageFilter import SMOOTH_MORE

import sift


class ImageWrapper:

    def __init__(self, image_path, image_name):
        self.name = image_name

        image = Image.open(image_path)
        grayscaled_image = image.convert('L')
        self.image = grayscaled_image

        # cropped_img = grayscaled_image.resize((512, 512), Image.BILINEAR)
        # self.image = np.array(cropped_img)


class ImagesContainer:

    def __init__(self, images_paths, images_names):
        # self.images = [ImageWrapper(images_paths[15], images_names[15]), ImageWrapper(images_paths[14], images_names[14])]
        self.images = [ImageWrapper(path, name) for (path, name) in zip(images_paths, images_names)]
        self.sift = [sift.SIFT(image) for image in self.images]
        self.compare_imgs()

    def compare_imgs(self):
        out_str = ''
        # (octave_i, scale_i, m, n, sigma, x, y, omega)
        imgs_info = [(self.sift[i].extremes, self.sift[i].image.name) for i in range(len(self.sift))]

        c_match = 0.6

        # for k in range(len(self.images)):
        #     for t in range(k + 1, len(self.images)):
        #         m = self.mse(self.images[k].image, self.images[t].image)
                # from skimage import measure
                # s = measure.compare_ssim(self.images[k].image, self.images[t].image)
                # if m < 4000 and s > 0.45:
                #     print(f'{self.images[k].name}\t\t\t\t{self.images[t].name}\t\t\t\tmse: {m}\t\t\tssim: {s}')

        for k in range(len(imgs_info)):
            for t in range(k + 1, len(imgs_info)):
                m = self.mse(self.images[k].image, self.images[t].image)
                # if m < 4000:
                #     print(f'{imgs_info[k][1]}\t\t{imgs_info[t][1]}\tmse: {m}')

                points_left = [(point[5], point[6]) for point in imgs_info[k][0]]
                points_right = [(point[5], point[6]) for point in imgs_info[t][0]]
                # points_left_scalar = [(point[0] ** 2 + point[1] ** 2) ** 0.5 for point in points_left]

                matches = 0
                for i in range(len(points_left)):
                    distances = []
                    for j in range(len(points_right)):
                        distances.append(self.calculate_distance(points_left[i], points_right[j]))
                    distances.sort()
                    first_neighbour = distances[0]
                    second_neighbour = distances[1]
                    if first_neighbour < c_match * second_neighbour:
                        matches += 1

                if matches >= len(self.sift[k].extremes) / 4 and m < 2500:
                    out_str += (f'{imgs_info[k][1]}\t\t{imgs_info[t][1]}\n'
                                f'{len(self.sift[k].extremes)}\t{round(matches / len(self.sift[k].extremes), 2)}\t{len(self.sift[t].extremes)}\t\tmse: {m}\n\n')
        with open('results.txt', 'w') as f:
            f.write(out_str)

    def calculate_distance(self, a, b):
        return ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5

    def mse(self, imageA, imageB):
        cropped_img = imageA.resize((256, 256), Image.BILINEAR)
        filtered_image = cropped_img.filter(SMOOTH_MORE)
        imageA = np.array(filtered_image)

        cropped_img = imageB.resize((256, 256), Image.BILINEAR)
        filtered_image = cropped_img.filter(SMOOTH_MORE)
        # filtered_image = cropped_img.filter(ImageFilter.GaussianBlur(radius=1.6))
        imageB = np.array(filtered_image)

        # the 'Mean Squared Error' between the two images is the
        # sum of the squared difference between the two images;
        # NOTE: the two images must have the same dimension
        err = np.sum((imageA.astype("float") - imageB.astype("float")) ** 2)
        err /= float(imageA.shape[0] * imageA.shape[1])

        # return the MSE, the lower the error, the more "similar"
        # the two images are
        return err
