import math
import numpy as np
from PIL import Image, ImageFilter
# remove warnings
np.seterr(all='ignore')


class SIFT:
    """
    SIFT algorithm to detect key points and calculate descriptors (not implemented)
    """
    def __init__(self):
        self.sigma = 1.6
        self.k = math.sqrt(2)
        self.sigma = self.sigma * self.k ** 3
        self.octaves_count = 1  # 4
        self.count_scales_per_octave = 3
        self.threshold = 0.015
        self.extremes = ...

    def get_key_points(self, image):
        """
        Run all steps to calculate key points and specify them
        :param image:
        :return: key points
        """
        gaussian_pyramid = self.get_gaussian_pyramid(image)
        differences_of_gaussian = self.get_differences_of_gaussian(gaussian_pyramid)

        self.extremes = self.get_local_extremum(differences_of_gaussian)
        self.discard_low_contrast_points_initial(differences_of_gaussian)
        self.extremes = self.key_point_interpolation(differences_of_gaussian)
        self.discard_low_contrast_points()
        self.discard_points_on_edges(differences_of_gaussian)

        key_points = [(extrema[5], extrema[6]) for extrema in self.extremes]
        return key_points

        # self.images_gradient_x, self.images_gradient_y = self.compute_gradients(gaussian_pyramid)
        # self.extremes = self.compute_key_points_reference_orientation(differences_of_gaussian)
        # self.descriptor = self.construct_key_points_descriptors()

    def get_gaussian_pyramid(self, image):
        """
        Compute the Gaussian scale-space for SIFT
        :param image:
        :return: gaussian scale-space array
        """
        pyramid = []
        layer = []
        radius = self.sigma
        for i in range(self.octaves_count):
            size = int(256 / (2 ** i))
            temp_img = image.resize((size, size), Image.BILINEAR)
            for j in range(self.count_scales_per_octave + 2):
                filtered_image = temp_img.filter(ImageFilter.GaussianBlur(radius=radius))
                radius = radius * self.k
                img_arr = np.array(filtered_image)
                layer.append(img_arr)
            radius = radius / self.k ** 3

            pyramid.append(layer)
            layer = []

        return pyramid

    def get_differences_of_gaussian(self, gaussian_pyramid):
        """
        Compute the differences of Gaussians (DoG)
        :param gaussian_pyramid:
        :return: differences of Gaussians
        """
        differences_of_gaussian = []
        differences_layer = []
        for layer in gaussian_pyramid:
            for i in range(self.count_scales_per_octave + 1):
                difference = layer[i+1] - layer[i]
                differences_layer.append(difference)
            differences_of_gaussian.append(differences_layer)
            differences_layer = []
        return differences_of_gaussian

    @staticmethod
    def check_extremum(octave, x, y, scale, type_check):
        """
        Checks if point is extrema comparing point to it 26 neighbours (8 on it's level, 18 on levels up and down)
        :param octave:
        :param x:
        :param y:
        :param scale:
        :param type_check:
        :return: boolean flag
        """
        val = octave[scale][x, y]
        for k in range(-1, 2):
            for i in range(-1, 2):
                for j in range(-1, 2):
                    if k == i == j == 0:
                        continue
                    if type_check == 'max':
                        # val = val * 0.95
                        if val <= octave[scale + k][x + i, y + j]:
                            return False
                    elif type_check == 'min':
                        # val = val * 1.05
                        if val >= octave[scale + k][x + i, y + j]:
                            return False
                    else:
                        raise Exception('Unknown type check')
        return True

    def get_local_extremum(self, differences_of_gaussian):
        """
        Calculates local extremes using Taylor second order expansion
        :param differences_of_gaussian:
        :return: extremes array
        """
        extremes = []
        for octave_index, octave in enumerate(differences_of_gaussian):
            shape = octave[0].shape[0]
            for scale in range(1, len(octave) - 1):
                for x in range(1, shape - 1):
                    for y in range(1, shape - 1):
                        if self.check_extremum(octave, x, y, scale, 'max'):
                            extremes.append((octave_index, scale, x, y))
                        if self.check_extremum(octave, x, y, scale, 'min'):
                            extremes.append((octave_index, scale, x, y))
        return extremes

    def discard_low_contrast_points_initial(self, differences_of_gaussian):
        """
        Discards points with low contrast
        :param differences_of_gaussian:
        :return:
        """
        for extrema_index, extrema in enumerate(self.extremes):
            octave, scale, x, y = extrema[0], extrema[1], extrema[2], extrema[3]
            if differences_of_gaussian[octave][scale][x, y] < 0.8 * self.threshold:
                self.extremes.pop(extrema_index)

    def key_point_interpolation(self, differences_of_gaussian):
        """
        Refine the position of candidate key points
        :param differences_of_gaussian:
        :return: interpolated key points array
        """
        interpolated_key_points = []

        for extrema in self.extremes:
            t = 0
            shape = differences_of_gaussian[extrema[0]][extrema[1]].shape[0]
            while t < 5:
                octave_i, scale_i, m, n = extrema[0], extrema[1], extrema[2], extrema[3]
                if 0 < m < shape - 1 and 0 < n < shape - 1 and 0 < scale_i < self.count_scales_per_octave:
                    alpha, omega = self.quadratic_interpolation(extrema, differences_of_gaussian)

                    delta_min = 0.5
                    delta_o = delta_min * 2 ** (octave_i - 1)

                    sigma, x, y = (
                        (delta_o / delta_min) * self.sigma * 2 ** ((alpha[0] + scale_i) / self.count_scales_per_octave),
                        delta_o * (alpha[1] + m),
                        delta_o * (alpha[2] + n)
                    )
                    if max(*alpha) < 0.6:
                        interpolated_key_points.append(
                            (octave_i, scale_i, m, n, sigma, x, y, omega)
                        )
                        break
                    extrema = (octave_i, int(round(scale_i + alpha[0])), int(round(m + alpha[1])), int(round(n + alpha[2])))
                t += 1

        return interpolated_key_points

    @staticmethod
    def quadratic_interpolation(extrema, differences_of_gaussian):
        """
        Refine position and scale of extrema
        :param extrema:
        :param differences_of_gaussian:
        :return:
        """
        octave_i, sc_i, m, n = extrema[0], extrema[1], extrema[2], extrema[3]
        oct = differences_of_gaussian[octave_i]
        g = np.array([
            (int(oct[sc_i + 1][m, n]) - int(oct[sc_i - 1][m, n])) / 2,
            (int(oct[sc_i][m + 1, n]) - int(oct[sc_i][m - 1, n])) / 2,
            (int(oct[sc_i][m, n + 1]) - int(oct[sc_i][m, n - 1])) / 2
        ])
        h_11 = int(oct[sc_i + 1][m, n]) + int(oct[sc_i - 1][m, n]) - 2 * int(oct[sc_i][m, n])
        h_22 = int(oct[sc_i][m + 1, n]) + int(oct[sc_i][m - 1, n]) - 2 * int(oct[sc_i][m, n])
        h_33 = int(oct[sc_i][m, n + 1]) + int(oct[sc_i][m, n - 1]) - 2 * int(oct[sc_i][m, n])
        h_12 = (int(oct[sc_i + 1][m + 1, n]) - int(oct[sc_i + 1][m - 1, n]) - int(oct[sc_i - 1][m + 1, n]) + int(oct[sc_i - 1][m - 1, n])) / 4
        h_13 = (int(oct[sc_i + 1][m, n + 1]) - int(oct[sc_i + 1][m, n - 1]) - int(oct[sc_i - 1][m, n + 1]) + int(oct[sc_i - 1][m, n - 1])) / 4
        h_23 = (int(oct[sc_i][m + 1, n + 1]) - int(oct[sc_i][m + 1, n - 1]) - int(oct[sc_i][m - 1, n + 1]) + int(oct[sc_i][m - 1, n - 1])) / 4
        H = np.array([
            [h_11, h_12, h_13],
            [h_12, h_22, h_23],
            [h_13, h_23, h_33]

        ])
        # add just a little noise to data
        H = H + 0.00001 * np.random.rand(3, 3)
        inverse_H = np.linalg.inv(H)
        alpha = - inverse_H @ g
        omega = oct[sc_i][m, n] - 0.5 * g.transpose() @ inverse_H @ g
        return alpha, omega

    def discard_low_contrast_points(self):
        """
        Discard low contrast points
        :return:
        """
        for extrema_index, extrema in enumerate(self.extremes):
            if abs(extrema[-1]) < self.threshold:
                self.extremes.pop(extrema_index)

    def discard_points_on_edges(self, differences_of_gaussian):
        """
        Discard points on edges
        :param differences_of_gaussian:
        :return:
        """
        c_edge = 10
        check = (c_edge + 1) ** 2 / c_edge
        for extrema_index, extrema in enumerate(self.extremes):
            octave_i, sc_i, m, n = extrema[0], extrema[1], extrema[2], extrema[3]
            oct = differences_of_gaussian[octave_i]
            h_11 = int(oct[sc_i][m + 1, n]) + int(oct[sc_i][m - 1, n]) - 2 * int(oct[sc_i][m, n])
            h_22 = int(oct[sc_i][m, n + 1]) + int(oct[sc_i][m, n - 1]) - 2 * int(oct[sc_i][m, n])
            h_12 = (int(oct[sc_i][m + 1, n + 1]) - int(oct[sc_i][m + 1, n - 1]) - int(oct[sc_i][m - 1, n + 1]) + int(
                oct[sc_i][m - 1, n - 1])) / 4
            H = np.array([
                [h_11, h_12],
                [h_12, h_22]
            ])
            tr_H = H.trace() ** 2 / np.linalg.det(H)
            if tr_H >= check:
                self.extremes.pop(extrema_index)

    @staticmethod
    def compute_gradients(gaussian_pyramid):
        """
        Compute gradients for image
        :param gaussian_pyramid:
        :return:
        """
        images_gradient_x = []
        images_gradient_y = []
        for octave in gaussian_pyramid:
            for image in octave:
                gradients = np.gradient(image)
                images_gradient_x.append(gradients[0])
                images_gradient_y.append(gradients[1])
        return images_gradient_x, images_gradient_y

    def compute_key_points_reference_orientation(self, differences_of_gaussian):
        lambda_ori = 1.5
        n_bins = 36
        for key_point in self.extremes:
            (octave_i, scale_i, m, n, sigma, x, y, omega) = key_point
            shape = differences_of_gaussian[octave_i][scale_i].shape[0]
            if (3 * lambda_ori * sigma <= x <= shape - 3 * lambda_ori * sigma) and (3 * lambda_ori * sigma <= y <= shape - 3 * lambda_ori * sigma):
                for k in range(n_bins + 1):
                    # TODO compute key point orientation
                    pass
        return self.extremes

    def construct_key_points_descriptors(self):
        for key_point in self.extremes:
            # TODO construct key point descriptor
            pass
