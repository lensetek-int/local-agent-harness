di webgui tidak bisa cancle proses "Sedang berpikir... (Langkah 3/8) [Tekan Ctrl+C untuk membatalkan]"
biasanya tombol submit nya jadi tombol cancel kan ya

[1/5] Using Python: Python 3.14.5
[2/5] Updating existing installation in C:\Users\ACER\.lensetek-agent...
error: Your local changes to the following files would be overwritten by merge:
        cli-agent/agent.py
        cli-agent/i18n.py
        cli-agent/main.py
        cli-agent/plugin_manager.py
        cli-agent/tools_fs.py
        cli-agent/user_settings.json
        cli-agent/version.json
        cli-agent/version.py
        plugins/manifest.json
        plugins/webui/__init__.py
        plugins/webui/plugin.json
        plugins/webui/server.py
        plugins/webui/static/index.html
Please commit your changes or stash them before you merge.
Aborting

remove juga error
PS C:\Users\ACER\Documents\GitHub\Latihan-riset\COBA 2> Remove-Item -Recurse -Force "$HOME\.lensetek-agent"
Remove-Item : Cannot remove item C:\Users\ACER\.lensetek-agent\bin\ggml-base.dll: Access to the path 'ggml-base.dll'
is denied.
At line:1 char:1
+ Remove-Item -Recurse -Force "$HOME\.lensetek-agent"
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (ggml-base.dll:FileInfo) [Remove-Item], UnauthorizedAccessException
    + FullyQualifiedErrorId : RemoveFileSystemItemUnAuthorizedAccess,Microsoft.PowerShell.Commands.RemoveItemCommand
Remove-Item : Cannot remove item C:\Users\ACER\.lensetek-agent\bin\ggml-cpu-haswell.dll: Access to the path
'ggml-cpu-haswell.dll' is denied.
At line:1 char:1
+ Remove-Item -Recurse -Force "$HOME\.lensetek-agent"
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (ggml-cpu-haswell.dll:FileInfo) [Remove-Item], UnauthorizedAccessExcep
   tion
    + FullyQualifiedErrorId : RemoveFileSystemItemUnAuthorizedAccess,Microsoft.PowerShell.Commands.RemoveItemCommand
Remove-Item : Cannot remove item C:\Users\ACER\.lensetek-agent\bin\ggml-rpc.dll: Access to the path 'ggml-rpc.dll' is
denied.
At line:1 char:1
+ Remove-Item -Recurse -Force "$HOME\.lensetek-agent"
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (ggml-rpc.dll:FileInfo) [Remove-Item], UnauthorizedAccessException
    + FullyQualifiedErrorId : RemoveFileSystemItemUnAuthorizedAccess,Microsoft.PowerShell.Commands.RemoveItemCommand
Remove-Item : Cannot remove item C:\Users\ACER\.lensetek-agent\bin\ggml.dll: Access to the path 'ggml.dll' is denied.
At line:1 char:1
+ Remove-Item -Recurse -Force "$HOME\.lensetek-agent"
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (ggml.dll:FileInfo) [Remove-Item], UnauthorizedAccessException
    + FullyQualifiedErrorId : RemoveFileSystemItemUnAuthorizedAccess,Microsoft.PowerShell.Commands.RemoveItemCommand
Remove-Item : Cannot remove item C:\Users\ACER\.lensetek-agent\bin\libomp.dll: Access to the path 'libomp.dll' is
denied.
At line:1 char:1
+ Remove-Item -Recurse -Force "$HOME\.lensetek-agent"
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (libomp.dll:FileInfo) [Remove-Item], UnauthorizedAccessException
    + FullyQualifiedErrorId : RemoveFileSystemItemUnAuthorizedAccess,Microsoft.PowerShell.Commands.RemoveItemCommand
Remove-Item : Cannot remove item C:\Users\ACER\.lensetek-agent\bin\llama-common.dll: Access to the path
'llama-common.dll' is denied.
At line:1 char:1
+ Remove-Item -Recurse -Force "$HOME\.lensetek-agent"
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (llama-common.dll:FileInfo) [Remove-Item], UnauthorizedAccessException
    + FullyQualifiedErrorId : RemoveFileSystemItemUnAuthorizedAccess,Microsoft.PowerShell.Commands.RemoveItemCommand
Remove-Item : Cannot remove item C:\Users\ACER\.lensetek-agent\bin\llama-server-impl.dll: Access to the path
'llama-server-impl.dll' is denied.
At line:1 char:1
+ Remove-Item -Recurse -Force "$HOME\.lensetek-agent"
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (llama-server-impl.dll:FileInfo) [Remove-Item], UnauthorizedAccessExce
   ption
    + FullyQualifiedErrorId : RemoveFileSystemItemUnAuthorizedAccess,Microsoft.PowerShell.Commands.RemoveItemCommand
Remove-Item : Cannot remove item C:\Users\ACER\.lensetek-agent\bin\llama-server.exe: Access to the path
'llama-server.exe' is denied.
At line:1 char:1
+ Remove-Item -Recurse -Force "$HOME\.lensetek-agent"
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (llama-server.exe:FileInfo) [Remove-Item], UnauthorizedAccessException
    + FullyQualifiedErrorId : RemoveFileSystemItemUnAuthorizedAccess,Microsoft.PowerShell.Commands.RemoveItemCommand
Remove-Item : Cannot remove item C:\Users\ACER\.lensetek-agent\bin\llama.dll: Access to the path 'llama.dll' is denied.
At line:1 char:1
+ Remove-Item -Recurse -Force "$HOME\.lensetek-agent"
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (llama.dll:FileInfo) [Remove-Item], UnauthorizedAccessException
    + FullyQualifiedErrorId : RemoveFileSystemItemUnAuthorizedAccess,Microsoft.PowerShell.Commands.RemoveItemCommand
Remove-Item : Cannot remove item C:\Users\ACER\.lensetek-agent\bin\mtmd.dll: Access to the path 'mtmd.dll' is denied.
At line:1 char:1
+ Remove-Item -Recurse -Force "$HOME\.lensetek-agent"
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (mtmd.dll:FileInfo) [Remove-Item], UnauthorizedAccessException
    + FullyQualifiedErrorId : RemoveFileSystemItemUnAuthorizedAccess,Microsoft.PowerShell.Commands.RemoveItemCommand
Remove-Item : Cannot remove item C:\Users\ACER\.lensetek-agent\bin: The directory is not empty.
At line:1 char:1
+ Remove-Item -Recurse -Force "$HOME\.lensetek-agent"
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : WriteError: (bin:DirectoryInfo) [Remove-Item], IOException
    + FullyQualifiedErrorId : RemoveFileSystemItemIOError,Microsoft.PowerShell.Commands.RemoveItemCommand
Remove-Item : Cannot remove item C:\Users\ACER\.lensetek-agent: The directory is not empty.
At line:1 char:1
+ Remove-Item -Recurse -Force "$HOME\.lensetek-agent"
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : WriteError: (C:\Users\ACER\.lensetek-agent:DirectoryInfo) [Remove-Item], IOException
    + FullyQualifiedErrorId : RemoveFileSystemItemIOError,Microsoft.PowerShell.Commands.RemoveItemCommand

setelah uninstall error lalu install lagi malah tidak bisa panggil
PS C:\Users\ACER\Documents\GitHub\Latihan-riset\COBA 2> lensetek --gui
C:\Users\ACER\AppData\Local\Python\pythoncore-3.14-64\python.exe: can't open file 'C:\\Users\\ACER\\.lensetek-agent\\cli-agent\\main.py': [Errno 2] No such file or directory
PS C:\Users\ACER\Documents\GitHub\Latihan-riset\COBA 2> lensetek
C:\Users\ACER\AppData\Local\Python\pythoncore-3.14-64\python.exe: can't open file 'C:\\Users\\ACER\\.lensetek-agent\\cli-agent\\main.py': [Errno 2] No such file or directory