#!/usr/bin/python
# -*- coding:utf-8 -*-
"""
这个脚本用于jenkin构建后打包rpm
构建的WORKSPACE必须是project-version形式
方便压缩
rpm的spec文件的release使用RELEASEVERSION字符串替换
如下示例

%define _release RELEASEVERSION
Release:        %{_release}%{?dist}
"""
import os
import re
import sys
import functools
import subprocess

TAR = '/bin/tar'
RPMBUILD = '/usr/bin/rpmbuild'
RELEASEVERSIONKEY = 'RELEASEVERSION'
ARCHFINDER = functools.partial(re.findall, re.compile('BuildArch:\s+?([\S]+)\s'))
PACKAGEFINDER = functools.partial(re.findall, re.compile('%package\s+?([\S]+)\s'))

HOME = os.environ['HOME']
WORKSPACE = os.environ['WORKSPACE']

if HOME.endswith('/'):
    HOME = HOME[:-1]
if WORKSPACE.endswith('/'):
    WORKSPACE = WORKSPACE[:-1]

if WORKSPACE == '/' or HOME == '/':
    raise RuntimeError('WORKSPACE or HOME is root path')

RPMSOURCEPATH = os.path.join(HOME, 'rpmbuild', 'SOURCES')
RPMSPECPATH = os.path.join(HOME, 'rpmbuild', 'SPECS')
RPMSPATH = os.path.join(HOME, 'rpmbuild', 'RPMS')


RPMINFO = {'arch': 'noarch',
           'project': None,
           'verion': None,
           'release': os.environ[RELEASEVERSIONKEY],
           'dist': 'el6',
           'packages': []}


def archfinder(buffer):
    # 找Arch
    return ARCHFINDER(buffer)[0]


def packagesfinder(buffer):
    # 派生生成的包
    return PACKAGEFINDER(buffer)


def create_source():
    # 生成source文件
    _pwd, path = os.path.split(WORKSPACE)
    if not path:
        raise RuntimeError('package path is empty')
    project, verion = path.split('-')
    RPMINFO['project'] = project
    RPMINFO['verion'] = verion
    print 'Project %s with version %s-%s' % (project, verion, RPMINFO['release'])
    dst = os.path.join(RPMSOURCEPATH, '%s.tar.gz' % path)
    args = [TAR, '--exclude=.git', '--exclude=.gitignore', '--exclude=.svn', '-zcf', dst, '-C']
    args.append(_pwd)
    args.append(path)
    sub = subprocess.Popen(executable=TAR, args=args, stderr=subprocess.PIPE)
    if sub.wait() != 0:
        print sub.stderr.read()
        raise RuntimeError('Build source file fail')
    print 'create source %s success' % dst


def create_spec():
    # 生成spce文件
    specfile = '%s.spec' % sys.argv[1]
    src = os.path.join(WORKSPACE, specfile)
    if not os.path.exists(src):
        raise RuntimeError('spec file not exist')
    dst = os.path.join(RPMSPECPATH, specfile)
    with open(specfile, 'rb') as f:
        specbuffer = f.read()
    arch = archfinder(specbuffer)
    if arch != RPMINFO['arch']:
        RPMINFO['arch'] = arch
    RPMINFO['packages'].extend(packagesfinder(specbuffer))
    specbuffer = specbuffer.replace(RELEASEVERSIONKEY, RPMINFO['release'])
    with open(dst, 'wb') as f:
        f.write(specbuffer)
    print 'create spec %s success' % dst
    return dst


def build_rpm(specfile):
    # 执行rpmbuild
    args = [RPMBUILD, '--quiet', '-bb']
    args.append(specfile)
    sub = subprocess.Popen(executable=RPMBUILD, args=args)
    if sub.wait() != 0:
        raise RuntimeError('Call rpmbuild fail')
    print 'call rpm build success'


def checker():
    # 检查生成的rpm包
    project = RPMINFO['project']
    verion = RPMINFO['verion']
    release = RPMINFO['release']
    dist = RPMINFO['dist']
    packages = RPMINFO['packages']
    arch = RPMINFO['arch']
    package_list = []
    project_package_name = 'python-%s-%s-%s%s.rpm' % (project, verion, release, dist)
    package_list.append(os.path.join(RPMSPATH, arch, project_package_name))
    for package in packages:
        package_name = 'python-%s-%s-%s-%s%s.rpm' % (project, package, verion, release, dist)
        path = os.path.join(RPMSPATH, arch, package_name)
        package_list.append(path)
    for path in package_list:
        if os.path.exists(path):
            print 'build package: %s' % path


def main():
    create_source()
    specfile = create_spec()
    build_rpm(specfile)
    checker()


if __name__ == '__main__':
    main()
