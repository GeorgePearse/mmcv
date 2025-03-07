# Copyright (c) OpenMMLab. All rights reserved.

import numpy as np
import torch
from typing import Union, List

from mmcv.ops.pure_pytorch_contour_expand.contour_expand import contour_expand_pytorch


def contour_expand(kernel_mask: Union[np.ndarray, torch.Tensor],
                   internal_kernel_label: Union[np.ndarray, torch.Tensor],
                   min_kernel_area: int, kernel_num: int) -> List:
    """Expand kernel contours so that foreground pixels are assigned into
    instances.

    Args:
        kernel_mask (np.array or torch.Tensor): The instance kernel mask with
            size hxw.
        internal_kernel_label (np.array or torch.Tensor): The instance internal
            kernel label with size hxw.
        min_kernel_area (int): The minimum kernel area.
        kernel_num (int): The instance kernel number.

    Returns:
        list: The instance index map with size hxw.
    """
    assert isinstance(kernel_mask, (torch.Tensor, np.ndarray))
    assert isinstance(internal_kernel_label, (torch.Tensor, np.ndarray))
    assert isinstance(min_kernel_area, int)
    assert isinstance(kernel_num, int)

    if isinstance(kernel_mask, np.ndarray):
        kernel_mask = torch.from_numpy(kernel_mask)
    if isinstance(internal_kernel_label, np.ndarray):
        internal_kernel_label = torch.from_numpy(internal_kernel_label)

    if kernel_mask.shape[0] == 0 or internal_kernel_label.shape[0] == 0:
        label = []
    else:
        label = contour_expand_pytorch(kernel_mask, internal_kernel_label,
                                         min_kernel_area, kernel_num)
    return label
