# Copyright (c) OpenMMLab. All rights reserved.
import mmcv
import numpy as np
import pytest
from numpy.testing import assert_array_equal

try:
    import torch
except ImportError:
    torch = None


@pytest.mark.skipif(torch is None, reason='requires torch library')
def test_tensor2imgs():

    # test tensor obj
    with pytest.raises(AssertionError):
        tensor = np.random.rand(2, 3, 3)
        mmcv.tensor2imgs(tensor)

    # test tensor ndim
    with pytest.raises(AssertionError):
        tensor = torch.randn(2, 3, 3)
        mmcv.tensor2imgs(tensor)

    # test tensor dim-1
    with pytest.raises(AssertionError):
        tensor = torch.randn(2, 4, 3, 3)
        mmcv.tensor2imgs(tensor)

    # test mean length
    with pytest.raises(AssertionError):
        tensor = torch.randn(2, 3, 5, 5)
        mmcv.tensor2imgs(tensor, mean=(1, ))
        tensor = torch.randn(2, 1, 5, 5)
        mmcv.tensor2imgs(tensor, mean=(0, 0, 0))

    # test std length
    with pytest.raises(AssertionError):
        tensor = torch.randn(2, 3, 5, 5)
        mmcv.tensor2imgs(tensor, std=(1, ))
        tensor = torch.randn(2, 1, 5, 5)
        mmcv.tensor2imgs(tensor, std=(1, 1, 1))

    # test to_rgb
    with pytest.raises(AssertionError):
        tensor = torch.randn(2, 1, 5, 5)
        mmcv.tensor2imgs(tensor, mean=(0, ), std=(1, ), to_rgb=True)

    # test rgb=True
    tensor = torch.randn(2, 3, 5, 5)
    gts = [
        t.cpu().numpy().transpose(1, 2, 0).astype(np.uint8)
        for t in tensor.flip(1)
    ]
    outputs = mmcv.tensor2imgs(tensor, to_rgb=True)
    for gt, output in zip(gts, outputs, strict=False):
        assert_array_equal(gt, output)

    # test rgb=False
    tensor = torch.randn(2, 3, 5, 5)
    gts = [t.cpu().numpy().transpose(1, 2, 0).astype(np.uint8) for t in tensor]
    outputs = mmcv.tensor2imgs(tensor, to_rgb=False)
    for gt, output in zip(gts, outputs, strict=False):
        assert_array_equal(gt, output)

    # test tensor channel 1 and rgb=False
    tensor = torch.randn(2, 1, 5, 5)
    gts = [t.squeeze(0).cpu().numpy().astype(np.uint8) for t in tensor]
    outputs = mmcv.tensor2imgs(tensor, to_rgb=False)
    for gt, output in zip(gts, outputs, strict=False):
        assert_array_equal(gt, output)
