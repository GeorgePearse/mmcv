# Copyright (c) OpenMMLab. All rights reserved.
import inspect

from mmengine.registry import MODELS
from torch import nn

MODELS.register_module('Conv1d', module=nn.Conv1d)
MODELS.register_module('Conv2d', module=nn.Conv2d)
MODELS.register_module('Conv3d', module=nn.Conv3d)
MODELS.register_module('Conv', module=nn.Conv2d)


def build_conv_layer(cfg: dict | None, *args, **kwargs) -> nn.Module:
    """Build convolution layer.

    Args:
        cfg (None or dict): The conv layer config, which should contain:
            - type (str): Layer type.
            - layer args: Args needed to instantiate an conv layer.
        args (argument list): Arguments passed to the `__init__`
            method of the corresponding conv layer.
        kwargs (keyword arguments): Keyword arguments passed to the `__init__`
            method of the corresponding conv layer.

    Returns:
        nn.Module: Created conv layer.
    """
    if cfg is None:
        cfg_ = {'type': 'Conv2d'}
    else:
        if not isinstance(cfg, dict):
            raise TypeError('cfg must be a dict')
        if 'type' not in cfg:
            raise KeyError('the cfg dict must contain the key "type"')
        cfg_ = cfg.copy()

    layer_type = cfg_.pop('type')
    if inspect.isclass(layer_type):
        return layer_type(*args, **kwargs, **cfg_)  # type: ignore
    # Switch registry to the target scope. If `conv_layer` cannot be found
    # in the registry, fallback to search `conv_layer` in the
    # mmengine.MODELS.
    with MODELS.switch_scope_and_registry(None) as registry:
        conv_layer = registry.get(layer_type)
    if conv_layer is None:
        raise KeyError(f'Cannot find {conv_layer} in registry under scope '
                       f'name {registry.scope}')
    layer = conv_layer(*args, **kwargs, **cfg_)

    return layer
