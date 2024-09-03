# © 2024 The Johns Hopkins University Applied Physics Laboratory LLC.  This material was sponsored by the U.S. Government under contract number 2020-20081800401.
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in
# the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import boto3
import os
import re

# database functionality is currently only supported in developer mode
DEV = False


# download a file from S3 to the local filesystem
def s3_get(path, destination, reg_exp=".*", s3_client=None):
    bucket = path.split("/")[2]
    key_or_prefix = "/".join(path.split("/")[3:])
    if s3_client is None:
        s3_client = boto3.client("s3")
    if key_or_prefix.endswith("/"):
        keys = []
        paginator = s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=key_or_prefix):
            for contents in page["Contents"]:
                key = contents["Key"]
                if not key.endswith("/") and re.match(reg_exp, key.split("/")[-1]):
                    keys.append(key)
    else:
        keys = [key_or_prefix]
    for key in keys:
        filename = key.split("/")[-1]
        os.makedirs(destination, exist_ok=True)
        s3_client.download_file(bucket, key, os.path.join(destination, filename))


# get the path to a file on the local filesystem
def as_local_path(input_path, default_path, reg_exp=".*", s3_client=None):
    if not input_path:
        return default_path
    # convert an S3 path to a path on the local filesystem where the file has been downloaded
    elif input_path.startswith("s3://"):
        if not default_path.endswith("/"):
            _default_path = "/".join(default_path.split("/")[:-1])
        else:
            _default_path = default_path
        s3_get(input_path, _default_path, reg_exp=reg_exp, s3_client=s3_client)
        return default_path
    else:
        return input_path
