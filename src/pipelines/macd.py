#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MACD Pipeline
"""

from .configurable import ConfigurablePipeline


class MacdPipeline(ConfigurablePipeline):
    name = 'macd'
    config_id = 'macd_v1'

    def __init__(self):
        super().__init__(config_id=self.config_id, name=self.name)
