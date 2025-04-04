import torch
import random
import cv2
import numpy as np
import torch.nn.functional as F
import data_processing.camera_pipeline as rgb2raw
from utils.data_format_utils import torch_to_numpy, numpy_to_torch


def random_crop(frames, crop_sz):
    """ Extract a random crop of size crop_sz from the input frames. If the crop_sz is larger than the input image size,
    then the largest possible crop of same aspect ratio as crop_sz will be extracted from frames, and upsampled to
    crop_sz.
    """
    if not isinstance(crop_sz, (tuple, list)):
        crop_sz = (crop_sz, crop_sz)
    crop_sz = torch.tensor(crop_sz).float()

    shape = frames.shape

    # Select scale_factor. Ensure the crop fits inside the image
    max_scale_factor = torch.tensor(shape[-2:]).float() / crop_sz
    max_scale_factor = max_scale_factor.min().item()

    if max_scale_factor < 1.0:
        scale_factor = max_scale_factor
    else:
        scale_factor = 1.0

    # Extract the crop
    orig_crop_sz = (crop_sz * scale_factor).floor()

    assert orig_crop_sz[-2] <= shape[-2] and orig_crop_sz[-1] <= shape[-1], 'Bug in crop size estimation!'

    r1 = random.randint(0, shape[-2] - orig_crop_sz[-2])
    c1 = random.randint(0, shape[-1] - orig_crop_sz[-1])

    r2 = r1 + orig_crop_sz[0].int().item()
    c2 = c1 + orig_crop_sz[1].int().item()

    frames_crop = frames[:, r1:r2, c1:c2]

    # Resize to crop_sz
    if scale_factor < 1.0:
        frames_crop = F.interpolate(frames_crop.unsqueeze(0), size=crop_sz.int().tolist(), mode='bilinear', align_corners=True).squeeze(0)
    return frames_crop


def rgb2rawburst(image, burst_size, downsample_factor=1, burst_transformation_params=None,
                 image_processing_params=None, interpolation_type='bilinear'):
    """ Generates a synthetic LR RAW burst from the input image. The input sRGB image is first converted to linear
    sensor space using an inverse camera pipeline. A LR burst is then generated by applying random
    transformations defined by burst_transformation_params to the input image, and downsampling it by the
    downsample_factor. The generated burst is then mosaicekd and corrputed by random noise.
    """

    if image_processing_params is None:
        image_processing_params = {}

    _defaults = {'random_ccm': True, 'random_gains': True, 'smoothstep': True, 'gamma': True, 'add_noise': True}
    for k, v in _defaults.items():
        if k not in image_processing_params:
            image_processing_params[k] = v

    # Sample camera pipeline params
    if image_processing_params['random_ccm']:
        rgb2cam = rgb2raw.random_ccm()
    else:
        rgb2cam = torch.eye(3).float()
    cam2rgb = rgb2cam.inverse()

    # Sample gains
    if image_processing_params['random_gains']:
        rgb_gain, red_gain, blue_gain = rgb2raw.random_gains()
    else:
        rgb_gain, red_gain, blue_gain = (1.0, 1.0, 1.0)

    # Approximately inverts global tone mapping.
    use_smoothstep = image_processing_params['smoothstep']
    if use_smoothstep:
        image = rgb2raw.invert_smoothstep(image)

    # Inverts gamma compression.
    use_gamma = image_processing_params['gamma']
    if use_gamma:
        image = rgb2raw.gamma_expansion(image)

    # Inverts color correction.
    image = rgb2raw.apply_ccm(image, rgb2cam)

    # Approximately inverts white balance and brightening.
    image = rgb2raw.safe_invert_gains(image, rgb_gain, red_gain, blue_gain)

    # Clip saturated pixels.
    image = image.clamp(0.0, 1.0)

    # Generate LR burst
    image_burst_rgb, flow_vectors = single2lrburst(image, burst_size=burst_size,
                                                   downsample_factor=downsample_factor,
                                                   transformation_params=burst_transformation_params,
                                                   interpolation_type=interpolation_type)

    # mosaic
    image_burst = rgb2raw.mosaic(image_burst_rgb.clone())

    # Add noise
    if image_processing_params['add_noise']:
        shot_noise_level, read_noise_level = rgb2raw.random_noise_levels()
        image_burst = rgb2raw.add_noise(image_burst, shot_noise_level, read_noise_level)
    else:
        shot_noise_level = 0
        read_noise_level = 0

    # Clip saturated pixels.
    image_burst = image_burst.clamp(0.0, 1.0)

    meta_info = {'rgb2cam': rgb2cam, 'cam2rgb': cam2rgb, 'rgb_gain': rgb_gain, 'red_gain': red_gain,
                 'blue_gain': blue_gain, 'smoothstep': use_smoothstep, 'gamma': use_gamma,
                 'shot_noise_level': shot_noise_level, 'read_noise_level': read_noise_level}
    return image_burst, image, image_burst_rgb, flow_vectors, meta_info


def get_tmat(image_shape, translation, theta, shear_values, scale_factors):
    """ Generates a transformation matrix corresponding to the input transformation parameters """
    im_h, im_w = image_shape

    t_mat = np.identity(3)

    t_mat[0, 2] = translation[0]
    t_mat[1, 2] = translation[1]
    t_rot = cv2.getRotationMatrix2D((im_w * 0.5, im_h * 0.5), theta, 1.0)
    t_rot = np.concatenate((t_rot, np.array([0.0, 0.0, 1.0]).reshape(1, 3)))

    t_shear = np.array([[1.0, shear_values[0], -shear_values[0] * 0.5 * im_w],
                        [shear_values[1], 1.0, -shear_values[1] * 0.5 * im_h],
                        [0.0, 0.0, 1.0]])

    t_scale = np.array([[scale_factors[0], 0.0, 0.0],
                        [0.0, scale_factors[1], 0.0],
                        [0.0, 0.0, 1.0]])

    t_mat = t_scale @ t_rot @ t_shear @ t_mat

    t_mat = t_mat[:2, :]

    return t_mat


def single2lrburst(image, burst_size, downsample_factor=1, transformation_params=None,
                   interpolation_type='bilinear'):
    """ Generates a burst of size burst_size from the input image by applying random transformations defined by
    transformation_params, and downsampling the resulting burst by downsample_factor.
    """

    if interpolation_type == 'bilinear':
        interpolation = cv2.INTER_LINEAR
    elif interpolation_type == 'lanczos':
        interpolation = cv2.INTER_LANCZOS4
    else:
        raise ValueError

    normalize = False
    if isinstance(image, torch.Tensor):
        if image.max() < 2.0:
            image = image * 255.0
            normalize = True
        image = torch_to_numpy(image).astype(np.uint8)

    burst = []
    sample_pos_inv_all = []

    rvs, cvs = torch.meshgrid([torch.arange(0, image.shape[0]),
                               torch.arange(0, image.shape[1])])

    sample_grid = torch.stack((cvs, rvs, torch.ones_like(cvs)), dim=-1).float()

    for i in range(burst_size):
        if i == 0:
            # For base image, do not apply any random transformations. We only translate the image to center the
            # sampling grid
            shift = (downsample_factor / 2.0) - 0.5
            translation = (shift, shift)
            theta = 0.0
            shear_factor = (0.0, 0.0)
            scale_factor = (1.0, 1.0)
        else:
            # Sample random image transformation parameters
            max_translation = transformation_params.get('max_translation', 0.0)

            if max_translation <= 0.01:
                shift = (downsample_factor / 2.0) - 0.5
                translation = (shift, shift)
            else:
                translation = (random.uniform(-max_translation, max_translation),
                               random.uniform(-max_translation, max_translation))

            max_rotation = transformation_params.get('max_rotation', 0.0)
            theta = random.uniform(-max_rotation, max_rotation)

            max_shear = transformation_params.get('max_shear', 0.0)
            shear_x = random.uniform(-max_shear, max_shear)
            shear_y = random.uniform(-max_shear, max_shear)
            shear_factor = (shear_x, shear_y)

            max_ar_factor = transformation_params.get('max_ar_factor', 0.0)
            ar_factor = np.exp(random.uniform(-max_ar_factor, max_ar_factor))

            max_scale = transformation_params.get('max_scale', 0.0)
            scale_factor = np.exp(random.uniform(-max_scale, max_scale))

            scale_factor = (scale_factor, scale_factor * ar_factor)

        output_sz = (image.shape[1], image.shape[0])

        # Generate a affine transformation matrix corresponding to the sampled parameters
        t_mat = get_tmat((image.shape[0], image.shape[1]), translation, theta, shear_factor, scale_factor)
        t_mat_tensor = torch.from_numpy(t_mat)

        # Apply the sampled affine transformation
        image_t = cv2.warpAffine(image, t_mat, output_sz, flags=interpolation,
                                 borderMode=cv2.BORDER_CONSTANT)

        t_mat_tensor_3x3 = torch.cat((t_mat_tensor.float(), torch.tensor([0.0, 0.0, 1.0]).view(1, 3)), dim=0)
        t_mat_tensor_inverse = t_mat_tensor_3x3.inverse()[:2, :].contiguous()

        sample_pos_inv = torch.mm(sample_grid.view(-1, 3), t_mat_tensor_inverse.t().float()).view(
            *sample_grid.shape[:2], -1)

        if transformation_params.get('border_crop') is not None:
            border_crop = transformation_params.get('border_crop')

            image_t = image_t[border_crop:-border_crop, border_crop:-border_crop, :]
            sample_pos_inv = sample_pos_inv[border_crop:-border_crop, border_crop:-border_crop, :]

        downsample_img_size = np.floor(image_t.shape[0]/downsample_factor).astype('uint8')
        # Downsample the image       
        image_t = cv2.resize(image_t, dsize=(downsample_img_size, downsample_img_size),
                             interpolation=interpolation)
        sample_pos_inv = cv2.resize(sample_pos_inv.numpy(), dsize=(downsample_img_size, downsample_img_size),
                                    interpolation=interpolation)

        sample_pos_inv = torch.from_numpy(sample_pos_inv).permute(2, 0, 1)

        if normalize:
            image_t = numpy_to_torch(image_t).float() / 255.0
        else:
            image_t = numpy_to_torch(image_t).float()
        burst.append(image_t)
        sample_pos_inv_all.append(sample_pos_inv / downsample_factor)

    burst_images = torch.stack(burst)
    sample_pos_inv_all = torch.stack(sample_pos_inv_all)

    # Compute the flow vectors to go from the i'th burst image to the base image
    flow_vectors = sample_pos_inv_all - sample_pos_inv_all[:, :1, ...]

    return burst_images, flow_vectors
