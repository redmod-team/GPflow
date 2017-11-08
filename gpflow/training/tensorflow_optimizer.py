# Copyright 2017 Artem Artemev @awav
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys
import tensorflow as tf

from . import optimizer
from ..models.model import Model


_REGISTERED_TENSORFLOW_OPTIMIZERS = {}


class _TensorFlowOptimizer(optimizer.Optimizer):
    def __init__(self, *args, **kwargs):
        name = self.__class__.__name__
        tf_optimizer = _get_registered_optimizer(name)
        if tf_optimizer is None:
            raise ValueError('Optimizer not found.')
        self._model = None
        super(_TensorFlowOptimizer, self).__init__()
        self._optimizer = tf_optimizer(*args, **kwargs)
        self._minimize_operation = None

    def minimize(self, model, session=None, var_list=None, feed_dict=None,
                 maxiter=1000, initialize=True, anchor=True, **kwargs):
        if model is None or not isinstance(model, Model):
            raise ValueError('Unknown type passed for optimization.')

        session = model.enquire_session(session)

        self._model = model
        objective = model.objective

        with session.graph.as_default():
            self._minimize_operation = self.optimizer.minimize(
                objective, var_list=var_list, **kwargs)
            model.initialize(session=session, force=initialize)
            full_var_list = self._gen_var_list(model, var_list)
            self._initialize_optimizer(session, full_var_list)

        for _i in range(maxiter):
            if model.feeds:
                feed_dict.update(model.feeds)
            session.run(self.minimize_operation, feed_dict=feed_dict)

        if anchor:
            model.anchor(session)

    def _initialize_optimizer(self, session, var_list):
        # TODO(@awav): AdamOptimizer creates beta1 and beta2 variables which are
        #             not included in slots.
        extra_vars = [v for v in self.optimizer.__dict__.values() if isinstance(v, tf.Variable)]
        optimizer_vars = [self.optimizer.get_slot(var, name)
                          for name in self.optimizer.get_slot_names()
                          for var in var_list]
        var_list = list(set(optimizer_vars + extra_vars))
        session.run(tf.variables_initializer(var_list))

    @property
    def minimize_operation(self):
        return self._minimize_operation

    @property
    def model(self):
        return self._model

    @property
    def optimizer(self):
        return self._optimizer

    @model.setter
    def model(self, value):
        self._model = value
        self._optimizer = None
        self._minimize_operation = None


def _get_registered_optimizer(name):
    return _REGISTERED_TENSORFLOW_OPTIMIZERS.get(name)


def _register_optimizer(name, optimizer_type):
    if optimizer_type.__base__ is not tf.train.Optimizer:
        raise ValueError('Wrong TensorFlow optimizer type passed: "{0}".'
                         .format(optimizer_type))
    gp_optimizer = type(name, (_TensorFlowOptimizer, ), {})
    _REGISTERED_TENSORFLOW_OPTIMIZERS[name] = optimizer_type
    module = sys.modules[__name__]
    setattr(module, name, gp_optimizer)


# Create GPflow optimizer classes with same names as TensorFlow optimizers
for key, train_type in tf.train.__dict__.items():
    suffix = 'Optimizer'
    if key != suffix and key.endswith(suffix):
        _register_optimizer(key, train_type)


__all__ = list(_REGISTERED_TENSORFLOW_OPTIMIZERS.keys())
