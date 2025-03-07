# Copyright (c) OpenMMLab. All rights reserved.
# Code reference from "Temporal Interlacing Network"
# https://github.com/deepcs233/TIN/blob/master/cuda_shift/rtc_wrap.py
# Hao Shao, Shengju Qian, Yu Liu
# shaoh19@mails.tsinghua.edu.cn, sjqian@cse.cuhk.edu.hk, yuliu@ee.cuhk.edu.hk

import torch
import torch.nn as nn
from torch.autograd import Function

from mmcv.ops.pure_pytorch_tin_shift.tin_shift_forward import tin_shift_forward_pytorch
from mmcv.ops.pure_pytorch_tin_shift.tin_shift_backward import tin_shift_backward_pytorch
from mmcv.ops.pure_pytorch_tin_shift.tin_shift_forward import tin_shift_forward_pytorch
from mmcv.ops.pure_pytorch_tin_shift.tin_shift_backward import tin_shift_backward_pytorch

                                 ['tin_shift_forward', 'tin_shift_backward'])


class TINShiftFunction(Function):

    @staticmethod
    def forward(ctx, input, shift):
        if input.size(0) != shift.size(0):
            raise ValueError(
                'The first dim (batch) of `input` and `shift` should be '
                f'same, but got {input.size(0)} and {shift.size(0)}.')
        C = input.size(2)
        num_segments = shift.size(1)
        if C // num_segments <= 0 or C % num_segments != 0:
            raise ValueError('C should be a multiple of num_segments, '
                             f'but got C={C} and num_segments={num_segments}.')

        ctx.save_for_backward(shift)

        out = torch.zeros_like(input)
        tin_shift_forward_pytorch(input, shift, out)

        return out

    @staticmethod
    def backward(ctx, grad_output):

        shift = ctx.saved_tensors[0]
        data_grad_input = grad_output.new(*grad_output.size()).zero_()
        shift_grad_input = shift.new(*shift.size()).zero_()
        tin_shift_backward_pytorch(grad_output, shift, data_grad_input)

        return data_grad_input, shift_grad_input


tin_shift = TINShiftFunction.apply


class TINShift(nn.Module):
    """Temporal Interlace Shift.

    Temporal Interlace shift is a differentiable temporal-wise frame shifting
    which is proposed in "Temporal Interlacing Network"

    Please refer to
    `Temporal Interlacing Network <https://arxiv.org/abs/2001.06499>`_
     for more details.

    Code is modified from
    https://github.com/mit-han-lab/temporal-shift-module
    """

    def forward(self, input, shift):
        """Perform temporal interlace shift.

        Args:
            input (torch.Tensor): Feature map with shape
                [N, num_segments, C, H * W].
            shift (torch.Tensor): Shift tensor with shape [N, num_segments].

        Returns:
            Feature map after temporal interlace shift.
        """
        return tin_shift(input, shift)
