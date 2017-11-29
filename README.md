这个脚本用于jenkin构建后打包rpm

构建的WORKSPACE必须是project-version形式,方便压缩

rpm的spec文件的release使用RELEASEVERSION字符串替换

如下示例

    %define _release RELEASEVERSION
    Release:        %{_release}%{?dist}