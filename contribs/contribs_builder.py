#!/usr/bin/env python3

import os
import sys
import platform

if sys.version_info < (3, 0):
    print("This script NEEDS Python 3. Run it with 'python3 contribs.py'")
    sys.exit()

if os.path.basename(os.getcwd()) != "contribs":
    print("This script MUST be run from the contribs/ directory")
    sys.exit()

if platform.system() != "Windows":
    if os.getuid() == 0:
        print("This script SHOULD NOT be run as root")
        sys.exit()

import re
import glob
import shutil
import zipfile
import tarfile
import argparse
import subprocess
import multiprocessing
import urllib.request

## WELCOME #####################################################################

print("")
print("> Theengs contribs builder script")
print("> Make sure you consult ./contribs_builder.py --help")
print("")

targets = ['linux', 'macos', 'macos_x86_64', 'macos_arm64', 'msvc2019', 'msvc2022',
           'android_armv8', 'android_armv7', 'android_x86_64', 'android_x86',
           'ios', 'ios_simulator', 'ios_armv7', 'ios_armv8']

softwares = ['qtmqtt', 'qtconnectivity']

print("> targets available:")
print(str(targets))
print("")
print("> softwares available:")
print(str(softwares))

## DEPENDENCIES ################################################################
# These software dependencies are needed for this script to run!

## linux:
# python3 cmake ninja libtool automake m4

## macOS:
# brew install python cmake automake ninja
# brew install libtool pkg-config
# xcode (13+)

## Windows:
# python3 (https://www.python.org/downloads/)
# cmake (https://cmake.org/download/)
# MSVC (2019+)

## HOST ########################################################################

# Supported platforms / architectures:

# Natives:
# - Linux
# - macOS
# - Windows
# Cross compilation (from Linux):
# - Windows (mingw32-w64)
# Cross compilation (from Linux or macOS):
# - Android (armv7, armv8, x86, x86_64)
# Cross compilation (from macOS):
# - iOS (simulator, armv7, armv8)

OS_HOST = platform.system()
ARCH_HOST = platform.machine()
CPU_COUNT = multiprocessing.cpu_count()

print("")
print("HOST SYSTEM : " + platform.system() + " (" + platform.release() + ") [" + os.name + "]")
print("HOST ARCH   : " + ARCH_HOST)
print("HOST CPUs   : " + str(CPU_COUNT) + " cores")
print("")

## UTILS #######################################################################

def copytree(src, dst, symlinks=False, ignore=None):
    if not os.path.exists(dst):
        os.makedirs(dst)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            copytree(s, d, symlinks, ignore)
        else:
            if not os.path.exists(d) or os.stat(s).st_mtime - os.stat(d).st_mtime > 1:
                shutil.copy2(s, d)

def copytree_wildcard(src, dst, symlinks=False, ignore=None):
    if not os.path.exists(dst):
        os.makedirs(dst)
    for item in glob.glob(src):
        shutil.copy2(item, dst)

## SETTINGS ####################################################################

contribs_dir = os.getcwd()
src_dir = contribs_dir + "/src/"
deploy_dir = contribs_dir + "/deploy/"

clean = False
rebuild = False
targets_selected = []
softwares_selected = []
QT_VERSION = "6.6.3"
QT_DIRECTORY = os.getenv('QT_DIRECTORY', '')
ANDROID_SDK_ROOT = os.getenv('ANDROID_SDK_ROOT', '')
ANDROID_NDK_ROOT = os.getenv('ANDROID_NDK_ROOT', '')
MSVC_GEN_VER = ""

## ARGUMENTS ###################################################################

parser = argparse.ArgumentParser(prog='contribs.py',
                                 description='',
                                 formatter_class=argparse.RawTextHelpFormatter)

parser.add_argument('-c', '--clean', help="clean everything and exit (downloaded files and all temporary directories)", action='store_true')
parser.add_argument('-r', '--rebuild', help="rebuild the contribs even if already built", action='store_true')
parser.add_argument('--targets', dest='targets', help="specify target(s) platforms")
parser.add_argument('--softwares', dest='softwares', help="specify software(s) to build")
parser.add_argument('--qt-version', dest='qtversion', help="specify a Qt version to use")
parser.add_argument('--qt-directory', dest='qtdirectory', help="specify a custom path to the Qt install root dir (if QT_DIRECTORY environment variable isn't set)")
parser.add_argument('--android-sdk', dest='androidsdk', help="specify a custom path to the android-sdk (if ANDROID_SDK_ROOT environment variable isn't set)")
parser.add_argument('--android-ndk', dest='androidndk', help="specify a custom path to the android-ndk (if ANDROID_NDK_ROOT environment variable isn't set)")

if len(sys.argv) > 1:
    result = parser.parse_args()
    if result.clean:
        clean = result.clean
    if result.rebuild:
        rebuild = result.rebuild
    if result.targets:
        targets_selected = result.targets.split(',')
    if result.softwares:
        softwares_selected = result.softwares.split(',')
    if result.qtversion:
        QT_VERSION = result.qtversion
    if result.qtdirectory:
        QT_DIRECTORY = result.qtdirectory
    if result.androidsdk:
        ANDROID_SDK_ROOT = result.androidsdk
    if result.androidndk:
        ANDROID_NDK_ROOT = result.androidndk

if len(softwares_selected) == 0:
    softwares_selected = softwares

## CLEAN #######################################################################

if rebuild:
    if os.path.exists(contribs_dir + "/build/"):
        shutil.rmtree(contribs_dir + "/build/")

if clean:
    if os.path.exists(contribs_dir + "/src/"):
        shutil.rmtree(contribs_dir + "/src/")
    if os.path.exists(contribs_dir + "/build/"):
        shutil.rmtree(contribs_dir + "/build/")
    if os.path.exists(contribs_dir + "/env/"):
        shutil.rmtree(contribs_dir + "/env/")
    print(">> Contribs cleaned!")
    sys.exit()

if not os.path.exists(src_dir):
    os.makedirs(src_dir)
if not os.path.exists(deploy_dir):
    os.makedirs(deploy_dir)

## TARGETS #####################################################################

TARGETS = [] # 1: OS_TARGET # 2: ARCH_TARGET # 3: QT_TARGET

# > using script arguments
if len(targets_selected):
    print("TARGETS from script arguments")

    if "linux" in targets_selected: TARGETS.append(["linux", "x86_64", "gcc_64"])
    if "macos" in targets_selected: TARGETS.append(["macOS", "unified", "macOS"])
    if "macos_x86_64" in targets_selected: TARGETS.append(["macOS", "x86_64", "macOS"])
    if "macos_arm64" in targets_selected: TARGETS.append(["macOS", "arm64", "macOS"])
    if "msvc2019" in targets_selected:
        MSVC_GEN_VER = "Visual Studio 16 2019"
        TARGETS.append(["windows", "x86_64", "msvc2019_64"])
    if "msvc2022" in targets_selected:
        MSVC_GEN_VER = "Visual Studio 17 2022"
        TARGETS.append(["windows", "x86_64", "msvc2019_64"])

    if "android_armv8" in targets_selected: TARGETS.append(["android", "armv8", "android_arm64_v8a"])
    if "android_armv7" in targets_selected: TARGETS.append(["android", "armv7", "android_armv7"])
    if "android_x86_64" in targets_selected: TARGETS.append(["android", "x86_64", "android_x86_64"])
    if "android_x86" in targets_selected: TARGETS.append(["android", "x86", "android_x86"])
    if "ios" in targets_selected: TARGETS.append(["iOS", "unified", "iOS"])
    if "ios_simulator" in targets_selected: TARGETS.append(["iOS", "simulator", "iOS"])
    if "ios_armv7" in targets_selected: TARGETS.append(["iOS", "armv7", "iOS"])
    if "ios_armv8" in targets_selected: TARGETS.append(["iOS", "armv8", "iOS"])

# > using auto-selection
if len(TARGETS) == 0:
    print("TARGETS auto-selection")

    if OS_HOST == "Linux":
        TARGETS.append(["linux", "x86_64", "gcc_64"])
        #TARGETS.append(["windows", "x86_64", ""]) # Windows cross compilation

    if OS_HOST == "Darwin":
        TARGETS.append(["macOS", "unified", "macOS"])
        TARGETS.append(["iOS", "unified", "iOS"])

    if OS_HOST == "Windows":
        if "17.0" in os.getenv('VisualStudioVersion', ''):
            MSVC_GEN_VER = "Visual Studio 17 2022"
            TARGETS.append(["windows", "x86_64", "msvc2019_64"])
        else: # if "16.0" in os.getenv('VisualStudioVersion', ''):
            MSVC_GEN_VER = "Visual Studio 16 2019"
            TARGETS.append(["windows", "x86_64", "msvc2019_64"])

    if ANDROID_NDK_ROOT: # Android cross compilation
        TARGETS.append(["android", "armv8", "android_arm64_v8a"])
        TARGETS.append(["android", "armv7", "android_armv7"])
        TARGETS.append(["android", "x86_64", "android_x86_64"])
        TARGETS.append(["android", "x86", "android_x86"])

## RECAP #######################################################################

# > targets recap:
print("TARGETS selected:\n" + str(TARGETS) + "\n")

# > softwares recap:
print("SOFTWARES selected:\n" + str(softwares_selected) + "\n")

## DOWNLOAD TOOLS ##############################################################

## Android OpenSSL (version: git)
for TARGET in TARGETS:
    if TARGET[0] == "android":
        FILE_androidopenssl = "android_openssl-master.zip"
        DIR_androidopenssl = "android_openssl"

        if not os.path.exists(src_dir + FILE_androidopenssl):
            print("> Downloading " + FILE_androidopenssl + "...")
            urllib.request.urlretrieve("https://github.com/KDAB/android_openssl/archive/master.zip", src_dir + FILE_androidopenssl)
        if not os.path.isdir("env/" + DIR_androidopenssl):
            zipSSL = zipfile.ZipFile(src_dir + FILE_androidopenssl)
            zipSSL.extractall("env/")

## linuxdeploy (version: git)
for TARGET in TARGETS:
    if TARGET[0] == "linux":
        FILE_linuxdeploy = "linuxdeploy-x86_64.AppImage"
        if not os.path.exists(deploy_dir + FILE_linuxdeploy):
            print("> Downloading " + FILE_linuxdeploy + "...")
            urllib.request.urlretrieve("https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/" + FILE_linuxdeploy, deploy_dir + FILE_linuxdeploy)
            urllib.request.urlretrieve("https://github.com/linuxdeploy/linuxdeploy-plugin-appimage/releases/download/continuous/linuxdeploy-plugin-appimage-x86_64.AppImage", deploy_dir + "linuxdeploy-plugin-appimage-x86_64.AppImage")
            urllib.request.urlretrieve("https://github.com/linuxdeploy/linuxdeploy-plugin-qt/releases/download/continuous/linuxdeploy-plugin-qt-x86_64.AppImage", deploy_dir + "linuxdeploy-plugin-qt-x86_64.AppImage")

## DOWNLOAD SOFTWARES ##########################################################

## QtMqtt (version: QT_VERSION)
FILE_qtmqtt = "qtmqtt-" + QT_VERSION + ".zip"
DIR_qtmqtt = "qtmqtt-" + QT_VERSION

if "qtmqtt" in softwares_selected:
    if not os.path.exists(src_dir + FILE_qtmqtt):
        print("> Downloading " + FILE_qtmqtt + "...")
        urllib.request.urlretrieve("https://github.com/qt/qtmqtt/archive/refs/tags/v" + QT_VERSION + ".zip", src_dir + FILE_qtmqtt)

## Android QtConnectivity (version: QT_VERSION custom)
for TARGET in TARGETS:
    if TARGET[0] == "android":
        FILE_qtconnectivity = "qtconnectivity-blescanfiltering_v1_" + QT_VERSION.replace('.', '') + ".zip"
        DIR_qtconnectivity = "qtconnectivity-blescanfiltering_v1_" + QT_VERSION.replace('.', '')

        if "qtconnectivity" in softwares_selected:
            if not os.path.exists(src_dir + FILE_qtconnectivity):
                print("> Downloading " + FILE_qtconnectivity + "...")
                urllib.request.urlretrieve("https://github.com/emericg/qtconnectivity/archive/refs/heads/blescanfiltering_v1_" + QT_VERSION.replace('.','') + ".zip", src_dir + FILE_qtconnectivity)

## BUILD SOFTWARES #############################################################

for TARGET in TARGETS:

    ## PREPARE environment
    OS_TARGET = TARGET[0]
    ARCH_TARGET = TARGET[1]
    QT_TARGET = TARGET[2]

    build_dir = contribs_dir + "/build/" + OS_TARGET + "_" + ARCH_TARGET + "/"
    env_dir = contribs_dir + "/env/" + OS_TARGET + "_" + ARCH_TARGET + "/"
    qt6_dir = QT_DIRECTORY + "/" + QT_VERSION + "/" + QT_TARGET + "/bin/"

    try:
        os.makedirs(build_dir)
        os.makedirs(env_dir)
    except:
        print() # who cares

    print("> TARGET : " + str(TARGET))
    print("- build_dir : " + build_dir)
    print("- env_dir : " + env_dir)
    print("- qt6_dir : " + qt6_dir)

    ## PREPARE Qt module build
    if OS_HOST == "Windows":
        QT_CONF_MODULE_cmd = qt6_dir + "qt-configure-module.bat"
        #VCVARS_cmd = "C:/Program Files (x86)/Microsoft Visual Studio/2019/Community/VC/Auxiliary/Build/" + "vcvarsall.bat"
        #subprocess.check_call([VCVARS_cmd, "x86_amd64"], cwd="C:/Program Files (x86)/Microsoft Visual Studio/2019/Community/VC/Auxiliary/Build/")
    else:
        QT_CONF_MODULE_cmd = qt6_dir + "qt-configure-module"
        if OS_TARGET == "android" or OS_TARGET == "iOS":
            # HACK # GitHub CI + aqt + Qt cross compilation
            if (OS_HOST == "Linux"): os.environ["QT_HOST_PATH"] = str(QT_DIRECTORY + "/" + QT_VERSION + "/gcc_64/")
            if (OS_HOST == "Darwin"): os.environ["QT_HOST_PATH"] = str(QT_DIRECTORY + "/" + QT_VERSION + "/macOS/")

    ## CMAKE command selection
    CMAKE_cmd = ["cmake"]
    CMAKE_gen = "Ninja"
    build_shared = "ON"
    build_static = "OFF"

    if OS_HOST == "Linux":
        if OS_TARGET == "windows":
            if ARCH_TARGET == "i686":
                CMAKE_cmd = ["i686-w64-mingw32-cmake"]
            else:
                CMAKE_cmd = ["x86_64-w64-mingw32-cmake"]

    if OS_HOST == "Darwin":
        if OS_TARGET == "macOS":
            if ARCH_TARGET == "unified":
                CMAKE_cmd = ["cmake", "-DCMAKE_OSX_ARCHITECTURE=x86_64;arm64"]
            elif ARCH_TARGET == "x86_64":
                CMAKE_cmd = ["cmake", "-DCMAKE_OSX_ARCHITECTURE=x86_64"]
            elif ARCH_TARGET == "arm64":
                CMAKE_cmd = ["cmake", "-DCMAKE_OSX_ARCHITECTURE=arm64"]
        if OS_TARGET == "iOS":
            CMAKE_gen = "Xcode"
            #IOS_DEPLOYMENT_TARGET="13.0"
            build_shared = "OFF"
            build_static = "ON"
            if ARCH_TARGET == "unified":
                CMAKE_cmd = ["cmake", "-DCMAKE_TOOLCHAIN_FILE=" + contribs_dir + "/tools/ios.toolchain.cmake", "-DPLATFORM=OS64COMBINED"]
            elif ARCH_TARGET == "simulator":
                CMAKE_cmd = ["cmake", "-DCMAKE_TOOLCHAIN_FILE=" + contribs_dir + "/tools/ios.toolchain.cmake", "-DPLATFORM=SIMULATOR64"]
            elif ARCH_TARGET == "armv7":
                CMAKE_cmd = ["cmake", "-DCMAKE_TOOLCHAIN_FILE=" + contribs_dir + "/tools/ios.toolchain.cmake", "-DPLATFORM=OS"]
            elif ARCH_TARGET == "armv8":
                CMAKE_cmd = ["cmake", "-DCMAKE_TOOLCHAIN_FILE=" + contribs_dir + "/tools/ios.toolchain.cmake", "-DPLATFORM=OS64"]
            else:
                # Without custom toolchain?
                CMAKE_cmd = ["cmake", "-DCMAKE_SYSTEM_NAME=iOS", "-DCMAKE_OSX_DEPLOYMENT_TARGET=11.0"]

    if OS_HOST == "Windows":
        CMAKE_gen = MSVC_GEN_VER
        if ARCH_TARGET == "armv7":
            CMAKE_cmd = ["cmake", "-A", "ARM"]
        elif ARCH_TARGET == "armv8":
            CMAKE_cmd = ["cmake", "-A", "ARM64"]
        elif ARCH_TARGET == "x86":
            CMAKE_cmd = ["cmake", "-A", "Win32"]
        else: # ARCH_TARGET == "x86_64":
            CMAKE_cmd = ["cmake", "-A", "x64"]

    if OS_TARGET == "android":
        if ARCH_TARGET == "x86":
            CMAKE_cmd = ["cmake", "-DCMAKE_TOOLCHAIN_FILE=" + ANDROID_NDK_ROOT + "/build/cmake/android.toolchain.cmake", "-DANDROID_ABI=x86", "-DANDROID_PLATFORM=android-23"]
        elif ARCH_TARGET == "x86_64":
            CMAKE_cmd = ["cmake", "-DCMAKE_TOOLCHAIN_FILE=" + ANDROID_NDK_ROOT + "/build/cmake/android.toolchain.cmake", "-DANDROID_ABI=x86_64", "-DANDROID_PLATFORM=android-23"]
        elif ARCH_TARGET == "armv7":
            CMAKE_cmd = ["cmake", "-DCMAKE_TOOLCHAIN_FILE=" + ANDROID_NDK_ROOT + "/build/cmake/android.toolchain.cmake", "-DANDROID_ABI=armeabi-v7a", "-DANDROID_PLATFORM=android-23"]
        else: # ARCH_TARGET == "armv8":
            CMAKE_cmd = ["cmake", "-DCMAKE_TOOLCHAIN_FILE=" + ANDROID_NDK_ROOT + "/build/cmake/android.toolchain.cmake", "-DANDROID_ABI=arm64-v8a", "-DANDROID_PLATFORM=android-23"]

    #### EXTRACT, BUILD & INSTALL ####

    ## QtMqtt
    if "qtmqtt" in softwares_selected:
        if not os.path.isdir(build_dir + DIR_qtmqtt):
            zipQtM = zipfile.ZipFile(src_dir + FILE_qtmqtt)
            zipQtM.extractall(build_dir)

        try: os.makedirs(build_dir + DIR_qtmqtt + "/build")
        except: print() # who cares

        print("> Building QtMqtt")
        subprocess.check_call([QT_CONF_MODULE_cmd, ".."], cwd=build_dir + DIR_qtmqtt + "/build")
        subprocess.check_call(["cmake", "--build", ".", "--target", "all"], cwd=build_dir + DIR_qtmqtt + "/build")
        #subprocess.check_call(["cmake", "--install", "."], cwd=build_dir + DIR_qtmqtt + "/build")
        subprocess.check_call(["ninja", "install"], cwd=build_dir + DIR_qtmqtt + "/build") # Qt bug 91647

    ## QtConnectivity (patched)
    if "qtconnectivity" in softwares_selected:
        if OS_TARGET == "android":
            if not os.path.isdir(build_dir + DIR_qtconnectivity):
                zipQtC = zipfile.ZipFile(src_dir + FILE_qtconnectivity)
                zipQtC.extractall(build_dir)

            try: os.makedirs(build_dir + DIR_qtconnectivity + "/build")
            except: print() # who cares

            print("> Building QtConnectivity")
            subprocess.check_call([QT_CONF_MODULE_cmd, ".."], cwd=build_dir + DIR_qtconnectivity + "/build")
            subprocess.check_call(["cmake", "--build", ".", "--target", "all"], cwd=build_dir + DIR_qtconnectivity + "/build")
            #subprocess.check_call(["cmake", "--install", "."], cwd=build_dir + DIR_qtconnectivity + "/build")
            subprocess.check_call(["ninja", "install"], cwd=build_dir + DIR_qtconnectivity + "/build") # Qt bug 91647
