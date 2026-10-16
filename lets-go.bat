@echo off
rem lets-go 命令入口：把本文件所在目录加入 PATH 后即可直接使用 lets-go 命令
rem 例如：set PATH=D:\ProjectCode\lets-go;%PATH%
python "%~dp0cli.py" %*
