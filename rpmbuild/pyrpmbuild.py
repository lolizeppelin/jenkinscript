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
import shutil
import subprocess

TAR = '/bin/tar'
RPMBUILD = '/usr/bin/rpmbuild'
CREATEREPO = '/usr/bin/createrepo'
DEPLOYPATH = '/home/centos/goputils'
TME = '/tmp'
RELEASEVERSIONKEY = 'RELEASEVERSION'
RPMVERSIONKEY = 'RPMVERSION'
FINDERREGX = re.compile('BuildArch:\s+?([\S]+)\s|%package\s+?([\S]+)\s')

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
           'version': None,
           'release': os.environ[RELEASEVERSIONKEY],
           'dist': 'el6',
           'prefix': os.environ.get('PACKAGEPREFIX', ''),
           'packages': []}


def findvaluefromspce(buffer):
    # 从spec文件中找出arch指和其他安装包的名字
    noarch = None
    packages = []
    for f in re.findall(FINDERREGX, buffer):
        if f[0]:
            if noarch is not None:
                raise RuntimeError('BuildArch value more then one')
        if f[1]:
            packages.append(f[1])
    return noarch, packages


def get_projcet_version(project):
    # 从init文件中获取版本号
    path = os.path.join(WORKSPACE, project, '__init__.py')
    with open(path, 'rb') as f:
        buffer = f.read(4096)
    versions = re.findall("^__version__[\s]{0,}?=[\s]{0,}?\'(\S+?)\'", buffer)
    if len(versions) > 1:
        raise RuntimeError('version in file more then one')
    return versions[0]


def create_source():
    # 生成source文件
    _pwd, path = os.path.split(WORKSPACE)
    if not path:
        raise RuntimeError('package path is empty')
    project = path

    # 载入项目代码获取version
    # pwd = os.getcwd()
    # os.chdir(WORKSPACE)
    # print os.getcwd()
    # __import__(project)
    # module = sys.modules[project]
    # version = module.__version__
    # os.chdir(pwd)
    version = get_projcet_version(project)

    RPMINFO['project'] = project
    RPMINFO['version'] = version
    project_with_version = '%s-%s' % (project, version)
    print 'Project %s with version %s-%s' % (project, version, RPMINFO['release'])

    dst = os.path.join(RPMSOURCEPATH, '%s.tar.gz' % project_with_version)
    args = [TAR, '--exclude=.git', '--exclude=.gitignore', '--exclude=.svn', '-zcf', dst, '-C']
    args.append(_pwd)
    args.append(path)
    # 压缩时替换文件夹名称,带上版本号
    args.append('--transform=s/^%s/%s/' % (project, project_with_version))
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
    arch, packages = findvaluefromspce(specbuffer)
    if arch and arch != RPMINFO['arch']:
        RPMINFO['arch'] = arch
    RPMINFO['packages'].extend(packages)
    # 替换spec文件中的version和release
    replacemap = {RELEASEVERSIONKEY: RPMINFO['release'], RPMVERSIONKEY: RPMINFO['version']}
    regex = re.compile("(%s)" % "|".join(map(re.escape, replacemap.keys())))
    specbuffer = regex.sub(lambda mo: replacemap[mo.string[mo.start():mo.end()]],
                           specbuffer)
    # 生成spec文件
    with open(dst, 'wb') as f:
        f.write(specbuffer)
    print 'create spec %s success' % dst
    return dst


def build_rpm(specfile):
    # 执行rpmbuild
    args = [RPMBUILD, '--quiet', '-bb']
    args.append(specfile)
    sub = subprocess.Popen(executable=RPMBUILD, args=args, stderr=subprocess.PIPE)
    if sub.wait() != 0:
        print sub.stderr.read()
        raise RuntimeError('Call rpmbuild fail')
    print 'call rpm build success'


def checker_deploy():
    # 检查生成的rpm包
    prefix = RPMINFO['prefix']
    project = RPMINFO['project']
    version = RPMINFO['version']
    release = RPMINFO['release']
    dist = RPMINFO['dist']
    packages = RPMINFO['packages']
    arch = RPMINFO['arch']
    PREFIX = '%s%s' % (prefix, project)
    package_list = []
    project_package_name = '%s-%s-%s.%s.%s.rpm' % (PREFIX, version, release, dist, arch)
    package_list.append(os.path.join(RPMSPATH, arch, project_package_name))
    # 扩展rpm包
    for package in packages:
        package_name = '%s-%s-%s-%s.%s.%s.rpm' % (PREFIX, package, version, release, dist, arch)
        path = os.path.join(RPMSPATH, arch, package_name)
        package_list.append(path)
    # 检查所有rpm包
    for path in package_list:
        if os.path.exists(path):
            print 'build package: %s' % path
        else:
            raise ValueError('%s not found' % path)
    for _file in os.listdir(DEPLOYPATH):
        if _file.startswith(PREFIX):
            os.remove(os.path.join(DEPLOYPATH, _file))
    # 移动到rpm源目录
    for path in package_list:
        shutil.move(path, DEPLOYPATH)

    # RPM源更新

    args = [CREATEREPO, '--update', os.path.split(DEPLOYPATH)[0]]
    sub = subprocess.Popen(executable=CREATEREPO, args=args, stderr=subprocess.PIPE)
    if sub.wait() != 0:
        print sub.stderr.read()
        raise RuntimeError('exec %s fail' % CREATEREPO)
    print 'deploy success'


def main():
    create_source()
    specfile = create_spec()
    build_rpm(specfile)
    checker_deploy()


if __name__ == '__main__':
    main()
