"""Verify the actual Windows PE icon resources, without executing the file."""
import ctypes, json, struct, sys
from ctypes import wintypes
from pathlib import Path

k=ctypes.WinDLL('kernel32',use_last_error=True)
k.LoadLibraryExW.argtypes=[wintypes.LPCWSTR,wintypes.HANDLE,wintypes.DWORD]
k.LoadLibraryExW.restype=wintypes.HMODULE
k.FindResourceW.argtypes=[wintypes.HMODULE,ctypes.c_void_p,ctypes.c_void_p]
k.FindResourceW.restype=ctypes.c_void_p
k.LoadResource.argtypes=[wintypes.HMODULE,ctypes.c_void_p];k.LoadResource.restype=ctypes.c_void_p
k.LockResource.argtypes=[ctypes.c_void_p];k.LockResource.restype=ctypes.c_void_p
k.SizeofResource.argtypes=[wintypes.HMODULE,ctypes.c_void_p];k.SizeofResource.restype=wintypes.DWORD
k.FreeLibrary.argtypes=[wintypes.HMODULE]
Callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HMODULE,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ssize_t)
k.EnumResourceNamesW.argtypes=[wintypes.HMODULE,ctypes.c_void_p,Callback,ctypes.c_ssize_t]

def inspect(path):
    module=k.LoadLibraryExW(str(path.resolve()),None,0x2|0x20)
    assert module,ctypes.get_last_error()
    groups=[]
    @Callback
    def visit(handle,kind,name,unused):
        res=k.FindResourceW(handle,name,kind);size=k.SizeofResource(handle,res)
        data=ctypes.string_at(k.LockResource(k.LoadResource(handle,res)),size)
        reserved,typ,count=struct.unpack_from('<HHH',data)
        if reserved==0 and typ==1 and len(data)>=6+14*count:
            groups.append([data[6+14*i] or 256 for i in range(count)])
        return True
    try:k.EnumResourceNamesW(module,ctypes.c_void_p(14),visit,0)
    finally:k.FreeLibrary(module)
    required={16,24,32,48,64,128,256}
    assert any(required.issubset(set(sizes)) for sizes in groups),(path,groups)
    return {'file':path.name,'iconSizes':sorted(required),'passed':True}

if __name__=='__main__':
    print(json.dumps([inspect(Path(name)) for name in sys.argv[1:]],indent=2))
