from typing import Any, Union

import numpy as np
import torch
from mmengine.utils import deprecated_api_warning
from torch import Tensor

from mmcv.ops.pure_pytorch_nms import nms_match_pytorch, nms_pytorch, soft_nms_pytorch


# Define a stub for nms_rotated for backwards compatibility
def nms_rotated(*args, **kwargs):
    raise NotImplementedError(
        'nms_rotated has been removed. The functionality for rotated detection has been removed.'
    )


# This function is modified from: https://github.com/pytorch/vision/
class NMSop(torch.autograd.Function):

    @staticmethod
    def forward(ctx: Any, bboxes: Tensor, scores: Tensor, iou_threshold: float,
                offset: int, score_threshold: float, max_num: int) -> Tensor:
        is_filtering_by_score = score_threshold > 0
        if is_filtering_by_score:
            valid_mask = scores > score_threshold
            bboxes, scores = bboxes[valid_mask], scores[valid_mask]
            valid_inds = torch.nonzero(
                valid_mask, as_tuple=False).squeeze(dim=1)

        # Use pure PyTorch implementation instead of CUDA
        inds = nms_pytorch(bboxes, scores, float(iou_threshold))

        if max_num > 0:
            inds = inds[:max_num]
        if is_filtering_by_score:
            inds = valid_inds[inds]
        return inds


class SoftNMSop(torch.autograd.Function):

    @staticmethod
    def forward(ctx: Any, boxes: Tensor, scores: Tensor, iou_threshold: float,
                sigma: float, min_score: float, method: int,
                offset: int) -> tuple[Tensor, Tensor]:
        # Map method int to string for pure PyTorch implementation
        method_map = {0: 'naive', 1: 'linear', 2: 'gaussian'}
        method_str = method_map[method]
        
        # Use pure PyTorch implementation
        dets, inds = soft_nms_pytorch(
            boxes,
            scores,
            iou_threshold=float(iou_threshold),
            sigma=float(sigma),
            min_score=float(min_score),
            method=method_str)
            
        return dets, inds

    @staticmethod
    def symbolic(g, boxes, scores, iou_threshold, sigma, min_score, method,
                 offset):
        from packaging import version
        assert version.parse(torch.__version__) >= version.parse('1.7.0')
        nms_out = g.op(
            'mmcv::SoftNonMaxSuppression',
            boxes,
            scores,
            iou_threshold_f=float(iou_threshold),
            sigma_f=float(sigma),
            min_score_f=float(min_score),
            method_i=int(method),
            offset_i=int(offset),
            outputs=2)
        return nms_out


array_like_type = Union[Tensor, np.ndarray]


@deprecated_api_warning({'iou_thr': 'iou_threshold'})
def nms(boxes: array_like_type,
        scores: array_like_type,
        iou_threshold: float,
        offset: int = 0,
        score_threshold: float = 0,
        max_num: int = -1) -> tuple[array_like_type, array_like_type]:
    """Dispatch to either CPU or GPU NMS implementations.

    The input can be either torch tensor or numpy array. GPU NMS will be used
    if the input is gpu tensor, otherwise CPU NMS
    will be used. The returned type will always be the same as inputs.

    Arguments:
        boxes (torch.Tensor or np.ndarray): boxes in shape (N, 4).
        scores (torch.Tensor or np.ndarray): scores in shape (N, ).
        iou_threshold (float): IoU threshold for NMS.
        offset (int, 0 or 1): boxes' width or height is (x2 - x1 + offset).
        score_threshold (float): score threshold for NMS.
        max_num (int): maximum number of boxes after NMS.

    Returns:
        tuple: kept dets (boxes and scores) and indice, which always have
        the same data type as the input.

    Example:
        >>> boxes = np.array([[49.1, 32.4, 51.0, 35.9],
        >>>                   [49.3, 32.9, 51.0, 35.3],
        >>>                   [49.2, 31.8, 51.0, 35.4],
        >>>                   [35.1, 11.5, 39.1, 15.7],
        >>>                   [35.6, 11.8, 39.3, 14.2],
        >>>                   [35.3, 11.5, 39.9, 14.5],
        >>>                   [35.2, 11.7, 39.7, 15.7]], dtype=np.float32)
        >>> scores = np.array([0.9, 0.9, 0.5, 0.5, 0.5, 0.4, 0.3],\
               dtype=np.float32)
        >>> iou_threshold = 0.6
        >>> dets, inds = nms(boxes, scores, iou_threshold)
        >>> assert len(inds) == len(dets) == 3
    """
    assert isinstance(boxes, Tensor | np.ndarray)
    assert isinstance(scores, Tensor | np.ndarray)
    is_numpy = False
    if isinstance(boxes, np.ndarray):
        is_numpy = True
        boxes = torch.from_numpy(boxes)
    if isinstance(scores, np.ndarray):
        scores = torch.from_numpy(scores)
    assert boxes.size(1) == 4
    assert boxes.size(0) == scores.size(0)
    assert offset in (0, 1)

    inds = NMSop.apply(boxes, scores, iou_threshold, offset, score_threshold,
                       max_num)
    dets = torch.cat((boxes[inds], scores[inds].reshape(-1, 1)), dim=1)
    if is_numpy:
        dets = dets.cpu().numpy()
        inds = inds.cpu().numpy()
    return dets, inds


@deprecated_api_warning({'iou_thr': 'iou_threshold'})
def soft_nms(boxes: array_like_type,
             scores: array_like_type,
             iou_threshold: float = 0.3,
             sigma: float = 0.5,
             min_score: float = 1e-3,
             method: str = 'linear',
             offset: int = 0) -> tuple[array_like_type, array_like_type]:
    """Dispatch to only CPU Soft NMS implementations.

    The input can be either a torch tensor or numpy array.
    The returned type will always be the same as inputs.

    Args:
        boxes (torch.Tensor or np.ndarray): boxes in shape (N, 4).
        scores (torch.Tensor or np.ndarray): scores in shape (N, ).
        iou_threshold (float): IoU threshold for NMS.
        sigma (float): hyperparameter for gaussian method
        min_score (float): score filter threshold
        method (str): either 'linear' or 'gaussian'
        offset (int, 0 or 1): boxes' width or height is (x2 - x1 + offset).

    Returns:
        tuple: kept dets (boxes and scores) and indice, which always have
        the same data type as the input.

    Example:
        >>> boxes = np.array([[4., 3., 5., 3.],
        >>>                   [4., 3., 5., 4.],
        >>>                   [3., 1., 3., 1.],
        >>>                   [3., 1., 3., 1.],
        >>>                   [3., 1., 3., 1.],
        >>>                   [3., 1., 3., 1.]], dtype=np.float32)
        >>> scores = np.array([0.9, 0.9, 0.5, 0.5, 0.4, 0.0], dtype=np.float32)
        >>> iou_threshold = 0.6
        >>> dets, inds = soft_nms(boxes, scores, iou_threshold, sigma=0.5)
        >>> assert len(inds) == len(dets) == 5
    """

    assert isinstance(boxes, Tensor | np.ndarray)
    assert isinstance(scores, Tensor | np.ndarray)
    is_numpy = False
    if isinstance(boxes, np.ndarray):
        is_numpy = True
        boxes = torch.from_numpy(boxes)
    if isinstance(scores, np.ndarray):
        scores = torch.from_numpy(scores)
    assert boxes.size(1) == 4
    assert boxes.size(0) == scores.size(0)
    assert offset in (0, 1)
    method_dict = {'naive': 0, 'linear': 1, 'gaussian': 2}
    assert method in method_dict.keys()

    dets, inds = SoftNMSop.apply(boxes.cpu(), scores.cpu(),
                                 float(iou_threshold), float(sigma),
                                 float(min_score), method_dict[method],
                                 int(offset))

    dets = dets[:inds.size(0)]

    if is_numpy:
        dets = dets.cpu().numpy()
        inds = inds.cpu().numpy()
        return dets, inds
    else:
        return dets.to(device=boxes.device), inds.to(device=boxes.device)


def batched_nms(boxes: Tensor,
                scores: Tensor,
                idxs: Tensor,
                nms_cfg: dict | None,
                class_agnostic: bool = False) -> tuple[Tensor, Tensor]:
    r"""Performs non-maximum suppression in a batched fashion.

    Modified from `torchvision/ops/boxes.py#L39
    <https://github.com/pytorch/vision/blob/
    505cd6957711af790211896d32b40291bea1bc21/torchvision/ops/boxes.py#L39>`_.
    In order to perform NMS independently per class, we add an offset to all
    the boxes. The offset is dependent only on the class idx, and is large
    enough so that boxes from different classes do not overlap.

    Note:
        In v1.4.1 and later, ``batched_nms`` supports skipping the NMS and
        returns sorted raw results when `nms_cfg` is None.

    Args:
        boxes (torch.Tensor): boxes in shape (N, 4) or (N, 5).
        scores (torch.Tensor): scores in shape (N, ).
        idxs (torch.Tensor): each index value correspond to a bbox cluster,
            and NMS will not be applied between elements of different idxs,
            shape (N, ).
        nms_cfg (dict | optional): Supports skipping the nms when `nms_cfg`
            is None, otherwise it should specify nms type and other
            parameters like `iou_thr`. Possible keys includes the following.

            - iou_threshold (float): IoU threshold used for NMS.
            - split_thr (float): threshold number of boxes. In some cases the
              number of boxes is large (e.g., 200k). To avoid OOM during
              training, the users could set `split_thr` to a small value.
              If the number of boxes is greater than the threshold, it will
              perform NMS on each group of boxes separately and sequentially.
              Defaults to 10000.
        class_agnostic (bool): if true, nms is class agnostic,
            i.e. IoU thresholding happens over all boxes,
            regardless of the predicted class. Defaults to False.

    Returns:
        tuple: kept dets and indice.

        - boxes (Tensor): Bboxes with score after nms, has shape
          (num_bboxes, 5). last dimension 5 arrange as
          (x1, y1, x2, y2, score)
        - keep (Tensor): The indices of remaining boxes in input
          boxes.
    """
    # skip nms when nms_cfg is None
    if nms_cfg is None:
        scores, inds = scores.sort(descending=True)
        boxes = boxes[inds]
        return torch.cat([boxes, scores[:, None]], -1), inds

    nms_cfg_ = nms_cfg.copy()
    class_agnostic = nms_cfg_.pop('class_agnostic', class_agnostic)
    if class_agnostic:
        boxes_for_nms = boxes
    else:
        # When using rotated boxes, only apply offsets on center.
        if boxes.size(-1) == 5:
            # Strictly, the maximum coordinates of the rotating box
            # (x,y,w,h,a) should be calculated by polygon coordinates.
            # But the conversion from rotated box to polygon will
            # slow down the speed.
            # So we use max(x,y) + max(w,h) as max coordinate
            # which is larger than polygon max coordinate
            # max(x1, y1, x2, y2,x3, y3, x4, y4)
            max_coordinate = boxes[..., :2].max() + boxes[..., 2:4].max()
            offsets = idxs.to(boxes) * (
                max_coordinate + torch.tensor(1).to(boxes))
            boxes_ctr_for_nms = boxes[..., :2] + offsets[:, None]
            boxes_for_nms = torch.cat([boxes_ctr_for_nms, boxes[..., 2:5]],
                                      dim=-1)
        else:
            max_coordinate = boxes.max()
            offsets = idxs.to(boxes) * (
                max_coordinate + torch.tensor(1).to(boxes))
            boxes_for_nms = boxes + offsets[:, None]

    nms_op = nms_cfg_.pop('type', 'nms')
    if isinstance(nms_op, str):
        nms_op = eval(nms_op)

    split_thr = nms_cfg_.pop('split_thr', 10000)
    # Won't split to multiple nms nodes when exporting to onnx
    if boxes_for_nms.shape[0] < split_thr:
        dets, keep = nms_op(boxes_for_nms, scores, **nms_cfg_)
        boxes = boxes[keep]

        # This assumes `dets` has arbitrary dimensions where
        # the last dimension is score.
        # Currently it supports bounding boxes [x1, y1, x2, y2, score] or
        # rotated boxes [cx, cy, w, h, angle_radian, score].

        scores = dets[:, -1]
    else:
        max_num = nms_cfg_.pop('max_num', -1)
        total_mask = scores.new_zeros(scores.size(), dtype=torch.bool)
        # Some type of nms would reweight the score, such as SoftNMS
        scores_after_nms = scores.new_zeros(scores.size())
        for id in torch.unique(idxs):
            mask = (idxs == id).nonzero(as_tuple=False).view(-1)
            dets, keep = nms_op(boxes_for_nms[mask], scores[mask], **nms_cfg_)
            total_mask[mask[keep]] = True
            scores_after_nms[mask[keep]] = dets[:, -1]
        keep = total_mask.nonzero(as_tuple=False).view(-1)

        scores, inds = scores_after_nms[keep].sort(descending=True)
        keep = keep[inds]
        boxes = boxes[keep]

        if max_num > 0:
            keep = keep[:max_num]
            boxes = boxes[:max_num]
            scores = scores[:max_num]

    boxes = torch.cat([boxes, scores[:, None]], -1)
    return boxes, keep


def nms_match(dets: array_like_type,
              iou_threshold: float) -> list[array_like_type]:
    """Matched dets into different groups by NMS.

    NMS match is Similar to NMS but when a bbox is suppressed, nms match will
    record the indice of suppressed bbox and form a group with the indice of
    kept bbox. In each group, indice is sorted as score order.

    Args:
        dets (torch.Tensor | np.ndarray): Det boxes with scores, shape (N, 5).
        iou_threshold (float): IoU thresh for NMS.

    Returns:
        list[torch.Tensor | np.ndarray]: The outer list corresponds different
        matched group, the inner Tensor corresponds the indices for a group
        in score order.
    """
    if dets.shape[0] == 0:
        matched = []
    else:
        assert dets.shape[-1] == 5, 'inputs dets.shape should be (N, 5), ' \
                                    f'but get {dets.shape}'
        if isinstance(dets, np.ndarray):
            dets_t = torch.from_numpy(dets)
        else:
            dets_t = dets
        
        # Use pure PyTorch implementation
        matched = nms_match_pytorch(dets_t, float(iou_threshold))

    if isinstance(dets, np.ndarray):
        return [m.cpu().numpy() for m in matched]
    else:
        return matched


def nms_quadri(dets: Tensor,
               scores: Tensor,
               iou_threshold: float,
               labels: Tensor | None = None) -> tuple[Tensor, Tensor]:
    """Performs non-maximum suppression (NMS) on the quadrilateral boxes
    according to their intersection-over-union (IoU).

    Quadri NMS iteratively removes lower scoring quadrilateral boxes
    which have an IoU greater than iou_threshold with another (higher
    scoring) quadrilateral box.

    Args:
        dets (torch.Tensor):  Quadri boxes in shape (N, 8).
            They are expected to be in
            (x1, y1, ..., x4, y4) format.
        scores (torch.Tensor): scores in shape (N, ).
        iou_threshold (float): IoU thresh for NMS.
        labels (torch.Tensor, optional): boxes' label in shape (N,).

    Returns:
        tuple: kept dets(boxes and scores) and indice, which is always the
        same data type as the input.
    """
    from mmcv.ops.pure_pytorch_nms import nms_quadri_pytorch
    
    if dets.shape[0] == 0:
        return dets, None

    # Use pure PyTorch implementation
    dets_out, keep_inds = nms_quadri_pytorch(dets, scores, iou_threshold, labels)
    
    return dets_out, keep_inds
