Get the source and install the requirements:

```shell
$ git clone https://github.com/seird/ntfy-tray.git
$ cd ntfy-tray
$ pip install -r requirements.txt
$ pip install pyinstaller
```

Currently it's only possible to create installer packages from the pyinstaller output. For any target platform, first create the executable with pyinstaller:

```shell
$ pyinstaller ntfy-tray.spec
```


# Windows

## Create an installer with Inno Setup

Create an installer for windows with [inno setup](https://github.com/jrsoftware/issrc) from pyinstaller output:

```shell
$ iscc ntfy-tray.iss
```

The installer is created at `inno-output/ntfy-tray-installer.exe`.


# Linux

Packages can be created from the pyinstaller output with [fpm](https://fpm.readthedocs.io/). Run the `build_linux.sh` script with the desired package type:

## Create a deb package


```shell
$ ./build_linux.sh deb
```


## Create a pacman package


```shell
$ ./build_linux.sh pacman
```


# MacOS

## Create a macos .app

```shell
$ pip install pyinstaller Pillow
$ pyinstaller ntfy-tray.spec
```

# Create and install a pip package

- Create the pip package:
    ```shell
    $ python -m build
    ```

- Install the pip package:
    ```shell
    $ pip install dist/ntfy_tray-{{VERSION}}-py3-none-any.whl
    ```

- Launch from the command line:
    ```shell
    $ ntfy-tray
    ```
