#!/usr/bin/env python
# © 2025 The Johns Hopkins University Applied Physics Laboratory LLC.  This material was sponsored by the U.S. Government under contract number 2020-20081800401.
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in
# the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""The setup script."""
from os.path import exists
from setuptools import setup, find_packages


def parse_version(fpath):
    """
    Statically parse the version number from a python file
    """
    import ast

    if not exists(fpath):
        raise ValueError("fpath={!r} does not exist".format(fpath))
    with open(fpath, "r") as file_:
        sourcecode = file_.read()
    pt = ast.parse(sourcecode)

    class VersionVisitor(ast.NodeVisitor):
        def visit_Assign(self, node):
            for target in node.targets:
                if getattr(target, "id", None) == "__version__":
                    self.version = node.value.s

    visitor = VersionVisitor()
    visitor.visit(pt)
    return visitor.version


def parse_requirements(fpath="requirements.txt", pinned="free"):
    """
    Args:
        pinned (str): can be
            free - remove all constraints
            loose - use the greater or equal (>=) in the req file
            strict - replace all greater equal with equals
    """
    # Note: different versions of pip might have different internals.
    # This may need to be fixed.
    from pip._internal.req import parse_requirements
    from pip._internal.network.session import PipSession

    requirements = []
    for req in parse_requirements(fpath, session=PipSession()):
        if pinned == "free":
            req_name = req.requirement.split(" ")[0]
            requirements.append(req_name)
        elif pinned == "loose":
            requirements.append(req.requirement)
        elif pinned == "strict":
            requirements.append(req.requirement.replace(">=", "=="))
        else:
            raise KeyError(pinned)
    return requirements


VERSION = parse_version("iarpa_smart_metrics/__init__.py")

try:
    with open("README.md") as readme_file:
        README = readme_file.read()
except Exception:
    README = ""

try:
    REQUIREMENTS = parse_requirements("requirements.txt")
except Exception as ex:
    print("ex = {!r}".format(ex))
    REQUIREMENTS = []

setup(
    author="Michael Kelbaugh",
    author_email="michael.kelbaugh@jhuapl.edu",
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    description="",
    install_requires=REQUIREMENTS,
    long_description_content_type="text/markdown",
    long_description=README,
    include_package_data=True,
    name="iarpa_smart_metrics",
    packages=find_packages(),
    url="https://smartgitlab.com/TE/metrics-and-test-framework",
    version=VERSION,
    zip_safe=False,
)
