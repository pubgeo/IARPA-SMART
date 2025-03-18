# IARPA SMART Installation

This document has installation instructions for several current operating systems and versions. If you cannot find your system listed below, or encounter a problem with the instructions, please reach out to:

* iarpa.smart@jhuapl.edu

## Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04
- **Clone the Git repository**

```
git clone https://github.com/pubgeo/IARPA_SMART.git
```

- **Install Python 3.11**

```
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.11
```

- **Install pip for Python 3.11**

```
sudo apt install python3.11-distutils
sudo apt install pip
python3.11 -m ensurepip
```

- **Install Python modules for Python 3.11**
(use `--default-timeout` if needed, for downloading larger packages)

```
cd IARPA-SMART/src
python3.11 -m pip install -r requirements.txt --default-timeout=1000
```

- **Set up alias for python3.11**

```
alias python=python3.11
alias python3=python3.11
```

- **Run the example script**
(run the .sh script *directly*, without using `/bin/sh`)

```
./example/example_run.sh
```

- **Check outputs**

  - Check that the script runs without errors
  - Check that the `example/output` and `example/output.compare` folders have been created and populated

## Redhat 8, Redhat 9
- **Clone the Git repository**

```
git clone https://github.com/pubgeo/IARPA_SMART.git
```

- **Install Python 3.11**

```
sudo yum install python3.11
```

- **Install pip for Python 3.11**

```
sudo dnf install python3-pip
python3.11 -m ensurepip
```

- **Install Python modules for Python 3.11**
(use `--default-timeout` if needed, for downloading larger packages)

```
cd IARPA-SMART/src
python3.11 -m pip install -r requirements.txt --default-timeout=1000
```

- **Set up alias for python3.11**

```
alias python=python3.11
alias python3=python3.11
```

- **Run example script**
(run the .sh script *directly*, without using `/bin/sh`)

```
./example/example_run.sh
```

- **Check outputs**

  - Check that the script runs without errors
  - Check that the `example/output` and `example/output.compare` folders have been created and populated

## Windows 10/11 / Anaconda

- **Clone the Git repository**

```
git clone https://github.com/pubgeo/IARPA_SMART.git
```

- **Install Anaconda / Python3.11**

```
https://anaconda.org/anaconda/python/files?version=3.11.9
```

- **Install pip for python3.11**

```
conda install pip
python -m ensurepip
```

- **Install Python modules for Python 3.11**
(use `--default-timeout` if needed, for downloading larger packages)

```
cd IARPA-SMART/src
python -m pip install -r requirements.txt --default-timeout=1000
```

- **Run example script**
(run the .sh script *directly*, *without* using `/bin/sh`)

```
./example/example_run.sh
```

- **Check outputs**

  - Check that the script runs without errors
  - Check that the example/output and example/output.compare folders have been created and populated

## Troubleshooting

- **Python version mismatch**

```
./example/example_run.sh
```

If the first line upon running the example script does *not* read “Python 3.11.xx”, then either your Python alias is not set up properly to point to `python3.11`, or you may need to edit your `.sh` script.
	
- Open the file `example_run.sh` in a text editor
- Change the reference to `python` on line 39 to `python3.11`

```
python3.11 "$REPO/iarpa_smart_metrics/run_evaluation.py" \
```

- **Python PROJ setup**

If you get messages like the one below, your Python pyproj is not properly configured / cannot find its support files.

    ERROR - collection.py:__init__:243 - PROJ: proj_create_from_database: proj.db lacks DATABASE.LAYOUT.VERSION.MAJOR / DATABASE.LAYOUT.VERSION.MINOR metadata. It comes from another PROJ installation.

You may need to either re-install pyproj or hardcode a line like the one below into the beginning of your script to ensure it can find the correct proj.db.

```
export PROJ_LIB="C:\ProgramData\anaconda3\Library\share\proj"
```

