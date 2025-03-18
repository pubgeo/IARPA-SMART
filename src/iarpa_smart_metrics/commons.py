# © 2025 The Johns Hopkins University Applied Physics Laboratory LLC.  This material was sponsored by the U.S. Government under contract number 2020-20081800401.
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


def s3_get(path, destination, reg_exp=".*", s3_client=None):
    """
    Downloads one or more files from an S3 bucket to a local directory.

    Parameters:
        path (str): The S3 path of the file(s) to download.
            Format: "bucket/prefix/key" or "bucket/prefix".
            The path can include multiple files or a single file.
        destination (str): The local directory where the file(s) will be downloaded.
            Format: "/path/to/local/directory"
        reg_exp (str, optional): A regular expression pattern used to filter the files to download.
            Defaults to ".*" (match all files).
            Format: "^regex_pattern$"
        s3_client (boto3.client, optional): The S3 client to use for downloading the file(s).
            If not provided, a new S3 client will be created.
            Format: boto3.client("s3")

    Returns:
        None
    """
    # Extract bucket and key/prefix from the S3 path
    bucket = path.split("/")[2]
    key_or_prefix = "/".join(path.split("/")[3:])

    # If s3_client is not provided, create a new one
    if s3_client is None:
        s3_client = boto3.client("s3")

    # If key/prefix ends with a "/", paginate through the objects in the bucket
    if key_or_prefix.endswith("/"):
        keys = []
        paginator = s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=key_or_prefix):
            for contents in page["Contents"]:
                key = contents["Key"]
                # Filter objects based on the regular expression pattern
                if not key.endswith("/") and re.match(reg_exp, key.split("/")[-1]):
                    keys.append(key)
    else:
        # If key/prefix does not end with a "/", assume it is a single file
        keys = [key_or_prefix]

    # Download each file using the S3 client and save it in the destination directory
    for key in keys:
        filename = key.split("/")[-1]
        os.makedirs(destination, exist_ok=True)
        s3_client.download_file(bucket, key, os.path.join(destination, filename))


def as_local_path(input_path, default_path, reg_exp=".*", s3_client=None):
    """
    Convert an input path to a local path.

    This function takes an input path and a default path as parameters. If the input path is not provided or is empty,
    the function returns the default path. If the input path starts with "s3://", indicating an S3 path, the function
    downloads the file to the default path and returns the default path. Otherwise, it returns the input path.

    The default_path must end with a trailing slash!

    Parameters:
        input_path (str): The input path to be converted.
        default_path (str): The default path to be used if the input path is not provided or is empty. Must end with a trailing slash!
        reg_exp (str, optional): A regular expression pattern used to filter the files to download (when input_path starts with "s3://").
            Defaults to ".*" (match all files).
        s3_client (boto3.client, optional): The S3 client to use for downloading the file (when input_path starts with "s3://").
            If not provided, a new S3 client will be created.

    Returns:
        str: The converted local path.

    """
    # Check if the input path is empty
    if not input_path:
        return default_path
    # Convert an S3 path to a path on the local filesystem where the file has been downloaded
    elif input_path.startswith("s3://"):
        # Check if the default path ends with a "/"
        if not default_path.endswith("/"):
            _default_path = "/".join(default_path.split("/")[:-1])
        else:
            _default_path = default_path

        # Download the file to the default path using the provided S3 client
        s3_get(input_path, _default_path, reg_exp=reg_exp, s3_client=s3_client)
        return default_path
    else:
        return input_path
