# -*- coding: utf-8 -*-

from dipy.io.stateful_tractogram import StatefulTractogram
import numpy as np
from scilpy.reconst.bingham import NB_PARAMS, bingham_to_peak_direction
from scilpy.tractanalysis.grid_intersections import grid_intersections


def fiber_density_map_along_streamlines(sft: StatefulTractogram,
                                        bingham_coeffs: np.ndarray,
                                        fiber_density: np.ndarray,
                                        max_theta: float,
                                        length_weighting: bool):
    """
    Compute fiber density map along streamlines.

    Parameters
    ----------
    sft : StatefulTractogram
        StatefulTractogram containing the streamlines needed.
    bingham_coeffs : ndarray
        Array of shape (X, Y, Z, N_LOBES, NB_PARAMS) containing
        the Bingham distributions parameters.
    fiber_density : ndarray
        Array of shape (X, Y, Z) containing the fiber density.
    """

    fd_sum, weights = \
        fd_sum_along_streamlines(sft, bingham_coeffs,
                                 fiber_density, max_theta,
                                 length_weighting)

    non_zeros = np.nonzero(fd_sum)
    weights_nz = weights[non_zeros]
    fd_sum[non_zeros] /= weights_nz

    return fd_sum


def fd_sum_along_streamlines(sft, bingham_coeffs, fd,
                             max_theta, length_weighting):
    """
    Compute the mean Fiber Density (FD) maps along a bundle.

    Parameters
    ----------
    sft : StatefulTractogram
        StatefulTractogram containing the streamlines needed.
    bingham_coeffs : ndarray (X, Y, Z, N_LOBES, NB_PARAMS)
        Bingham distributions parameters volume.
    fd : ndarray (X, Y, Z)
        N-dimensional fiber density volume.
    length_weighting : bool
        If True, will weigh the FD values according to segment lengths.

    Returns
    -------
    fd_sum_map : np.array
        Fiber density sum map.
    weight_map : np.array
        Segment lengths.
    """

    sft.to_vox()
    sft.to_corner()

    fd_sum_map = np.zeros(fd.shape[:-1])
    weight_map = np.zeros(fd.shape[:-1])
    min_cos_theta = np.cos(np.radians(max_theta))

    all_crossed_indices = grid_intersections(sft.streamlines)
    for crossed_indices in all_crossed_indices:
        segments = crossed_indices[1:] - crossed_indices[:-1]
        seg_lengths = np.linalg.norm(segments, axis=1)

        # Remove points where the segment is zero.
        # This removes numpy warnings of division by zero.
        non_zero_lengths = np.nonzero(seg_lengths)[0]
        segments = segments[non_zero_lengths]
        seg_lengths = seg_lengths[non_zero_lengths]

        # Those starting points are used for the segment vox_idx computations
        seg_start = crossed_indices[non_zero_lengths]
        vox_indices = (seg_start + (0.5 * segments)).astype(int)

        normalization_weights = np.ones_like(seg_lengths)
        if length_weighting:
            normalization_weights = seg_lengths

        normalized_seg = np.reshape(segments / seg_lengths[..., None], (-1, 3))

        for vox_idx, seg_dir, norm_weight in zip(vox_indices,
                                                 normalized_seg,
                                                 normalization_weights):
            vox_idx = tuple(vox_idx)
            bingham_at_idx = bingham_coeffs[vox_idx]  # (5, N_PARAMS)

            bingham_peak_dir = bingham_to_peak_direction(bingham_at_idx)
            cos_theta = np.abs(np.dot(seg_dir.reshape((-1, 3)),
                                      bingham_peak_dir.T))

            fd_val = 0.0
            if (cos_theta > min_cos_theta).any():
                lobe_idx = np.argmax(np.squeeze(cos_theta), axis=0)  # (n_segs)
                fd_val = fd[vox_idx][lobe_idx]

            fd_sum_map[vox_idx] += fd_val * norm_weight
            weight_map[vox_idx] += norm_weight

    return fd_sum_map, weight_map
