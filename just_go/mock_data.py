#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/6/20 15:11
# @Author   :luye
from faker import Faker


class MockData:

    def __init__(self, locale='zh_CN'):
        self.fake: Faker = Faker(locale=locale)
