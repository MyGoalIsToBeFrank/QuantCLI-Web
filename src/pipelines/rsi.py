#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSI Pipeline
"""

from .configurable import ConfigurablePipeline


class RSIPipeline(ConfigurablePipeline):
    name = 'rsi'
    config_id = 'rsi_v1'

    def __init__(self):
        super().__init__(config_id=self.config_id, name=self.name)
