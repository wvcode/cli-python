# -*- coding: utf-8 -*-
import base64


def encode(value):
    return_value = base64.b64encode(value.encode())
    return_value = (
        return_value[2 : len(return_value) - 1]
        + return_value[0:2]
        + return_value[len(return_value) - 1 :]
    )
    return return_value.decode("utf-8")


def decode(value):
    try:
        encoded = value.encode()
    except:
        encoded = value
    return_value = (
        encoded[len(encoded) - 3 : len(encoded) - 1]
        + encoded[0 : len(encoded) - 3]
        + encoded[len(encoded) - 1 :]
    )
    return_value = base64.b64decode(return_value)
    return return_value.decode()
