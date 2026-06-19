#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bollinger Bands Pipeline
"""

from .configurable import ConfigurablePipeline


class BollPipeline(ConfigurablePipeline):
    name = 'boll'
    config_id = 'boll_v1'

    def __init__(self):
        super().__init__(config_id=self.config_id, name=self.name)
