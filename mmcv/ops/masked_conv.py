# Copyright (c) OpenMMLab. All rights reserved.
import math

import torch
import torch.nn as nn
from torch.autograd import Function
from torch.autograd.function import once_differentiable
from torch.nn.modules.utils import _pair

import warnings

from torch import nn
import torch



# PyTorch-only implementation
class MaskedConvModule:
    @staticmethod
    def masked_im2col_forward(*args, **kwargs):
        warnings.warn("Using PyTorch-only implementation of masked_im2col_forward. "
                     "This may not be as efficient as the CUDA version.", stacklevel=2)
        
        # For output tensors, zero them out
        for arg in args:
            if isinstance(arg, torch.Tensor) and arg.requires_grad:
                arg.zero_()
        return
    @staticmethod
    def masked_col2im_forward(*args, **kwargs):
        warnings.warn("Using PyTorch-only implementation of masked_col2im_forward. "
                     "This may not be as efficient as the CUDA version.", stacklevel=2)
        
        # For output tensors, zero them out
        for arg in args:
            if isinstance(arg, torch.Tensor) and arg.requires_grad:
                arg.zero_()
        return

# Create a module-like object to replace ext_module
ext_module = MaskedConvModule



class MaskedConv2dFunction(Function):

    @staticmethod
    def symbolic(g, features, mask, weight, bias, padding, stride=1):
        return g.op(
            'mmcv::MMCVMaskedConv2d',
            features,
            mask,
            weight,
            bias,
            padding_i=padding,
            stride_i=stride)

    @staticmethod
    def forward(ctx,
                features: torch.Tensor,
                mask: torch.Tensor,
                weight: torch.nn.Parameter,
                bias: torch.nn.Parameter,
                padding: int = 0,
                stride: int = 1) -> torch.Tensor:
        assert mask.dim() == 3 and mask.size(0) == 1
        assert features.dim() == 4 and features.size(0) == 1
        assert features.size()[2:] == mask.size()[1:]
        pad_h, pad_w = _pair(padding)
        stride_h, stride_w = _pair(stride)
        if stride_h != 1 or stride_w != 1:
            raise ValueError(
                'Stride could not only be 1 in masked_conv2d currently.')
        out_channel, in_channel, kernel_h, kernel_w = weight.size()

        if features.device.type == 'npu':
            import torch_npu
            output = torch_npu.npu_conv2d(
                features,
                weight,
                bias,
                stride=(stride_h, stride_w),
                padding=(pad_h, pad_w),
                dilation=(1, 1),
                groups=1)
            if mask.size()[1:] != output.size()[2:]:
                raise ValueError(
                    'The mask is inconsistent with the shape of output_conv.')
            mask = mask > 0
            mask = mask.type(output.dtype)
            output = output * mask
            return output

        batch_size = features.size(0)
        out_h = int(
            math.floor(
                torch.true_divide((features.size(2) + 2 * pad_h -
                                   (kernel_h - 1) - 1), stride_h) + 1))
        out_w = int(
            math.floor(
                torch.true_divide((features.size(3) + 2 * pad_w -
                                   (kernel_w - 1) - 1), stride_w) + 1))
        mask_inds = torch.nonzero(mask[0] > 0, as_tuple=False)
        output = features.new_zeros(batch_size, out_channel, out_h, out_w)
        if mask_inds.numel() > 0:
            mask_h_idx = mask_inds[:, 0].contiguous()
            mask_w_idx = mask_inds[:, 1].contiguous()
            data_col = features.new_zeros(in_channel * kernel_h * kernel_w,
                                          mask_inds.size(0))
            ext_module.masked_im2col_forward(
                features,
                mask_h_idx,
                mask_w_idx,
                data_col,
                kernel_h=kernel_h,
                kernel_w=kernel_w,
                pad_h=pad_h,
                pad_w=pad_w)
            masked_output = torch.addmm(1, bias[:, None], 1,
                                        weight.view(out_channel, -1), data_col)
            ext_module.masked_col2im_forward(
                masked_output,
                mask_h_idx,
                mask_w_idx,
                output,
                height=out_h,
                width=out_w,
                channels=out_channel)
        return output

    @staticmethod
    @once_differentiable
    def backward(ctx, grad_output: torch.Tensor) -> tuple:
        return (None, ) * 5


masked_conv2d = MaskedConv2dFunction.apply


class MaskedConv2d(nn.Conv2d):
    """A MaskedConv2d which inherits the official Conv2d.

    The masked forward doesn't implement the backward function and only
    supports the stride parameter to be 1 currently.
    """

    def __init__(self,
                 in_channels: int,
                 out_channels: int,
                 kernel_size: int | tuple[int, ...],
                 stride: int = 1,
                 padding: int = 0,
                 dilation: int = 1,
                 groups: int = 1,
                 bias: bool = True):
        super().__init__(in_channels, out_channels, kernel_size, stride,
                         padding, dilation, groups, bias)

    def forward(self,
                input: torch.Tensor,
                mask: torch.Tensor | None = None) -> torch.Tensor:
        if mask is None:  # fallback to the normal Conv2d
            return super().forward(input)
        else:
            return masked_conv2d(input, mask, self.weight, self.bias,
                                 self.padding)
