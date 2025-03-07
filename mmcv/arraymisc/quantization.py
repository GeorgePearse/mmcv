# Copyright (c) OpenMMLab. All rights reserved.

import numpy as np


def quantize(arr: np.ndarray,
             min_val: int | float,
             max_val: int | float,
             levels: int,
             dtype=np.int64) -> tuple:
    """Quantize an array of (-inf, inf) to [0, levels-1].

    Args:
        arr (ndarray): Input array.
        min_val (int or float): Minimum value to be clipped.
        max_val (int or float): Maximum value to be clipped.
        levels (int): Quantization levels.
        dtype (np.type): The type of the quantized array.

    Returns:
        tuple: Quantized array.
    """
    if not (isinstance(levels, int) and levels > 1):
        raise ValueError(
            f'levels must be a positive integer, but got {levels}')
    if min_val >= max_val:
        raise ValueError(
            f'min_val ({min_val}) must be smaller than max_val ({max_val})')

    arr = np.clip(arr, min_val, max_val) - min_val
    quantized_arr = np.minimum(
        np.floor(levels * arr / (max_val - min_val)).astype(dtype), levels - 1)

    return quantized_arr


def dequantize(arr: np.ndarray,
               min_val: int | float,
               max_val: int | float,
               levels: int,
               dtype=np.float64) -> tuple:
    """Dequantize an array.

    Args:
        arr (ndarray): Input array.
        min_val (int or float): Minimum value to be clipped.
        max_val (int or float): Maximum value to be clipped.
        levels (int): Quantization levels.
        dtype (np.type): The type of the dequantized array.

    Returns:
        tuple: Dequantized array.
    """
    if not (isinstance(levels, int) and levels > 1):
        raise ValueError(
            f'levels must be a positive integer, but got {levels}')
    if min_val >= max_val:
        raise ValueError(
            f'min_val ({min_val}) must be smaller than max_val ({max_val})')

    dequantized_arr = (arr + 0.5).astype(dtype) * (max_val -
                                                   min_val) / levels + min_val

    return dequantized_arr
